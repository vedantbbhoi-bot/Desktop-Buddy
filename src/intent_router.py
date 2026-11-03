"""src/intent_router.py — Dispatches text/STT input to tool or small talk (F-07, F-10).

Intent patterns:
  open <file>           → file_opener tool
  check <file>          → code_checker tool → LLM for spoken explanation
  <anything else>       → LLM small talk / general chat

Animation state transitions are emitted via callbacks so the UI layer can
react without the router knowing about Qt or sprites.
"""
from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

log = logging.getLogger(__name__)


class IntentType(Enum):
    OPEN_FILE = auto()
    CHECK_CODE = auto()
    SMALL_TALK = auto()
    UNKNOWN = auto()


@dataclass
class Intent:
    type: IntentType
    target: Optional[str] = None   # filename for OPEN_FILE / CHECK_CODE
    raw_text: str = ""


# ── Intent parsing ─────────────────────────────────────────────────────────────

_OPEN_RE = re.compile(
    r"""^(?:open|show|launch|start|edit)\s+["']?([^\s"']+)["']?""",
    re.IGNORECASE,
)
_CHECK_RE = re.compile(
    r"""^(?:check|lint|review|analyze|analyse|scan)\s+["']?([^\s"']+)["']?""",
    re.IGNORECASE,
)


def parse_intent(text: str) -> Intent:
    """Parse user text into a structured Intent."""
    text = text.strip()

    m = _OPEN_RE.match(text)
    if m:
        return Intent(type=IntentType.OPEN_FILE, target=m.group(1), raw_text=text)

    m = _CHECK_RE.match(text)
    if m:
        return Intent(type=IntentType.CHECK_CODE, target=m.group(1), raw_text=text)

    if text:
        return Intent(type=IntentType.SMALL_TALK, raw_text=text)

    return Intent(type=IntentType.UNKNOWN, raw_text=text)


# ── Router ────────────────────────────────────────────────────────────────────

