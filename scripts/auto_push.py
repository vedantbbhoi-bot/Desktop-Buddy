#!/usr/bin/env python3
"""Idempotent per-file commit and push for Desktop Buddy.

Usage:
    python scripts/auto_push.py --file src/llm_client.py --message "feat(llm): ollama chat wrapper"
"""

import argparse
import datetime
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PROGRESS = REPO / "PROGRESS.md"
BRANCH = "main"


def run(cmd):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def already_committed(path: pathlib.Path) -> bool:
    """Return True if the file's current content already exists at HEAD."""
    rel = path.relative_to(REPO).as_posix()
    head = run(["git", "show", f"HEAD:{rel}"])
    if head.returncode != 0:
        return False
    return head.stdout == path.read_text(encoding="utf-8")


def append_progress(file_path: str, note: str) -> None:
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] {file_path} — {note}\n"
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(line)


def fail(file_path: str, reason: str, detail: str = "") -> int:
    append_progress(file_path, f"FAILED — {reason}")
    print(f"FAILED: {file_path} — {reason}", file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def auto_push(file_path: str, message: str) -> int:
    path = (REPO / file_path).resolve()
    if not path.exists():
        return fail(file_path, "file does not exist")

    if already_committed(path):
        print(f"SKIP: {file_path} already committed at HEAD")
        return 0

    pull = run(["git", "pull", "--rebase", "origin", BRANCH])
    if pull.returncode != 0:
        return fail(file_path, "git pull --rebase failed", pull.stderr)

    add = run(["git", "add", str(path)])
    if add.returncode != 0:
        return fail(file_path, "git add failed", add.stderr)

    commit = run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        return fail(file_path, "git commit failed", commit.stderr)

    last_err = ""
    for _ in range(3):
        push = run(["git", "push", "origin", f"HEAD:{BRANCH}"])
        if push.returncode == 0:
            append_progress(file_path, f"done | message: {message}")
            print(f"PUSHED: {file_path}")
            return 0
        last_err = push.stderr

    return fail(file_path, "git push failed after 3 attempts", last_err)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    return auto_push(args.file, args.message)


if __name__ == "__main__":
    raise SystemExit(main())