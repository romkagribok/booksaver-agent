"""Application services for the replaceable price-browser executor boundary."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from booksaver.application.ports import (
    PriceBrowserExecutor,
    SessionRestoreTarget,
    VerifiedSessionRefreshSource,
)
from booksaver.domain.agent import LLMUsage
from booksaver.domain.browser_executor import (
    ExecutionLimits,
    ExecutionUsage,
    PriceExecutionRequest,
    PriceExecutionResult,
    PriceObservationValidation,
    SessionLeaseReference,
    TrustedPriceQuery,
    validate_price_observation,
)
from booksaver.domain.model_policy import UsdAmount
from booksaver.domain.models import Booking


@dataclass(slots=True)
class _LeaseRecord:
    reference: SessionLeaseReference
    session_material: bytes | None = field(repr=False)
    consumed: bool = False
    closed: bool = False
    verified_refresh: bytes | None = field(default=None, repr=False)


class InMemorySessionLeaseBroker:
    """Single-process, single-use session lease registry.

    Session bytes are pushed directly into a code-owned browser bootstrap.  They are never returned
    by ``restore_into`` and never become part of the executor request or result.
    """

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[str, _LeaseRecord] = {}
        self._lock = threading.Lock()

    def issue(
        self,
        *,
        owner_user_id: int,
        booking_id: str,
        execution_id: str,
        session_material: bytes,
        ttl: timedelta = timedelta(minutes=4),
    ) -> SessionLeaseReference:
        if not session_material:
            raise ValueError("session material cannot be empty")
        if ttl <= timedelta(0) or ttl > timedelta(minutes=5):
            raise ValueError("session lease ttl must be positive and no greater than five minutes")
        reference = SessionLeaseReference(
            lease_id=str(uuid.uuid4()),
            owner_user_id=owner_user_id,
            booking_id=booking_id,
            execution_id=execution_id,
            expires_at=self._clock() + ttl,
        )
        with self._lock:
            self._records[reference.lease_id] = _LeaseRecord(
                reference=reference,
                session_material=bytes(session_material),
            )
        return reference

    def _record(self, reference: SessionLeaseReference) -> _LeaseRecord:
        record = self._records.get(reference.lease_id)
        if record is None or record.reference != reference:
            raise ValueError("unknown or mismatched session lease")
        if reference.is_expired(self._clock()):
            record.session_material = None
            record.closed = True
            raise ValueError("session lease expired")
        return record

    def restore_into(self, reference: SessionLeaseReference, target: SessionRestoreTarget) -> None:
        with self._lock:
            record = self._record(reference)
            if record.closed or record.consumed or record.session_material is None:
                raise ValueError("session lease is no longer consumable")
            record.consumed = True
            material = record.session_material
        target.restore_session(material)

    def capture_verified_refresh(
        self,
        reference: SessionLeaseReference,
        source: VerifiedSessionRefreshSource,
    ) -> bool:
        with self._lock:
            record = self._record(reference)
            if record.closed or not record.consumed:
                raise ValueError("session lease is not active")
        if not source.verify_authenticated_account():
            return False
        refreshed = source.capture_session()
        if not refreshed:
            return False
        with self._lock:
            record = self._record(reference)
            if record.closed:
                raise ValueError("session lease closed during refresh capture")
            record.verified_refresh = bytes(refreshed)
        return True

    def store_verified_refresh(
        self,
        reference: SessionLeaseReference,
        refreshed_session: bytes,
    ) -> None:
        """Store bytes produced only by a code-owned verified local browser probe."""
        if not refreshed_session:
            raise ValueError("verified refreshed session cannot be empty")
        with self._lock:
            record = self._record(reference)
            if record.closed or not record.consumed:
                raise ValueError("session lease is not active")
            record.verified_refresh = bytes(refreshed_session)

    def take_verified_refresh(self, reference: SessionLeaseReference) -> bytes | None:
        with self._lock:
            record = self._records.get(reference.lease_id)
            if record is None or record.reference != reference:
                return None
            refreshed = record.verified_refresh
            record.verified_refresh = None
            if record.closed:
                self._records.pop(reference.lease_id, None)
            return refreshed

    def close(self, reference: SessionLeaseReference) -> None:
        with self._lock:
            record = self._records.get(reference.lease_id)
            if record is None or record.reference != reference:
                return
            record.session_material = None
            record.closed = True
            if record.verified_refresh is None:
                self._records.pop(reference.lease_id, None)

    def active_count(self) -> int:
        with self._lock:
            return sum(not record.closed for record in self._records.values())


class ExecutionMeter:
    """Shared exact meter for semantic and computer-use work inside one execution."""

    def __init__(self, limits: ExecutionLimits) -> None:
        self._limits = limits
        self._model_calls = 0
        self._total_actions = 0
        self._computer_actions = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost = UsdAmount()
        self._lock = threading.Lock()

    def record_action(self, *, computer_use: bool = False) -> None:
        with self._lock:
            total = self._total_actions + 1
            computer = self._computer_actions + int(computer_use)
            if total > self._limits.max_actions:
                raise RuntimeError("executor action limit exhausted")
            if computer > self._limits.max_computer_use_actions:
                raise RuntimeError("computer-use action limit exhausted")
            self._total_actions = total
            self._computer_actions = computer

    def record_model_call(self, usage: LLMUsage, cost: UsdAmount) -> None:
        with self._lock:
            next_cost = self._cost + cost
            self._model_calls += 1
            self._input_tokens += usage.input_tokens
            self._output_tokens += usage.output_tokens
            self._cost = next_cost
            if next_cost > self._limits.max_job_cost:
                # The provider response is already billable. Preserve its exact cost so validation
                # and qualification can record the breach before the execution fails closed.
                raise RuntimeError("executor job cost limit exhausted")

    def snapshot(self) -> ExecutionUsage:
        with self._lock:
            return ExecutionUsage(
                model_calls=self._model_calls,
                total_actions=self._total_actions,
                computer_use_actions=self._computer_actions,
                tokens=LLMUsage(self._input_tokens, self._output_tokens),
                cost=self._cost,
            )


class FakePriceBrowserExecutor:
    """Deterministic contract fake shared by monitor and qualification tests."""

    def __init__(self, results: Iterable[PriceExecutionResult]) -> None:
        self._results = list(results)
        self.requests: list[PriceExecutionRequest] = []

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionResult:
        self.requests.append(request)
        if not self._results:
            raise RuntimeError("fake executor has no queued result")
        return self._results.pop(0)


@dataclass(frozen=True, slots=True)
class PriceExecutionOutcome:
    result: PriceExecutionResult
    validation: PriceObservationValidation
    refreshed_session: bytes | None = field(default=None, repr=False)


class AgenticPriceExecutionService:
    """Invoke, validate, and close one executor lease without domain side effects."""

    def __init__(
        self,
        executor: PriceBrowserExecutor,
        lease_broker: InMemorySessionLeaseBroker,
    ) -> None:
        self._executor = executor
        self._lease_broker = lease_broker

    def execute(self, request: PriceExecutionRequest) -> PriceExecutionOutcome:
        result: PriceExecutionResult | None = None
        refreshed: bytes | None = None
        try:
            result = self._executor.execute(request)
            validation = validate_price_observation(request, result)
        finally:
            self._lease_broker.close(request.session_lease)
            refreshed = self._lease_broker.take_verified_refresh(request.session_lease)
        if result is None or not result.refreshed_session_eligible:
            refreshed = None
        return PriceExecutionOutcome(
            result=result,
            validation=validation,
            refreshed_session=refreshed,
        )


class OwnerBoundAgenticPriceCheck:
    """Build one owner/session-bound executor request from trusted booking state."""

    def __init__(
        self,
        service: AgenticPriceExecutionService,
        lease_broker: InMemorySessionLeaseBroker,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._leases = lease_broker
        self._clock = clock or (lambda: datetime.now(UTC))

    def execute(
        self,
        *,
        owner_user_id: int,
        booking: Booking,
        session_material: bytes,
    ) -> PriceExecutionOutcome:
        if booking.occupancy is None:
            raise ValueError("agentic price checks require registered occupancy")
        execution_id = f"agentic-{uuid.uuid4().hex}"
        lease = self._leases.issue(
            owner_user_id=owner_user_id,
            booking_id=booking.booking_id,
            execution_id=execution_id,
            session_material=session_material,
        )
        now = self._clock()
        request = PriceExecutionRequest(
            execution_id=execution_id,
            owner_user_id=owner_user_id,
            booking_id=booking.booking_id,
            query=TrustedPriceQuery(
                property_name=booking.property.name,
                property_reference=booking.property.booking_com_ref,
                stay_dates=booking.stay_dates,
                occupancy=booking.occupancy,
                currency=booking.baseline_price.currency,
            ),
            session_lease=lease,
            limits=ExecutionLimits(
                deadline=now + timedelta(seconds=180),
            ),
        )
        return self._service.execute(request)
