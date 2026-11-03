import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no real screen needed for tests


def test_core_small_talk_without_ollama(tmp_path, monkeypatch):
    import main

    core = main.build_core(working_dir=tmp_path, db_path=tmp_path / "ctx.db")
    states = []
    core.router._on_state = states.append
    monkeypatch.setattr(core.ollama, "is_available", lambda: False)
    monkeypatch.setattr(core.tts, "speak_async", lambda t: None)  # stay quiet in tests

    reply = core.router.handle("hello there")

    assert "Desktop Buddy" in reply
    assert states[0] == "thinking" and states[-1] == "idle"
    assert core.store.get_history(tmp_path)[-1]["role"] == "assistant"
    core.store.close()


def test_core_reads_model_dir_relative_to_project(tmp_path):
    import main

    core = main.build_core(working_dir=tmp_path, db_path=tmp_path / "ctx.db")
    assert str(main.REPO_ROOT) in str(core.stt.model_dir)
    core.store.close()


def test_pet_window_draws_every_state():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from src.config import AppConfig
    from src.pet_window import STATE_COLORS, PetWindow

    app = QApplication.instance() or QApplication([])
    win = PetWindow(AppConfig())
    win.show()
    for state in STATE_COLORS:
        win.state_changed.emit(state)
        app.processEvents()
        assert win.state == state
        image = win.grab().toImage()
        opaque = sum(1 for x in range(0, image.width(), 6) for y in range(0, image.height(), 6)
                     if image.pixelColor(x, y).alpha() > 0)
        assert opaque > 20, f"state {state!r} drew nothing"
    win.state_changed.emit("not-a-state")
    assert win.state == "idle"
    win.close()


def test_pet_window_signals():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from src.config import AppConfig
    from src.pet_window import PetWindow

    QApplication.instance() or QApplication([])
    win = PetWindow(AppConfig())
    got = []
    win.user_text.connect(got.append)
    win.user_text.emit("hi")
    win.bubble_requested.emit("hello")
    assert got == ["hi"]
    assert win._bubble.text() == "hello"
    win.close()
