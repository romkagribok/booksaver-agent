from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import booksaver.evaluation as evaluation_module
import booksaver.infrastructure.llm.anthropic_adapter as anthropic_adapter
from booksaver.cli import commands
from booksaver.cli.commands import cmd_evaluate_recovery, create_parser
from booksaver.domain.model_policy import (
    QualificationEvaluator,
    QualificationMetrics,
    UsdAmount,
)
from booksaver.evaluation import (
    PACKAGED_QUALIFICATION_VERSION,
    approved_recovery_profiles,
)
from booksaver.infrastructure.persistence.model_policy import (
    SqliteQualificationRepository,
)
from booksaver.infrastructure.persistence.sqlite_store import SqliteStore


def _args(*extra: str):
    return create_parser().parse_args(
        ["evaluate", "recovery", *extra]
    )


def test_recovery_evaluation_parser_defaults_to_ten_non_live_runs() -> None:
    args = _args()

    assert args.runs == 10
    assert args.live is False
    assert args.fixture is None
    assert args.max_cost_usd is None
    assert args.qualify is False
    assert args.persist is False
    assert args.func is cmd_evaluate_recovery


def test_recovery_evaluation_requires_explicit_live_opt_in(capsys) -> None:
    result = cmd_evaluate_recovery(_args())

    assert result == 2
    assert "without --live" in capsys.readouterr().err


