"""src/tts_piper.py — offline TTS engine (Piper primary, pyttsx3 fallback)."""
from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_EXE = "piper.exe" if sys.platform == "win32" else "piper"


@dataclass
class TTSConfig:
    piper_binary: str | None = None  # explicit override; else PATH / bin/piper/
    model_path: str = "models/piper/en_US-lessac-medium.onnx"
    fallback_rate: int = 175


class TTSEngine:
    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._lock = threading.Lock()
        self._piper_path = self._resolve_piper()
        # Marker only: pyttsx3 engines are created per call, inside the speaking
        # thread (SAPI5 on Windows breaks if init and runAndWait are on different threads).
        self._fallback = None
        try:
            import pyttsx3  # noqa: F401

            self._fallback = "pyttsx3"
        except Exception:
            log.warning("pyttsx3 not available; fallback voice disabled")
        if not self._piper_path:
            log.warning("Piper not found; using pyttsx3 fallback. "
                        "Run: python scripts/download_models.py")

    # ── Locating Piper ──────────────────────────────────────────────────────

    def _resolve_piper(self) -> str | None:
        cfg = self.config.piper_binary
        if cfg:
            p = pathlib.Path(cfg)
            if not p.is_absolute():
                p = REPO_ROOT / p  # relative paths are relative to the project, not the cwd
            if p.is_dir():
                p = p / _EXE
            if p.is_file():
                return str(p)
            log.warning("Configured piper_binary not found: %s", p)
        which = shutil.which("piper")
        if which:
            return which
        for cand in (REPO_ROOT / "bin" / "piper" / _EXE, REPO_ROOT / "bin" / _EXE):
            if cand.is_file():
                return str(cand)
        return None

    def _model(self) -> pathlib.Path:
        p = pathlib.Path(self.config.model_path)
        return p if p.is_absolute() else (REPO_ROOT / p)

    # ── Speaking ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        with self._lock:  # serialize; no overlapping playback
            if self._piper_path and self._speak_piper(text):
                return
            if self._fallback is not None:
                self._speak_fallback(text)
            else:
                log.debug("TTS skipped (no engine): %s", text[:60])

    def _speak_piper(self, text: str) -> bool:
        """Return True if Piper spoke; False so the caller can use the fallback."""
        model = self._model()
        if not model.is_file() or not pathlib.Path(str(model) + ".json").is_file():
            log.error("Piper voice missing (need .onnx and .onnx.json): %s", model)
            return False
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            cmd = [self._piper_path, "--model", str(model), "--output_file", wav_path]
            kwargs: dict = {"cwd": str(pathlib.Path(self._piper_path).parent)}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            try:
                proc = subprocess.run(
                    cmd, input=text.encode("utf-8"),
                    capture_output=True, check=False, timeout=30, **kwargs,
                )
            except subprocess.TimeoutExpired:
                log.warning("Piper timed out; skipping utterance")
                return False
            except OSError:
                log.exception("Could not start Piper")
                return False
            if proc.returncode != 0 or os.path.getsize(wav_path) == 0:
                log.error("Piper failed rc=%s stderr=%s", proc.returncode, proc.stderr[-300:])
                return False
            try:
                self._play_wav_file(wav_path)
            except Exception:
                log.exception("WAV playback failed")
                return False
            return True
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    @staticmethod
    def _play_wav_file(path: str) -> None:
        import sounddevice as sd
        import soundfile as sf

        data, fs = sf.read(path, dtype="float32")
        sd.play(data, fs)
        sd.wait()

    def _speak_fallback(self, text: str) -> None:
        try:
            import pyttsx3

            eng = pyttsx3.init()
            eng.setProperty("rate", self.config.fallback_rate)
            eng.say(text)
            eng.runAndWait()
            eng.stop()
        except Exception:
            log.exception("pyttsx3 fallback failed")

    def speak_async(self, text: str) -> threading.Thread:
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
        return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    eng = TTSEngine()
    print("piper:", eng._piper_path or "NOT FOUND", "| fallback:", eng._fallback)
    eng.speak("Hello! I am Desktop Buddy.")
