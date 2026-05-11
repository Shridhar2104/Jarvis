"""
proactive/focus.py — Focus Mode state management

Focus Mode gates all non-urgent notifications.
CRITICAL and URGENT events always fire regardless of focus state.

Commands:
  "Jarvis, focus mode on"              → focus indefinitely
  "Focus until 5pm"                    → timed focus, warns 10 min before expiry
  "Don't disturb me unless tests fail" → focus with tagged urgency override
  "Jarvis, focus mode off"             → flush queue + batched summary
  "What did I miss?"                   → replay queue summary
"""

import asyncio
import logging
import time
from datetime import datetime

from events.bus import bus, Event

logger = logging.getLogger(__name__)


class FocusMode:
    """
    Manages focus mode state.

    The ProactiveSurface calls is_active() before deciding whether to
    fire or queue an event.
    """

    def __init__(self) -> None:
        self._active = False
        self._until: int | None = None           # Unix timestamp, or None = indefinite
        self._override_tags: set[str] = set()    # event tags that bypass focus
        self._expiry_warned = False

        bus.on("focus.changed", self._on_focus_changed)

    # ── Public API ────────────────────────────────────────────────────────────

    def is_active(self) -> bool:
        """True if focus mode is currently active."""
        if not self._active:
            return False
        # Auto-expire timed focus
        if self._until and time.time() >= self._until:
            logger.info("Timed focus mode expired")
            self._active = False
            self._until = None
            return False
        return True

    def has_override(self, tag: str) -> bool:
        """True if this tag is explicitly whitelisted to bypass focus."""
        return tag in self._override_tags

    def minutes_remaining(self) -> int | None:
        if self._until:
            secs = self._until - int(time.time())
            return max(0, secs // 60)
        return None

    # ── Event Handler ─────────────────────────────────────────────────────────

    async def _on_focus_changed(self, event: Event) -> None:
        action: str = event.payload.get("action", "")
        until_ts: int | None = event.payload.get("until_ts", None)
        override_tag: str = event.payload.get("override_tag", "")

        if action == "on":
            self._active = True
            self._until = until_ts
            self._expiry_warned = False
            if override_tag:
                self._override_tags.add(override_tag)
            logger.info(
                "Focus mode ON%s",
                f" until {datetime.fromtimestamp(until_ts).strftime('%H:%M')}" if until_ts else " (indefinite)",
            )

        elif action == "off":
            self._active = False
            self._until = None
            self._override_tags.clear()
            logger.info("Focus mode OFF")

    async def check_expiry_warning(self, tts) -> None:
        """
        Called periodically. Warns user 10 minutes before timed focus ends.
        The 'tts' parameter is the TextToSpeech instance.
        """
        if not self._active or not self._until or self._expiry_warned:
            return
        mins = self.minutes_remaining()
        if mins is not None and mins <= 10:
            self._expiry_warned = True
            await tts.speak(
                f"Focus mode ends in {mins} minutes, sir. "
                f"You have a meeting coming up."
            )
