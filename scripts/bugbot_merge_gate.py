#!/usr/bin/env python3
"""Fail closed unless Cursor Bugbot has cleared the current pull-request head."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

_BUGBOT_MARKER = "<!-- BUGBOT_REVIEW -->"
_PR_URL = re.compile(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

_REVIEWS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      state
      headRefOid
      reviews(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          author { login }
          body
          commit { oid }
        }
      }
    }
  }
}
"""

_THREADS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first: 100) {
            nodes { author { login } }
          }
        }
      }
    }
  }
}
"""

_CHECKS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      commits(last: 1) {
        nodes {
          commit {
            oid
            statusCheckRollup {
              contexts(first: 100, after: $cursor) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  __typename
                  ... on CheckRun {
                    name
                    status
                    conclusion
                    checkSuite { app { slug } }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

JsonObject = dict[str, Any]


class GateRejected(RuntimeError):
    """The pull request does not satisfy the Bugbot review gate."""


class GitHubAccessError(RuntimeError):
    """Thread-aware GitHub state could not be loaded safely."""


@dataclass(frozen=True)
class GateData:
    state: str
    head_oid: str
    reviews: tuple[JsonObject, ...]
    threads: tuple[JsonObject, ...]
    checks: tuple[JsonObject, ...] = ()


@dataclass(frozen=True)
class GateSummary:
    head_oid: str
    bugbot_reviews_for_head: int
    bugbot_checks_for_head: int
    cursor_threads: int


def _is_cursor(login: object) -> bool:
    return isinstance(login, str) and login.casefold().startswith("cursor")


def _comment_authors(thread: JsonObject) -> tuple[str, ...]:
    comments = thread.get("comments")
    if not isinstance(comments, dict):
        return ()
    nodes = comments.get("nodes")
    if not isinstance(nodes, list):
        return ()
    authors: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        author = node.get("author")
        if not isinstance(author, dict):
            continue
        login = author.get("login")
        if isinstance(login, str):
            authors.append(login)
    return tuple(authors)


def evaluate_gate(data: GateData) -> GateSummary:
    """Evaluate already-fetched review state without exposing review contents."""

    if data.state != "OPEN":
        raise GateRejected("pull request is not open")
    if not data.head_oid:
        raise GateRejected("pull request head commit is unavailable")

    bugbot_reviews = []
    for review in data.reviews:
        author = review.get("author")
        login = author.get("login") if isinstance(author, dict) else None
        body = review.get("body")
        commit = review.get("commit")
        oid = commit.get("oid") if isinstance(commit, dict) else None
        if _is_cursor(login) and isinstance(body, str) and _BUGBOT_MARKER in body:
            bugbot_reviews.append(oid)

    current_reviews = [oid for oid in bugbot_reviews if oid == data.head_oid]
    current_checks = []
    for check in data.checks:
        suite = check.get("checkSuite")
        app = suite.get("app") if isinstance(suite, dict) else None
        if (
            check.get("headOid") == data.head_oid
            and check.get("__typename") == "CheckRun"
            and check.get("name") == "Cursor Bugbot"
            and check.get("status") == "COMPLETED"
            and check.get("conclusion") == "SUCCESS"
            and isinstance(app, dict)
            and app.get("slug") == "cursor"
        ):
            current_checks.append(check)

    if not current_reviews and not current_checks:
        current_bugbot_checks = [
            check
            for check in data.checks
            if check.get("headOid") == data.head_oid and check.get("name") == "Cursor Bugbot"
        ]
        if current_bugbot_checks:
            raise GateRejected("Bugbot check has not completed successfully for the current head")
        if bugbot_reviews:
            raise GateRejected("Bugbot review is stale for the current pull-request head")
        raise GateRejected("Bugbot has not completed a review for the pull request")

    cursor_threads = [
        thread
        for thread in data.threads
        if any(_is_cursor(login) for login in _comment_authors(thread))
    ]
    unresolved = [thread for thread in cursor_threads if thread.get("isResolved") is not True]
    if unresolved:
        raise GateRejected(f"{len(unresolved)} Cursor review thread(s) remain unresolved")

    return GateSummary(
        head_oid=data.head_oid,
        bugbot_reviews_for_head=len(current_reviews),
        bugbot_checks_for_head=len(current_checks),
        cursor_threads=len(cursor_threads),
    )


def _run_json(command: list[str], *, stdin: str | None = None) -> JsonObject:
    try:
        completed = subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitHubAccessError("GitHub CLI is not installed") from exc
    if completed.returncode != 0:
        raise GitHubAccessError("GitHub CLI request failed; check gh auth and network access")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubAccessError("GitHub CLI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise GitHubAccessError("GitHub CLI returned an unexpected response")
    return payload


def _graphql(query: str, owner: str, repo: str, number: int, cursor: str | None) -> JsonObject:
    command = [
        "gh",
        "api",
        "graphql",
        "-F",
        "query=@-",
        "-F",
        f"owner={owner}",
        "-F",
        f"repo={repo}",
        "-F",
        f"number={number}",
    ]
    if cursor is not None:
        command.extend(("-F", f"cursor={cursor}"))
    payload = _run_json(command, stdin=query)
    errors = payload.get("errors")
    if errors:
        raise GitHubAccessError("GitHub GraphQL returned an error")
    return payload


def _pull_request(payload: JsonObject) -> JsonObject:
    data = payload.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    pull_request = repository.get("pullRequest") if isinstance(repository, dict) else None
    if not isinstance(pull_request, dict):
        raise GitHubAccessError("pull request was not found")
    return pull_request


def fetch_gate_data(owner: str, repo: str, number: int) -> GateData:
    reviews: list[JsonObject] = []
    review_cursor: str | None = None
    state: str | None = None
    head_oid: str | None = None
    while True:
        pull_request = _pull_request(_graphql(_REVIEWS_QUERY, owner, repo, number, review_cursor))
        current_state = pull_request.get("state")
        current_head = pull_request.get("headRefOid")
        if not isinstance(current_state, str) or not isinstance(current_head, str):
            raise GitHubAccessError("pull request review metadata is incomplete")
        state = current_state
        head_oid = current_head
        connection = pull_request.get("reviews")
        if not isinstance(connection, dict):
            raise GitHubAccessError("pull request reviews are unavailable")
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise GitHubAccessError("pull request reviews are malformed")
        reviews.extend(node for node in nodes if isinstance(node, dict))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or page_info.get("hasNextPage") is not True:
            break
        review_cursor = page_info.get("endCursor")
        if not isinstance(review_cursor, str) or not review_cursor:
            raise GitHubAccessError("pull request review pagination is malformed")

    threads: list[JsonObject] = []
    thread_cursor: str | None = None
    while True:
        pull_request = _pull_request(_graphql(_THREADS_QUERY, owner, repo, number, thread_cursor))
        connection = pull_request.get("reviewThreads")
        if not isinstance(connection, dict):
            raise GitHubAccessError("pull request review threads are unavailable")
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise GitHubAccessError("pull request review threads are malformed")
        threads.extend(node for node in nodes if isinstance(node, dict))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or page_info.get("hasNextPage") is not True:
            break
        thread_cursor = page_info.get("endCursor")
        if not isinstance(thread_cursor, str) or not thread_cursor:
            raise GitHubAccessError("pull request thread pagination is malformed")

    checks: list[JsonObject] = []
    check_cursor: str | None = None
    while True:
        pull_request = _pull_request(_graphql(_CHECKS_QUERY, owner, repo, number, check_cursor))
        commits = pull_request.get("commits")
        commit_nodes = commits.get("nodes") if isinstance(commits, dict) else None
        if not isinstance(commit_nodes, list) or len(commit_nodes) != 1:
            raise GitHubAccessError("pull request head checks are unavailable")
        commit = commit_nodes[0].get("commit") if isinstance(commit_nodes[0], dict) else None
        commit_oid = commit.get("oid") if isinstance(commit, dict) else None
        if not isinstance(commit_oid, str) or commit_oid != head_oid:
            raise GitHubAccessError("pull request head checks do not match the current head")
        rollup = commit.get("statusCheckRollup") if isinstance(commit, dict) else None
        if rollup is None:
            break
        connection = rollup.get("contexts") if isinstance(rollup, dict) else None
        if not isinstance(connection, dict):
            raise GitHubAccessError("pull request head checks are malformed")
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise GitHubAccessError("pull request head check contexts are malformed")
        for node in nodes:
            if isinstance(node, dict):
                checks.append({**node, "headOid": commit_oid})
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or page_info.get("hasNextPage") is not True:
            break
        check_cursor = page_info.get("endCursor")
        if not isinstance(check_cursor, str) or not check_cursor:
            raise GitHubAccessError("pull request head check pagination is malformed")

    assert state is not None
    assert head_oid is not None
    return GateData(state, head_oid, tuple(reviews), tuple(threads), tuple(checks))


def _current_repository() -> str:
    payload = _run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    repository = payload.get("nameWithOwner")
    if not isinstance(repository, str) or _REPOSITORY.fullmatch(repository) is None:
        raise GitHubAccessError("current GitHub repository is unavailable")
    return repository


def _target(value: str, repository: str | None) -> tuple[str, str, int]:
    match = _PR_URL.fullmatch(value)
    if match is not None:
        owner, repo, number = match.groups()
        url_repository = f"{owner}/{repo}"
        if repository is not None and repository != url_repository:
            raise ValueError("pull-request URL and --repo refer to different repositories")
        return owner, repo, int(number)
    if not value.isdigit() or int(value) <= 0:
        raise ValueError("pull request must be a positive number or canonical GitHub PR URL")
    selected_repository = repository or _current_repository()
    if _REPOSITORY.fullmatch(selected_repository) is None:
        raise ValueError("--repo must use owner/name format")
    owner, repo = selected_repository.split("/", 1)
    return owner, repo, int(value)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Require a current clean Cursor Bugbot review before merging a pull request."
    )
    parser.add_argument("pull_request", help="PR number or canonical GitHub pull-request URL")
    parser.add_argument("--repo", help="Repository in owner/name form when a PR number is used")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        owner, repo, number = _target(args.pull_request, args.repo)
        summary = evaluate_gate(fetch_gate_data(owner, repo, number))
    except ValueError as exc:
        print(f"Bugbot merge gate input error: {exc}", file=sys.stderr)
        return 2
    except GateRejected as exc:
        print(f"Bugbot merge gate blocked: {exc}", file=sys.stderr)
        return 3
    except GitHubAccessError as exc:
        print(f"Bugbot merge gate unavailable: {exc}", file=sys.stderr)
        return 4

    print(
        "Bugbot merge gate passed: "
        f"PR #{number}, head {summary.head_oid[:12]}, "
        f"current reviews {summary.bugbot_reviews_for_head}, "
        f"successful checks {summary.bugbot_checks_for_head}, "
        f"resolved Cursor threads {summary.cursor_threads}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
