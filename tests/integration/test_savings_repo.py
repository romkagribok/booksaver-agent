from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from booksaver.domain.check_result import (
    CheckResult,
    ExtractionMethod,
    FailureCode,
    FailureReason,
)
from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteCheckHistoryRepository,
    SqliteSavingsRepository,
    SqliteStore,
)

from .test_check_history import _register_booking


def _opportunity(booking_id: str = "b-1") -> SavingsOpportunity:
    return SavingsOpportunity(
        opportunity_id=str(uuid.uuid4()),
        booking_id=booking_id,
        check_id=str(uuid.uuid4()),
        baseline_price=Money(amount=Decimal("400.00"), currency="EUR"),
        live_price=Money(amount=Decimal("350.00"), currency="EUR"),
        amount_saved=Money(amount=Decimal("50.00"), currency="EUR"),
        percent_saved=Decimal("12.50"),
        validated_at=datetime.now(UTC),
    )


def _record_success(
    store: SqliteStore,
    *,
    booking_id: str,
    check_id: str,
    checked_at: datetime,
    amount: str = "350.00",
) -> None:
    result = replace(
        CheckResult.success(
            booking_id=booking_id,
            checked_at=checked_at,
            live_price=Money(amount=Decimal(amount), currency="EUR"),
            extraction_method=ExtractionMethod.DOM,
        ),
        check_id=check_id,
    )
    SqliteCheckHistoryRepository(store).add(result)


def _record_failure(
    store: SqliteStore,
    *,
    booking_id: str,
    check_id: str,
    checked_at: datetime,
    code: FailureCode,
) -> None:
    result = replace(
        CheckResult.failure(
            booking_id=booking_id,
            checked_at=checked_at,
            reason=FailureReason(code=code, detail=f"{code.value} test"),
        ),
        check_id=check_id,
    )
    SqliteCheckHistoryRepository(store).add(result)


def _add_checked_opportunity(
    store: SqliteStore,
    repo: SqliteSavingsRepository,
    opportunity: SavingsOpportunity,
) -> None:
    _record_success(
        store,
        booking_id=opportunity.booking_id,
        check_id=opportunity.check_id,
        checked_at=opportunity.validated_at,
        amount=str(opportunity.live_price.amount),
    )
    repo.add(opportunity)


