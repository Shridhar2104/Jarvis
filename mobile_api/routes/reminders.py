"""mobile_api/routes/reminders.py — Reminders endpoints."""

import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.schema import RemindersTable
from db.models import Reminder

router = APIRouter()
_reminders = RemindersTable()


class CreateReminderRequest(BaseModel):
    title: str
    due_at: int           # unix timestamp
    priority: str = "normal"
    context: str = ""


@router.get("")
async def list_reminders():
    reminders = _reminders.list_pending()
    return [_reminder_dict(r) for r in reminders]


@router.post("")
async def create_reminder(req: CreateReminderRequest):
    reminder = Reminder(
        id=str(uuid.uuid4()),
        title=req.title,
        due_at=req.due_at,
        recurrence="",
        priority=req.priority,
        context=req.context,
        status="pending",
        notified_at=0,
    )
    _reminders.upsert(reminder)
    return _reminder_dict(reminder)


@router.delete("/{reminder_id}")
async def dismiss_reminder(reminder_id: str):
    _reminders.mark_done(reminder_id)
    return {"status": "dismissed", "id": reminder_id}


def _reminder_dict(r) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "due_at": r.due_at,
        "priority": r.priority,
        "context": r.context,
        "status": r.status,
    }
