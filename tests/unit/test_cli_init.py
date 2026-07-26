from __future__ import annotations

import argparse
import tomllib

from booksaver.cli.commands import cmd_init


def test_init_config_uses_requested_data_directory(tmp_path) -> None:
    data_dir = tmp_path / "custom data"

    assert cmd_init(argparse.Namespace(data_dir=str(data_dir))) == 0

    config = tomllib.loads((data_dir / "config.toml").read_text())
    assert config["storage"]["data_directory"] == str(data_dir.resolve())
