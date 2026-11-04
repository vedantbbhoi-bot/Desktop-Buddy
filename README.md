# Desktop Buddy

A small AI pet that lives on your desktop. It runs **fully offline**: it listens to you
(Vosk), thinks (a local Ollama model), and talks back (Piper voice). It can also open files
and check code for you.

- **UI:** PySide6, a transparent always-on-top window with an animated character
- **Brain:** [Ollama](https://ollama.com) (default model `qwen2.5-coder:3b`)
- **Ears:** [Vosk](https://alphacephei.com/vosk/) speech recognition (push-to-talk)
- **Voice:** [Piper](https://github.com/rhasspy/piper), with `pyttsx3` as a fallback voice
- **Memory:** a small SQLite database, kept separately for each folder you launch it from

## Quick start

Needs Python 3.11 or newer.

```bash
# 1. Install
python -m pip install -e .[dev]

# 2. Download the voice, the speech model and the Piper program (about 100 MB)
python scripts/download_models.py

# 3. Create your settings file (it is git-ignored)
cp config.example.json config.json        # Windows: copy config.example.json config.json
#    then set  "tts": { "piper_binary": "bin/piper/piper.exe" }   (no .exe on Linux/macOS)

# 4. Install Ollama from https://ollama.com, then:
ollama pull qwen2.5-coder:3b

# 5. Run
python main.py
```

Try the terminal version first if something doesn't work: `python main.py --cli`
(type to chat, `/voice` to use the microphone, `/quit` to exit; add `--debug` for details).

## Using the pet

| Action | What it does |
|---|---|
| Click the pet | Push-to-talk: it listens until you stop speaking |
| Drag the pet | Moves it around the screen |
| Right-click | Menu: Talk, Type a message, Quit |

Things you can say or type: normal chat, `open README.md`, `check src/config.py`.

The pet shows a different animation for each mood: idle, listening, thinking, working,
celebrate, confused and talking (while the voice is speaking).

## Settings

Edit `config.json` (see `config.example.json`). Common ones:

| Setting | Meaning |
|---|---|
| `scale` | Makes the pet bigger or smaller (for example `1.5`) |
| `always_on_top` | Keep the pet above other windows |
| `llm.model` | Which Ollama model to use. Run `ollama list` to see yours |
| `tts.model_path` | Which Piper voice to use (a `.onnx` file plus its `.onnx.json`) |
| `window.x`, `window.y` | Where the pet starts |

Environment variables override the file: `BUDDY_LLM_MODEL`, `BUDDY_LLM_URL`,
`BUDDY_SCALE`, `BUDDY_THEME`, `BUDDY_ALWAYS_ON_TOP`.

Other Piper voices: https://rhasspy.github.io/piper-samples/ (download from
https://huggingface.co/rhasspy/piper-voices). Pick single-speaker voices.

## Changing the character

The character comes from one sprite sheet, `assets/sprites/default/sprite_sheet.png`
(640 x 1024, transparent background): 8 rows of 64 x 128 frames. Each row is one animation.
See `assets/sprites/default/README.md` for which row is which mood. To use your own
character, keep the same grid, or change the grid settings in `src/pet_window.py`. If the
sheet is missing, the pet falls back to a simple drawn face.

## If something goes wrong

| Problem | Fix |
|---|---|
| "Ollama is not running" | Start Ollama, then ask again |
| The Windows voice speaks instead of Piper | Run `python scripts/download_models.py`, then check `piper_binary` in `config.json` |
| `python -m src.tts_piper` prints `piper: NOT FOUND` | Same fix as above |
| Voice says the model is not loaded | Run `python scripts/download_models.py` |
| Pet doesn't appear | Run `python main.py --cli --debug` and read the messages |

## Development

```bash
python -m pytest tests -q       # tests (no screen or microphone needed)
ruff check .                    # lint
```

GitHub Actions runs the tests on Python 3.11 and 3.12 for every push.

## Project layout

```
main.py                 entry point (window mode, or --cli)
src/pet_window.py       the transparent pet window and animations
src/intent_router.py    decides what your message means (chat / open file / check code)
src/llm/                Ollama client
src/stt/                Vosk speech-to-text
src/tts_piper.py        Piper voice with fallback
src/memory/             per-folder conversation memory (SQLite)
scripts/                model downloader and helpers
docs/                   product notes and project workflow
```
