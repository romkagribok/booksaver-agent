from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from booksaver.domain.savings import SavingsOpportunity
from booksaver.domain.value_objects import Money
from booksaver.infrastructure.persistence.sqlite_store import (
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

    def test_get_unknown_returns_none(self, tmp_path: Path) -> None:
        with SqliteStore(tmp_path / "t.db") as store:
            repo = SqliteSavingsRepository(store)
            assert repo.get("nope") is None
