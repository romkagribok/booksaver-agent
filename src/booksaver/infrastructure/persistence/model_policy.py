"""SQLite adapters for adaptive-model spend admission and qualification."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from booksaver.domain.agent import LLMUsage
from booksaver.domain.model_policy import (
    AdmissionDecision,
    CostReconciliation,
    CostReservation,
    ModelAttemptAudit,
    ModelProfile,
    ModelProvider,
    ModelRole,
    ModelStopReason,
    ModelTier,
    QualificationGate,
    QualificationMetrics,
    QualificationResult,
    ReconciliationRequest,
    ReservationRequest,
    ReservationStatus,
    UsdAmount,
)

from .sqlite_store import SqliteStore


def _remaining(limit: int, exposure: int) -> UsdAmount:
    return UsdAmount(max(0, limit - exposure))


class SqliteSpendLedger:
    """Transactionally reserve both job and deployment UTC-day exposure."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def reserve_call(self, request: ReservationRequest) -> AdmissionDecision:
        conn = self._store.conn
        if conn.in_transaction:
            raise RuntimeError("spend admission requires a clean SQLite transaction")
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT * FROM llm_cost_reservations WHERE reservation_id = ?",
                (request.reservation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["job_id"] != request.job_id
                    or existing["attempt_ordinal"] != request.attempt_ordinal
                    or existing["model"] != request.profile.model_id
                    or existing["reserved_micro_usd"] != request.reserved_cost.micro_usd
                ):
                    conn.rollback()
                    return AdmissionDecision(
                        denied_reason=ModelStopReason.COST_ACCOUNTING_ERROR
                    )
                day = conn.execute(
                    "SELECT * FROM llm_spend_days WHERE utc_date = ?",
                    (existing["utc_date"],),
                ).fetchone()
                job_exposure = self._job_exposure(conn, request.job_id)
                assert day is not None
                day_exposure = day["reserved_micro_usd"] + day["charged_micro_usd"]
                conn.commit()
                return AdmissionDecision(
                    reservation=self._reservation(existing, was_new=False),
                    job_remaining=_remaining(
                        request.job_limit.micro_usd, job_exposure
                    ),
                    day_remaining=_remaining(day["limit_micro_usd"], day_exposure),
                )

            caller = conn.execute(
                "SELECT access_state FROM users WHERE user_id = ?",
                (request.caller_user_id,),
            ).fetchone()
            if caller is None or caller["access_state"] != "active":
                conn.rollback()
                return AdmissionDecision(denied_reason=ModelStopReason.CALLER_REVOKED)

            newest = conn.execute("SELECT MAX(utc_date) FROM llm_spend_days").fetchone()[0]
            utc_date = request.utc_date.isoformat()
            if newest is not None and str(newest) > utc_date:
                conn.rollback()
                return AdmissionDecision(denied_reason=ModelStopReason.CLOCK_ROLLBACK)

            day = conn.execute(
                "SELECT * FROM llm_spend_days WHERE utc_date = ?", (utc_date,)
            ).fetchone()
            if day is None:
                conn.execute(
                    """
                    INSERT INTO llm_spend_days (
                        utc_date, reserved_micro_usd, charged_micro_usd,
                        limit_micro_usd, price_table_version, updated_at
                    ) VALUES (?, 0, 0, ?, ?, ?)
                    """,
                    (
                        utc_date,
                        request.day_limit.micro_usd,
                        request.price_table_version,
                        request.created_at.astimezone(UTC).isoformat(),
                    ),
                )
                day = conn.execute(
                    "SELECT * FROM llm_spend_days WHERE utc_date = ?", (utc_date,)
                ).fetchone()
            assert day is not None
            if day["price_table_version"] != request.price_table_version:
                conn.rollback()
                return AdmissionDecision(
                    denied_reason=ModelStopReason.MODEL_PRICING_UNAVAILABLE
                )
            effective_day_limit = min(
                int(day["limit_micro_usd"]), request.day_limit.micro_usd
            )
            if effective_day_limit != day["limit_micro_usd"]:
                conn.execute(
                    "UPDATE llm_spend_days SET limit_micro_usd = ?, updated_at = ? "
                    "WHERE utc_date = ?",
                    (
                        effective_day_limit,
                        request.created_at.astimezone(UTC).isoformat(),
                        utc_date,
                    ),
                )

            existing_kind = conn.execute(
                "SELECT job_kind FROM llm_cost_reservations WHERE job_id = ? LIMIT 1",
                (request.job_id,),
            ).fetchone()
            if existing_kind is not None and existing_kind["job_kind"] != request.job_kind.value:
                conn.rollback()
                return AdmissionDecision(
                    denied_reason=ModelStopReason.COST_ACCOUNTING_ERROR
                )

            job_exposure = self._job_exposure(conn, request.job_id)
            day_exposure = int(day["reserved_micro_usd"]) + int(day["charged_micro_usd"])
            proposed = request.reserved_cost.micro_usd
            if (
                job_exposure
                + proposed
                + request.preserved_job_allowance.micro_usd
                > request.job_limit.micro_usd
            ):
                conn.rollback()
                return AdmissionDecision(
                    denied_reason=ModelStopReason.JOB_COST_LIMIT,
                    job_remaining=_remaining(request.job_limit.micro_usd, job_exposure),
                    day_remaining=_remaining(effective_day_limit, day_exposure),
                )
            if day_exposure + proposed > effective_day_limit:
                conn.rollback()
                return AdmissionDecision(
                    denied_reason=ModelStopReason.DAILY_COST_LIMIT,
                    job_remaining=_remaining(request.job_limit.micro_usd, job_exposure),
                    day_remaining=_remaining(effective_day_limit, day_exposure),
                )

            try:
                conn.execute(
                    """
                    INSERT INTO llm_cost_reservations (
                        reservation_id, job_id, job_kind, caller_user_id, utc_date,
                        attempt_ordinal, provider, model, role, prompt_version,
                        trigger, outcome, reserved_micro_usd, charged_micro_usd,
                        status, input_tokens, output_tokens, latency_ms,
                        created_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL,
                              'reserved', NULL, NULL, NULL, ?, NULL)
                    """,
                    (
                        request.reservation_id,
                        request.job_id,
                        request.job_kind.value,
                        request.caller_user_id,
                        utc_date,
                        request.attempt_ordinal,
                        request.profile.provider.value,
                        request.profile.model_id,
                        request.profile.role.value,
                        request.profile.prompt_version,
                        request.trigger.value,
                        proposed,
                        request.created_at.astimezone(UTC).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return AdmissionDecision(
                    denied_reason=ModelStopReason.COST_ACCOUNTING_ERROR
                )
            conn.execute(
                "UPDATE llm_spend_days SET reserved_micro_usd = "
                "reserved_micro_usd + ?, updated_at = ? WHERE utc_date = ?",
                (
                    proposed,
                    request.created_at.astimezone(UTC).isoformat(),
                    utc_date,
                ),
            )
            conn.commit()
            reservation = CostReservation(
                reservation_id=request.reservation_id,
                job_id=request.job_id,
                utc_date=request.utc_date,
                profile=request.profile,
                reserved_cost=request.reserved_cost,
                status=ReservationStatus.RESERVED,
            )
            return AdmissionDecision(
                reservation=reservation,
                job_remaining=_remaining(
                    request.job_limit.micro_usd, job_exposure + proposed
                ),
                day_remaining=_remaining(effective_day_limit, day_exposure + proposed),
            )
        except Exception:
            conn.rollback()
            raise

    def reconcile_call(
        self, request: ReconciliationRequest
    ) -> CostReconciliation:
        conn = self._store.conn
        if conn.in_transaction:
            raise RuntimeError("spend reconciliation requires a clean SQLite transaction")
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM llm_cost_reservations WHERE reservation_id = ?",
                (request.reservation_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(f"Unknown cost reservation {request.reservation_id!r}")
            if row["status"] != ReservationStatus.RESERVED.value:
                result = CostReconciliation(
                    reservation_id=request.reservation_id,
                    charged_cost=UsdAmount(int(row["charged_micro_usd"])),
                    status=ReservationStatus(row["status"]),
                    already_reconciled=True,
                )
                conn.commit()
                return result

            status = (
                ReservationStatus.CONSERVATIVE
                if request.conservative
                else ReservationStatus.CHARGED
            )
            charged = request.charged_cost.micro_usd
            reserved = int(row["reserved_micro_usd"])
            conn.execute(
                """
                UPDATE llm_cost_reservations
                SET charged_micro_usd = ?, status = ?, outcome = ?,
                    input_tokens = ?, output_tokens = ?, latency_ms = ?, completed_at = ?
                WHERE reservation_id = ? AND status = 'reserved'
                """,
                (
                    charged,
                    status.value,
                    request.outcome.value,
                    request.usage.input_tokens if request.usage is not None else None,
                    request.usage.output_tokens if request.usage is not None else None,
                    request.latency_ms,
                    request.completed_at.astimezone(UTC).isoformat(),
                    request.reservation_id,
                ),
            )
            conn.execute(
                """
                UPDATE llm_spend_days
                SET reserved_micro_usd = reserved_micro_usd - ?,
                    charged_micro_usd = charged_micro_usd + ?, updated_at = ?
                WHERE utc_date = ?
                """,
                (
                    reserved,
                    charged,
                    request.completed_at.astimezone(UTC).isoformat(),
                    row["utc_date"],
                ),
            )
            conn.commit()
            return CostReconciliation(
                reservation_id=request.reservation_id,
                charged_cost=request.charged_cost,
                status=status,
            )
        except Exception:
            conn.rollback()
            raise

    def list_attempts(self, job_id: str) -> tuple[ModelAttemptAudit, ...]:
        rows = self._store.conn.execute(
            "SELECT * FROM llm_cost_reservations WHERE job_id = ? "
            "ORDER BY attempt_ordinal",
            (job_id,),
        ).fetchall()
        return tuple(self._audit(row) for row in rows)

    @staticmethod
    def _job_exposure(conn: sqlite3.Connection, job_id: str) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(
                CASE WHEN status = 'reserved' THEN reserved_micro_usd
                     ELSE charged_micro_usd END
            ), 0) FROM llm_cost_reservations WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _profile(row: sqlite3.Row) -> ModelProfile:
        tier = ModelTier.SONNET if row["model"] == "claude-sonnet-5" else ModelTier.OPUS
        return ModelProfile(
            provider=ModelProvider(row["provider"]),
            model_id=row["model"],
            tier=tier,
            role=ModelRole(row["role"]),
            prompt_version=row["prompt_version"],
            pricing_key=row["model"],
        )

    @classmethod
    def _reservation(
        cls, row: sqlite3.Row, *, was_new: bool
    ) -> CostReservation:
        return CostReservation(
            reservation_id=row["reservation_id"],
            job_id=row["job_id"],
            utc_date=datetime.fromisoformat(row["utc_date"]).date(),
            profile=cls._profile(row),
            reserved_cost=UsdAmount(int(row["reserved_micro_usd"])),
            status=ReservationStatus(row["status"]),
            was_new=was_new,
        )

    @classmethod
    def _audit(cls, row: sqlite3.Row) -> ModelAttemptAudit:
        usage = None
        if row["input_tokens"] is not None or row["output_tokens"] is not None:
            usage = LLMUsage(
                input_tokens=int(row["input_tokens"] or 0),
                output_tokens=int(row["output_tokens"] or 0),
            )
        return ModelAttemptAudit(
            reservation_id=row["reservation_id"],
            job_id=row["job_id"],
            ordinal=int(row["attempt_ordinal"]),
            provider=row["provider"],
            model=row["model"],
            role=row["role"],
            trigger=row["trigger"],
            outcome=row["outcome"],
            status=ReservationStatus(row["status"]),
            reserved_cost=UsdAmount(int(row["reserved_micro_usd"])),
            charged_cost=(
                UsdAmount(int(row["charged_micro_usd"]))
                if row["charged_micro_usd"] is not None
                else None
            ),
            usage=usage,
            latency_ms=row["latency_ms"],
        )


class ThreadScopedSqliteSpendLedger:
    """Run each ledger operation on a connection owned by the calling thread.

    Agentic browser work crosses from the synchronous coordinator into its dedicated async runner.
    Keeping only the database path here prevents a coordinator-created ``sqlite3.Connection`` from
    crossing that boundary while preserving ``SqliteSpendLedger`` as the single implementation of
    transactional cost rules.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def reserve_call(self, request: ReservationRequest) -> AdmissionDecision:
        with SqliteStore(self._db_path) as store:
            return SqliteSpendLedger(store).reserve_call(request)

    def reconcile_call(
        self, request: ReconciliationRequest
    ) -> CostReconciliation:
        with SqliteStore(self._db_path) as store:
            return SqliteSpendLedger(store).reconcile_call(request)

    def list_attempts(self, job_id: str) -> tuple[ModelAttemptAudit, ...]:
        with SqliteStore(self._db_path) as store:
            return SqliteSpendLedger(store).list_attempts(job_id)


class SqliteQualificationRepository:
    """Aggregate-only qualification persistence; never accepts fixture content."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def save(self, result: QualificationResult) -> str:
        qualification_id = f"qual-{uuid.uuid4().hex}"
        metrics = result.metrics
        self._store.conn.execute(
            """
            INSERT INTO llm_profile_qualifications (
                qualification_id, profile_identity, fixture_version, runs,
                correct_runs, diagnosis_runs, diagnosis_correct_runs, schema_valid_runs,
                prohibited_action_proposals, prohibited_action_executions,
                escalation_count, total_calls, total_actions, input_tokens, output_tokens,
                latency_ms, estimated_micro_usd, gate_result, completed_at,
                override_owner_user_id, override_reason, overridden_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                qualification_id,
                result.profile_identity,
                result.fixture_version,
                metrics.runs,
                metrics.correct_runs,
                metrics.diagnosis_runs,
                metrics.diagnosis_correct_runs,
                metrics.schema_valid_runs,
                metrics.prohibited_action_proposals,
                metrics.prohibited_action_executions,
                metrics.escalation_count,
                metrics.total_calls,
                metrics.total_actions,
                metrics.input_tokens,
                metrics.output_tokens,
                metrics.latency_ms,
                metrics.estimated_cost.micro_usd,
                result.gate.value,
                result.created_at.astimezone(UTC).isoformat(),
                result.owner_override_user_id,
                result.owner_override_reason,
                result.owner_override_at.astimezone(UTC).isoformat()
                if result.owner_override_at is not None
                else None,
            ),
        )
        self._store.conn.commit()
        return qualification_id

    def latest(
        self, profile_identity: str, fixture_version: str
    ) -> QualificationResult | None:
        row = self._store.conn.execute(
            """
            SELECT * FROM llm_profile_qualifications
            WHERE profile_identity = ? AND fixture_version = ?
            ORDER BY completed_at DESC, qualification_id DESC LIMIT 1
            """,
            (profile_identity, fixture_version),
        ).fetchone()
        return self._result(row) if row is not None else None

    def record_owner_override(
        self,
        qualification_id: str,
        *,
        owner_user_id: int,
        reason: str,
        overridden_at: datetime,
    ) -> QualificationResult:
        safe_reason = reason.strip()
        if not safe_reason or len(safe_reason) > 500:
            raise ValueError("override reason must contain 1 to 500 characters")
        owner = self._store.conn.execute(
            "SELECT role FROM users WHERE user_id = ?", (owner_user_id,)
        ).fetchone()
        if owner is None or owner["role"] != "owner":
            raise PermissionError("qualification override requires the local owner")
        cursor = self._store.conn.execute(
            """
            UPDATE llm_profile_qualifications
            SET override_owner_user_id = ?, override_reason = ?, overridden_at = ?
            WHERE qualification_id = ?
            """,
            (
                owner_user_id,
                safe_reason,
                overridden_at.astimezone(UTC).isoformat(),
                qualification_id,
            ),
        )
        self._store.conn.commit()
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown qualification {qualification_id!r}")
        row = self._store.conn.execute(
            "SELECT * FROM llm_profile_qualifications WHERE qualification_id = ?",
            (qualification_id,),
        ).fetchone()
        assert row is not None
        return self._result(row)

    @staticmethod
    def _result(row: sqlite3.Row) -> QualificationResult:
        metrics = QualificationMetrics(
            runs=int(row["runs"]),
            correct_runs=int(row["correct_runs"]),
            diagnosis_runs=int(row["diagnosis_runs"]),
            diagnosis_correct_runs=int(row["diagnosis_correct_runs"]),
            schema_valid_runs=int(row["schema_valid_runs"]),
            prohibited_action_proposals=int(row["prohibited_action_proposals"]),
            prohibited_action_executions=int(row["prohibited_action_executions"]),
            escalation_count=int(row["escalation_count"]),
            total_calls=int(row["total_calls"]),
            total_actions=int(row["total_actions"]),
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            latency_ms=int(row["latency_ms"]),
            estimated_cost=UsdAmount(int(row["estimated_micro_usd"])),
        )
        result = QualificationResult(
            profile_identity=row["profile_identity"],
            fixture_version=row["fixture_version"],
            metrics=metrics,
            gate=QualificationGate(row["gate_result"]),
            created_at=datetime.fromisoformat(row["completed_at"]),
        )
        if row["override_owner_user_id"] is None:
            return result
        return replace(
            result,
            owner_override_user_id=int(row["override_owner_user_id"]),
            owner_override_reason=row["override_reason"],
            owner_override_at=datetime.fromisoformat(row["overridden_at"]),
        )
