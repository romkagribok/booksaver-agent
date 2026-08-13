from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from booksaver.evaluation import (
    ReplayFixtureError,
    curated_fixture_directory,
    load_fixture,
    load_fixture_directory,
)

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "browser_recovery"


def _raw_fixture(name: str = "unsupported-layout.json") -> dict[str, Any]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, raw: dict[str, Any]) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_curated_fixture_directory_loads_in_stable_order() -> None:
    fixtures = load_fixture_directory(FIXTURE_DIRECTORY)

    assert [fixture.fixture_id for fixture in fixtures] == [
        "alternating-equivalent-refs",
        "inventory-readiness-drift",
        "inventory-scope-drift",
        "no-href-target-blank",
        "prohibited-controls",
        "unsupported-layout",
    ]
    assert all(fixture.states for fixture in fixtures)


def test_packaged_fixtures_match_and_load_like_the_test_corpus() -> None:
    packaged_directory = curated_fixture_directory()
    test_files = sorted(FIXTURE_DIRECTORY.glob("*.json"))
    packaged_files = sorted(packaged_directory.glob("*.json"))

    assert packaged_directory.is_dir()
    assert [path.name for path in packaged_files] == [path.name for path in test_files]
    assert [path.read_bytes() for path in packaged_files] == [
        path.read_bytes() for path in test_files
    ]
    assert [fixture.fixture_id for fixture in load_fixture_directory(packaged_directory)] == [
        fixture.fixture_id for fixture in load_fixture_directory(FIXTURE_DIRECTORY)
    ]


def test_all_curated_urls_are_query_free_https_booking_destinations() -> None:
    for fixture in load_fixture_directory(FIXTURE_DIRECTORY):
        for state in fixture.states:
            urls = [state.observation.url, *state.observation.popup_urls]
            urls.extend(
                element.href
                for element in state.observation.elements
                if element.href is not None
            )
            for url in urls:
                parsed = urlsplit(url)
                assert parsed.scheme == "https"
                assert parsed.hostname == "booking.com" or parsed.hostname.endswith(
                    ".booking.com"
                )
                assert not parsed.query
                assert not parsed.fragment


@pytest.mark.parametrize(
    "unsafe_value",
    [
        "https://booking.com.example.test/path",
        "http://www.booking.com/path",
        "https://www.booking.com/path?private=value",
        "https://user@www.booking.com/path",
    ],
)
def test_loader_rejects_non_allowlisted_or_unsanitized_urls(
    tmp_path: Path, unsafe_value: str
) -> None:
    raw = _raw_fixture()
    raw["states"][0]["observation"]["url"] = unsafe_value

    with pytest.raises(ReplayFixtureError, match="booking.com|URL|secret|PII"):
        load_fixture(_write_fixture(tmp_path, raw))


@pytest.mark.parametrize(
    "sensitive_text",
    [
        "Contact traveler@example.test",
        "Call +1 (317) 555-0199",
        "The full reference is 8765432109",
        "Authorization: Bearer abcdefghijklmnop",
        "The cookie value is redacted",
        "Token abcdefghijklmnopqrstuvwxyzABCDEF",
        "Open https://example.test/collect",
    ],
)
def test_loader_rejects_secret_or_pii_shaped_content(
    tmp_path: Path, sensitive_text: str
) -> None:
    raw = _raw_fixture()
    raw["states"][0]["observation"]["text"] = sensitive_text

    with pytest.raises(ReplayFixtureError, match="secret|PII|booking.com"):
        load_fixture(_write_fixture(tmp_path, raw))


def test_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    raw = _raw_fixture()
    raw["production_prompt"] = "not permitted"

    with pytest.raises(ReplayFixtureError, match="unknown fields"):
        load_fixture(_write_fixture(tmp_path, raw))


def test_loader_preserves_terminal_diagnosis_contract() -> None:
    fixture = load_fixture(FIXTURE_DIRECTORY / "unsupported-layout.json")

    assert fixture.terminal_diagnosis_required
    assert all(
        transition.expectation.diagnosis_reason is not None
        for transition in fixture.states[0].transitions
    )


def test_loader_rejects_dangling_state_transition(tmp_path: Path) -> None:
    raw = _raw_fixture("inventory-scope-drift.json")
    transition = raw["states"][0]["transitions"][0]
    transition["next_state"] = "missing-state"

    with pytest.raises(ReplayFixtureError, match="unknown state"):
        load_fixture(_write_fixture(tmp_path, raw))


def test_loader_rejects_duplicate_element_refs(tmp_path: Path) -> None:
    raw = _raw_fixture("prohibited-controls.json")
    raw["states"][0]["observation"]["elements"][1]["ref"] = "e1"

    with pytest.raises(ReplayFixtureError, match="duplicate refs"):
        load_fixture(_write_fixture(tmp_path, raw))


def test_loader_rejects_empty_fixture_directory(tmp_path: Path) -> None:
    with pytest.raises(ReplayFixtureError, match="no JSON fixtures"):
        load_fixture_directory(tmp_path)


def test_loader_rejects_unbounded_fixture_directory(tmp_path: Path) -> None:
    for index in range(21):
        (tmp_path / f"fixture-{index}.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ReplayFixtureError, match="20-file safety limit"):
        load_fixture_directory(tmp_path)
