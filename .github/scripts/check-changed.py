#!/usr/bin/env python3
"""Print 'true' if any file changed between <base> and <head> is NOT matched
by a `.dockerignore` pattern, otherwise 'false'.

Usage:
    check-changed.py [BASE [HEAD]]

Defaults: BASE=HEAD~1, HEAD=HEAD.

In CI this is called with BASE=${{ github.event.before }} (the tip of the
branch BEFORE this push). That way a single push that lands several commits
is treated as one diff — relevant for the initial import of a repo, where
HEAD~1 is one of the import's own commits.

A BASE that doesn't exist or is the all-zeros sha (GitHub's sentinel for
"no previous commit", e.g. first push to a brand-new branch) prints 'true':
no prior state to compare against, treat everything as new.

Pattern syntax: a small but practical subset of Docker's .dockerignore:
- comments / blank lines are ignored
- a leading `!` negates a previous match (re-includes)
- a trailing `/` is stripped (treat as the dir itself + anything under it)
- `*` and `?` are fnmatch glob metas
- otherwise the pattern is matched against the path AND any parent dir AND
  the basename — Docker's "match anywhere" semantics
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
import sys


def load_patterns(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out


def matches_pattern(path: str, raw: str) -> bool:
    pat = raw.rstrip("/")
    if fnmatch.fnmatchcase(path, pat):
        return True
    if fnmatch.fnmatchcase(path, pat + "/*"):
        return True
    if "/" not in pat and fnmatch.fnmatchcase(os.path.basename(path), pat):
        return True
    parts = path.split("/")
    for i in range(1, len(parts)):
        prefix = "/".join(parts[:i])
        if fnmatch.fnmatchcase(prefix, pat):
            return True
    return False


def is_ignored(path: str, patterns: list[str]) -> bool:
    ignored = False
    for p in patterns:
        if p.startswith("!"):
            if matches_pattern(path, p[1:]):
                ignored = False
        else:
            if matches_pattern(path, p):
                ignored = True
    return ignored


def first_push(base: str) -> bool:
    """True when `base` is the all-zeros sha or doesn't resolve to a commit."""
    if base.replace("0", "") == "":
        return True
    return subprocess.run(
        ["git", "rev-parse", "--verify", base + "^{commit}"],
        capture_output=True,
    ).returncode != 0


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"

    if first_push(base):
        print("true")
        sys.stderr.write(f"base {base!r} has no prior state — treating as buildable\n")
        return 0

    diff = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        capture_output=True, text=True, check=True,
    )
    changed = [l for l in diff.stdout.splitlines() if l]
    patterns = load_patterns(".dockerignore")
    relevant = [c for c in changed if not is_ignored(c, patterns)]
    print("true" if relevant else "false")
    if relevant:
        sys.stderr.write("buildable changes:\n  " + "\n  ".join(relevant) + "\n")
    else:
        sys.stderr.write(
            f"no buildable changes (changed: {changed or '[none]'}, "
            "all filtered by .dockerignore)\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
