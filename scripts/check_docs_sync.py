"""Warn when staged source changes have no staged document beside them.

Rule 3 of [docs/contributing/DOCUMENTATION.md] — *code and docs change together* — is
written for people, and a written rule is only as good as the moment someone remembers
it. This script remembers it at commit time: it reads the staged paths, applies the
source -> document mapping from section 5 of that same document, and names the documents
that were not staged.

It **never blocks a commit**. The rule requires a document only when *behaviour* changes,
and no script can tell a behaviour change from a rename. So this reports candidates and
leaves the judgement where it belongs.

Two entry points, one body of logic:

    python scripts/check_docs_sync.py     # git pre-commit hook, and by hand
    python scripts/check_docs_sync.py --hook   # Claude Code PreToolUse hook (stdin JSON)

Install the git hook once per clone:

    git config core.hooksPath scripts/hooks
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The mapping in section 5 of docs/contributing/DOCUMENTATION.md, in executable form.
# When a row is added there, add it here in the same commit — this file is governed by
# the rule it enforces.
MAPPING: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "app/controllers/",
        (
            "docs/api/ENDPOINTS.md",
            "docs/api/OVERVIEW.md",
            "docs/requirements/FRS.md",
            "docs/manual/USER_MANUAL.md",
        ),
    ),
    ("app/schemas/", ("docs/api/ENDPOINTS.md", "docs/requirements/FRS.md")),
    ("app/models/", ("docs/design/ERD.md",)),
    ("app/services/instance_service.py", ("docs/business-rules/INSTANCE_LIFECYCLE.md",)),
    ("app/services/monitor_service.py", ("docs/business-rules/ALERTING.md",)),
    ("app/services/alert_service.py", ("docs/business-rules/ALERTING.md",)),
    (
        "app/services/client_service.py",
        ("docs/business-rules/COST.md", "docs/business-rules/SLA.md"),
    ),
    ("app/services/llm_service.py", ("docs/design/LLM_FEATURE.md",)),
    (
        "app/core/",
        (
            "docs/api/AUTHENTICATION.md",
            "docs/business-rules/AUTHORIZATION.md",
            "docs/api/ERRORS.md",
        ),
    ),
    ("app/database.py", ("docs/design/DATABASE.md", "docs/design/ARCHITECTURE.md")),
    ("app/pagination.py", ("docs/api/CONVENTIONS.md",)),
    (
        "app/config.py",
        (
            "docs/business-rules/README.md",
            "docs/design/ARCHITECTURE.md",
            "docs/operations/CONFIGURATION.md",
        ),
    ),
    ("app/seed.py", ("docs/demo/SEED_DATA.md", "docs/demo/ACCOUNTS.md")),
    (
        "app/main.py",
        (
            "docs/design/ARCHITECTURE.md",
            "docs/api/ERRORS.md",
            "docs/operations/DEPLOYMENT.md",
        ),
    ),
    ("tests/", ("docs/testing/FUNCTIONAL_TESTS.md", "docs/testing/TEST_CASES.md")),
)

# Sources whose change can show up in a Swagger capture. Whether it actually did is a
# judgement call, so this is reported as a reminder rather than a mapping hit.
SWAGGER_SOURCES = ("app/controllers/", "app/schemas/", "app/core/", "app/main.py", "app/seed.py")

CHANGELOG = "docs/changelog/CHANGELOG.md"
READING_ORDER = "docs/onboarding/READING_ORDER.md"
WALKTHROUGH = "docs/demo/WALKTHROUGH.md"
SCREENSHOTS = "docs/screenshots/"

DEF_LINE = re.compile(r"^[+-]\s*(async\s+def|def|class)\s+\w+")
GIT_COMMIT = re.compile(r"\bgit\b(?:\s+-{1,2}\S+)*\s+commit\b")


def git(*args: str) -> str:
    """Run a git command in the repository root and return its stdout."""
    result = subprocess.run(
        ("git", *args), cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else ""


def staged_paths() -> list[str]:
    return [line for line in git("diff", "--cached", "--name-only").splitlines() if line]


def signatures_moved() -> bool:
    """True when the staged diff adds or removes a function or class under app/."""
    diff = git("diff", "--cached", "-U0", "--", "app")
    return any(DEF_LINE.match(line) for line in diff.splitlines())


def report(paths: list[str]) -> list[str]:
    """Return the warning lines for these staged paths, empty when nothing is missing."""
    staged = set(paths)
    sources = [p for p in paths if p.startswith(("app/", "tests/"))]
    if not sources:
        return []

    lines: list[str] = []
    for source in sources:
        docs = [
            doc
            for prefix, targets in MAPPING
            if source.startswith(prefix)
            for doc in targets
        ]
        missing = [doc for doc in dict.fromkeys(docs) if doc not in staged]
        entry = []
        # Any one of the mapped documents staged means the author consulted the mapping;
        # which of them the change actually touches is their call, not this script's.
        if missing and len(missing) == len(set(docs)):
            entry.append(f"    -> {', '.join(missing)}")
        if source.startswith(SWAGGER_SOURCES) and not any(
            p.startswith(SCREENSHOTS) for p in staged
        ):
            entry.append(
                f"    -> {SCREENSHOTS}*.png — re-capture if a route, field, status code,"
                " error body or seed number changed"
            )
        if entry:
            lines.append(f"  {source}")
            lines.extend(entry)

    if any(p.startswith("app/") for p in sources):
        tail_start = len(lines)
        if CHANGELOG not in staged:
            lines.append(f"    {CHANGELOG} — one entry per change a reader would notice")
        if WALKTHROUGH not in staged:
            lines.append(f"    {WALKTHROUGH} — if a step or an expected number moved")
        if READING_ORDER not in staged and signatures_moved():
            lines.append(
                f"    {READING_ORDER} — a function or class was added, removed or renamed,"
                " and it cites line numbers"
            )
        if len(lines) > tail_start:
            lines[tail_start:tail_start] = ["", "  Whatever the change touched:"]
    return lines


def render(lines: list[str]) -> str:
    return "\n".join(
        [
            "docs-sync: staged source changes with no matching document staged.",
            "",
            *lines,
            "",
            "Rule 3 of docs/contributing/DOCUMENTATION.md: behaviour and the document",
            "describing it change in the same commit. Nothing to do if this change",
            "alters no behaviour. This is a reminder, not a gate — the commit proceeds.",
        ]
    )


def hook_command(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    return str(tool_input.get("command") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hook",
        action="store_true",
        help="Read a Claude Code PreToolUse payload on stdin and answer with hook JSON",
    )
    args = parser.parse_args()

    if args.hook:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0
        if not GIT_COMMIT.search(hook_command(payload)):
            return 0
        lines = report(staged_paths())
        if not lines:
            return 0
        message = render(lines)
        json.dump(
            {
                "systemMessage": message,
                "suppressOutput": True,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": message,
                },
            },
            sys.stdout,
        )
        return 0

    lines = report(staged_paths())
    if lines:
        print(render(lines), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
