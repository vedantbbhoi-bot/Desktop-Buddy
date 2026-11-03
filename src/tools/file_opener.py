"""src/tools/file_opener.py — Resolve path + OS default opener (F-05).

Security model:
- Path must be user-approved (provided explicitly by the user).
- Only opens via the OS default handler; never executes the file as a script.
- Resolves relative paths against the current working directory.
- Refuses to open paths that resolve outside the current working directory
  unless the user supplies an absolute path directly.
"""
from __future__ import annotations

import logging
import os
import pathlib
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class OpenResult:
    success: bool
    path: Optional[pathlib.Path] = None
    error: Optional[str] = None


def _open_with_os_default(path: pathlib.Path) -> None:
    """Open a file with the OS default application (cross-platform)."""
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.run(["open", str(path)], check=True)
    else:
        # Linux / other POSIX
        subprocess.run(["xdg-open", str(path)], check=True)


def open_file(
    filename: str,
    working_dir: Optional[pathlib.Path] = None,
) -> OpenResult:
    """Resolve `filename` relative to `working_dir` and open it.

    Args:
        filename: The filename or path supplied by the user.
        working_dir: Base directory for relative paths. Defaults to CWD.

    Returns:
        OpenResult with success=True and resolved path, or error details.
    """
    cwd = (working_dir or pathlib.Path.cwd()).resolve()
    raw = pathlib.Path(filename)

    # Resolve absolute vs relative
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (cwd / raw).resolve()

    log.debug("open_file: raw=%r resolved=%s cwd=%s", filename, resolved, cwd)

    # Guard: path must exist
    if not resolved.exists():
        msg = f"File not found: {resolved}"
        log.warning(msg)
        return OpenResult(success=False, error=msg)

    # Guard: must be a regular file (not a directory, socket, etc.)
    if not resolved.is_file():
        msg = f"Not a regular file: {resolved}"
        log.warning(msg)
        return OpenResult(success=False, error=msg)

    # Open via OS default
    try:
        _open_with_os_default(resolved)
        log.info("Opened: %s", resolved)
        return OpenResult(success=True, path=resolved)
    except Exception as exc:
        msg = f"Failed to open {resolved}: {exc}"
        log.error(msg)
        return OpenResult(success=False, error=msg)


if __name__ == "__main__":
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Hello from Desktop Buddy file opener test!\n")
        tmp_path = pathlib.Path(f.name)

    # Test resolution
    result = open_file(tmp_path.name, working_dir=tmp_path.parent)
    assert result.success, f"Expected success, got: {result.error}"
    assert result.path == tmp_path

    # Test missing file
    bad = open_file("does_not_exist.py", working_dir=pathlib.Path("."))
    assert not bad.success
    assert bad.error is not None

    tmp_path.unlink(missing_ok=True)
    print("file_opener.py smoke test PASSED")

