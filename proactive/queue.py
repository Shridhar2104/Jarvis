"""
proactive/queue.py — Notification queue

Holds events that are deferred during Focus Mode.
On focus exit, flushes in urgency order with smart batching.

- Items older than 2 hours are summarised in bulk, not individually announced.
- Related items are batched: "While you were focused, 3 things completed — ..."
"""

import logging
import time
from dataclasses import dataclass, field

from proactive.urgency import UrgencyScore

logger = logging.getLogger(__name__)

_OLD_ITEM_SECS = 2 * 3600  # 2 hours


@dataclass(order=True)
class QueuedItem:
    urgency_score: int          # Used for sort (higher = more urgent, sorted DESC)
    enqueued_at: int = field(compare=False)
    event_type: str = field(compare=False)
    payload: dict = field(compare=False, default_factory=dict)
    score: UrgencyScore = field(compare=False, default=None)


class NotificationQueue:
    """
    Priority queue for deferred notifications.
    Items are sorted by urgency score (descending) on flush.
    """

    def __init__(self) -> None:
        self._items: list[QueuedItem] = []

    def enqueue(self, event_type: str, payload: dict, score: UrgencyScore) -> None:
        item = QueuedItem(
            urgency_score=score.score,
            enqueued_at=int(time.time()),
            event_type=event_type,
            payload=payload,
            score=score,
        )
        self._items.append(item)
        logger.debug("Queued: %s (score=%d)", event_type, score.score)

    def flush(self) -> list[QueuedItem]:
        """
        Return all queued items sorted by urgency (highest first).
        Clears the queue.
        """
        sorted_items = sorted(self._items, key=lambda x: x.urgency_score, reverse=True)
        self._items = []
        return sorted_items

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def count(self) -> int:
        return len(self._items)

    def build_summary(self) -> str:
        """
        Build a batched spoken summary of all queued items.
        Groups by event type; old items collapsed.
        """
        if not self._items:
            return "Nothing queued while you were focused, sir."

        now = int(time.time())
        items = sorted(self._items, key=lambda x: x.urgency_score, reverse=True)

        parts = []
        completed_jobs = [i for i in items if i.event_type == "job.completed"]
        reminders = [i for i in items if i.event_type == "reminder.triggered"]
        other = [i for i in items if i.event_type not in ("job.completed", "reminder.triggered")]

        if completed_jobs:
            titles = [i.payload.get("title", "a task") for i in completed_jobs]
            if len(titles) == 1:
                parts.append(f"{titles[0]} completed")
            else:
                parts.append(f"{len(titles)} tasks completed: {', '.join(titles)}")

        for r in reminders:
            age = now - r.enqueued_at
            title = r.payload.get("title", "a reminder")
            if age > _OLD_ITEM_SECS:
                parts.append(f"older reminder: {title}")
            else:
                parts.append(title)

        for o in other:
            parts.append(o.event_type.replace(".", " "))

        if len(parts) == 1:
            return f"While you were focused — {parts[0]}."
        summary = "; ".join(parts[:-1]) + f"; and {parts[-1]}"
        return f"While you were focused — {summary}."
