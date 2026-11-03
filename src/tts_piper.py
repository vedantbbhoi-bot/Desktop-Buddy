"""src/tts_piper.py — offline TTS engine (Piper primary, pyttsx3 fallback)."""
import io
import logging
import pathlib
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


@dataclass
class TTSConfig:
    piper_binary: Optional[str] = None  # explicit override; else shutil.which / bin/piper
    model_path: str = "models/piper/en_US-lessac-medium.onnx"
    fallback_rate: int = 175


class TTSEngine:
    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._lock = threading.Lock()
        self._piper_path = self._resolve_piper()
        self._fallback = None
        if not self._piper_path:
            try:
                import pyttsx3
                self._fallback = pyttsx3.init()
                self._fallback.setProperty("rate", self.config.fallback_rate)
                log.warning("Piper not found; using pyttsx3 fallback")
            except Exception:
                log.exception("pyttsx3 fallback unavailable; TTS disabled")

    def _resolve_piper(self) -> Optional[str]:
        if self.config.piper_binary:
            p = pathlib.Path(self.config.piper_binary)
            return str(p) if p.is_file() else None
        which = shutil.which("piper")
        if which:
            return which
        local = REPO_ROOT / "bin" / "piper"
        return str(local) if local.is_file() else None

    def _model(self) -> pathlib.Path:
        p = pathlib.Path(self.config.model_path)
        return p if p.is_absolute() else (REPO_ROOT / p)

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        with self._lock:  # serialize; drop overlapping playback
            if self._piper_path:
                self._speak_piper(text)
            elif self._fallback is not None:
                self._fallback.say(text)
                self._fallback.runAndWait()
            else:
                log.debug("TTS skipped (no engine): %s", text[:60])

    def _speak_piper(self, text: str) -> None:
        model = self._model()
        if not model.is_file():
            log.error("Piper model missing: %s", model)
            return
        cmd = [self._piper_path, "--model", str(model), "--output_file", "-"]
        try:
            proc = subprocess.run(
                cmd, input=text.encode("utf-8"),
                capture_output=True, check=False, timeout=30,
            )
        except subprocess.TimeoutExpired:
            log.warning("Piper timed out; skipping utterance")
            return
        if proc.returncode != 0 or not proc.stdout:
            log.error("Piper failed rc=%s stderr=%s", proc.returncode, proc.stderr[-200:])
            return
        try:
            self._play_wav_bytes(proc.stdout)
        except Exception:
            log.exception("WAV playback failed")

    @staticmethod
    def _play_wav_bytes(wav: bytes) -> None:
        import soundfile as sf
        import sounddevice as sd
        data, fs = sf.read(io.BytesIO(wav), dtype="float32")
        sd.play(data, fs)
        sd.wait()

    def speak_async(self, text: str) -> threading.Thread:
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()
        return t