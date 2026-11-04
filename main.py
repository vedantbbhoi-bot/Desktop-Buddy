"""Desktop Buddy entry point.

    python main.py          # desktop pet window
    python main.py --cli    # text chat in the terminal (no window; good for testing)

Click the pet to talk (push-to-talk), drag it to move it, right-click for the menu.
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import pathlib
import queue
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent
log = logging.getLogger("desktop_buddy")


@dataclass
class Core:
    """Everything except the UI."""
    router: object
    stt: object
    tts: object
    store: object
    ollama: object


class Worker:
    """Runs jobs one at a time on a daemon thread.

    Daemon matters: when the user clicks Quit while the model is still answering, the
    process must exit right away instead of waiting for the slow job to finish.
    """

    def __init__(self, closing: threading.Event) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._closing = closing
        threading.Thread(target=self._run, name="buddy-worker", daemon=True).start()

    def submit(self, fn: Callable, *args) -> None:
        self._jobs.put((fn, args))

    def _run(self) -> None:
        while True:
            fn, args = self._jobs.get()
            if self._closing.is_set():
                return
            try:
                fn(*args)
            except Exception:
                if not self._closing.is_set():  # errors during shutdown are expected noise
                    log.exception("Background job failed")


def build_core(
    on_state: Optional[Callable[[str], None]] = None,
    working_dir: Optional[pathlib.Path] = None,
    db_path: Optional[pathlib.Path] = None,
) -> Core:
    from src.config import CONFIG
    from src.intent_router import IntentRouter
    from src.llm.ollama_client import OllamaClient
    from src.memory.context_store import DB_PATH, ContextStore
    from src.stt.vosk_engine import VoskEngine
    from src.tts_piper import TTSConfig, TTSEngine

    ollama = OllamaClient(**dataclasses.asdict(CONFIG.llm))
    tts = TTSEngine(TTSConfig(**dataclasses.asdict(CONFIG.tts)))
    store = ContextStore(db_path or DB_PATH)

    if on_state is not None:  # show the "talking" animation while the voice speaks
        _orig_speak = tts.speak

        def _speak_with_state(text: str) -> None:
            on_state("talking")
            try:
                _orig_speak(text)
            finally:
                on_state("idle")

        tts.speak = _speak_with_state  # speak_async() looks speak up on the instance

    model_dir = pathlib.Path(CONFIG.stt.model_dir)
    if not model_dir.is_absolute():
        model_dir = REPO_ROOT / model_dir
    stt = VoskEngine(model_dir)

    router = IntentRouter(
        working_dir=(working_dir or pathlib.Path.cwd()).resolve(),
        ollama_client=ollama,
        tts_engine=tts,
        store=store,
        on_state_change=on_state,
    )
    return Core(router=router, stt=stt, tts=tts, store=store, ollama=ollama)


# ── Terminal mode ──────────────────────────────────────────────────────────

def run_cli(show_states: bool = False) -> int:
    on_state = (lambda s: print(f"   [state: {s}]")) if show_states else None
    core = build_core(on_state=on_state)
    print("Desktop Buddy (terminal mode).  /voice = use microphone, /quit = exit")
    if not core.ollama.is_available():
        print("Note: Ollama is not running, so replies will be basic. Start it with: ollama serve")
    try:
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ("/quit", "/exit"):
                break
            if line == "/voice":
                if not core.stt.is_ready():
                    print("buddy> Voice model not loaded. Run: python scripts/download_models.py")
                    continue
                print("   listening…")
                line = core.stt.listen(on_partial=lambda p: print(f"   … {p}"))
                print(f"   heard: {line!r}")
                if not line:
                    continue
            print("buddy>", core.router.handle(line))
    finally:
        core.store.close()
    return 0


# ── Window mode ────────────────────────────────────────────────────────────

def run_gui() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed. Run: python -m pip install -e .")
        return 1

    from src.config import CONFIG
    from src.pet_window import PetWindow

    app = QApplication(sys.argv)
    window = PetWindow(CONFIG)
    # IntentRouter calls this from a worker thread; the signal makes it thread-safe.
    core = build_core(on_state=window.state_changed.emit)
    closing = threading.Event()  # set when the app is quitting
    worker = Worker(closing)     # one job at a time

    def reply_to(text: str) -> None:
        try:
            reply = core.router.handle(text)
        except Exception:
            if closing.is_set():
                return  # app is quitting; nobody is waiting for this answer
            log.exception("Router failed")
            window.state_changed.emit("confused")
            reply = "Oops, something went wrong. Check the terminal for details."
        if not closing.is_set():
            window.bubble_requested.emit(reply)

    def on_user_text(text: str) -> None:
        worker.submit(reply_to, text)

    def listen_job() -> None:
        if not core.stt.is_ready():
            window.bubble_requested.emit("My voice model isn't loaded. Run scripts/download_models.py")
            return
        window.state_changed.emit("listening")
        text = core.stt.listen(
            on_partial=lambda p: None if closing.is_set() else window.bubble_requested.emit(p)
        )
        if closing.is_set():
            return
        if not text:
            window.state_changed.emit("idle")
            window.bubble_requested.emit("I didn't hear anything.")
            return
        reply_to(text)

    window.user_text.connect(on_user_text)
    window.talk_requested.connect(lambda: worker.submit(listen_job))
    window.quit_requested.connect(app.quit)

    def cleanup() -> None:
        closing.set()  # tell background work to stay quiet, then close the database
        core.store.close()

    app.aboutToQuit.connect(cleanup)
    window.show()
    QTimer.singleShot(600, lambda: window.show_bubble("Hi! Click me to talk. Right-click for more."))
    return app.exec()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Desktop Buddy")
    ap.add_argument("--cli", action="store_true", help="terminal chat instead of the pet window")
    ap.add_argument("--debug", action="store_true", help="verbose logging (and states in --cli)")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return run_cli(show_states=args.debug) if args.cli else run_gui()


if __name__ == "__main__":
    sys.exit(main())