def test_recovery_evaluation_requires_provider_key_before_reading_fixture(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.delenv("BOOKSAVER_LLM_API_KEY", raising=False)
    args = _args("--live", "--fixture", str(tmp_path / "missing.json"))
    args.fixture = str(tmp_path / "missing.json")

    result = cmd_evaluate_recovery(args)

    assert result == 2
    assert "BOOKSAVER_LLM_API_KEY" in capsys.readouterr().err


def test_recovery_evaluation_parser_caps_live_repetitions() -> None:
    with pytest.raises(SystemExit):
        _args("--runs", "11")


def test_live_replay_requires_explicit_cost_limit(monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")

    result = cmd_evaluate_recovery(_args("--live"))

    assert result == 2
    assert "--max-cost-usd" in capsys.readouterr().err


def test_recovery_evaluation_rejects_plan_over_250_calls(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        evaluation_module,
        "load_fixture_directory",
        lambda _path: tuple(SimpleNamespace(max_calls=4) for _ in range(7)),
    )

    result = cmd_evaluate_recovery(
        _args(
            "--live",
            "--max-cost-usd",
            "100.00",
            "--runs",
            "10",
            "--fixture",
            str(tmp_path),
        )
    )

    assert result == 2
    assert "more than 250 provider calls" in capsys.readouterr().err


def test_recovery_evaluation_reports_provider_token_usage(
    monkeypatch, capsys
) -> None:
    fixture = (
        Path(__file__).parent.parent
        / "fixtures"
        / "browser_recovery"
        / "unsupported-layout.json"
    )
    aggregate = SimpleNamespace(
        fixture_id="unsupported-layout",
        runs=10,
        correct_runs=10,
        safe_runs=10,
        correct_rate=1.0,
        prohibited_action_executions=0,
        total_actual_calls=10,
        total_actions=0,
        total_input_tokens=1234,
        total_output_tokens=210,
        total_tokens=1444,
        total_latency_seconds=2.5,
        estimated_micro_usd=123,
        outcome_categories=(("unsupported-layout", 10),),
    )

    class _Runner:
        def run(self, fixture, brain, *, runs):
            return (), aggregate

    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        commands,
        "_load_config_for_args",
        lambda args: SimpleNamespace(agent_settings=SimpleNamespace(model="test-model")),
    )
    monkeypatch.setattr(evaluation_module, "ReplayRunner", _Runner)
    monkeypatch.setattr(
        anthropic_adapter,
        "AnthropicAgentBrain",
        lambda **kwargs: SimpleNamespace(),
    )

    result = cmd_evaluate_recovery(
        _args(
            "--live",
            "--max-cost-usd",
            "100.00",
            "--fixture",
            str(fixture),
        )
    )

    assert result == 0
    assert "tokens=1234in/210out/1444total" in capsys.readouterr().out


def test_custom_fixture_cannot_be_qualified_or_persisted(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")

    result = cmd_evaluate_recovery(
        _args(
            "--live",
            "--max-cost-usd",
            "100.00",
            "--qualify",
            "--persist",
            "--fixture",
            str(tmp_path / "fixture.json"),
        )
    )

    assert result == 2
    assert "packaged fixture corpus" in capsys.readouterr().err


def test_persist_requires_qualification(monkeypatch, capsys) -> None:
    monkeypatch.setenv("BOOKSAVER_LLM_API_KEY", "test-key")

    result = cmd_evaluate_recovery(
        _args("--live", "--max-cost-usd", "100.00", "--persist")
    )

    assert result == 2
    assert "only valid with --qualify" in capsys.readouterr().err


def test_qualification_parser_routes_to_release_gate() -> None:
    args = create_parser().parse_args(["evaluate", "qualification"])

    assert args.func is commands.cmd_validate_model_qualification
    assert args.override is None
    assert args.reason is None


def test_release_gate_requires_both_locally_recorded_profiles(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    cfg = SimpleNamespace(data_directory=SimpleNamespace(path=tmp_path))
    monkeypatch.setattr(commands, "_load_config_for_args", lambda _args: cfg)
    metrics = QualificationMetrics(
        runs=10,
        correct_runs=10,
        diagnosis_runs=10,
        diagnosis_correct_runs=10,
        schema_valid_runs=10,
        prohibited_action_proposals=0,
        prohibited_action_executions=0,
        escalation_count=0,
        total_calls=10,
        total_actions=0,
        input_tokens=100,
        output_tokens=10,
        latency_ms=50,
        estimated_cost=UsdAmount(300),
    )
    sonnet, opus = approved_recovery_profiles()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repository = SqliteQualificationRepository(store)
        repository.save(
            QualificationEvaluator().evaluate(
                profile_identity=sonnet.identity,
                fixture_version=PACKAGED_QUALIFICATION_VERSION,
                metrics=metrics,
                created_at=datetime(2026, 8, 13, tzinfo=UTC),
                required_fixture_results=((10, 10),),
            )
        )

    args = create_parser().parse_args(["evaluate", "qualification"])
    assert commands.cmd_validate_model_qualification(args) == 1
    assert f"{opus.model_id}=missing" in capsys.readouterr().err

    with SqliteStore(tmp_path / "booksaver.db") as store:
        SqliteQualificationRepository(store).save(
            QualificationEvaluator().evaluate(
                profile_identity=opus.identity,
                fixture_version=PACKAGED_QUALIFICATION_VERSION,
                metrics=metrics,
                created_at=datetime(2026, 8, 13, tzinfo=UTC),
                required_fixture_results=((10, 10),),
            )
        )

    assert commands.cmd_validate_model_qualification(args) == 0
    assert "qualification is valid" in capsys.readouterr().out


def test_release_gate_accepts_explicit_local_owner_override(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    cfg = SimpleNamespace(data_directory=SimpleNamespace(path=tmp_path))
    monkeypatch.setattr(commands, "_load_config_for_args", lambda _args: cfg)
    passed_metrics = QualificationMetrics(
        runs=10,
        correct_runs=10,
        diagnosis_runs=10,
        diagnosis_correct_runs=10,
        schema_valid_runs=10,
        prohibited_action_proposals=0,
        prohibited_action_executions=0,
        escalation_count=0,
        total_calls=10,
        total_actions=0,
        input_tokens=100,
        output_tokens=10,
        latency_ms=50,
        estimated_cost=UsdAmount(300),
    )
    sonnet, opus = approved_recovery_profiles()
    with SqliteStore(tmp_path / "booksaver.db") as store:
        repository = SqliteQualificationRepository(store)
        failed_id = repository.save(
            QualificationEvaluator().evaluate(
                profile_identity=sonnet.identity,
                fixture_version=PACKAGED_QUALIFICATION_VERSION,
                metrics=replace(passed_metrics, correct_runs=8),
                created_at=datetime(2026, 8, 13, tzinfo=UTC),
                required_fixture_results=((10, 8),),
            )
        )
        repository.save(
            QualificationEvaluator().evaluate(
                profile_identity=opus.identity,
                fixture_version=PACKAGED_QUALIFICATION_VERSION,
                metrics=passed_metrics,
                created_at=datetime(2026, 8, 13, tzinfo=UTC),
                required_fixture_results=((10, 10),),
            )
        )

    args = create_parser().parse_args(
        [
            "evaluate",
            "qualification",
            "--override",
            failed_id,
            "--reason",
            "Reviewed aggregate local replay",
        ]
    )
    assert commands.cmd_validate_model_qualification(args) == 0
    output = capsys.readouterr().out
    assert "override recorded locally" in output
    assert "qualification is valid" in output
