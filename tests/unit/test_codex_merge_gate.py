from __future__ import annotations

import json
from typing import Any

import pytest
from scripts.codex_merge_gate import GateRejected, evaluate_gate

_HEAD = "a" * 40
_LANDED = "2026-11-03T01:00:00Z"


def _state(**review: object) -> dict[str, Any]:
    body = {"commit_sha": _HEAD, "status": "completed", "has_unresolved_findings": False, **review}
    return {
        "author": {"login": "chatgpt-codex-connector"},
        "body": f"<!-- codex-review-state:v1 {json.dumps({'code_review': body})} -->",
        "createdAt": "2026-11-03T01:05:00Z",
    }


def _pr(*comments: dict[str, Any], state: str = "OPEN") -> dict[str, Any]:
    return {
        "state": state,
        "headRefOid": _HEAD,
        "comments": list(comments),
        "commits": [{"committedDate": _LANDED}],
    }


def _thread(*, resolved: bool, author: str = "chatgpt-codex-connector") -> dict[str, Any]:
    return {"isResolved": resolved, "comments": {"nodes": [{"author": {"login": author}}]}}


def test_clean_review_of_the_current_head_passes() -> None:
    assert evaluate_gate(_pr(_state()), [_thread(resolved=True)]) == "passed"


def test_another_authors_unresolved_thread_does_not_block() -> None:
    assert evaluate_gate(_pr(_state()), [_thread(resolved=False, author="someone")]) == "passed"


@pytest.mark.parametrize(
    ("pr", "threads"),
    [
        (_pr(), []),  # no review reported
        (_pr(_state(commit_sha="b" * 40)), []),  # a previous head
        (_pr(_state(status="in_progress")), []),
        (_pr(_state(has_unresolved_findings=True)), []),
        (_pr(_state(has_unresolved_findings=None)), []),
        (_pr(_state()), [_thread(resolved=False)]),
        (_pr(_state(), state="MERGED"), []),
        # Someone else's comment cannot claim a clean review.
        (_pr({**_state(), "author": {"login": "someone"}}), []),
    ],
)
def test_gate_fails_closed(pr: dict[str, Any], threads: list[dict[str, Any]]) -> None:
    with pytest.raises(GateRejected):
        evaluate_gate(pr, threads)


def _limit_notice(
    created_at: str = "2026-11-03T01:05:00Z", login: str = "chatgpt-codex-connector",
) -> dict[str, Any]:
    return {
        "author": {"login": login},
        "body": "Codex could not run: your usage limit was reached.",
        "createdAt": created_at,
    }


def test_current_codex_usage_limit_notice_waives_the_gate() -> None:
    assert evaluate_gate(_pr(_limit_notice()), []) == "waived"


@pytest.mark.parametrize(
    "notice",
    [
        _limit_notice(created_at="2026-11-03T00:30:00Z"),  # before the head landed
        _limit_notice(login="someone"),
    ],
)
def test_stale_or_foreign_limit_notice_does_not_waive(notice: dict[str, Any]) -> None:
    with pytest.raises(GateRejected):
        evaluate_gate(_pr(notice), [])


def test_waiver_still_requires_codex_threads_resolved() -> None:
    with pytest.raises(GateRejected):
        evaluate_gate(_pr(_limit_notice()), [_thread(resolved=False)])
