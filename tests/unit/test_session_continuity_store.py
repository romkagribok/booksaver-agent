from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from booksaver.domain.session import SessionStatus
from booksaver.domain.session_maintenance import (
    SessionMaintenanceState,
    SessionNotice,
    SessionVerificationOutcome,
    SessionVerificationResult,
)
from booksaver.domain.user_session import (
    SessionUnavailableReason,
    UserSessionMetadata,
    UserSessionSnapshot,
)
from booksaver.domain.value_objects import DataDirectory, Platform
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)
COOKIES = b'[{"name":"session-secret","value":"private-value","expires":1790000000}]'


def _snapshot(owner: int = 7) -> UserSessionSnapshot:
    return UserSessionSnapshot(
        UserSessionMetadata.imported(
            owner,
            Platform.BOOKING_COM,
            NOW - timedelta(days=7),
            NOW - timedelta(days=1),
        ),
        COOKIES,
    )


def _repo(path: Path, key: str) -> EncryptedUserSessionRepository:
    return EncryptedUserSessionRepository(
        DataDirectory.of(str(path)),
        FernetKeyStore(secret_key=key),
    )


@pytest.fixture
def store(tmp_path):
    key = Fernet.generate_key().decode()
    return _repo(tmp_path, key), key


def _claim(repo, snapshot, now=NOW):
    claimed = repo.claim_maintenance(
        snapshot.metadata.owner_user_id,
        snapshot.metadata.revision_id,
        now,
    )
    assert claimed is not None
    assert claimed.metadata.maintenance.attempt_id is not None
    return claimed


def _finish(repo, claimed, outcome, now=NOW, cookies=COOKIES):
    result = SessionVerificationResult(
        outcome,
        cookies=cookies if outcome is SessionVerificationOutcome.AUTHENTICATED else None,
        verified_at=now if outcome is SessionVerificationOutcome.AUTHENTICATED else None,
    )
    return repo.complete_maintenance(
        claimed.metadata.owner_user_id,
        claimed.metadata.revision_id,
        claimed.metadata.maintenance.attempt_id,
        result,
        now,
    )


def _path(tmp_path):
    return tmp_path / "booking_sessions" / "user-7-booking-com.session"


def _rewrite_secret(tmp_path, key, mutate):
    path = _path(tmp_path)
    envelope = json.loads(path.read_text())
    fernet = Fernet(key.encode())
    secret = json.loads(fernet.decrypt(envelope["fernet_token"].encode()))
    mutate(secret)
    envelope["fernet_token"] = fernet.encrypt(json.dumps(secret).encode()).decode()
    path.write_text(json.dumps(envelope))


def test_legacy_expiry_is_readable_only_for_verification(store):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(snapshot)
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.EXPIRED
    assert repo.load_for_maintenance(7) == snapshot
    assert _claim(repo, snapshot).metadata.revision_id == snapshot.metadata.revision_id
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.EXPIRED


@pytest.mark.parametrize("status", [SessionStatus.EXPIRED, SessionStatus.REQUIRES_REAUTH])
def test_explicit_terminal_status_cannot_be_maintained(store, status):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(replace(snapshot, metadata=replace(snapshot.metadata, status=status)))
    assert repo.load_for_maintenance(7) is None
    assert repo.claim_maintenance(7, snapshot.metadata.revision_id, NOW) is None


@pytest.mark.parametrize("unavailable", ["missing", "corrupt", "purged"])
def test_missing_corrupt_and_purged_state_cannot_be_recovered(store, tmp_path, unavailable):
    repo, _ = store
    snapshot = _snapshot()
    if unavailable != "missing":
        repo.save(snapshot)
        if unavailable == "corrupt":
            _path(tmp_path).write_text("not a session")
        else:
            repo.revoke(7)
    assert repo.load_for_maintenance(7) is None
    assert repo.claim_maintenance(7, snapshot.metadata.revision_id, NOW) is None


