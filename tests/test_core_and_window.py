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


def test_pet_window_loads_and_advances_sprite_frames():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from src.config import AppConfig
    from src.pet_window import PetWindow

    QApplication.instance() or QApplication([])
    win = PetWindow(AppConfig())

    assert len(win._sprite_frames["idle"]) == 10
    assert len(win._sprite_frames["celebrate"]) == 6
    first = win._current_sprite_frame(now=win._state_started)
    next_frame = win._current_sprite_frame(now=win._state_started + 0.13)
    assert first is not None and next_frame is not None
    assert first.cacheKey() != next_frame.cacheKey()
    assert first.pixelColor(0, 0).alpha() == 0
    win.close()


def test_typed_message_dialog_is_top_level_and_emits_text(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QInputDialog

    from src.config import AppConfig
    from src.pet_window import PetWindow

    app = QApplication.instance() or QApplication([])
    win = PetWindow(AppConfig())
    win.show()
    app.processEvents()
    submitted = []
    dialog_args = {}

    def fake_get_text(parent, title, label, *, flags):
        dialog_args.update(parent=parent, title=title, label=label, flags=flags)
        dialog_args["pet_hidden"] = not win.isVisible()
        return "check this task", True

    monkeypatch.setattr(QInputDialog, "getText", fake_get_text)
    win.user_text.connect(submitted.append)
    win._ask_text()

    assert dialog_args["parent"] is None
    assert dialog_args["flags"] & Qt.WindowStaysOnTopHint
    assert dialog_args["pet_hidden"]
    assert win.isVisible()
    assert submitted == ["check this task"]
    win.close()
