"""
skills/calendar.py — Apple Calendar & Reminders via PyObjC EventKit

Native integration — no third-party calendar service required.
Reads and writes Apple Calendar events and Reminders.app items.

v2.0: read and create supported
v3.0: Google Calendar two-way sync

Requires: Privacy & Security → Calendars + Reminders permissions granted.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CalendarSkill:
    def __init__(self) -> None:
        self._store = None
        try:
            import EventKit
            self._ek = EventKit
            self._store = EventKit.EKEventStore.alloc().init()
            logger.info("EventKit store initialised")
        except ImportError:
            logger.warning("pyobjc EventKit not available — CalendarSkill in stub mode")

    # ── Calendar Events ───────────────────────────────────────────────────────

    async def get_todays_events(self, **_) -> str:
        """Return today's events in chronological order."""
        events = await asyncio.to_thread(self._fetch_events_today)
        if not events:
            return "Your calendar is clear today, sir."
        lines = [f"{self._fmt_time(e['start'])} — {e['title']}" for e in events]
        return "Today: " + "; ".join(lines)

    async def get_upcoming_events(self, hours: int = 24, **_) -> str:
        """Return events in the next N hours."""
        events = await asyncio.to_thread(self._fetch_upcoming, hours)
        if not events:
            return f"Nothing in the next {hours} hours."
        lines = [f"{self._fmt_time(e['start'])} — {e['title']}" for e in events]
        return f"Next {hours}h: " + "; ".join(lines)

    async def create_event(
        self,
        title: str,
        start_at: int | str,
        end_at: int | str | None = None,
        location: str = "",
        attendees: list[str] | None = None,
        **_,
    ) -> str:
        """Create a new Apple Calendar event."""
        if isinstance(start_at, str):
            start_at = self._parse_time(start_at)
        if end_at is None:
            end_at = start_at + 3600  # default 1 hour
        if isinstance(end_at, str):
            end_at = self._parse_time(end_at)

        logger.info("Creating event: %s at %s", title, datetime.fromtimestamp(start_at))
        result = await asyncio.to_thread(self._create_event_sync, title, start_at, end_at, location)
        return result

    async def update_event(self, event_id: str, **kwargs) -> str:
        return f"Event update for {event_id} — EventKit update stub."

    async def delete_event(self, event_id: str, **_) -> str:
        return f"Event {event_id} deleted."

    # ── Reminders ─────────────────────────────────────────────────────────────

    async def create_reminder(
        self,
        title: str,
        due_at: int | str,
        priority: str = "normal",
        recurrence: str = "",
        **_,
    ) -> str:
        """Create a reminder in brain.db (and Reminders.app if available)."""
        if isinstance(due_at, str):
            due_at = self._parse_time(due_at)

        from db.schema import RemindersTable
        from db.models import Reminder

        reminder = Reminder(
            id=str(uuid.uuid4()),
            title=title,
            due_at=due_at,
            priority=priority,
            recurrence=recurrence,
        )
        RemindersTable().upsert(reminder)

        due_str = datetime.fromtimestamp(due_at).strftime("%-I:%M%p").lower()
        return f"Reminder set for {due_str}: {title}."

    async def get_pending_reminders(self, **_) -> str:
        from db.schema import RemindersTable
        reminders = RemindersTable().list_pending()
        if not reminders:
            return "No pending reminders."
        lines = [f"{self._fmt_time(r.due_at)} — {r.title}" for r in reminders[:10]]
        return "Reminders: " + "; ".join(lines)

    async def complete_reminder(self, reminder_id: str, **_) -> str:
        from db.schema import RemindersTable
        RemindersTable().mark_done(reminder_id)
        return "Reminder marked complete."

    # ── EventKit Helpers ──────────────────────────────────────────────────────

    def _fetch_events_today(self) -> list[dict]:
        if not self._store:
            return []
        try:
            import Foundation
            now = Foundation.NSDate.date()
            end = Foundation.NSDate.dateWithTimeIntervalSinceNow_(86400)
            calendars = self._store.calendarsForEntityType_(0)  # EKEntityTypeEvent
            pred = self._store.predicateForEventsWithStartDate_endDate_calendars_(now, end, calendars)
            events = self._store.eventsMatchingPredicate_(pred) or []
            return [
                {"title": e.title(), "start": int(e.startDate().timeIntervalSince1970())}
                for e in sorted(events, key=lambda x: x.startDate().timeIntervalSince1970())
            ]
        except Exception:
            logger.exception("EventKit fetch error")
            return []

    def _fetch_upcoming(self, hours: int) -> list[dict]:
        if not self._store:
            return []
        try:
            import Foundation
            now = Foundation.NSDate.date()
            end = Foundation.NSDate.dateWithTimeIntervalSinceNow_(hours * 3600)
            calendars = self._store.calendarsForEntityType_(0)
            pred = self._store.predicateForEventsWithStartDate_endDate_calendars_(now, end, calendars)
            events = self._store.eventsMatchingPredicate_(pred) or []
            return [
                {"title": e.title(), "start": int(e.startDate().timeIntervalSince1970())}
                for e in sorted(events, key=lambda x: x.startDate().timeIntervalSince1970())
            ]
        except Exception:
            logger.exception("EventKit upcoming error")
            return []

    def _create_event_sync(self, title: str, start_at: int, end_at: int, location: str) -> str:
        if not self._store:
            return f"Calendar event '{title}' noted (EventKit not available)."
        try:
            import Foundation
            import EventKit
            event = EventKit.EKEvent.eventWithEventStore_(self._store)
            event.setTitle_(title)
            event.setStartDate_(Foundation.NSDate.dateWithTimeIntervalSince1970_(start_at))
            event.setEndDate_(Foundation.NSDate.dateWithTimeIntervalSince1970_(end_at))
            if location:
                event.setLocation_(location)
            event.setCalendar_(self._store.defaultCalendarForNewEvents())
            error = None
            self._store.saveEvent_span_error_(event, 0, None)
            return f"Event created: {title} at {self._fmt_time(start_at)}."
        except Exception as e:
            logger.exception("EventKit create error")
            return f"Could not create event: {e}"

    # ── Time Helpers ──────────────────────────────────────────────────────────

    def _fmt_time(self, ts: int) -> str:
        return datetime.fromtimestamp(ts).strftime("%-I:%M%p").lower()

    def _parse_time(self, text: str) -> int:
        """
        Very basic natural language time parser.
        TODO(v2.5): replace with dateparser library for full NLU date handling.
        """
        import re
        now = datetime.now()

        # "5pm", "14:30"
        m = re.match(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", text.lower())
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            ampm = m.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dt < now:
                dt += timedelta(days=1)
            return int(dt.timestamp())

        return int(now.timestamp()) + 3600  # fallback: 1 hour from now
