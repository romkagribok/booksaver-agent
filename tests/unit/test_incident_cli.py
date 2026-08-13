from __future__ import annotations

import argparse
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from booksaver.cli import commands
from booksaver.domain.browser_resilience import (
    DomJourney,
    DomStepId,
    TerminalBrowserReason,
)
from booksaver.domain.dom_incident import (
    DiagnosticBundle,
    DiagnosticInspection,
    DiagnosticModelAttempt,
    DomDriftFingerprint,
    DomDriftIncident,
    EvidenceState,
    IncidentBudgetState,
    IncidentProviderState,
    IncidentSeverity,
    IncidentSourceProvenance,
    IncidentState,
    StructuralDigest,
)
from booksaver.domain.model_policy import (
    SONNET_5_MODEL,
    EscalationTrigger,
    ModelAttemptOutcome,
    ModelProvider,
    ModelRole,
    ReservationStatus,
)
from booksaver.domain.models import Config
from booksaver.domain.value_objects import (
    CheckInterval,
    DataDirectory,
    NotificationSettings,
    TelegramBotSettings,
)

_INCIDENT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def _config(tmp_path: Path) -> Path:
    config = tmp_path / "config.toml"
    config.write_text(f'[storage]\ndata_directory = "{tmp_path}"\n')
    return config


def _incident() -> DomDriftIncident:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    return DomDriftIncident(
        incident_id=_INCIDENT_ID,
        fingerprint=DomDriftFingerprint("a" * 64),
        journey=DomJourney.ACCOUNT_INVENTORY,
        step_id=DomStepId.INVENTORY_EXTRACTION,
        terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
        verifier_category="inventory_parser_v2",
        structural_digest=StructuralDigest("b" * 64),
        model_roles=(ModelRole.RECOVERY, ModelRole.DIAGNOSTIC),
        provider_state=IncidentProviderState.COMPLETED,
        budget_state=IncidentBudgetState.WITHIN_LIMIT,
        provenance=IncidentSourceProvenance.CODE_MAINTENANCE_REQUIRED,
        state=IncidentState.OPEN,
        severity=IncidentSeverity.MAINTENANCE_REQUIRED,
        recovered=False,
        occurrence_count=2,
        window_occurrence_count=2,
        first_observed_at=now,
        last_observed_at=now,
        opened_at=now,
        resolved_at=None,
        alert_suppressed_until=None,
        evidence_state=EvidenceState.AVAILABLE,
    )


def _runtime_config(tmp_path: Path, *, enabled: bool) -> Config:
    return Config(
        check_interval=CheckInterval.parse("1h"),
        data_directory=DataDirectory(path=tmp_path),
        notification_settings=NotificationSettings(),
        loaded_at=datetime.now(UTC),
        telegram_bot_settings=TelegramBotSettings(
            enabled=enabled,
            owner_chat_id=42 if enabled else None,
        ),
    )


def test_parser_exposes_local_incident_commands() -> None:
    listed = commands.create_parser().parse_args(["incidents", "list"])
    inspected = commands.create_parser().parse_args(["incidents", "inspect", str(_INCIDENT_ID)])

    assert listed.func is commands.cmd_incidents_list
    assert listed.limit == 50
    assert inspected.func is commands.cmd_incidents_inspect


def test_incident_inspect_rejects_non_uuid_before_loading_config(capsys) -> None:
    args = argparse.Namespace(incident_id="../../not-an-incident", config=None)

    assert commands.cmd_incidents_inspect(args) == 2

    assert capsys.readouterr().err == "Incident ID must be a UUID.\n"


