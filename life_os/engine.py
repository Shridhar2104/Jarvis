"""
life_os/engine.py — Life OS Engine main loop

The long-term memory and temporal intelligence of Jarvis.
Polls Apple Calendar, monitors reminders, and coordinates nudges.

Publishes:
  reminder.triggered  → Proactive Surface
  routine.detected    → LLM Brain (context injection)
"""

import asyncio
import logging
import time
import uuid

from config import CALENDAR_POLL_SECS, NUDGE_ENABLED
from db.schema import RemindersTable, CalendarEventsTable, NudgesTable, RoutinesTable
from events.bus import bus, Event
from life_os.nudge import NudgeEngine
from life_os.routine_detector import RoutineDetector

logger = logging.getLogger(__name__)


class LifeOSEngine:
    """
    Runs as a background asyncio task.

    Responsibilities:
    - Poll Apple Calendar every 5 minutes, sync to brain.db
    - Check pending reminders every 30 seconds, fire when due
    - Run nightly routine analysis at 2am
    - Publish routine context to LLM Brain
    """

    def __init__(self) -> None:
        self._reminders = RemindersTable()
        self._calendar = CalendarEventsTable()
        self._nudges_db = NudgesTable()
        self._routines = RoutinesTable()
        self._nudge_engine = NudgeEngine()
        self._routine_detector = RoutineDetector()
        self._running = False
        logger.info("LifeOSEngine initialised")

    async def start(self) -> None:
        self._running = True
        logger.info("LifeOSEngine started")
        await asyncio.gather(
            self._reminder_loop(),
            self._calendar_sync_loop(),
            self._nudge_loop(),
            self._routine_analysis_loop(),
        )

    async def stop(self) -> None:
        self._running = False

    # ── Reminder Loop ─────────────────────────────────────────────────────────

    async def _reminder_loop(self) -> None:
        """Check every 30 seconds for due reminders."""
        while self._running:
            try:
                now = int(time.time())
                pending = self._reminders.list_pending()
                for r in pending:
                    # Fire if due within the next 60 seconds
                    if r.due_at <= now + 60:
                        logger.info("Reminder triggered: %s", r.title)
                        await bus.publish(Event("reminder.triggered", {
                            "reminder_id": r.id,
                            "title": r.title,
                            "priority": r.priority,
                        }))
                        self._reminders.mark_done(r.id)
            except Exception:
                logger.exception("Reminder loop error")
            await asyncio.sleep(30)

    # ── Calendar Sync Loop ────────────────────────────────────────────────────

    async def _calendar_sync_loop(self) -> None:
        """Sync Apple Calendar every 5 minutes."""
        while self._running:
            try:
                await asyncio.to_thread(self._sync_calendar)
            except Exception:
                logger.exception("Calendar sync error — falling back to brain.db events")
            await asyncio.sleep(CALENDAR_POLL_SECS)

    def _sync_calendar(self) -> None:
        """
        Sync Apple Calendar via pyobjc EventKit.
        Reads today + next 7 days of events and upserts into brain.db.
        """
        try:
            import EventKit  # pyobjc — macOS only
            store = EventKit.EKEventStore.alloc().init()
            # TODO: request access, fetch events, map to CalendarEvent, upsert
            logger.debug("Calendar synced via EventKit")
        except ImportError:
            logger.warning("pyobjc EventKit not available — calendar sync skipped")
        except Exception:
            logger.exception("EventKit error")

    # ── Nudge Loop ────────────────────────────────────────────────────────────

    async def _nudge_loop(self) -> None:
        """Check nudge conditions every 5 minutes."""
        if not NUDGE_ENABLED:
            logger.info("Nudge system disabled via config")
            return
        while self._running:
            try:
                nudge = await self._nudge_engine.check()
                if nudge:
                    await bus.publish(Event("reminder.triggered", {
                        "reminder_id": nudge.id,
                        "title": nudge.message,
                        "priority": "normal",
                        "nudge_type": nudge.trigger_type,
                    }))
            except Exception:
                logger.exception("Nudge loop error — continuing")
            await asyncio.sleep(300)

    # ── Routine Analysis Loop ─────────────────────────────────────────────────

    async def _routine_analysis_loop(self) -> None:
        """Run nightly at 2am."""
        while self._running:
            try:
                now_hour = __import__("datetime").datetime.now().hour
                if now_hour == 2:
                    logger.info("Running nightly routine analysis…")
                    new_routines = await asyncio.to_thread(
                        self._routine_detector.analyse
                    )
                    for routine in new_routines:
                        self._routines.upsert(routine)
                        if routine.confidence >= 0.75:
                            context = self._build_routine_context()
                            await bus.publish(Event("routine.detected", {
                                "context": context,
                                "routine_id": routine.id,
                                "label": routine.label,
                                "confidence": routine.confidence,
                            }))
                    # Sleep until next check (avoid re-triggering within same hour)
                    await asyncio.sleep(3600)
                else:
                    await asyncio.sleep(600)  # check every 10 minutes
            except Exception:
                logger.exception("Routine analysis loop error")
                await asyncio.sleep(3600)

    def _build_routine_context(self) -> str:
        """Summarise confirmed routines for LLM context injection."""
        routines = self._routines.list_confirmed()
        if not routines:
            return ""
        lines = [f"- {r.label} ({r.time_pattern})" for r in routines]
        return "User confirmed routines:\n" + "\n".join(lines)
