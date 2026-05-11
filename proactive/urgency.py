"""
proactive/urgency.py — Urgency scoring engine

Scores incoming events 1–10 and assigns a UrgencyLevel.
Used by the Proactive Surface to decide whether to fire immediately
or queue during Focus Mode.

Scores:
  10 CRITICAL  Meeting in < 10 minutes
   9 URGENT    Agent BLOCKED (needs human input)
   8 URGENT    Agent FAILED | User-tagged urgent reminder
   5 NORMAL    Agent DONE | Standard reminder
   3 LOW       Routine nudge
   2 LOW       Health break nudge
"""

from dataclasses import dataclass

from config import UrgencyLevel, NudgeType


@dataclass
class UrgencyScore:
    score: int
    level: UrgencyLevel
    bypasses_focus: bool


_SCORE_TABLE: dict[str, UrgencyScore] = {
    "meeting_imminent":     UrgencyScore(10, UrgencyLevel.CRITICAL, True),
    "job.blocked":          UrgencyScore(9,  UrgencyLevel.URGENT,   True),
    "job.failed":           UrgencyScore(8,  UrgencyLevel.URGENT,   True),
    "reminder.urgent":      UrgencyScore(8,  UrgencyLevel.URGENT,   True),
    "job.completed":        UrgencyScore(5,  UrgencyLevel.NORMAL,   False),
    "reminder.normal":      UrgencyScore(5,  UrgencyLevel.NORMAL,   False),
    NudgeType.ROUTINE_MISS: UrgencyScore(3,  UrgencyLevel.LOW,      False),
    NudgeType.IDLE_TOO_LONG: UrgencyScore(3, UrgencyLevel.LOW,      False),
    NudgeType.GOAL_STALE:   UrgencyScore(3,  UrgencyLevel.LOW,      False),
    NudgeType.MEETING_PREP: UrgencyScore(8,  UrgencyLevel.URGENT,   True),
    NudgeType.HEALTH_BREAK: UrgencyScore(2,  UrgencyLevel.LOW,      False),
}

_DEFAULT = UrgencyScore(5, UrgencyLevel.NORMAL, False)


def score_urgency(event_type: str, payload: dict) -> UrgencyScore:
    """
    Assign an urgency score to an incoming event.

    Args:
        event_type: the bus topic (e.g. "job.completed", "reminder.triggered")
        payload:    the event payload dict
    """
    # Reminder urgency depends on the reminder's own priority field
    if event_type == "reminder.triggered":
        nudge_type = payload.get("nudge_type", "")
        priority = payload.get("priority", "normal")

        if nudge_type in _SCORE_TABLE:
            return _SCORE_TABLE[nudge_type]
        if priority == "urgent":
            return _SCORE_TABLE["reminder.urgent"]
        # meeting_prep nudge specifically always bypasses
        if nudge_type == NudgeType.MEETING_PREP:
            return _SCORE_TABLE[NudgeType.MEETING_PREP]
        return _SCORE_TABLE["reminder.normal"]

    return _SCORE_TABLE.get(event_type, _DEFAULT)
