"""mobile_api/routes/calendar_routes.py — Calendar events endpoints."""

import time

from fastapi import APIRouter

from db.schema import CalendarEventsTable

router = APIRouter()
_calendar = CalendarEventsTable()


@router.get("")
async def upcoming_events(hours: int = 24):
    """Return calendar events in the next N hours."""
    now = int(time.time())
    to_ts = now + hours * 3600
    events = _calendar.list_upcoming(now, to_ts)
    return [_event_dict(e) for e in events]


def _event_dict(e) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "start_at": e.start_at,
        "end_at": e.end_at,
        "location": e.location,
        "attendees": e.attendees,
        "source": e.source,
        "alert_mins": e.alert_mins,
    }
