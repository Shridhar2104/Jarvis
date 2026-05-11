"""
brain/intent.py — LLM-powered intent classification

Receives transcribed voice commands and classifies them into:
  - tool_type: which skill or agent type to invoke
  - action:    specific action within that tool
  - params:    extracted parameters
  - priority:  urgent | normal | background (for agent jobs)
  - is_long_running: True if this should spawn an Agent vs direct tool call
"""

import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from config import LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL
from brain.context import get_context_line

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

SYSTEM_PROMPT = """
You are J.A.R.V.I.S — a deeply capable, drily witty AI chief of staff running on macOS.
You speak like Tony Stark's butler: efficient, precise, occasionally sardonic, always helpful.
You have awareness of what the user is currently doing and you use it subtly.

Given a voice command (and optionally the user's current app), return a JSON intent:
- tool_type: one of [claude_code, shell, file_ops, browser, apps, files, system, mouse, terminal, calendar, focus, status, memory, chat]
  Use "chat" for casual conversation, jokes, questions, or anything that doesn't map to a tool.
- action: specific action string (e.g. "launch", "rename", "create_event", "focus_on", "query_jobs", "respond")
- params: dict of extracted parameters
- priority: "urgent" | "normal" | "background"
- is_long_running: true only if this must run as a background agent job
- spoken_ack: What JARVIS says out loud immediately. Make it natural and human.
  - Reference the user's current app or activity when it adds wit or relevance
  - Crack a dry joke when the moment calls for it — never forced, never too long
  - For tool_type "chat": this IS the full response, make it complete and conversational
  - Keep it under 2 sentences. No bullet points. No markdown.

Examples of good spoken_ack:
  "Setting that reminder — though I notice you've been in Xcode for three hours straight."
  "On it. Might I suggest also closing the 47 Safari tabs you've accumulated?"
  "Reminder set. Also, it's 1am — just mentioning that."
  "Sure, opening Spotify. The code will still be broken when you get back."
  "That's a great question. The answer is no one knows, and Stack Overflow is lying to you."

Respond with valid JSON only. No markdown fences.
""".strip()


@dataclass
class Intent:
    tool_type: str
    action: str
    params: dict
    priority: str
    is_long_running: bool
    spoken_ack: str
    raw_text: str


class IntentClassifier:
    """
    Classifies a natural language command into a structured Intent.

    Injects routine context from the Life OS engine when available,
    so the LLM has awareness of the user's patterns.
    """

    def __init__(self) -> None:
        self._routine_context: str = ""

    def update_routine_context(self, context: str) -> None:
        """Called by Life OS when routine.detected events arrive."""
        self._routine_context = context

    async def classify(self, text: str) -> Intent:
        """Classify a raw command string into a structured Intent."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        context_parts = []
        app_context = get_context_line()
        if app_context:
            context_parts.append(app_context)
        if self._routine_context:
            context_parts.append(f"Routine context: {self._routine_context}")
        if context_parts:
            messages.append({
                "role": "system",
                "content": "\n".join(context_parts),
            })

        messages.append({"role": "user", "content": text})

        logger.debug("Classifying intent for: '%s'", text)

        response = await _client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )

        raw_json = response.choices[0].message.content or "{}"
        data = json.loads(raw_json)

        intent = Intent(
            tool_type=data.get("tool_type", "unknown"),
            action=data.get("action", ""),
            params=data.get("params", {}),
            priority=data.get("priority", "normal"),
            is_long_running=bool(data.get("is_long_running", False)),
            spoken_ack=data.get("spoken_ack", "On it, sir."),
            raw_text=text,
        )

        logger.info(
            "Intent: tool=%s action=%s long_running=%s",
            intent.tool_type, intent.action, intent.is_long_running,
        )
        return intent
