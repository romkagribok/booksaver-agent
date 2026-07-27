from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from booksaver.domain.account_sync import (
    AccountReservation,
    InventoryDiscoveryResult,
    SynchronizationReport,
    SynchronizationTrigger,
)


class BookingAccountInventorySource(Protocol):
    def discover(self, browser: Any) -> InventoryDiscoveryResult: ...


class AccountReservationRepository(Protocol):
    def reconcile(
        self,
        *,
        user_id: int,
        run_id: str,
        trigger: SynchronizationTrigger,
        session_revision: str,
        result: InventoryDiscoveryResult,
        observed_at: datetime,
    ) -> SynchronizationReport: ...

    def list_for_user(self, user_id: int) -> list[AccountReservation]: ...


class SynchronizeBookingAccount:
    def __init__(
        self,
        source: BookingAccountInventorySource,
        repository: AccountReservationRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        *,
        browser: Any,
        user_id: int,
        trigger: SynchronizationTrigger,
        session_revision: str,
    ) -> SynchronizationReport:
        now = self._clock()
        result = self._source.discover(browser)
        return self._repository.reconcile(
            user_id=user_id,
            run_id=str(uuid.uuid4()),
            trigger=trigger,
            session_revision=session_revision,
            result=result,
            observed_at=now,
        )
