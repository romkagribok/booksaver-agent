#!/usr/bin/env python3
"""Fail closed unless the Codex code review has cleared the current pull-request head.

One owner-approved exception: when Codex itself reports, naming the current head commit, that it
could not run because its usage limit was reached, the gate is waived (see AGENTS.md).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

_CODEX_BOT = "chatgpt-codex-connector"
_STATE = re.compile(r"<!-- codex-review-state:v1 (\{.*?\}) -->", re.S)
_USAGE_LIMIT = re.compile(r"usage limit", re.I)
_COMMIT = re.compile(r"\b[0-9a-f]{7,40}\b")

_THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        pageInfo { hasNextPage }
        nodes { isResolved comments(first: 1) { nodes { author { login } } } }
      }
    }
  }
}
"""


class GateRejected(RuntimeError):
    """The pull request does not satisfy the Codex review gate."""


def _is_codex(login: object) -> bool:
    return isinstance(login, str) and login.removesuffix("[bot]") == _CODEX_BOT


def evaluate_gate(pr: dict[str, Any], threads: list[dict[str, Any]]) -> str:
    """Return ``passed`` or ``waived``, or raise ``GateRejected``."""
    if pr["state"] != "OPEN":
        raise GateRejected("the pull request is not open")
    comments = [c for c in pr["comments"] if _is_codex((c.get("author") or {}).get("login"))]
    unresolved = sum(
        not thread["isResolved"]
        and any(
            _is_codex((comment.get("author") or {}).get("login"))
            for comment in thread["comments"]["nodes"]
        )
        for thread in threads
    )
    if unresolved:
        raise GateRejected(f"{unresolved} unresolved Codex review thread(s)")
    # A timestamp cannot prove this: an older commit can be pushed after the notice.
    if any(
        _USAGE_LIMIT.search(c["body"]) and not _STATE.search(c["body"])
        and any(pr["headRefOid"].startswith(sha) for sha in _COMMIT.findall(c["body"]))
        for c in comments
    ):
        return "waived"
    review = None
    for comment in comments:
        match = _STATE.search(comment["body"])
        if match:
            review = json.loads(match[1]).get("code_review") or {}
    if review is None:
        raise GateRejected("Codex has not reported a review")
    if review.get("commit_sha") != pr["headRefOid"]:
        raise GateRejected("the latest Codex review is not of the current head")
    if review.get("status") != "completed":
        raise GateRejected("the Codex review of the current head has not completed")
    if review.get("has_unresolved_findings") is not False:
        raise GateRejected("the Codex review has unresolved findings")
    return "passed"


def _gh(*args: str) -> dict[str, Any]:
    result = subprocess.run(["gh", *args], capture_output=True, check=False, text=True)
    if result.returncode != 0:
        raise GateRejected("GitHub CLI request failed; check gh auth and network access")
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int)
    args = parser.parse_args(argv)
    try:
        pr = _gh(
            "pr", "view", str(args.pr), "--json", "state,headRefOid,comments",
        )
        owner, repo = _gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"].split("/")
        data = _gh(
            "api", "graphql", "-f", f"query={_THREADS_QUERY}", "-F", f"owner={owner}",
            "-F", f"repo={repo}", "-F", f"number={args.pr}",
        )
        threads = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        if threads["pageInfo"]["hasNextPage"]:
            raise GateRejected("more than 100 review threads; check them by hand")
        print(evaluate_gate(pr, threads["nodes"]))
    except GateRejected as error:
        print(f"Codex merge gate blocked: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
