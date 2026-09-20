"""Session maintenance stays caller-scoped, quiet, durable and behind the browser gate."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from booksaver.domain.account_sync import SynchronizationFailureCode, SynchronizationTrigger
from booksaver.domain.check_result import FailureCode
from booksaver.domain.session_maintenance import (
    SessionMaintenanceCleanupError,
    SessionMaintenanceStatus,
    SessionVerificationOutcome,
    SessionVerificationResult,
)
from booksaver.domain.user import UserAccessState, UserRole
from booksaver.domain.user_session import (
    SessionStatus,
    SessionUnavailableReason,
    UserSessionMetadata,
    UserSessionSnapshot,
)
from booksaver.domain.value_objects import Platform
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore, SqliteUserRepository
from tests.unit.daemon.test_check_coordinator import (
    _build_coordinator,
    _config,
    _future_booking,
    _session_repo,
)

NOW = datetime.now(UTC).replace(microsecond=0)


def harness(tmp_path, *, outcome=SessionVerificationOutcome.AUTHENTICATED):
    clock = [NOW]
    repo = _session_repo(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        caller = users.get_or_create_by_telegram_id(200, UserRole.USER)
    for user in (owner, caller):
        repo.save(UserSessionSnapshot(
            UserSessionMetadata.imported(user.user_id, Platform.BOOKING_COM,
                                         NOW - timedelta(days=2), NOW - timedelta(hours=1)),
            f"private-cookie-{user.user_id}".encode(),
        ))
    calls, notices, uncertain = [], [], []

    def verify(cookies, deadline):
        calls.append((cookies, deadline))
        if outcome is SessionVerificationOutcome.AUTHENTICATED:
            return SessionVerificationResult(outcome, b"renewed-private", clock[0])
        return SessionVerificationResult(outcome)

    coordinator = _build_coordinator(
        _config(tmp_path), session_repository=repo, session_verifier=verify,
        auth_required_notifier=notices.append, session_uncertain_notifier=uncertain.append,
        session_clock=lambda: clock[0],
        llm_factory_builder=lambda *_: pytest.fail("Maintenance cannot use a model"),
        notifier_builder=lambda *_: pytest.fail("Maintenance cannot use savings notifiers"),
    )
    return coordinator, repo, caller.user_id, owner.user_id, clock, calls, notices, uncertain


def test_exact_invitee_without_bookings_is_verified_once_daily_and_owner_unchanged(tmp_path):
    c, repo, caller, owner, clock, calls, notices, uncertain = harness(tmp_path)
    before = repo.load_for_maintenance(owner)
    result = c.request_session_maintenance(caller)
    assert result.status is SessionMaintenanceStatus.VERIFIED
    assert result.next_attempt_at == NOW + timedelta(hours=24)
    assert calls == [(f"private-cookie-{caller}".encode(), NOW + timedelta(seconds=60))]
    assert repo.resolve(caller).snapshot.cookies == b"renewed-private"
    assert repo.load_for_maintenance(owner) == before
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.NOT_DUE
    assert len(calls) == 1
    assert notices == uncertain == []
    assert not c._execution_gate.locked()


@pytest.mark.parametrize("condition,status", [
    ("busy", SessionMaintenanceStatus.BUSY),
    ("stopping", SessionMaintenanceStatus.STOPPING),
    ("revoked", SessionMaintenanceStatus.UNAVAILABLE),
    ("missing", SessionMaintenanceStatus.UNAVAILABLE),
])
def test_unadmitted_work_never_claims_or_opens_browser(tmp_path, condition, status):
    c, repo, caller, _owner, _clock, calls, notices, uncertain = harness(tmp_path)
    if condition == "busy":
        c._execution_gate.acquire()
    elif condition == "stopping":
        c._stop_event.set()
    elif condition == "revoked":
        with SqliteStore(tmp_path / "booksaver.db") as store:
            SqliteUserRepository(store).set_access_state(caller, UserAccessState.REVOKED)
    else:
        repo.delete(caller)
    before = repo.load_for_maintenance(caller)
    assert c.request_session_maintenance(caller).status is status
    assert repo.load_for_maintenance(caller) == before
    assert calls == notices == uncertain == []
    if condition == "busy":
        c._execution_gate.release()


@pytest.mark.parametrize("race", ["new_login", "disconnect", "purge", "revoke", "stop"])
def test_late_browser_result_cannot_override_disconnect_or_revocation(tmp_path, race):
    c, repo, caller, _owner, clock, _calls, notices, uncertain = harness(tmp_path)

    def verify(cookies, deadline):
        if race == "new_login":
            repo.save(UserSessionSnapshot(
                UserSessionMetadata.imported(caller, Platform.BOOKING_COM, NOW, None),
                b"new-login",
            ))
        elif race == "disconnect":
            repo.delete(caller)
        elif race == "purge":
            repo.revoke(caller)
        elif race == "stop":
            c._stop_event.set()
        else:
            with SqliteStore(tmp_path / "booksaver.db") as store:
                SqliteUserRepository(store).set_access_state(caller, UserAccessState.REVOKED)
        return SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED,
                                         b"stale-renewal", clock[0])

    c._session_verifier = verify
    result = c.request_session_maintenance(caller)
    assert result.status in {SessionMaintenanceStatus.STALE, SessionMaintenanceStatus.STOPPING,
                             SessionMaintenanceStatus.UNAVAILABLE}
    current = repo.load_for_maintenance(caller)
    assert current is None or current.cookies != b"stale-renewal"
    assert notices == uncertain == []
    assert not c._execution_gate.locked()


def test_transient_failure_retains_session_and_only_notifies_once_after_48_hours(tmp_path):
    c, repo, caller, _owner, clock, calls, notices, uncertain = harness(
        tmp_path, outcome=SessionVerificationOutcome.RETRY_LATER,
    )
    original = repo.load_for_maintenance(caller).cookies
    for delay in (timedelta(minutes=15), timedelta(hours=1),
                  timedelta(hours=6), timedelta(hours=24)):
        result = c.request_session_maintenance(caller)
        assert result.status is SessionMaintenanceStatus.RETRY_LATER
        assert result.next_attempt_at == clock[0] + delay
        assert notices == uncertain == []
        clock[0] = result.next_attempt_at
    clock[0] = NOW + timedelta(hours=49)
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.RETRY_LATER
    assert notices == [] and uncertain == [caller]
    clock[0] += timedelta(days=1)
    c.request_session_maintenance(caller)
    assert uncertain == [caller]
    assert repo.load_for_maintenance(caller).cookies == original
    assert len(calls) == 6


def test_confirmed_signout_notifies_once_per_revision_across_restart(tmp_path):
    c, repo, caller, _owner, clock, calls, notices, uncertain = harness(
        tmp_path, outcome=SessionVerificationOutcome.SIGNED_OUT,
    )
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.REAUTH_REQUIRED
    assert repo.resolve(caller).unavailable_reason is SessionUnavailableReason.REAUTH_REQUIRED
    c._notify_auth_required(caller)
    c2 = _build_coordinator(_config(tmp_path), session_repository=_session_repo(tmp_path),
                            auth_required_notifier=notices.append, session_clock=lambda: clock[0])
    c2._notify_auth_required(caller)
    assert notices == [caller] and uncertain == []
    assert len(calls) == 1


def test_late_new_login_prevents_a_stale_notice(tmp_path, monkeypatch):
    c, repo, caller, _owner, _clock, _calls, notices, uncertain = harness(
        tmp_path, outcome=SessionVerificationOutcome.SIGNED_OUT,
    )
    claim = repo.claim_session_notice

    def replace_during_claim(*args):
        result = claim(*args)
        repo.save(UserSessionSnapshot(
            UserSessionMetadata.imported(caller, Platform.BOOKING_COM, NOW, None), b"new-login",
        ))
        return result

    monkeypatch.setattr(repo, "claim_session_notice", replace_during_claim)
    c.request_session_maintenance(caller)
    assert notices == uncertain == []


def test_scheduler_skips_corrupt_user_and_services_no_booking_invitee(tmp_path):
    c, repo, caller, owner, _clock, calls, notices, uncertain = harness(tmp_path)
    repo._path(owner).write_text("broken")
    assert c.run_session_maintenance() == NOW + timedelta(seconds=60)
    assert calls[0][0] == f"private-cookie-{caller}".encode()
    assert c.run_session_maintenance() == NOW + timedelta(hours=24)
    assert len(calls) == 1 and notices == uncertain == []


def test_late_success_is_not_accepted_past_absolute_deadline(tmp_path):
    c, repo, caller, _owner, clock, _calls, notices, uncertain = harness(tmp_path)

    def verify(*args):
        clock[0] += timedelta(seconds=61)
        return SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED,
                                         b"too-late", clock[0])

    c._session_verifier = verify
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.RETRY_LATER
    assert repo.load_for_maintenance(caller).cookies != b"too-late"
    assert notices == uncertain == []


@pytest.mark.parametrize("agentic", [False, True])
def test_legacy_local_expiry_foreground_defers_without_reconnect(tmp_path, agentic):
    c, repo, caller, _owner, _clock, calls, notices, uncertain = harness(tmp_path)
    with SqliteStore(tmp_path / "booksaver.db") as store:
        if agentic:
            report = c._synchronize_agentic_inventory(
                store, caller, SynchronizationTrigger.BOOKINGS,
            )
        else:
            report = c._synchronize_user(store, object(), caller, SynchronizationTrigger.BOOKINGS)
        assert report.failure_code is SynchronizationFailureCode.VERIFICATION_PENDING
        assert "/connect" not in report.failure_detail
        price = c._session_unavailable_result(SqliteUserRepository(store), caller,
                                              _future_booking("pending"),
                                              SessionUnavailableReason.EXPIRED)
        assert price.failure_reason.code is FailureCode.OBSERVATION_UNAVAILABLE
        assert "/connect" not in price.failure_reason.detail
    assert calls == notices == uncertain == []


def test_foreground_renewal_prevents_daily_duplicate_and_invalidates_old_claim(tmp_path):
    c, repo, caller, _owner, clock, calls, _notices, _uncertain = harness(tmp_path)
    old = repo.load_for_maintenance(caller)
    claimed = repo.claim_maintenance(caller, old.metadata.revision_id, NOW)
    fresh = old.refreshed(b"foreground", validated_at=NOW)
    assert repo.compare_and_replace(caller, old.metadata.revision_id, fresh)
    result = SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED, b"old", NOW)
    assert repo.complete_maintenance(caller, old.metadata.revision_id,
                                     claimed.metadata.maintenance.attempt_id, result, NOW) is None
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.NOT_DUE
    assert calls == []


def test_same_revision_success_keeps_notice_claim_but_clears_failure_state(tmp_path):
    c, repo, caller, _owner, _clock, _calls, _notices, _uncertain = harness(tmp_path)
    snapshot = repo.load_for_maintenance(caller)
    updated = snapshot.refreshed(b"success", validated_at=NOW)
    updated = replace(updated, metadata=replace(updated.metadata,
                      maintenance=replace(updated.metadata.maintenance, notice_sent_at=NOW)))
    repo.save(updated)
    renewed = updated.refreshed(b"again", validated_at=NOW + timedelta(days=1))
    assert renewed.metadata.maintenance.notice_sent_at == NOW
    assert renewed.metadata.maintenance.failure_started_at is None


@pytest.mark.parametrize("agentic", [False, True])
def test_explicit_expired_session_requires_reconnect_not_automatic_recovery(tmp_path, agentic):
    c, repo, caller, _owner, _clock, calls, notices, uncertain = harness(tmp_path)
    old = repo.load_for_maintenance(caller)
    repo.save(replace(old, metadata=replace(old.metadata, status=SessionStatus.EXPIRED)))
    with SqliteStore(tmp_path / "booksaver.db") as store:
        if agentic:
            report = c._synchronize_agentic_inventory(
                store, caller, SynchronizationTrigger.BOOKINGS,
            )
        else:
            report = c._synchronize_user(store, object(), caller, SynchronizationTrigger.BOOKINGS)
        assert report.failure_code is SynchronizationFailureCode.AUTH_REQUIRED
        assert "automatically" not in report.failure_detail
    c._notify_auth_required(caller)
    assert notices == [caller] and calls == uncertain == []
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.UNAVAILABLE


def test_unconfirmed_owned_browser_cleanup_stops_all_further_admission(tmp_path, caplog):
    c, repo, caller, _owner, _clock, calls, notices, uncertain = harness(tmp_path)

    def cleanup_failure(*args):
        calls.append("started")
        raise SessionMaintenanceCleanupError("private-cookie-secret")

    c._session_verifier = cleanup_failure
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.STOPPING
    assert c._stop_event.is_set()
    assert not c._execution_gate.locked()
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.STOPPING
    assert c.run_session_maintenance() is None
    assert calls == ["started"] and notices == uncertain == []
    assert "private-cookie-secret" not in caplog.text
    assert repo.load_for_maintenance(caller).metadata.maintenance.attempt_id is not None


def test_unsupported_platform_is_disabled_without_durable_failure_or_notices(tmp_path, monkeypatch):
    from booksaver.infrastructure.browser.session_maintenance import BrowserSessionMaintenance

    c, repo, caller, _owner, clock, calls, notices, uncertain = harness(tmp_path)
    c._session_verifier = None
    monkeypatch.setattr(BrowserSessionMaintenance, "is_supported", staticmethod(lambda: False))
    before = repo.load_for_maintenance(caller)
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.DISABLED
    clock[0] += timedelta(days=3)
    assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.DISABLED
    assert repo.load_for_maintenance(caller) == before
    assert calls == notices == uncertain == []


def test_thirty_daily_verifications_do_not_invent_monthly_expiry_or_cookie_lifetime(tmp_path):
    c, repo, caller, _owner, clock, calls, notices, uncertain = harness(tmp_path)
    provider_expiry = (NOW + timedelta(days=40)).timestamp()
    cookies = json.dumps([{"name": "session", "value": "private", "domain": ".booking.com",
                           "expires": provider_expiry}]).encode()
    old = repo.load_for_maintenance(caller)
    repo.save(replace(old, cookies=cookies))

    def verify(saved, deadline):
        assert saved == cookies
        assert deadline == clock[0] + timedelta(seconds=60)
        calls.append(clock[0])
        return SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED,
                                         saved, clock[0])

    c._session_verifier = verify
    for day in range(31):
        clock[0] = NOW + timedelta(days=day)
        assert c.request_session_maintenance(caller).status is SessionMaintenanceStatus.VERIFIED
        saved = repo.load_for_maintenance(caller)
        assert saved.metadata.expires_at is None
        assert saved.metadata.maintenance.next_attempt_at == clock[0] + timedelta(days=1)
        assert json.loads(saved.cookies)[0]["expires"] == provider_expiry
    assert len(calls) == 31 and notices == uncertain == []
