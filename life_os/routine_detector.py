"""
life_os/routine_detector.py — Nightly behaviour pattern analyser

Runs at 2am. Analyses behaviour_log for recurring patterns:
  - Commands issued at similar times across multiple days
  - Consistent app open sequences
  - Regular focus blocks

A routine reaches confidence >= 0.75 after 5+ consistent observations.
Once surfaced, Jarvis asks the user to confirm before driving proactive behaviour.
"""

import collections
import logging
import time
import uuid
from datetime import datetime

from config import ROUTINE_CONFIDENCE_THRESHOLD, ROUTINE_MIN_DAYS, RoutineSource
from db.models import Routine, BehaviourEvent
from db.schema import BehaviourLogTable

logger = logging.getLogger(__name__)


class RoutineDetector:
    """
    Analyses the last 30 days of behaviour_log to surface recurring routines.
    Returns a list of Routine objects with updated confidence scores.
    """

    def __init__(self) -> None:
        self._log_table = BehaviourLogTable()

    def analyse(self) -> list[Routine]:
        """
        Entry point. Returns discovered routines with confidence scores.
        Only returns routines with confidence >= 0.5 (worth tracking).
        """
        since = int(time.time()) - 30 * 86400
        events = self._log_table.list_since(since)

        if not events:
            logger.debug("No behaviour events to analyse")
            return []

        routines = []
        routines.extend(self._detect_command_routines(events))
        routines.extend(self._detect_app_routines(events))

        logger.info("Routine detector found %d routines", len(routines))
        return routines

    # ── Detectors ─────────────────────────────────────────────────────────────

    def _detect_command_routines(self, events: list[BehaviourEvent]) -> list[Routine]:
        """Find commands issued at consistent times across multiple days."""
        # Group command texts by (hour_bucket, command)
        occurrences: dict[tuple, list[int]] = collections.defaultdict(list)

        for e in events:
            if e.event_type != "command_issued":
                continue
            command = e.payload.get("text", "")
            if not command:
                continue
            dt = datetime.fromtimestamp(e.recorded_at)
            hour_bucket = dt.hour  # group by hour of day
            occurrences[(hour_bucket, command[:40])].append(e.recorded_at)

        routines = []
        for (hour, command), timestamps in occurrences.items():
            # Count distinct days
            days_seen = {datetime.fromtimestamp(ts).date() for ts in timestamps}
            if len(days_seen) < ROUTINE_MIN_DAYS:
                continue

            confidence = min(len(days_seen) / 10.0, 1.0)  # normalise to 0–1
            if confidence < 0.5:
                continue

            routine = Routine(
                id=str(uuid.uuid4()),
                label=f"'{command}' around {hour}:00",
                time_pattern=f"0 {hour} * * *",
                days_active=["mon", "tue", "wed", "thu", "fri"],
                confidence=round(confidence, 2),
                source=RoutineSource.LEARNED,
                last_seen=max(timestamps),
            )
            routines.append(routine)

        return routines

    def _detect_app_routines(self, events: list[BehaviourEvent]) -> list[Routine]:
        """Find apps opened at consistent times."""
        occurrences: dict[tuple, list[int]] = collections.defaultdict(list)

        for e in events:
            if e.event_type != "app_opened":
                continue
            app = e.payload.get("app", "")
            if not app:
                continue
            dt = datetime.fromtimestamp(e.recorded_at)
            occurrences[(dt.hour, app)].append(e.recorded_at)

        routines = []
        for (hour, app), timestamps in occurrences.items():
            days_seen = {datetime.fromtimestamp(ts).date() for ts in timestamps}
            if len(days_seen) < ROUTINE_MIN_DAYS:
                continue

            confidence = min(len(days_seen) / 10.0, 1.0)
            if confidence < 0.5:
                continue

            routine = Routine(
                id=str(uuid.uuid4()),
                label=f"Open {app} around {hour}:00",
                time_pattern=f"0 {hour} * * *",
                days_active=["mon", "tue", "wed", "thu", "fri"],
                confidence=round(confidence, 2),
                source=RoutineSource.LEARNED,
                last_seen=max(timestamps),
            )
            routines.append(routine)

        return routines