class TestSqliteSavingsRepository:
    def test_round_trip(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            original = _opportunity()
            repo.add(original)

            loaded = repo.get(original.opportunity_id)

        assert loaded is not None
        assert loaded.baseline_price == original.baseline_price
        assert loaded.live_price == original.live_price
        assert loaded.amount_saved == original.amount_saved
        assert loaded.percent_saved == original.percent_saved
        assert loaded.notified_at is None

    def test_mark_notified(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            opportunity = _opportunity()
            repo.add(opportunity)

            at = datetime.now(UTC)
            repo.mark_notified(opportunity.opportunity_id, at)
            loaded = repo.get(opportunity.opportunity_id)

        assert loaded is not None
        assert loaded.notified_at == at

    def test_list_for_booking_and_all(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store, "b-1")
            _register_booking(store, "b-2")
            repo = SqliteSavingsRepository(store)
            repo.add(_opportunity("b-1"))
            repo.add(_opportunity("b-1"))
            repo.add(_opportunity("b-2"))

            assert len(repo.list_for_booking("b-1")) == 2
            assert len(repo.list_for_booking("b-2")) == 1
            assert len(repo.list_all()) == 3

    def test_current_opportunities_are_one_per_active_booking_and_keep_history(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store, "b-1")
            _register_booking(store, "b-2")
            repo = SqliteSavingsRepository(store)
            old_b1 = replace(
                _opportunity("b-1"),
                opportunity_id="old-b1",
                validated_at=now - timedelta(minutes=3),
            )
            new_b1 = replace(
                _opportunity("b-1"),
                opportunity_id="new-b1",
                validated_at=now - timedelta(minutes=1),
            )
            new_b2 = replace(
                _opportunity("b-2"),
                opportunity_id="new-b2",
                validated_at=now,
            )
            _add_checked_opportunity(store, repo, old_b1)
            _add_checked_opportunity(store, repo, new_b1)
            _add_checked_opportunity(store, repo, new_b2)

            current = repo.list_current_for_user(1)

            assert [o.opportunity_id for o in current] == ["new-b2", "new-b1"]
            assert repo.get_current_for_booking("b-1") == new_b1
            assert [o.opportunity_id for o in repo.list_for_booking("b-1")] == [
                "new-b1",
                "old-b1",
            ]
            assert len(repo.list_all_for_user(1)) == 3

            store.conn.execute(
                "UPDATE bookings SET status = 'archived' WHERE booking_id = 'b-2'"
            )
            store.conn.commit()

            assert [o.opportunity_id for o in repo.list_current_for_user(1)] == [
                "new-b1"
            ]
            assert len(repo.list_all_for_user(1)) == 3

    def test_current_opportunity_uses_insertion_order_for_equal_timestamp(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            first = replace(
                _opportunity(),
                opportunity_id="first",
                validated_at=now,
            )
            second = replace(
                _opportunity(),
                opportunity_id="second",
                validated_at=now,
            )
            _add_checked_opportunity(store, repo, first)
            _add_checked_opportunity(store, repo, second)

            assert repo.get_current_for_booking("b-1") == second
            assert [o.opportunity_id for o in repo.list_current_for_user(1)] == [
                "second"
            ]

    @pytest.mark.parametrize(
        "failure_code",
        [code for code in FailureCode if code is not FailureCode.NO_EQUIVALENT_OFFER],
    )
    def test_technical_failure_preserves_last_conclusive_opportunity(
        self, tmp_path: Path, failure_code: FailureCode
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            opportunity = replace(
                _opportunity(),
                opportunity_id="last-verified",
                check_id="positive",
                validated_at=now,
            )
            _add_checked_opportunity(store, repo, opportunity)
            _record_failure(
                store,
                booking_id="b-1",
                check_id="technical-failure",
                checked_at=now + timedelta(minutes=1),
                code=failure_code,
            )

            assert repo.get_current_for_booking("b-1") == opportunity
            assert repo.list_current_for_user(1) == [opportunity]
            assert len(repo.list_for_booking("b-1")) == 1

    def test_newer_successful_smaller_saving_replaces_larger_saving(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            larger = replace(
                _opportunity(),
                opportunity_id="larger-saving",
                check_id="check-larger",
                validated_at=now,
            )
            smaller = replace(
                _opportunity(),
                opportunity_id="smaller-saving",
                check_id="check-smaller",
                live_price=Money(Decimal("380.00"), "EUR"),
                amount_saved=Money(Decimal("20.00"), "EUR"),
                percent_saved=Decimal("5.00"),
                validated_at=now + timedelta(minutes=1),
            )
            _add_checked_opportunity(store, repo, larger)
            _add_checked_opportunity(store, repo, smaller)

            assert repo.get_current_for_booking("b-1") == smaller
            assert repo.list_current_for_user(1) == [smaller]
            assert [o.opportunity_id for o in repo.list_for_booking("b-1")] == [
                "smaller-saving",
                "larger-saving",
            ]

    def test_successful_non_saving_check_invalidates_prior_opportunity(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            opportunity = replace(
                _opportunity(),
                opportunity_id="old-saving",
                check_id="old-positive",
                validated_at=now,
            )
            _add_checked_opportunity(store, repo, opportunity)
            _record_success(
                store,
                booking_id="b-1",
                check_id="at-baseline",
                checked_at=now + timedelta(minutes=1),
                amount="400.00",
            )

            assert repo.get_current_for_booking("b-1") is None
            assert repo.list_current_for_user(1) == []
            assert repo.get(opportunity.opportunity_id) == opportunity

    def test_no_equivalent_then_technical_failure_does_not_revive_prior_opportunity(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            opportunity = replace(
                _opportunity(),
                opportunity_id="old-saving",
                check_id="old-positive",
                validated_at=now,
            )
            _add_checked_opportunity(store, repo, opportunity)
            _record_failure(
                store,
                booking_id="b-1",
                check_id="no-equivalent",
                checked_at=now + timedelta(minutes=1),
                code=FailureCode.NO_EQUIVALENT_OFFER,
            )
            _record_failure(
                store,
                booking_id="b-1",
                check_id="later-timeout",
                checked_at=now + timedelta(minutes=2),
                code=FailureCode.TIMEOUT,
            )

            assert repo.get_current_for_booking("b-1") is None
            assert repo.list_current_for_user(1) == []
            assert repo.get(opportunity.opportunity_id) == opportunity

    def test_later_positive_restores_actionability_after_conclusive_invalidation(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            old = replace(
                _opportunity(),
                opportunity_id="old",
                check_id="old-positive",
                validated_at=now,
            )
            restored = replace(
                _opportunity(),
                opportunity_id="restored",
                check_id="restored-positive",
                validated_at=now + timedelta(minutes=2),
            )
            _add_checked_opportunity(store, repo, old)
            _record_failure(
                store,
                booking_id="b-1",
                check_id="no-equivalent",
                checked_at=now + timedelta(minutes=1),
                code=FailureCode.NO_EQUIVALENT_OFFER,
            )
            _add_checked_opportunity(store, repo, restored)

            assert repo.get_current_for_booking("b-1") == restored
            assert repo.list_current_for_user(1) == [restored]

    def test_conclusive_invalidation_is_scoped_to_its_booking(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store, "b-1")
            _register_booking(store, "b-2")
            repo = SqliteSavingsRepository(store)
            first = replace(
                _opportunity("b-1"),
                opportunity_id="first",
                check_id="first-positive",
                validated_at=now,
            )
            second = replace(
                _opportunity("b-2"),
                opportunity_id="second",
                check_id="second-positive",
                validated_at=now + timedelta(seconds=1),
            )
            _add_checked_opportunity(store, repo, first)
            _add_checked_opportunity(store, repo, second)
            _record_failure(
                store,
                booking_id="b-1",
                check_id="first-no-equivalent",
                checked_at=now + timedelta(minutes=1),
                code=FailureCode.NO_EQUIVALENT_OFFER,
            )

            assert repo.get_current_for_booking("b-1") is None
            assert repo.get_current_for_booking("b-2") == second
            assert repo.list_current_for_user(1) == [second]

    def test_source_check_without_savings_row_temporarily_hides_old_opportunity(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            old = replace(
                _opportunity(),
                opportunity_id="old",
                check_id="old-positive",
                validated_at=now,
            )
            new = replace(
                _opportunity(),
                opportunity_id="new",
                check_id="new-positive",
                validated_at=now + timedelta(minutes=1),
            )
            _add_checked_opportunity(store, repo, old)
            _record_success(
                store,
                booking_id="b-1",
                check_id=new.check_id,
                checked_at=new.validated_at,
            )

            assert repo.get_current_for_booking("b-1") is None

            repo.add(new)

            assert repo.get_current_for_booking("b-1") == new

    def test_orphan_opportunity_is_historical_but_not_actionable(
        self, tmp_path: Path
    ) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            _register_booking(store)
            repo = SqliteSavingsRepository(store)
            orphan = replace(_opportunity(), opportunity_id="orphan")
            repo.add(orphan)

            assert repo.get(orphan.opportunity_id) == orphan
            assert repo.list_for_booking("b-1") == [orphan]
            assert repo.get_current_for_booking("b-1") is None
            assert repo.list_current_for_user(1) == []

    def test_get_unknown_returns_none(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteSavingsRepository(store)
            assert repo.get("nope") is None
