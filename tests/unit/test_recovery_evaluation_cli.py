from pathlib import Path
from types import SimpleNamespace

import pytest

import booksaver.evaluation as evaluation_module
import booksaver.infrastructure.llm.anthropic_adapter as anthropic_adapter
from booksaver.cli import commands
from booksaver.cli.commands import cmd_evaluate_recovery, create_parser


def _args(*extra: str):
    return create_parser().parse_args(
        ["evaluate", "recovery", *extra]
    )


def test_recovery_evaluation_parser_defaults_to_ten_non_live_runs() -> None:
    args = _args()

    assert args.runs == 10
    assert args.live is False
    assert args.fixture is None
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
        _args("--live", "--runs", "10", "--fixture", str(tmp_path))
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

    result = cmd_evaluate_recovery(_args("--live", "--fixture", str(fixture)))

    assert result == 0
    assert "tokens=1234in/210out/1444total" in capsys.readouterr().out
