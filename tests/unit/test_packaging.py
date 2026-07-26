from __future__ import annotations

import tomllib
from pathlib import Path


def test_sqlite_schema_is_declared_as_package_data() -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((project_root / "pyproject.toml").read_text())

    package_data = config["tool"]["setuptools"]["package-data"]

    assert package_data["booksaver.infrastructure.persistence"] == ["schema.sql"]


def test_publication_metadata_points_to_repository_files() -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((project_root / "pyproject.toml").read_text())
    project = config["project"]

    assert project["readme"] == "README.md"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert project["urls"]["Repository"].endswith("roman-marchuk/booksaver-agent")
