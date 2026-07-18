from __future__ import annotations

import tomllib
from pathlib import Path


def test_sqlite_schema_is_declared_as_package_data() -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((project_root / "pyproject.toml").read_text())

    package_data = config["tool"]["setuptools"]["package-data"]

    assert package_data["booksaver.infrastructure.persistence"] == ["schema.sql"]