def test_incident_list_renders_content_free_projection(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _config(tmp_path)
    (tmp_path / "booksaver.db").touch()

    class Repo:
        def __init__(self, _store) -> None: ...

        def list_incidents(self, limit: int = 50):
            assert limit == 5
            return (_incident(),)

    monkeypatch.setattr(
        "booksaver.infrastructure.persistence.dom_incident.SqliteDomIncidentRepository",
        Repo,
    )

    result = commands.cmd_incidents_list(argparse.Namespace(config=str(config), limit=5))

    assert result == 0
    output = capsys.readouterr().out
    assert str(_INCIDENT_ID) in output
    assert "account_inventory" in output
    assert "inventory.extraction" in output
    assert "PROPERTY" not in output
    assert "https://" not in output


def test_incident_inspect_decrypts_only_for_local_cli(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _config(tmp_path)
    (tmp_path / "booksaver.db").touch()
    now = datetime(2026, 8, 13, tzinfo=UTC)
    inspection = DiagnosticInspection(
        evidence_state=EvidenceState.AVAILABLE,
        bundle=DiagnosticBundle(
            incident_id=_INCIDENT_ID,
            source_user_ids=(7,),
            structural_roles=("reservation_card",),
            action_outcomes=("parser_empty",),
            terminal_reason=TerminalBrowserReason.CODE_MAINTENANCE_REQUIRED,
            model_roles=(ModelRole.RECOVERY,),
            provider_state=IncidentProviderState.COMPLETED,
            budget_state=IncidentBudgetState.WITHIN_LIMIT,
            created_at=now,
            model_attempts=(
                DiagnosticModelAttempt(
                    ordinal=1,
                    provider=ModelProvider.ANTHROPIC,
                    model=SONNET_5_MODEL,
                    role=ModelRole.RECOVERY,
                    trigger=EscalationTrigger.INITIAL_AMBIGUOUS,
                    outcome=ModelAttemptOutcome.RECOVERED,
                    status=ReservationStatus.CHARGED,
                    input_tokens=120,
                    output_tokens=30,
                    latency_ms=400,
                    reserved_micro_usd=900,
                    charged_micro_usd=700,
                ),
            ),
        ),
    )

    class Repo:
        def __init__(self, _store) -> None: ...

        def get_incident(self, incident_id):
            assert incident_id == _INCIDENT_ID
            return _incident()

    class Diagnostics:
        def __init__(self, _store) -> None: ...

        def inspect(self, incident_id, inspected_at):
            assert incident_id == _INCIDENT_ID
            assert inspected_at.tzinfo is UTC
            return inspection

    monkeypatch.setattr(
        "booksaver.infrastructure.persistence.dom_incident.SqliteDomIncidentRepository",
        Repo,
    )
    monkeypatch.setattr(
        "booksaver.infrastructure.persistence.encrypted_diagnostics.EncryptedDiagnosticStore",
        Diagnostics,
    )

    result = commands.cmd_incidents_inspect(
        argparse.Namespace(config=str(config), incident_id=str(_INCIDENT_ID))
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "Source users   : 7" in output
    assert "reservation_card" in output
    assert "parser_empty" in output
    assert "Model attempts : 1" in output
    assert "input=120 output=30 latency_ms=400" in output
    assert "provider=anthropic model=claude-sonnet-5" in output
    assert "reservation-secret" not in output
    assert "job-secret" not in output
    assert "Structural image: unavailable" in output


def test_incident_runner_is_disabled_without_owner_telegram(tmp_path: Path) -> None:
    assert (
        commands._make_dom_incident_runner(
            _runtime_config(tmp_path, enabled=False),
            tmp_path / "booksaver.db",
            None,
        )
        is None
    )


def test_incident_runner_owns_service_thread_store(tmp_path: Path, monkeypatch) -> None:
    class Client:
        def send_message(self, _chat_id, _text):
            return {}

    created: list[tuple[object, object, object]] = []

    class Worker:
        def __init__(self, *, incident_repository_factory, diagnostic_store_factory, notifier):
            with incident_repository_factory() as incidents:
                incident_name = incidents.__class__.__name__
            with diagnostic_store_factory() as diagnostics:
                diagnostic_name = diagnostics.__class__.__name__
            created.append((incident_name, diagnostic_name, notifier))

        def run(self, stop_event):
            assert stop_event.is_set()

    monkeypatch.setattr(
        "booksaver.application.dom_incident.DomIncidentLifecycleWorker",
        Worker,
    )
    config = _runtime_config(tmp_path, enabled=True)
    runner = commands._make_dom_incident_runner(
        config,
        tmp_path / "booksaver.db",
        Client(),  # type: ignore[arg-type]
    )

    assert runner is not None
    stop_event = threading.Event()
    stop_event.set()
    runner(stop_event)

    assert len(created) == 1
    incidents, diagnostics, notifier = created[0]
    assert incidents == "SqliteDomIncidentRepository"
    assert diagnostics == "EncryptedDiagnosticStore"
    assert notifier.__class__.__name__ == "OwnerIncidentTelegramNotifier"


def test_check_coordinator_composes_post_browser_incident_recorder(tmp_path: Path) -> None:
    coordinator = commands._make_check_coordinator(  # noqa: SLF001
        _runtime_config(tmp_path, enabled=False),
        threading.Event(),
    )

    factory = coordinator._incident_recorder_factory  # noqa: SLF001
    assert factory is not None
    with factory() as recorder:
        assert recorder.__class__.__name__ == "DomIncidentRecorder"
        assert recorder._incidents.__class__.__name__ == "SqliteDomIncidentRepository"  # noqa: SLF001
        assert recorder._diagnostics.__class__.__name__ == "EncryptedDiagnosticStore"  # noqa: SLF001
