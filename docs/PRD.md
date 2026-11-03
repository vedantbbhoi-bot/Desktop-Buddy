
---

### `docs/PRD.md`

```markdown
# PRD — Desktop Buddy (10-Day Challenge)

## 1. Product Definition

Desktop Buddy is a fully offline desktop AI pet. It lives as a transparent,
always-on-top overlay on the user's screen. It accepts voice input, speaks
back, remembers conversation context per working directory, performs basic
tasks (open a file, static bug-check a code file), makes small talk, and
changes appearance/size based on user configuration. It animates when a task
starts and when a task completes.

It is a native desktop application, not a web app and not a browser plugin.

## 2. Architecture Consequence of "Offline"

Because the app must run offline, the entire inference chain is local:

- **LLM**: Ollama at `127.0.0.1:11434`, model `qwen2.5-coder:3b` (Q4).
  Qwen2.5-Coder is tuned for code and also handles short conversation, which
  covers both the bug-check and small-talk requirements with one model.
  On 16 GB machines, a 7B variant may be substituted; 3B is the MVP baseline.
- **STT**: Vosk small English model (~50 MB), CPU real-time, command-length
  utterances.
- **TTS**: Piper (ONNX, ~60–70 MB on disk, ~150 MB runtime), low latency.
- **UI**: PySide6, frameless + always-on-top window, sprite-sheet animation.
- **Persistence**: SQLite, one logical session namespace per working directory.

## 3. User Stories (Acceptance Anchors)

- **US-1** — User says "open README.md"; the pet opens that file in the OS
  default editor, resolved relative to the current working directory.
- **US-2** — User asks the pet to check a `.py` file; the pet runs objective
  static checks and returns a short spoken explanation of the findings.
- **US-3** — User clicks the pet while idle; the pet speaks 1–2 sentences
  grounded in current time, current directory name, and recent task history.
- **US-4** — Conversation history is isolated per working directory. Restarting
  the app restores history for the same directory and does not leak across
  directories.
- **US-5** — User changes scale/theme/sprite set in config; the pet reflects
  the change. Task start plays a "thinking/working" animation; completion
  plays a "celebrate/nod" animation; failure plays "confused".
- **US-6** — During development, every completed file is committed and pushed
  to `https://github.com/vedantbbhoi-bot/Desktop-Buddy.git` before the next
  file begins. A token cutoff loses at most the file currently being written.

## 4. Functional Requirements

### P0 — Must be demoable within 10 days

| ID | Requirement | Technical note |
|---|---|---|
| F-01 | Transparent always-on-top desktop overlay | PySide6 `FramelessWindowHint` + `WindowStaysOnTopHint`; draggable; `QMovie` or frame-sequence animation |
| F-02 | Local LLM client | Ollama `/api/chat` wrapper; model configurable in `config.py` |
| F-03 | Local STT | Vosk small model; push-to-talk or VAD-gated short utterances |
| F-04 | Local TTS | Piper; async playback so UI never blocks |
| F-05 | Open a file | Resolve path relative to CWD; open via OS default opener (`os.startfile`, `open`, `xdg-open`); path must be user-approved |
| F-06 | Static bug check | `python -m py_compile` + `ruff check --output-format json`; feed objective results to LLM for a 2–4 sentence spoken explanation |
| F-07 | Small talk | Prompt grounded in directory name, time of day, last user message, recent task; avoid repeating recent opening phrases |
| F-08 | Per-directory context | SQLite table keyed by directory hash; history rows include role, content, timestamp, task id |
| F-09 | Appearance and size config | JSON config: `scale`, `theme`, `sprite_dir`, `always_on_top`; hot-reload or restart-to-apply |
| F-10 | Reaction animations | States: `idle`, `thinking`, `working`, `celebrate`, `confused`; mapped to task lifecycle events |
| F-11 | Per-file auto commit + push | `scripts/auto_push.py` invoked after each file; idempotent; retries push |
| F-12 | Progress log | `PROGRESS.md`, append-only; also serves as AI resume context |

### P1 — Add if time allows, never blocking

- Drag-and-drop a file onto the pet to trigger a bug check.
- Tray menu to toggle voice input/output.
- Idle wander behavior along screen edges.
- Live2D integration (high risk in 10 days; sprite frames are the default).

## 5. Non-Functional Requirements

- **Offline**: No network calls from application code at runtime. Ollama,
  Vosk, and Piper load from local disk.
- **Latency**: Cold start ≤ 8 s excluding model load. Warm interaction ≤ 3 s
  on CPU for 3B Q4.
- **Resources**: Resident memory ≤ 1.5 GB excluding OS; idle CPU ≤ 5%.
- **Safety**: File operations are restricted to user-approved paths. The pet
  never executes arbitrary shell commands. Git operations performed by the
  coding agent must be auditable.

## 6. Out of Scope (10-day version)

- Multi-user profiles.
- Cloud sync or remote model fallback.
- Plugin marketplace.
- Windows/macOS code-signing and notarization (packaging is in scope; signing
  is not).

## 7. 10-Day Milestones

| Day | Deliverable | Acceptance |
|---|---|---|
| D1 | Repo skeleton, `auto_push.py`, `PROGRESS.md`, transparent overlay with 3 animation states | Pet visible, draggable, animates |
| D2 | Ollama client + local model round-trip | Internal call returns text from `qwen2.5-coder:3b` |
| D3 | Vosk STT + intent routing | "open X" resolves to intent + target |
| D4 | Piper TTS + grounded small talk | Pet speaks a directory/time-aware sentence |
| D5 | File-open tool + static bug-check tool | Real `.py` file returns readable findings |
| D6 | Per-directory SQLite context | Two directories isolated; restart restores |
| D7 | Appearance/scale config + reaction wiring | Config change reflected; completion animation fires |
| D8 | Per-file auto push + `PROGRESS.md` stable | Simulated token cutoff resumes from last pushed file |
| D9 | End-to-end integration + packaging | `.exe` / `.app` runs on target machine |
| D10 | Demo script, README, edge-case hardening | 5-minute end-to-end demo |

## 8. Risks

| Risk | Mitigation |
|---|---|
| Antigravity preview instability (early termination, context drift) | One-file-per-turn rule + external `auto_push.py` + `PROGRESS.md` |
| CPU-only inference too slow for conversation | 3B Q4 baseline; small-talk prompts capped at 1–2 sentences; streaming TTS |
| TTS/STT latency perception | Play "thinking" animation immediately; speak partial output |
| Non-fast-forward push failures | `git pull --rebase` before write; push retry x3; failure logged |