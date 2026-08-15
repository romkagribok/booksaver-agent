from __future__ import annotations

from typing import Any

import pytest
from scripts.bugbot_merge_gate import (
    GateData,
    GateRejected,
    _target,
    evaluate_gate,
    fetch_gate_data,
    main,
)

_HEAD = "a" * 40
_OLD_HEAD = "b" * 40


def _review(oid: str = _HEAD) -> dict[str, Any]:
    return {
        "author": {"login": "cursor"},
        "body": "<!-- BUGBOT_REVIEW --> clean",
        "commit": {"oid": oid},
    }


def _thread(*, resolved: bool, author: str = "cursor") -> dict[str, Any]:
    return {
        "isResolved": resolved,
        "comments": {"nodes": [{"author": {"login": author}}]},
    }


def test_gate_accepts_current_review_with_all_cursor_threads_resolved() -> None:
    result = evaluate_gate(
        GateData(
            state="OPEN",
            head_oid=_HEAD,
            reviews=(_review(),),
            threads=(_thread(resolved=True), _thread(resolved=False, author="human-reviewer")),
        )
    )

    assert result.head_oid == _HEAD
    assert result.bugbot_reviews_for_head == 1
    assert result.cursor_threads == 1


def test_gate_rejects_missing_bugbot_review() -> None:
    with pytest.raises(GateRejected, match="has not completed"):
        evaluate_gate(GateData("OPEN", _HEAD, (), ()))


def test_gate_rejects_review_of_previous_head() -> None:
    with pytest.raises(GateRejected, match="stale"):
        evaluate_gate(GateData("OPEN", _HEAD, (_review(_OLD_HEAD),), ()))


def test_gate_rejects_any_unresolved_cursor_thread() -> None:
    with pytest.raises(GateRejected, match="1 Cursor review thread"):
        evaluate_gate(GateData("OPEN", _HEAD, (_review(),), (_thread(resolved=False),)))


def test_gate_rejects_closed_pull_request() -> None:
    with pytest.raises(GateRejected, match="not open"):
        evaluate_gate(GateData("MERGED", _HEAD, (_review(),), ()))


def test_target_parses_canonical_url_and_rejects_repository_conflict() -> None:
    assert _target("https://github.com/example/project/pull/23", None) == (
        "example",
        "project",
        23,
    )
    with pytest.raises(ValueError, match="different repositories"):
        _target("https://github.com/example/project/pull/23", "other/project")


def test_cli_fails_closed_without_review(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.bugbot_merge_gate.fetch_gate_data",
        lambda _owner, _repo, _number: GateData("OPEN", _HEAD, (), ()),
    )

    assert main(("23", "--repo", "example/project")) == 3


def test_fetch_gate_data_paginates_reviews_and_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _graphql(
        query: str,
        _owner: str,
        _repo: str,
        _number: int,
        cursor: str | None,
    ) -> dict[str, Any]:
        if "reviews(first" in query:
            nodes = [_review(_OLD_HEAD)] if cursor is None else [_review()]
            page_info = (
                {"hasNextPage": True, "endCursor": "review-page-2"}
                if cursor is None
                else {"hasNextPage": False, "endCursor": None}
            )
            pull_request = {
                "state": "OPEN",
                "headRefOid": _HEAD,
                "reviews": {"nodes": nodes, "pageInfo": page_info},
            }
        else:
            nodes = [_thread(resolved=True)]
            page_info = (
                {"hasNextPage": True, "endCursor": "thread-page-2"}
                if cursor is None
                else {"hasNextPage": False, "endCursor": None}
            )
            pull_request = {
                "reviewThreads": {"nodes": nodes, "pageInfo": page_info},
            }
        return {"data": {"repository": {"pullRequest": pull_request}}}

    monkeypatch.setattr("scripts.bugbot_merge_gate._graphql", _graphql)

    data = fetch_gate_data("example", "project", 23)

    assert len(data.reviews) == 2
    assert len(data.threads) == 2
    assert evaluate_gate(data).head_oid == _HEAD
