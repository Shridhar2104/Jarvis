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

from config import LLM_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are the intent classification engine for J.A.R.V.I.S — a macOS AI chief of staff.

Given a user's voice command, classify it into a structured intent JSON object with these fields:
- tool_type: one of [claude_code, shell, file_ops, browser, apps, files, system, mouse, terminal, calendar, focus, status, memory]
- action: specific action string (e.g. "launch", "rename", "create_event", "focus_on", "query_jobs")
- params: dict of extracted parameters (repo_path, goal, constraints, title, time, etc.)
- priority: "urgent" | "normal" | "background"
- is_long_running: true if this should run as a background agent, false for immediate tool calls
- spoken_ack: short 1-sentence acknowledgement Jarvis should speak immediately

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

        if self._routine_context:
            messages.append({
                "role": "system",
                "content": f"User routine context:\n{self._routine_context}",
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
