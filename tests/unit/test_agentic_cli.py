from __future__ import annotations

from datetime import UTC, datetime

from booksaver.cli import commands
from booksaver.domain.agentic_qualification import AgenticCanaryCheck
from booksaver.domain.model_policy import UsdAmount
from booksaver.infrastructure.persistence.sqlite_store import (
    SqliteAgenticQualificationRepository,
    SqliteStore,
    SqliteUserRepository,
)


def _setup(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[storage]\ndata_directory = "{data_dir}"\n\n'
        '[agentic_browser]\nrouting = "owner_canary"\n'
    )
    with SqliteStore(data_dir / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        SqliteAgenticQualificationRepository(store).record_check(
            AgenticCanaryCheck(
                check_id="check-agentic-1",
                owner_user_id=owner.user_id,
                observed_at=datetime(2026, 8, 17, tzinfo=UTC),
                eligible_unblocked=True,
                valid_observation=True,
                manual_price_correct=None,
                model_cost=UsdAmount(50_000),
                duration_ms=25_000,
                fallback_used=False,
            )
        )
    return config_path, data_dir


def _args(config_path, *parts: str):
    return commands.create_parser().parse_args(
        ["--config", str(config_path), "agentic", *parts]
    )


def test_agentic_parser_wires_all_local_operator_commands(tmp_path) -> None:
    config_path, _ = _setup(tmp_path)

    assert _args(config_path, "status").func is commands.cmd_agentic_status
    correct = _args(config_path, "compare", "check-agentic-1", "--correct")
    assert correct.func is commands.cmd_agentic_compare
    assert correct.correct and not correct.incorrect
    assert _args(config_path, "promote").func is commands.cmd_agentic_promote
    regress = _args(config_path, "regress", "price_correctness")
    assert regress.func is commands.cmd_agentic_regress
    assert regress.code == "price_correctness"


def test_agentic_status_is_redacted_and_promotion_stays_blocked(tmp_path, capsys) -> None:
    config_path, _ = _setup(tmp_path)

    status = _args(config_path, "status")
    assert status.func(status) == 0
    output = capsys.readouterr().out
    assert "Routing config  : owner_canary" in output
    assert "Owner checks    : 1" in output
    assert "too_few_checks" in output
    assert "Hotel" not in output

    promote = _args(config_path, "promote")
    assert promote.func(promote) == 1
    assert "promotion blocked" in capsys.readouterr().err.casefold()


def test_agentic_comparison_and_regression_are_explicit_local_mutations(
    tmp_path,
    capsys,
) -> None:
    config_path, data_dir = _setup(tmp_path)

    compare = _args(config_path, "compare", "check-agentic-1", "--correct")
    assert compare.func(compare) == 0
    regress = _args(config_path, "regress", "price_correctness")
    assert regress.func(regress) == 0

    with SqliteStore(data_dir / "booksaver.db") as store:
        owner = SqliteUserRepository(store).get_owner()
        repository = SqliteAgenticQualificationRepository(store)
        assert repository.list_checks(owner.user_id)[0].manual_price_correct is True
        assert repository.qualification_state().status.value == "regressed"
    assert "marked regressed" in capsys.readouterr().out


def test_agentic_comparison_rejects_unknown_or_invalid_check(tmp_path, capsys) -> None:
    config_path, _ = _setup(tmp_path)
    args = _args(config_path, "compare", "missing-check", "--incorrect")

    assert args.func(args) == 2
    assert "Manual comparison rejected" in capsys.readouterr().err
