Desktop-Buddy/
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                     # optional: lint + pytest on push
├── README.md
├── PROGRESS.md                        # append-only AI log (see prompts)
├── requirements.txt
├── pyproject.toml                     # ruff + pytest config, package metadata
├── main.py                            # app entry point; builds QApplication, wires modules
├── config.example.json                # checked-in template
├── config.json                        # [gitignored] user runtime config, copied from example
│
├── docs/
│   ├── PRD.md
│   ├── PROMPTS.md
│   └── AUTO_PUSH_WORKFLOW.md
│
├── scripts/
│   ├── auto_push.py                   # idempotent per-file commit+push (Prompt 1/2)
│   ├── download_models.py             # fetches Vosk + Piper model files into models/
│   └── run_demo.py                    # 5-minute scripted demo for D10
│
├── src/
│   ├── __init__.py
│   ├── config.py                      # loads config.json, dataclasses, env overrides
│   ├── logging_setup.py               # structured logging to data/logs/
│   │
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── pet_window.py              # frameless, always-on-top QWidget (F-01)
│   │   ├── sprite.py                  # QMovie/frame-sequence loader, state switching (F-10)
│   │   ├── animation_states.py        # enum: IDLE, THINKING, WORKING, CELEBRATE, CONFUSED
│   │   ├── settings_dialog.py         # scale/theme/sprite picker (F-09)
│   │   └── tray_menu.py               # optional P1: toggle voice, quit
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── ollama_client.py           # /api/chat wrapper, streaming (F-02)
│   │   └── prompts.py                 # runtime prompt templates (Prompts 3 & 4)
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   └── vosk_engine.py             # push-to-talk recognition (F-03)
│   │
│   ├── tts/
│   │   ├── __init__.py
│   │   └── tts.py                     # piper + pyttsx3 fallback (F-04) — reviewed above
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_opener.py             # resolve path + OS default opener (F-05)
│   │   └── code_checker.py            # py_compile + ruff JSON adapter (F-06)
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── context_store.py           # per-directory SQLite (F-08)
│   │   └── schema.sql                 # migrations seed
│   │
│   └── intent_router.py               # dispatches STT/text → tool | small talk (F-07, F-10)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auto_push.py              # idempotency: re-running on unchanged file is a no-op
│   ├── test_tts.py                    # fallback selection, empty input, timeout path
│   ├── test_code_checker.py           # known-bad file produces expected lint shape
│   ├── test_context_store.py          # directory isolation, restart persistence
│   └── test_intent_router.py          # "open X" and "check X" route correctly
│
├── assets/
│   ├── sprites/
│   │   ├── default/
│   │   │   ├── idle/                  # idle_000.png … (or idle.webp)
│   │   │   ├── thinking/
│   │   │   ├── working/
│   │   │   ├── celebrate/
│   │   │   └── confused/
│   │   └── minimal/                   # second theme proves F-09 works
│   └── icons/
│       └── tray.png
│
├── models/                            # [gitignored] downloaded, not committed
│   ├── vosk/
│   │   └── vosk-model-small-en-us-0.15/
│   └── piper/
│       ├── en_US-lessac-medium.onnx
│       └── en_US-lessac-medium.onnx.json
│
├── bin/                               # [gitignored] vendored binaries
│   └── piper                          # optional; otherwise resolved via PATH
│
└── data/                              # [gitignored] runtime state
    ├── context.db                     # SQLite (F-08)
    └── logs/
        └── app.log