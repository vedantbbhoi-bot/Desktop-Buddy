"""src/tools/code_checker.py — Static analysis: py_compile + ruff JSON (F-06).

Runs two objective checks on a Python file:
1. py_compile — catches syntax errors.
2. ruff check --output-format json — catches lint issues.

Returns structured results that the LLM prompt (Prompt 3) can digest.
"""
from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class LintIssue:
    code: str
    message: str
    line: int
    col: int
    filename: str


@dataclass
class CheckResult:
    file_path: pathlib.Path
    compile_ok: bool
    compile_error: Optional[str]          # stderr from py_compile, or None
    lint_issues: list[LintIssue] = field(default_factory=list)
    lint_error: Optional[str] = None      # if ruff itself failed to run

    @property
    def all_clear(self) -> bool:
        return self.compile_ok and not self.lint_issues

    def compile_result_str(self) -> str:
        return "OK" if self.compile_ok else (self.compile_error or "FAILED")

    def lint_result_str(self) -> str:
        """Compact human-readable summary of lint issues."""
        if self.lint_error:
            return f"ruff error: {self.lint_error}"
        if not self.lint_issues:
            return "clean"
        lines = []
        for issue in self.lint_issues[:10]:  # cap at 10 for LLM context
            lines.append(f"  L{issue.line}: [{issue.code}] {issue.message}")
        return "\n".join(lines)


def _run_py_compile(file_path: pathlib.Path) -> tuple[bool, Optional[str]]:
    """Return (ok, error_message_or_None)."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        return True, None
    # py_compile writes to stderr
    err = (result.stderr or result.stdout or "compile error").strip()
    return False, err


def _run_ruff(file_path: pathlib.Path) -> tuple[list[LintIssue], Optional[str]]:
    """Return (issues, error_or_None)."""
    import shutil

    ruff_bin = shutil.which("ruff")
    if not ruff_bin:
        log.warning("ruff not found on PATH — lint check skipped")
        return [], "ruff not installed"

    result = subprocess.run(
        [ruff_bin, "check", "--output-format", "json", str(file_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )

    # ruff exits 1 when there are issues (not an error), 2 on internal error
    if result.returncode == 2:
        return [], f"ruff internal error: {result.stderr.strip()[:200]}"

    raw = (result.stdout or "").strip()
    if not raw:
        return [], None

    try:
        findings = json.loads(raw)
    except json.JSONDecodeError:
        return [], f"ruff JSON parse error: {raw[:100]}"

    issues = []
    for f in findings:
        loc = f.get("location", {})
        issues.append(
            LintIssue(
                code=f.get("code", "?"),
                message=f.get("message", ""),
                line=loc.get("row", 0),
                col=loc.get("column", 0),
                filename=f.get("filename", str(file_path)),
            )
        )
    return issues, None


def check_file(file_path: str | pathlib.Path) -> CheckResult:
    """Run py_compile and ruff on `file_path`.

    Args:
        file_path: Path to the Python file to analyse.

    Returns:
        CheckResult with compile and lint findings.
    """
    path = pathlib.Path(file_path).resolve()
    if not path.exists():
        return CheckResult(
            file_path=path,
            compile_ok=False,
            compile_error=f"File not found: {path}",
        )
    if path.suffix not in {".py", ".pyw"}:
        log.warning("check_file called on non-Python file: %s", path)

    compile_ok, compile_err = _run_py_compile(path)
    issues, lint_err = _run_ruff(path)

    result = CheckResult(
        file_path=path,
        compile_ok=compile_ok,
        compile_error=compile_err,
        lint_issues=issues,
        lint_error=lint_err,
    )
    log.info(
        "check_file %s: compile=%s issues=%d",
        path.name, "ok" if compile_ok else "FAIL", len(issues),
    )
    return result


if __name__ == "__main__":
    import tempfile

    # Test with a file that has a known lint issue
    bad_code = "x=1\ny=2\nprint( x+y )\n"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(bad_code)
        tmp = pathlib.Path(f.name)

    res = check_file(tmp)
    print(f"compile: {res.compile_result_str()}")
    print(f"lint:    {res.lint_result_str()}")
    assert res.compile_ok, "Expected clean compile"
    tmp.unlink(missing_ok=True)

    # Test with a syntax error
    broken = "def foo(:\n    pass\n"
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(broken)
        tmp2 = pathlib.Path(f.name)

    res2 = check_file(tmp2)
    assert not res2.compile_ok, "Expected compile failure"
    print(f"compile error detected: {res2.compile_error[:60]!r}")
    tmp2.unlink(missing_ok=True)

    print("code_checker.py smoke test PASSED")

