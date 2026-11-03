# Desktop Buddy

Desktop Buddy is a planned offline desktop pet built with PySide6, Ollama, Vosk, and Piper. This folder currently contains the product notes, agent prompts, a TTS prototype, and project helper scripts; the complete application entry point is still to be added.

## Folder map

- `docs/` — product requirements, project schematic, workflow notes, and prompt library.
- `docs/prompts/` — individual prompts and recovery notes.
- `scripts/` — per-file Git helper scripts.
- `scripts/diagnostics/` — small Qt and audio diagnostic snippets.
- `src/` — application source prototypes, including the Piper TTS engine.
- `PROGRESS.md` — append-only development log used by the prompt workflow.
- `requirements.txt` — Python dependencies currently listed for audio support.

## Current files

The TTS prototype is in `src/tts_piper.py`. It uses Piper when available and falls back to `pyttsx3`. The diagnostic snippets under `scripts/diagnostics/` are examples, not application entry points.

Install the listed dependencies with:

```bash
python -m pip install -r requirements.txt
```

The full desktop app is not runnable yet; `main.py` and several modules shown in the project schematic have not been created.

## Project documents

- [Product requirements](docs/PRD.md)
- [File schematic](docs/FILE_SCHEMATIC.md)
- [Prompt library](docs/PROMPTS.md)
- [Auto-push workflow](docs/AUTO_PUSH_WORKFLOW.md)
- [Progress log](PROGRESS.md)
