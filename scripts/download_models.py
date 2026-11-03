"""Download Piper binary, Piper voice, and Vosk model into bin/ and models/.

Run from the project root:  python scripts/download_models.py
Safe to re-run: existing files are skipped.
"""
from __future__ import annotations

import platform
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPER_VERSION = "2023.11.14-2"
PIPER_BASE = f"https://github.com/rhasspy/piper/releases/download/{PIPER_VERSION}"
VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
VOICE_NAME = "en_US-lessac-medium"
VOSK_NAME = "vosk-model-small-en-us-0.15"
VOSK_URL = f"https://alphacephei.com/vosk/models/{VOSK_NAME}.zip"


def piper_archive() -> str:
    system, machine = platform.system(), platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if system == "Windows":
        return "piper_windows_amd64.zip"
    if system == "Darwin":
        return "piper_macos_aarch64.tar.gz" if arm else "piper_macos_x64.tar.gz"
    return "piper_linux_aarch64.tar.gz" if arm else "piper_linux_x86_64.tar.gz"


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"skip   {dest.relative_to(ROOT)}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"get    {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def extract(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    else:
        with tarfile.open(archive) as t:
            t.extractall(target)


def main() -> int:
    bin_dir, models = ROOT / "bin", ROOT / "models"
    exe = "piper.exe" if platform.system() == "Windows" else "piper"
    piper_exe = bin_dir / "piper" / exe

    if not piper_exe.exists():
        name = piper_archive()
        archive = bin_dir / name
        download(f"{PIPER_BASE}/{name}", archive)
        extract(archive, bin_dir)  # archive contains a top-level "piper/" folder
        archive.unlink()
        if piper_exe.suffix == "" and piper_exe.exists():
            piper_exe.chmod(0o755)
    else:
        print(f"skip   {piper_exe.relative_to(ROOT)}")

    voice_dir = models / "piper"
    for ext in (".onnx", ".onnx.json"):
        download(f"{VOICE_BASE}/{VOICE_NAME}{ext}", voice_dir / f"{VOICE_NAME}{ext}")

    vosk_dir = models / "vosk" / VOSK_NAME
    if not vosk_dir.exists():
        archive = models / "vosk" / f"{VOSK_NAME}.zip"
        download(VOSK_URL, archive)
        extract(archive, models / "vosk")
        archive.unlink()
    else:
        print(f"skip   {vosk_dir.relative_to(ROOT)}")

    print("\nDone. Set in config.json:")
    print(f'  "tts": {{"piper_binary": "{piper_exe.relative_to(ROOT).as_posix()}"}}')
    ok = piper_exe.exists() and (voice_dir / f"{VOICE_NAME}.onnx").exists()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
