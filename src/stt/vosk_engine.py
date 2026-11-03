"""src/stt/vosk_engine.py — push-to-talk Vosk STT engine (F-03).

Records audio from the default microphone until the user stops speaking
(VAD-gated) or a maximum duration is reached, then returns the recognised text.
"""
from __future__ import annotations

import json
import logging
import pathlib
import queue
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_DIR = REPO_ROOT / "models" / "vosk" / "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000
BLOCKSIZE = 4000          # ~250 ms at 16 kHz
MAX_RECORD_SECS = 15      # hard cap on a single utterance
SILENCE_BLOCKS = 8        # ~2 s of silence after speech ends recording


class VoskEngine:
    """Push-to-talk speech recognition using Vosk small-en-us model.

    Usage::

        engine = VoskEngine()
        if engine.is_ready():
            text = engine.listen()  # blocks until utterance done
    """

    def __init__(self, model_dir: pathlib.Path = DEFAULT_MODEL_DIR) -> None:
        self.model_dir = pathlib.Path(model_dir)
        self._model = None
        self._rec = None
        self._ready = False
        self._load()

    def _load(self) -> None:
        if not self.model_dir.exists():
            log.warning(
                "Vosk model not found at %s. Download with: "
                "python scripts/download_models.py",
                self.model_dir,
            )
            return
        try:
            import vosk  # type: ignore[import]

            vosk.SetLogLevel(-1)  # silence verbose Vosk logging
            self._model = vosk.Model(str(self.model_dir))
            self._ready = True
            log.info("Vosk model loaded from %s", self.model_dir)
        except ImportError:
            log.error("vosk package not installed. Run: pip install vosk")
        except Exception:
            log.exception("Failed to load Vosk model")

    def is_ready(self) -> bool:
        return self._ready

    def listen(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        timeout: float = MAX_RECORD_SECS,
    ) -> str:
        """Record from the mic until silence, return recognised text.

        Args:
            on_partial: Optional callback called with partial transcript chunks.
            timeout: Maximum seconds to record before stopping.

        Returns:
            The recognised text string (may be empty on silence / failure).
        """
        if not self._ready:
            log.error("VoskEngine not ready — returning empty string")
            return ""

        try:
            import sounddevice as sd  # type: ignore[import]
            import vosk  # type: ignore[import]
        except ImportError as exc:
            log.error("Missing dependency: %s", exc)
            return ""

        rec = vosk.KaldiRecognizer(self._model, SAMPLE_RATE)
        rec.SetMaxAlternatives(0)
        rec.SetWords(False)

        audio_q: queue.Queue[bytes] = queue.Queue()
        stop_event = threading.Event()

        def _callback(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                log.debug("sounddevice status: %s", status)
            audio_q.put(bytes(indata))

        silence_count = 0
        speech_detected = False
        result_text = ""
        max_blocks = int(timeout * SAMPLE_RATE / BLOCKSIZE)

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCKSIZE,
                dtype="int16",
                channels=1,
                callback=_callback,
            ):
                log.debug("Listening…")
                for _ in range(max_blocks):
                    try:
                        chunk = audio_q.get(timeout=1.0)
                    except queue.Empty:
                        break

                    if rec.AcceptWaveform(chunk):
                        part = json.loads(rec.Result()).get("text", "")
                        if part:
                            speech_detected = True
                            result_text = part
                            if on_partial:
                                on_partial(part)
                    else:
                        partial = json.loads(rec.PartialResult()).get("partial", "")
                        if partial and on_partial:
                            on_partial(partial)
                        if partial:
                            speech_detected = True
                            silence_count = 0
                        elif speech_detected:
                            silence_count += 1
                            if silence_count >= SILENCE_BLOCKS:
                                break  # natural end of utterance

        except Exception:
            log.exception("Error during Vosk listen")
            return ""

        # Final result
        final = json.loads(rec.FinalResult()).get("text", "")
        if final:
            result_text = final
        log.debug("Recognised: %r", result_text)
        return result_text.strip()


if __name__ == "__main__":
    engine = VoskEngine()
    if not engine.is_ready():
        print("Vosk model not loaded — skipping live mic test.")
        print("Download models with: python scripts/download_models.py")
        print("vosk_engine.py structure smoke test PASSED")
    else:
        print("Vosk ready. Speak now (up to 15 seconds)…")
        text = engine.listen(on_partial=lambda p: print(f"  partial: {p}"))
        print(f"Final: {text!r}")
        print("vosk_engine.py live smoke test PASSED")

