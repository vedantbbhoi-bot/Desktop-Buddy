"""src/llm/ollama_client.py — Ollama /api/chat wrapper with streaming (F-02).

Communicates with a local Ollama instance at 127.0.0.1:11434.
Supports both streaming and non-streaming responses.
No network calls outside localhost — fully offline.
"""
from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Generator, Optional

log = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:3b"
DEFAULT_TIMEOUT = 30


def _is_ollama_running(base_url: str, timeout: int = 2) -> bool:
    """Quick connectivity check to Ollama server."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False


class OllamaClient:
    """Minimal Ollama chat client that works with stdlib only (no requests dep)."""

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._chat_url = f"{self.base_url}/api/chat"

    # ── Connectivity ──────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return _is_ollama_running(self.base_url)

    # ── Non-streaming chat ────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> str:
        """Send a chat request and return the full assistant reply as a string."""
        payload = self._build_payload(
            messages, system=system, stream=False,
            temperature=temperature, max_tokens=max_tokens
        )
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._chat_url,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result.get("message", {}).get("content", "").strip()
        except urllib.error.URLError as exc:
            log.error("Ollama request failed: %s", exc)
            raise ConnectionError(f"Ollama unreachable: {exc}") from exc
        except Exception as exc:
            log.exception("Unexpected error in OllamaClient.chat")
            raise

    # ── Streaming chat ────────────────────────────────────────────────────────

    def chat_stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> Generator[str, None, None]:
        """Yield text chunks from a streaming Ollama response."""
        payload = self._build_payload(
            messages, system=system, stream=True,
            temperature=temperature, max_tokens=max_tokens
        )
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._chat_url,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
        except urllib.error.URLError as exc:
            log.error("Ollama stream failed: %s", exc)
            raise ConnectionError(f"Ollama unreachable: {exc}") from exc

    # ── Convenience ───────────────────────────────────────────────────────────

    def quick_reply(self, user_text: str, system: Optional[str] = None) -> str:
        """Single-turn, non-streaming helper for small-talk / one-shot queries."""
        return self.chat(
            messages=[{"role": "user", "content": user_text}],
            system=system,
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_payload(
        self,
        messages: list[dict],
        *,
        system: Optional[str],
        stream: bool,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        return {
            "model": self.model,
            "messages": msgs,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }


if __name__ == "__main__":
    client = OllamaClient()
    if not client.is_available():
        print("Ollama is not running — skipping live test.")
        print("Start Ollama with: ollama serve")
        print("ollama_client.py structure smoke test PASSED (no live call)")
    else:
        print(f"Ollama is running. Model: {client.model}")
        reply = client.quick_reply("Say hello in exactly 5 words.")
        print(f"Reply: {reply}")
        print("ollama_client.py live smoke test PASSED")

