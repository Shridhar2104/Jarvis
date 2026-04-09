"""
db/models.py — Typed dataclasses for all brain.db rows

These are plain Python dataclasses — no ORM magic.
The schema.py layer handles all SQLite I/O.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from config import JobStatus, JobPriority, AgentType, NudgeType, RoutineSource, BehaviourEventType


@dataclass
class Job:
    id: str
    title: str
    intent: str
    tool_type: str                        # AgentType value
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    context_json: dict = field(default_factory=dict)
    created_at: int = 0
    started_at: int = 0
    completed_at: int = 0
    summary: str = ""
    error_detail: str = ""
    notified: int = 0                     # 1 once user has been informed

    def context_str(self) -> str:
        return json.dumps(self.context_json)


@dataclass
class Reminder:
    id: str
    title: str
    due_at: int                           # Unix timestamp
    recurrence: str = ""                  # NULL | 'daily' | 'weekly' | cron expr
    priority: str = "normal"             # urgent | normal
    context: str = ""                     # optional: linked job_id or calendar_event_id
    status: str = "pending"              # pending | snoozed | done | dismissed
    notified_at: int = 0


@dataclass
class Routine:
    id: str
    label: str
    time_pattern: str                     # cron: '0 9 * * 1-5'
    days_active: list[str] = field(default_factory=list)  # ['mon','tue',...]
    confidence: float = 0.0              # 0.0–1.0
    source: str = RoutineSource.LEARNED
    last_seen: int = 0

    def days_str(self) -> str:
        return json.dumps(self.days_active)


@dataclass
class CalendarEvent:
    id: str
    title: str
    start_at: int
    end_at: int
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    source: str = "apple_calendar"       # apple_calendar | user_defined
    alert_mins: int = 10

    def attendees_str(self) -> str:
        return json.dumps(self.attendees)


@dataclass
class BehaviourEvent:
    id: str
    event_type: str                       # BehaviourEventType value
    payload: dict = field(default_factory=dict)
    recorded_at: int = 0

    def payload_str(self) -> str:
        return json.dumps(self.payload)


@dataclass
class Nudge:
    id: str
    trigger_type: str                     # NudgeType value
    message: str
    fired_at: int = 0
    user_response: str = ""              # acknowledged | dismissed | snoozed
