from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from booksaver.domain.agentic_qualification import (
    AgenticCanaryCheck,
    CriticalAgenticViolation,
    evaluate_agentic_canary,
)
from booksaver.domain.browser_executor import QualificationStatus
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.user import UserRole
from booksaver.infrastructure.persistence.sqlite_store import (
    SCHEMA_VERSION,
    SqliteAgenticDisclosureConsentRepository,
    SqliteAgenticQualificationRepository,
    SqliteStore,
    SqliteUserRepository,
)

START = datetime(2026, 8, 1, tzinfo=UTC)


def _check(index: int, owner_user_id: int) -> AgenticCanaryCheck:
    return AgenticCanaryCheck(
        check_id=f"canary-{index:02d}",
        owner_user_id=owner_user_id,
        observed_at=START + timedelta(days=14 * index / 29),
        eligible_unblocked=True,
        valid_observation=True,
        manual_price_correct=True if index < 10 else None,
        model_cost=UsdAmount(40_000),
        duration_ms=40_000,
        fallback_used=index < 6,
        violations=(
            frozenset({CriticalAgenticViolation.SESSION_LEAK}) if index == 29 else frozenset()
        ),
    )


def test_redacted_canary_consent_promotion_and_regression_round_trip(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        users = SqliteUserRepository(store)
        owner = users.get_owner()
        invitee = users.get_or_create_by_telegram_id(222, UserRole.USER)
        qualifications = SqliteAgenticQualificationRepository(store)
        consents = SqliteAgenticDisclosureConsentRepository(store)

        for index in range(30):
            qualifications.record_check(_check(index, owner.user_id))
        evidence = qualifications.list_checks(owner.user_id)
        assert len(evidence) == 30
        assert evidence[-1].violations == frozenset({CriticalAgenticViolation.SESSION_LEAK})
        assert qualifications.qualification_state().status is QualificationStatus.UNQUALIFIED

        blocked = evaluate_agentic_canary(
            evidence,
            deployment_owner_user_id=owner.user_id,
            owner_approved=True,
            now=START + timedelta(days=15),
        )
        assert not blocked.promotable
        with pytest.raises(ValueError, match="gates"):
            qualifications.promote(
                owner_user_id=owner.user_id,
                approved_at=START + timedelta(days=15),
            )

        clean_last = _check(29, owner.user_id)
        store.conn.execute(
            "DELETE FROM agentic_canary_checks WHERE check_id = ?",
            (clean_last.check_id,),
        )
        store.conn.commit()
        qualifications.record_check(replace(clean_last, violations=frozenset()))
        evidence = qualifications.list_checks(owner.user_id)
        verdict = evaluate_agentic_canary(
            evidence,
            deployment_owner_user_id=owner.user_id,
            owner_approved=True,
            now=START + timedelta(days=15),
        )
        assert verdict.promotable
        state = qualifications.promote(
            owner_user_id=owner.user_id,
            approved_at=START + timedelta(days=15),
        )
        assert state.status is QualificationStatus.QUALIFIED
        assert qualifications.qualification_state() == state

        consent = consents.acknowledge(
            user_id=invitee.user_id,
            disclosure_version="anthropic-visible-booking-page-v1",
            acknowledged_at=START,
        )
        assert consents.get(invitee.user_id) == consent

        regressed = qualifications.regress(
            owner_user_id=owner.user_id,
            regression_code="price_correctness",
            observed_at=START + timedelta(days=16),
        )
        assert regressed.status is QualificationStatus.REGRESSED
        assert qualifications.qualification_state().status is QualificationStatus.REGRESSED

        columns = {row[1] for row in store.conn.execute("PRAGMA table_info(agentic_canary_checks)")}
        assert (
            not {
                "screenshot",
                "page_text",
                "cookies",
                "prompt",
                "reasoning",
                "selector",
            }
            & columns
        )
        version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()[0]
        assert version == SCHEMA_VERSION == 18


def test_invitee_cannot_record_owner_canary_or_promote(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        user = SqliteUserRepository(store).get_or_create_by_telegram_id(222, UserRole.USER)
        qualifications = SqliteAgenticQualificationRepository(store)
        with pytest.raises(PermissionError, match="owner"):
            qualifications.record_check(_check(0, user.user_id))
        with pytest.raises(PermissionError, match="owner"):
            qualifications.promote(
                owner_user_id=user.user_id,
                approved_at=START,
            )
        with pytest.raises(ValueError, match="gates"):
            qualifications.promote(
                owner_user_id=owner.user_id,
                approved_at=START,
            )


def test_v18_migration_tags_existing_canary_evidence_as_stagehand(tmp_path: Path) -> None:
    db_path = tmp_path / "v17.db"
    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        SqliteAgenticQualificationRepository(store).record_check(
            _check(0, owner.user_id)
        )

    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE agentic_canary_checks DROP COLUMN policy_version")
    conn.execute("DELETE FROM schema_meta WHERE version > 17")
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta (version, applied_at) VALUES (17, ?)",
        (START.isoformat(),),
    )
    conn.commit()
    conn.close()

    with SqliteStore(db_path) as store:
        owner = SqliteUserRepository(store).get_owner()
        check = SqliteAgenticQualificationRepository(store).list_checks(owner.user_id)[0]
        version = store.conn.execute("SELECT MAX(version) FROM schema_meta").fetchone()[0]

    assert check.policy_version == "agentic-price-v1"
    assert version == SCHEMA_VERSION == 18


def _promote_clean_canary(
    qualifications: SqliteAgenticQualificationRepository,
    owner_user_id: int,
) -> None:
    for index in range(30):
        qualifications.record_check(
            replace(_check(index, owner_user_id), violations=frozenset())
        )
    qualifications.promote(
        owner_user_id=owner_user_id,
        approved_at=START + timedelta(days=15),
    )


def test_three_consecutive_eligible_failures_auto_regress_during_rollback(
    tmp_path: Path,
) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        qualifications = SqliteAgenticQualificationRepository(store)
        _promote_clean_canary(qualifications, owner.user_id)

        for index in range(3):
            qualifications.record_check(
                AgenticCanaryCheck(
                    check_id=f"post-promotion-failure-{index}",
                    owner_user_id=owner.user_id,
                    observed_at=START + timedelta(days=16, hours=index),
                    eligible_unblocked=True,
                    valid_observation=False,
                    manual_price_correct=None,
                    model_cost=UsdAmount(60_000),
                    duration_ms=30_000,
                    fallback_used=False,
                )
            )

        assert qualifications.qualification_state().status is QualificationStatus.REGRESSED


def test_false_manual_comparison_is_critical_and_auto_regresses(tmp_path: Path) -> None:
    with SqliteStore(tmp_path / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        qualifications = SqliteAgenticQualificationRepository(store)
        _promote_clean_canary(qualifications, owner.user_id)

        qualifications.record_manual_comparison(
            owner_user_id=owner.user_id,
            check_id="canary-10",
            correct=False,
        )

        check = qualifications.list_checks(owner.user_id)[10]
        assert CriticalAgenticViolation.FALSE_ACCEPTED_OFFER in check.violations
        assert qualifications.qualification_state().status is QualificationStatus.REGRESSED