def test_claim_persists_bounded_backoff_before_browser_work(store, tmp_path):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)
    at = NOW
    previous_attempt = None
    for index, delay in enumerate((15 * 60, 3600, 6 * 3600, 24 * 3600, 24 * 3600)):
        claimed = _claim(repo, snapshot, at)
        state = claimed.metadata.maintenance
        assert state.last_attempt_at == at
        assert state.next_attempt_at == at + timedelta(seconds=delay)
        assert state.failure_started_at == NOW
        assert state.consecutive_failures == min(index + 1, 4)
        assert state.attempt_id != previous_attempt
        previous_attempt = state.attempt_id
        # Simulate a crash: no completion, then reopen the durable store.
        repo = _repo(tmp_path, key)
        assert repo.load_for_maintenance(7) == claimed
        assert repo.claim_maintenance(7, snapshot.metadata.revision_id, at) is None
        at = state.next_attempt_at


def test_retry_claim_survives_a_fresh_python_process(store, tmp_path):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    script = """
import json, sys
from datetime import datetime
from booksaver.domain.value_objects import DataDirectory
from booksaver.infrastructure.crypto.fernet_key_store import FernetKeyStore
from booksaver.infrastructure.persistence.encrypted_session_store import (
    EncryptedUserSessionRepository,
)
args = json.load(sys.stdin)
repo = EncryptedUserSessionRepository(
    DataDirectory.of(args['path']), FernetKeyStore(secret_key=args['key']),
)
snapshot = repo.load_for_maintenance(7)
assert snapshot is not None
assert repo.claim_maintenance(7, args['revision'], datetime.fromisoformat(args['now'])) is None
print(json.dumps({'attempt': snapshot.metadata.maintenance.attempt_id,
                  'next': snapshot.metadata.maintenance.next_attempt_at.isoformat()}))
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    process = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(
            {
                "path": str(tmp_path),
                "key": key,
                "revision": snapshot.metadata.revision_id,
                "now": NOW.isoformat(),
            }
        ),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
        env=env,
    )
    assert json.loads(process.stdout) == {
        "attempt": claimed.metadata.maintenance.attempt_id,
        "next": (NOW + timedelta(minutes=15)).isoformat(),
    }


def test_positive_verification_migrates_legacy_expiry_without_rewriting_cookie_expiry(store):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    finished = _finish(repo, claimed, SessionVerificationOutcome.AUTHENTICATED)
    assert finished is not None
    assert finished.cookies == COOKIES
    assert json.loads(finished.cookies)[0]["expires"] == 1790000000
    assert finished.metadata.expires_at is None
    assert finished.metadata.continuity_version == 1
    assert finished.metadata.validated_at == NOW
    assert finished.metadata.revision_id == snapshot.metadata.revision_id
    state = finished.metadata.maintenance
    assert state.next_attempt_at == NOW + timedelta(hours=24)
    assert state.consecutive_failures == 0
    assert state.failure_started_at is None
    assert state.attempt_id is None
    assert repo.resolve(7, NOW).snapshot == finished
    assert repo.claim_maintenance(7, snapshot.metadata.revision_id, NOW) is None


@pytest.mark.parametrize("wrong", ["owner", "revision", "attempt"])
def test_completion_is_bound_to_owner_revision_and_attempt(store, wrong):
    repo, _ = store
    snapshot = _snapshot()
    other = _snapshot(8)
    repo.save(snapshot)
    repo.save(other)
    claimed = _claim(repo, snapshot)
    other_claimed = _claim(repo, other)
    result = SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED, COOKIES, NOW)
    assert (
        repo.complete_maintenance(
            8 if wrong == "owner" else 7,
            "wrong-revision" if wrong == "revision" else snapshot.metadata.revision_id,
            "wrong-attempt" if wrong == "attempt" else claimed.metadata.maintenance.attempt_id,
            result,
            NOW,
        )
        is None
    )
    assert repo.load_for_maintenance(7) == claimed
    assert repo.load_for_maintenance(8) == other_claimed


@pytest.mark.parametrize("race", ["new_login", "disconnect", "purge", "new_attempt"])
def test_concurrent_replacement_or_removal_defeats_old_completion(store, race):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    expected = None
    if race == "new_login":
        expected = _snapshot()
        repo.save(expected)
    elif race == "disconnect":
        repo.delete(7)
    elif race == "purge":
        repo.revoke(7)
    else:
        expected = _claim(repo, snapshot, NOW + timedelta(minutes=15))
    assert _finish(repo, claimed, SessionVerificationOutcome.AUTHENTICATED) is None
    assert repo.load_for_maintenance(7) == expected


def test_foreground_refresh_clears_old_claim_and_defeats_its_completion(store):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    fresh_cookies = COOKIES.replace(b"private-value", b"fresh-foreground-cookie")
    refreshed = claimed.refreshed(fresh_cookies, validated_at=NOW + timedelta(seconds=1))
    assert repo.compare_and_replace(7, snapshot.metadata.revision_id, refreshed)
    assert refreshed.metadata.maintenance.attempt_id is None
    assert refreshed.metadata.maintenance.consecutive_failures == 0
    assert (
        _finish(repo, claimed, SessionVerificationOutcome.SIGNED_OUT, NOW + timedelta(seconds=2))
        is None
    )
    assert repo.resolve(7, NOW).snapshot == refreshed


@pytest.mark.parametrize("offset", [-1, 2])
def test_positive_proof_time_must_fall_within_claim_and_completion(store, offset):
    repo, _ = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    result = SessionVerificationResult(
        SessionVerificationOutcome.AUTHENTICATED,
        COOKIES,
        NOW + timedelta(seconds=offset),
    )
    assert (
        repo.complete_maintenance(
            7,
            snapshot.metadata.revision_id,
            claimed.metadata.maintenance.attempt_id,
            result,
            NOW + timedelta(seconds=1),
        )
        is None
    )
    assert repo.load_for_maintenance(7) == claimed


@pytest.mark.parametrize(
    "outcome",
    [SessionVerificationOutcome.SIGNED_OUT, SessionVerificationOutcome.INTERACTION_REQUIRED],
)
def test_confirmed_signout_requests_reauth_and_only_one_notice_per_revision(
    store, tmp_path, outcome
):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)
    finished = _finish(repo, _claim(repo, snapshot), outcome)
    assert finished is not None
    assert finished.metadata.status is SessionStatus.REQUIRES_REAUTH
    assert repo.load_for_maintenance(7) is None
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.REAUTH_REQUIRED
    assert repo.claim_session_notice(7, "stale-revision", NOW) is None
    assert (
        repo.claim_session_notice(7, snapshot.metadata.revision_id, NOW) is SessionNotice.SIGNED_OUT
    )
    assert (
        _repo(tmp_path, key).claim_session_notice(
            7,
            snapshot.metadata.revision_id,
            NOW + timedelta(days=1),
        )
        is None
    )
    replacement = _snapshot()
    repo.save(replacement)
    _finish(repo, _claim(repo, replacement), outcome)
    assert (
        repo.claim_session_notice(
            7,
            replacement.metadata.revision_id,
            NOW,
        )
        is SessionNotice.SIGNED_OUT
    )


def test_two_day_uncertainty_notice_is_distinct_durable_and_deduplicated(store, tmp_path):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)
    _finish(repo, _claim(repo, snapshot), SessionVerificationOutcome.RETRY_LATER)
    assert (
        repo.claim_session_notice(
            7,
            snapshot.metadata.revision_id,
            NOW + timedelta(hours=48) - timedelta(microseconds=1),
        )
        is None
    )
    assert (
        repo.claim_session_notice(
            7,
            snapshot.metadata.revision_id,
            NOW + timedelta(hours=48),
        )
        is SessionNotice.UNVERIFIED
    )
    assert (
        _repo(tmp_path, key).claim_session_notice(
            7,
            snapshot.metadata.revision_id,
            NOW + timedelta(hours=49),
        )
        is None
    )
    retained = repo.load_for_maintenance(7)
    assert retained is not None
    assert retained.cookies == COOKIES
    assert retained.metadata.status is SessionStatus.ACTIVE


def test_maintenance_metadata_and_cookie_material_are_encrypted(store, tmp_path):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)
    claimed = _claim(repo, snapshot)
    envelope_text = _path(tmp_path).read_text()
    for secret in (
        "session-secret",
        "private-value",
        "maintenance",
        "attempt_id",
        "consecutive_failures",
        claimed.metadata.maintenance.attempt_id,
        (NOW + timedelta(minutes=15)).isoformat(),
    ):
        assert secret not in envelope_text
    envelope = json.loads(envelope_text)
    payload = json.loads(Fernet(key.encode()).decrypt(envelope["fernet_token"].encode()))
    assert payload["maintenance"]["attempt_id"] == claimed.metadata.maintenance.attempt_id
    assert base64.b64decode(payload["cookies_b64"]) == COOKIES


@pytest.mark.parametrize(
    "field,value",
    [
        ("next_attempt_at", "2026-09-20T12:00:00"),
        ("last_attempt_at", "not-a-date"),
        ("failure_started_at", 42),
        ("notice_sent_at", "2026-09-20T13:00:00+01:00"),
        ("consecutive_failures", True),
        ("consecutive_failures", -1),
        ("consecutive_failures", 5),
        ("consecutive_failures", 1),  # Missing required failure timestamps.
        ("attempt_id", "claim-without-retry"),
        ("unknown_field", "not accepted"),
    ],
)
def test_malformed_encrypted_maintenance_state_fails_closed(store, tmp_path, field, value):
    repo, key = store
    repo.save(_snapshot())
    _rewrite_secret(tmp_path, key, lambda secret: secret.update(maintenance={field: value}))
    assert repo.load_for_maintenance(7) is None
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.INVALID


@pytest.mark.parametrize("version", [True, -1, 2, "1"])
def test_unknown_continuity_policy_fails_closed(store, tmp_path, version):
    repo, key = store
    repo.save(_snapshot())
    _rewrite_secret(tmp_path, key, lambda secret: secret.update(continuity_version=version))
    assert repo.load_for_maintenance(7) is None
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.INVALID


@pytest.mark.parametrize("field", ["imported_at", "expires_at", "validated_at"])
def test_naive_envelope_timestamps_fail_closed(store, tmp_path, field):
    repo, _ = store
    repo.save(_snapshot())
    raw = json.loads(_path(tmp_path).read_text())
    raw[field] = "2026-09-20T12:00:00"
    _path(tmp_path).write_text(json.dumps(raw))
    assert repo.load_for_maintenance(7) is None
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.INVALID


def test_legacy_payload_without_maintenance_fields_remains_eligible_for_verification(
    store, tmp_path
):
    repo, key = store
    snapshot = _snapshot()
    repo.save(snapshot)

    def remove_new_fields(secret):
        secret.pop("maintenance")
        secret.pop("continuity_version")

    _rewrite_secret(tmp_path, key, remove_new_fields)
    assert repo.load_for_maintenance(7) == snapshot
    assert repo.resolve(7, NOW).unavailable_reason is SessionUnavailableReason.EXPIRED


@pytest.mark.parametrize("outcome", list(SessionVerificationOutcome))
def test_verification_result_enforces_exact_cookie_authority(outcome):
    if outcome is SessionVerificationOutcome.AUTHENTICATED:
        for cookies, verified_at in ((None, NOW), (b"", NOW), ("cookie", NOW), (COOKIES, None)):
            with pytest.raises(ValueError):
                SessionVerificationResult(outcome, cookies, verified_at)
    else:
        with pytest.raises(ValueError):
            SessionVerificationResult(outcome, COOKIES)
        with pytest.raises(ValueError):
            SessionVerificationResult(outcome, verified_at=NOW)
        assert SessionVerificationResult(outcome).cookies is None


def test_verification_result_rejects_untyped_outcome_and_non_utc_proof_time():
    with pytest.raises(ValueError):
        SessionVerificationResult("authenticated", COOKIES, NOW)
    for timestamp in (NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))):
        with pytest.raises(ValueError):
            SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED, COOKIES, timestamp)


def test_new_domain_result_reprs_do_not_reveal_session_or_attempt_secrets():
    result = SessionVerificationResult(SessionVerificationOutcome.AUTHENTICATED, COOKIES, NOW)
    assert "session-secret" not in repr(result)
    assert "private-value" not in repr(result)
    state = SessionMaintenanceState(
        next_attempt_at=NOW + timedelta(minutes=15),
        last_attempt_at=NOW,
        failure_started_at=NOW,
        consecutive_failures=1,
        attempt_id="private-attempt-id",
    )
    assert "private-attempt-id" not in repr(state)
