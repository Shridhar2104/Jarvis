"""
proactive/surface.py — Proactive Surface Layer

Handles all proactive interruptions: fires the NSPanel overlay,
speaks via TTS, and manages the notification queue during Focus Mode.

Subscribes to:
  job.completed       → normal priority surface
  job.failed          → urgent priority surface
  job.blocked         → urgent priority surface
  reminder.triggered  → priority based on reminder type

NSPanel overlay spec (from product spec):
  - Width: 380px fixed, height dynamic
  - Position: top-right, 20px from screen edges
  - Dark navy + Arc Reactor blue
  - Animated waveform while speaking
  - Text transcript for silent environments
  - Action buttons when input required: Open file / Dismiss / Snooze 30 mins
  - Auto-dismisses 5s after speaking (unless action required)
  - Implementation: NSPanel via PyObjC at NSWindowLevel.floating
"""

import asyncio
import logging
import time

from events.bus import bus, Event
from proactive.focus import FocusMode
from proactive.queue import NotificationQueue
from proactive.urgency import score_urgency, UrgencyLevel

logger = logging.getLogger(__name__)


class ProactiveSurface:
    """
    The Proactive Surface Layer.

    Routes incoming events through urgency scoring → focus mode gating
    → immediate fire or queue.
    """

    def __init__(self, tts, focus: FocusMode) -> None:
        self._tts = tts
        self._focus = focus
        self._queue = NotificationQueue()

        # Subscribe to all events that can trigger proactive surfaces
        for topic in ("job.completed", "job.failed", "job.blocked", "reminder.triggered"):
            bus.on(topic, self._on_event)

        # Focus mode off → flush queue
        bus.on("focus.changed", self._on_focus_changed)
        logger.info("ProactiveSurface ready")

    # ── Event Handlers ────────────────────────────────────────────────────────

    async def _on_event(self, event: Event) -> None:
        score = score_urgency(event.topic, event.payload)
        message = self._build_message(event)

        if score.bypasses_focus or not self._focus.is_active():
            await self._fire(message, event, score)
        else:
            # LOW nudges during focus: health break is dropped, others queued
            if score.level == UrgencyLevel.LOW and event.payload.get("nudge_type") == "health_break":
                logger.debug("Health break nudge dropped (focus mode active)")
                return
            self._queue.enqueue(event.topic, event.payload, score)
            logger.debug("Queued during focus: %s", event.topic)

    async def _on_focus_changed(self, event: Event) -> None:
        if event.payload.get("action") == "off":
            await self._flush_queue()

    # ── Fire / Queue ──────────────────────────────────────────────────────────

    async def _fire(self, message: str, event: Event, score) -> None:
        """Show overlay and speak the message."""
        logger.info("Proactive surface firing [%s]: %s", score.level, message[:80])

        # Show native NSPanel overlay
        await asyncio.to_thread(self._show_overlay, message, event)

        # Speak
        await self._tts.speak(message)

        # Mark job as notified
        job_id = event.payload.get("job_id")
        if job_id:
            from db.schema import JobsTable
            jobs = JobsTable()
            job = jobs.get(job_id)
            if job:
                job.notified = 1
                jobs.upsert(job)

    async def _flush_queue(self) -> None:
        """Flush the queue on focus exit with batched summary."""
        if self._queue.is_empty():
            return

        summary = self._queue.build_summary()
        items = self._queue.flush()

        logger.info("Flushing %d queued items", len(items))
        await self._tts.speak(summary)

        # Fire individual overlays for urgent items
        for item in items:
            if item.score and item.score.level in (UrgencyLevel.URGENT, UrgencyLevel.CRITICAL):
                msg = self._build_message_from_payload(item.event_type, item.payload)
                await asyncio.to_thread(self._show_overlay, msg, None)

    # ── Overlay ───────────────────────────────────────────────────────────────

    def _show_overlay(self, message: str, event: Event | None) -> None:
        """
        Display native NSPanel overlay via PyObjC.

        Spec: 380px wide, top-right 20px from edges, NSWindowLevel.floating,
        dark navy bg, Arc Reactor blue accent, auto-dismiss 5s.
        """
        try:
            import AppKit
            # TODO: implement full NSPanel overlay
            # For now, log as a stub. Full implementation requires:
            #   - NSPanel with NSWindowLevel.floating
            #   - Custom NSView with dark navy (#0D1B2A) background
            #   - Arc Reactor blue (#00B4FF) accent
            #   - Waveform animation while TTS plays
            #   - Action buttons for BLOCKED events
            #   - Auto-dismiss timer
            logger.debug("[overlay stub] %s", message)
        except ImportError:
            logger.debug("AppKit not available — overlay skipped (non-macOS?)")

    # ── Message Building ──────────────────────────────────────────────────────

    def _build_message(self, event: Event) -> str:
        return self._build_message_from_payload(event.topic, event.payload)

    def _build_message_from_payload(self, topic: str, payload: dict) -> str:
        title = payload.get("title", "")
        summary = payload.get("summary", "")
        error = payload.get("error", "")
        reason = payload.get("reason", "")

        if topic == "job.completed":
            return f"{title} is done. {summary}".strip()
        elif topic == "job.failed":
            return f"The {title} job ran into an error. {error}".strip()
        elif topic == "job.blocked":
            return f"I need your input on {title}. {reason}".strip()
        elif topic == "reminder.triggered":
            return payload.get("title", "Reminder triggered.")
        return f"{topic}: {title or summary}"
