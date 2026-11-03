The previous turn was interrupted (token cutoff or agent termination).

1. Read PROGRESS.md in full.
2. Run `git pull --rebase` and `git log --oneline -10`.
3. Identify the last successfully pushed file from the log.
4. If the working tree has uncommitted changes, run:
   python scripts/auto_push.py --file <changed_path> --message "wip: recover <name>"
   If that push fails, leave the file untouched and report the failure.
5. State the next single file to write, per Prompt 2. Do not write more than
   one file this turn.