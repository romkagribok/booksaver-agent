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
    assert '# max_job_cost_usd = "1.00"' in config_text
    assert '[agentic_browser]' in config_text
    assert '# price_executor = "jev"' in config_text
    assert '# disclosure_version = "typesafe-visible-booking-page-v1"' in config_text
    for retired in ("claude", "routing", "max_llm_calls", "max_steps", "[extraction]"):
        assert retired not in config_text.lower()


def test_config_commands_show_jev_settings_for_a_legacy_file(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("BOOKSAVER_TYPESAFE_API_KEY", "typesafe-key")
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
    assert "agent_job_cost_usd         : 1.00" in validate_output
    assert "agentic_browser.price_executor: jev" in validate_output
    assert "routing" not in validate_output

    assert cmd_config_show(args) == 0
    show_output = capsys.readouterr().out
    assert "agent.max_job_cost_usd       : 1.00" in show_output
    assert "agentic_browser.price_executor: jev" in show_output
    assert "agentic_browser.disclosure   : typesafe-visible-booking-page-v1" in show_output
    assert "BOOKSAVER_TYPESAFE_API_KEY   : (set)" in show_output
    assert "LLM_API_KEY" not in show_output
    assert "routing" not in show_output
