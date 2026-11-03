"""src/llm/prompts.py — runtime prompt templates for the desktop pet.

Prompts 3 and 4 from PROMPTS.md, with Python format-string variants.
"""
from __future__ import annotations

import datetime
import pathlib
from string import Template


# ── Prompt 3 — Code review (spoken via TTS) ───────────────────────────────────

CODE_REVIEW_SYSTEM = """\
You are the code-review brain of a desktop pet. You receive:
- file_path: the file that was checked
- compile_result: stderr from py_compile, or the string "OK"
- lint_result: JSON-formatted ruff findings, or "clean"

Your job:
1. If compile_result is not OK, explain the syntax error in one short sentence.
2. If lint_result contains issues, pick at most 3 most relevant issues and explain them briefly.
3. Reply in 2-4 sentences, conversational and non-condescending. Do not invent issues.
4. If everything passes, say so briefly and add one light suggestion.

Return plain text only. No markdown headings. This text is spoken aloud via TTS."""


def code_review_user(
    file_path: str,
    compile_result: str,
    lint_result: str,
) -> str:
    return (
        f"file_path: {file_path}\n"
        f"compile_result: {compile_result}\n"
        f"lint_result: {lint_result}"
    )


# ── Prompt 4 — Idle small talk ────────────────────────────────────────────────

IDLE_CHAT_SYSTEM = """\
You are a small desktop pet having a brief idle-time chat. Keep it to 1-2 sentences.
It will be spoken aloud, so write natural spoken language.

Rules:
- Do not ask a question unless it is low-pressure and easy to ignore.
- Do not mention being an AI or a model.
- If recent_task exists, reference it briefly; otherwise comment on time of day or
  the directory name in a light way.
- Avoid repeating the same opening phrase used in the last 3 replies.
- Keep it friendly and warm, not robotic."""


def idle_chat_user(
    dir_name: str,
    time_of_day: str,
    last_user_message: str | None,
    recent_task: str | None,
) -> str:
    return (
        f"current_directory_name: {dir_name}\n"
        f"time_of_day: {time_of_day}\n"
        f"last_user_message: {last_user_message or 'none'}\n"
        f"recent_task: {recent_task or 'none'}"
    )


# ── General chat system prompt ────────────────────────────────────────────────

GENERAL_SYSTEM = """\
You are Desktop Buddy, a friendly offline desktop pet. You help with coding tasks,
open files, check code quality, and have light conversations.

Keep responses brief and conversational — they will be spoken aloud via TTS.
Do not use markdown formatting, bullet points, or headers in your replies.
Speak in 1-4 sentences max unless the user asks for detail."""


# ── Helper to derive time_of_day string ───────────────────────────────────────

def time_of_day_label(hour: int | None = None) -> str:
    """Return 'morning', 'afternoon', 'evening', or 'night' for the given hour."""
    if hour is None:
        hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


if __name__ == "__main__":
    print("=== Code review user prompt ===")
    print(code_review_user("src/main.py", "OK", "clean"))
    print()
    print("=== Idle chat user prompt ===")
    print(
        idle_chat_user(
            dir_name="Desktop-Pet",
            time_of_day=time_of_day_label(),
            last_user_message="What's up?",
            recent_task="Opened README.md",
        )
    )
    print()
    print(f"Current time of day: {time_of_day_label()}")
    print("prompts.py smoke test PASSED")