class IntentRouter:
    """Routes parsed intents to the appropriate handler.

    All heavy work (LLM calls, file ops) is done synchronously here.
    The caller should invoke this from a worker thread so the UI stays responsive.

    Args:
        working_dir:     Base directory for resolving relative file paths.
        ollama_client:   OllamaClient instance (may be None if Ollama is offline).
        tts_engine:      TTSEngine for spoken responses.
        store:           ContextStore for per-directory conversation history.
        on_state_change: Callback(state_name: str) to drive animation states.
    """

    def __init__(
        self,
        working_dir: pathlib.Path,
        ollama_client,
        tts_engine,
        store,
        on_state_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.working_dir = working_dir
        self.ollama = ollama_client
        self.tts = tts_engine
        self.store = store
        self._on_state = on_state_change or (lambda s: None)

    def _set_state(self, state: str) -> None:
        log.debug("Animation state → %s", state)
        self._on_state(state)

    def handle(self, text: str) -> str:
        """Route text to the correct handler, return the response text."""
        intent = parse_intent(text)
        log.info("Intent: %s target=%r", intent.type.name, intent.target)

        if intent.type == IntentType.OPEN_FILE:
            return self._handle_open(intent)
        if intent.type == IntentType.CHECK_CODE:
            return self._handle_check(intent)
        if intent.type == IntentType.SMALL_TALK:
            return self._handle_small_talk(intent)
        return "Sorry, I didn't catch that."

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_open(self, intent: Intent) -> str:
        from src.tools.file_opener import open_file

        self._set_state("working")
        result = open_file(intent.target or "", working_dir=self.working_dir)
        if result.success:
            response = f"Opened {result.path.name}."  # type: ignore[union-attr]
            self._set_state("celebrate")
        else:
            response = f"I couldn't open that file. {result.error}"
            self._set_state("confused")

        self._speak_and_store(intent.raw_text, response, task_type="open_file")
        return response

    def _handle_check(self, intent: Intent) -> str:
        from src.llm.prompts import CODE_REVIEW_SYSTEM, code_review_user
        from src.tools.code_checker import check_file

        self._set_state("thinking")
        target_path = (self.working_dir / (intent.target or "")).resolve()
        result = check_file(target_path)
        self._set_state("working")

        compile_str = result.compile_result_str()
        lint_str = result.lint_result_str()

        if self.ollama and self.ollama.is_available():
            try:
                user_msg = code_review_user(
                    str(target_path), compile_str, lint_str
                )
                response = self.ollama.chat(
                    messages=[{"role": "user", "content": user_msg}],
                    system=CODE_REVIEW_SYSTEM,
                    max_tokens=150,
                )
            except Exception:
                log.exception("LLM code review failed")
                response = f"Compile: {compile_str}. Lint: {lint_str}"
        else:
            # Fallback without LLM
            if result.all_clear:
                response = f"{target_path.name} looks clean — no syntax errors and no lint issues."
            else:
                parts = []
                if not result.compile_ok:
                    parts.append(f"Syntax error: {compile_str}")
                if result.lint_issues:
                    parts.append(f"{len(result.lint_issues)} lint issue(s) found")
                response = ". ".join(parts) + "."

        state = "celebrate" if result.all_clear else "confused"
        self._set_state(state)
        self._speak_and_store(intent.raw_text, response, task_type="code_check")
        return response

    def _handle_small_talk(self, intent: Intent) -> str:
        import datetime

        from src.llm.prompts import (
            GENERAL_SYSTEM,
            IDLE_CHAT_SYSTEM,
            idle_chat_user,
            time_of_day_label,
        )

        self._set_state("thinking")

        # Build history for the LLM
        history = self.store.get_history(self.working_dir, limit=10)
        last_task = self.store.get_last_task(self.working_dir)

        if self.ollama and self.ollama.is_available():
            # Build Ollama messages from stored history
            messages = [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant")
            ]
            messages.append({"role": "user", "content": intent.raw_text})

            try:
                response = self.ollama.chat(
                    messages=messages,
                    system=GENERAL_SYSTEM,
                    max_tokens=128,
                )
            except Exception:
                log.exception("LLM small talk failed")
                response = "I'm here! Though I'm having trouble connecting to my brain right now."
        else:
            # Graceful offline fallback
            tod = time_of_day_label()
            response = (
                f"Good {tod}! I'm your Desktop Buddy. "
                "Ollama isn't running right now, so I can't chat much, "
                "but I can still open files and check code."
            )

        self._set_state("idle")
        self._speak_and_store(intent.raw_text, response, task_type="small_talk")
        return response

    def _speak_and_store(self, user_text: str, response: str, task_type: str) -> None:
        """Persist the exchange and speak the response."""
        task_id = self.store.create_task(self.working_dir, task_type, response[:120])
        self.store.add_message(self.working_dir, "user", user_text, task_id=task_id)
        self.store.add_message(self.working_dir, "assistant", response, task_id=task_id)
        self.store.finish_task(task_id, "done")
        if self.tts:
            self.tts.speak_async(response)


if __name__ == "__main__":
    # Parse intent unit tests
    cases = [
        ("open README.md", IntentType.OPEN_FILE, "README.md"),
        ("check src/config.py", IntentType.CHECK_CODE, "src/config.py"),
        ("open 'my file.txt'", IntentType.OPEN_FILE, "my"),  # quotes stripped partially
        ("what time is it?", IntentType.SMALL_TALK, None),
        ("", IntentType.UNKNOWN, None),
    ]
    for text, expected_type, expected_target in cases:
        intent = parse_intent(text)
        assert intent.type == expected_type, f"For {text!r}: expected {expected_type}, got {intent.type}"
        if expected_target is not None:
            assert intent.target == expected_target, (
                f"For {text!r}: expected target {expected_target!r}, got {intent.target!r}"
            )
        print(f"  ✓ {text!r} → {intent.type.name} target={intent.target!r}")

    print("intent_router.py parse smoke test PASSED")

