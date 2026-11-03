#!/usr/bin/env sh
cd "$(dirname "$0")/.." || exit 1
git pull --rebase
git log --oneline -10
tail -20 PROGRESS.md
