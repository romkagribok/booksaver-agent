from __future__ import annotations

import argparse
import tomllib

from booksaver.cli.commands import cmd_config_show, cmd_config_validate, cmd_init


def test_init_config_uses_requested_data_directory(tmp_path) -> None:
    data_dir = tmp_path / "custom data"

    assert cmd_init(argparse.Namespace(data_dir=str(data_dir))) == 0

    config_text = (data_dir / "config.toml").read_text()
    config = tomllib.loads(config_text)
    assert config["storage"]["data_directory"] == str(data_dir.resolve())
    assert "# max_recovery_calls_per_step = 4" in config_text
    assert "# recovery_timeout_seconds = 60" in config_text
    assert "# screenshot_after_no_progress = 2" in config_text
    assert "# max_semantic_action_executions = 2" in config_text


def test_config_commands_show_effective_recovery_defaults(tmp_path, capsys) -> None:
    config_path = tmp_path / "legacy-config.toml"
    config_path.write_text(
        '[storage]\n'
        f'data_directory = "{tmp_path}"\n'
        '\n[agent]\n'
        'max_steps = 15\n'
        'max_llm_calls = 20\n'
        'check_timeout_seconds = 180\n'
    )
    args = argparse.Namespace(config=str(config_path))

    assert cmd_config_validate(args) == 0
    validate_output = capsys.readouterr().out
    assert "agent_recovery_calls/step  : 4" in validate_output
    assert "agent_recovery_timeout_s   : 60" in validate_output

    assert cmd_config_show(args) == 0
    show_output = capsys.readouterr().out
    assert "agent.recovery_calls/step   : 4" in show_output
    assert "agent.recovery_timeout_s     : 60" in show_output
    assert "agent.screenshot_after_no_progress: 2" in show_output
    assert "agent.semantic_action_executions: 2" in show_output
