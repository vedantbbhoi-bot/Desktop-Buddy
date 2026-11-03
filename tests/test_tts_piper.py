import subprocess
import wave

import pytest

import src.tts_piper as tp


def _fake_voice(root):
    d = root / "models" / "piper"
    d.mkdir(parents=True)
    (d / "v.onnx").write_bytes(b"x")
    (d / "v.onnx.json").write_text("{}")
    return "models/piper/v.onnx"


def _fake_piper(root):
    d = root / "bin" / "piper"
    d.mkdir(parents=True)
    exe = d / tp._EXE
    exe.write_bytes(b"x")
    return exe


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tp.shutil, "which", lambda _n: None)
    return tmp_path


def test_finds_binary_in_bin_piper_dir(root):
    exe = _fake_piper(root)
    assert tp.TTSEngine()._piper_path == str(exe)


def test_relative_config_path_is_project_relative(root, monkeypatch, tmp_path_factory):
    exe = _fake_piper(root)
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    eng = tp.TTSEngine(tp.TTSConfig(piper_binary=f"bin/piper/{tp._EXE}"))
    assert eng._piper_path == str(exe)


def test_missing_binary_uses_fallback_not_crash(root, monkeypatch):
    spoken = []
    monkeypatch.setattr(tp.TTSEngine, "_speak_fallback", lambda self, t: spoken.append(t))
    eng = tp.TTSEngine()
    assert eng._piper_path is None
    eng.speak("hi")
    assert spoken == ["hi"] or eng._fallback is None


def test_piper_success_plays_wav(root, monkeypatch):
    _fake_piper(root)
    model = _fake_voice(root)
    played = []

    def fake_run(cmd, **kw):
        out = cmd[cmd.index("--output_file") + 1]
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(b"\x00\x00" * 100)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(tp.subprocess, "run", fake_run)
    monkeypatch.setattr(tp.TTSEngine, "_play_wav_file", staticmethod(lambda p: played.append(p)))
    eng = tp.TTSEngine(tp.TTSConfig(model_path=model))
    eng.speak("hello")
    assert len(played) == 1


def test_piper_failure_falls_back(root, monkeypatch):
    _fake_piper(root)
    model = _fake_voice(root)
    fb = []
    monkeypatch.setattr(tp.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, b"", b"boom"))
    monkeypatch.setattr(tp.TTSEngine, "_speak_fallback", lambda self, t: fb.append(t))
    eng = tp.TTSEngine(tp.TTSConfig(model_path=model))
    eng._fallback = "pyttsx3"
    eng.speak("hello")
    assert fb == ["hello"]


def test_missing_voice_falls_back(root, monkeypatch):
    _fake_piper(root)
    fb = []
    monkeypatch.setattr(tp.TTSEngine, "_speak_fallback", lambda self, t: fb.append(t))
    eng = tp.TTSEngine(tp.TTSConfig(model_path="models/piper/nope.onnx"))
    eng._fallback = "pyttsx3"
    eng.speak("hello")
    assert fb == ["hello"]
