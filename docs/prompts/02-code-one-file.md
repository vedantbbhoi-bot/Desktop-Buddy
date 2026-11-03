Task: Create or update exactly ONE file for Desktop Buddy.

Target file: {{FILE_PATH}}
Purpose: {{ONE_SENTENCE_PURPOSE}}
Already pushed dependencies: {{LIST_OF_ALREADY_PUSHED_FILES}}
Project root: {{PROJECT_ROOT}}

Requirements:
- The file must import cleanly given the dependencies above.
- Include a minimal `if __name__ == "__main__":` smoke check for executable
  files, or a `pytest`-style test function for modules.
- No hardcoded absolute paths. Use pathlib and environment variables.
- UI files use PySide6 and assume a frameless, always-on-top window context.
- Git operations, if any, use subprocess with a list of args; never shell=True.

After writing the file:
1. Run the smoke check or relevant test. If it fails, fix and re-run.
2. On success, run:
   python scripts/auto_push.py --file {{FILE_PATH}} --message "feat(<scope>): {{PURPOSE}}"
3. STOP. Do not proceed to another file.