"""src/tts/tts.py — Piper TTS + pyttsx3 fallback (F-04).

Wraps src/tts_piper.py (already reviewed and approved) into the package
structure expected by the rest of the app.  This module re-exports TTSEngine
and TTSConfig so callers only need to import from src.tts.tts.
"""
from __future__ import annotations

# Re-export from the existing canonical implementation
from src.tts_piper import TTSConfig, TTSEngine

__all__ = ["TTSEngine", "TTSConfig"]


if __name__ == "__main__":
    engine = TTSEngine()
    if engine._piper_path:
        print(f"Piper found at: {engine._piper_path}")
        engine.speak("Hello! I am Desktop Buddy.")
        print("TTS live test PASSED")
    elif engine._fallback is not None:
        print("Using pyttsx3 fallback")
        engine.speak("Hello! I am Desktop Buddy.")
        print("TTS fallback live test PASSED")
    else:
        print("No TTS engine available — skipping speak test")
        print("tts.py structure smoke test PASSED")

