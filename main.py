"""Desktop Buddy entry point.

!! ASSUMPTIONS: I have not seen src/pet_window.py, llm_client.py, stt_vosk.py or
!! tts_piper.py. The class/method names marked ASSUMED below must be matched to
!! your real code. Everything else (config loading, threading, wiring) is generic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent


def load_config() -> dict:
    cfg = ROOT / "config.json"
    if not cfg.exists():
        cfg = ROOT / "config.example.json"
    return json.loads(cfg.read_text(encoding="utf-8"))


class ChatWorker(QObject):
    """Runs LLM + TTS off the UI thread so the pet never freezes."""

    reply_ready = Signal(str)

    def __init__(self, llm, tts):
        super().__init__()
        self.llm, self.tts = llm, tts

    def handle(self, text: str) -> None:
        try:
            reply = self.llm.chat(text)  # ASSUMED: LLMClient.chat(str) -> str
        except Exception as exc:  # Ollama not running, timeout, etc.
            reply = f"Sorry, my brain is offline ({exc.__class__.__name__})."
        self.reply_ready.emit(reply)
        try:
            self.tts.speak(reply)  # ASSUMED: PiperTTS.speak(str)
        except Exception as exc:
            print(f"[tts] failed: {exc}", file=sys.stderr)


def main() -> int:
    cfg = load_config()
    app = QApplication(sys.argv)

    # ASSUMED names -- adjust to match your modules:
    from src.llm_client import LLMClient
    from src.pet_window import PetWindow
    from src.tts_piper import PiperTTS

    llm = LLMClient(**cfg["llm"])
    tts = PiperTTS(cfg["tts"])
    window = PetWindow(cfg)

    thread = QThread()
    worker = ChatWorker(llm, tts)
    worker.moveToThread(thread)
    thread.start()

    # ASSUMED: window emits user_text(str) and has show_bubble(str)
    window.user_text.connect(worker.handle)
    worker.reply_ready.connect(window.show_bubble)

    # Optional push-to-talk (ASSUMED: STT class with a text_ready signal)
    try:
        from src.stt_vosk import VoskSTT

        stt = VoskSTT(cfg["stt"])
        stt.text_ready.connect(worker.handle)
        window.ptt_pressed.connect(stt.start)
        window.ptt_released.connect(stt.stop)
    except Exception as exc:
        print(f"[stt] disabled: {exc}", file=sys.stderr)

    window.show()
    code = app.exec()
    thread.quit()
    thread.wait()
    return code


if __name__ == "__main__":
    sys.exit(main())
