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
import sys
from concurrent.futures import ThreadPoolExecutor
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
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="buddy")  # one job at a time

    def reply_to(text: str) -> None:
        try:
            reply = core.router.handle(text)
        except Exception:
            log.exception("Router failed")
            window.state_changed.emit("confused")
            reply = "Oops, something went wrong. Check the terminal for details."
        window.bubble_requested.emit(reply)

    def on_user_text(text: str) -> None:
        pool.submit(reply_to, text)

    def listen_job() -> None:
        if not core.stt.is_ready():
            window.bubble_requested.emit("My voice model isn't loaded. Run scripts/download_models.py")
            return
        window.state_changed.emit("listening")
        text = core.stt.listen(on_partial=lambda p: window.bubble_requested.emit(p))
        if not text:
            window.state_changed.emit("idle")
            window.bubble_requested.emit("I didn't hear anything.")
            return
        reply_to(text)

    window.user_text.connect(on_user_text)
    window.talk_requested.connect(lambda: pool.submit(listen_job))
    window.quit_requested.connect(app.quit)

    def cleanup() -> None:
        pool.shutdown(wait=False, cancel_futures=True)
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
