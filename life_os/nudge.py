"""
life_os/nudge.py — Nudge engine

Evaluates trigger conditions and returns a Nudge to fire, or None.

Nudge types (from spec):
  routine_miss   — Expected routine not seen +30 mins past expected time
  idle_too_long  — No input > 90 minutes
  goal_stale     — Linked job untouched > 48 hours
  health_break   — Continuous focus > 90 minutes
  meeting_prep   — Calendar event within 15 minutes

WARNING: Only meeting_prep nudges bypass Focus Mode.
         All others must be queued if Focus Mode is active.
"""

import logging
import time
import uuid
from datetime import datetime

from config import (
    NUDGE_IDLE_MINS, NUDGE_GOAL_STALE_HOURS, NUDGE_HEALTH_BREAK_MINS,
    NUDGE_MEETING_PREP_MINS, NUDGE_ROUTINE_MISS_MINS, NudgeType, JobStatus,
)
from db.models import Nudge
from db.schema import BehaviourLogTable, JobsTable, CalendarEventsTable, RoutinesTable

logger = logging.getLogger(__name__)


class NudgeEngine:
    """
    Evaluates all nudge trigger conditions and returns the highest-priority
    nudge to fire, or None if no conditions are met.

    Called every 5 minutes by the LifeOSEngine nudge loop.
    """

    def __init__(self) -> None:
        self._behaviour = BehaviourLogTable()
        self._jobs = JobsTable()
        self._calendar = CalendarEventsTable()
        self._routines = RoutinesTable()
        self._last_nudge_type: str = ""

    async def check(self) -> Nudge | None:
        """
        Evaluate all triggers. Returns the first applicable Nudge or None.
        Priority order: meeting_prep > routine_miss > goal_stale > health_break > idle_too_long
        """
        now = int(time.time())

        nudge = self._check_meeting_prep(now)
        if nudge:
            return nudge

        nudge = self._check_routine_miss(now)
        if nudge:
            return nudge

        nudge = self._check_goal_stale(now)
        if nudge:
            return nudge

        nudge = self._check_health_break(now)
        if nudge:
            return nudge

        nudge = self._check_idle(now)
        if nudge:
            return nudge

        return None

    # ── Trigger Checks ────────────────────────────────────────────────────────

    def _check_meeting_prep(self, now: int) -> Nudge | None:
        lookahead = now + NUDGE_MEETING_PREP_MINS * 60
        upcoming = self._calendar.list_upcoming(now, lookahead)
        if upcoming:
            event = upcoming[0]
            mins_away = max(1, (event.start_at - now) // 60)
            return self._make_nudge(
                NudgeType.MEETING_PREP,
                f"Your {self._format_time(event.start_at)} is in {mins_away} minutes, sir.",
            )
        return None

    def _check_routine_miss(self, now: int) -> Nudge | None:
        routines = self._routines.list_confirmed()
        current_hour = datetime.now().hour
        for routine in routines:
            # Simple check: routine expected this hour but not yet seen today
            expected_hour = self._cron_hour(routine.time_pattern)
            if expected_hour is None:
                continue
            if current_hour == expected_hour + 1:  # one hour past expected
                # Check if it was actually triggered today
                today_start = now - (now % 86400)
                recent = self._behaviour.list_since(today_start)
                seen_today = any(
                    routine.label.lower() in (e.payload.get("text", "").lower())
                    for e in recent
                )
                if not seen_today:
                    return self._make_nudge(
                        NudgeType.ROUTINE_MISS,
                        f"You usually {routine.label.lower()}, sir. Want me to handle it?",
                    )
        return None

    def _check_goal_stale(self, now: int) -> Nudge | None:
        cutoff = now - NUDGE_GOAL_STALE_HOURS * 3600
        recent_jobs = self._jobs.list_since(cutoff)
        running_untouched = [
            j for j in recent_jobs
            if j.status == JobStatus.RUNNING and j.started_at < cutoff
        ]
        if running_untouched:
            job = running_untouched[0]
            hours = (now - job.started_at) // 3600
            return self._make_nudge(
                NudgeType.GOAL_STALE,
                f"The '{job.title}' task hasn't had activity in {hours} hours, sir.",
            )
        return None

    def _check_health_break(self, now: int) -> Nudge | None:
        since = now - NUDGE_HEALTH_BREAK_MINS * 60
        recent = self._behaviour.list_since(since)
        # If there has been continuous activity with no idle gaps, suggest a break
        if len(recent) >= 10:
            return self._make_nudge(
                NudgeType.HEALTH_BREAK,
                "You've been at it for a while. Step away for a bit?",
            )
        return None

    def _check_idle(self, now: int) -> Nudge | None:
        since = now - NUDGE_IDLE_MINS * 60
        recent = self._behaviour.list_since(since)
        if not recent:
            return self._make_nudge(
                NudgeType.IDLE_TOO_LONG,
                "Been quiet for a while, sir. Anything I can move forward?",
            )
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_nudge(self, trigger_type: NudgeType, message: str) -> Nudge:
        return Nudge(
            id=str(uuid.uuid4()),
            trigger_type=trigger_type.value,
            message=message,
            fired_at=int(time.time()),
        )

    def _format_time(self, ts: int) -> str:
        return datetime.fromtimestamp(ts).strftime("%-I:%M%p").lower()

    def _cron_hour(self, pattern: str) -> int | None:
        """Extract the hour from a simple cron pattern like '0 9 * * 1-5'."""
        try:
            parts = pattern.split()
            return int(parts[1])
        except Exception:
            return None
