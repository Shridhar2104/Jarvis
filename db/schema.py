"""
db/schema.py — SQLite table definitions and CRUD helpers for brain.db

All tables are created at startup via init_db().
Each Table class provides upsert / get / list / delete helpers.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Generator

from config import DB_PATH
from db.models import Job, Reminder, Routine, CalendarEvent, BehaviourEvent, Nudge

# ── DDL ───────────────────────────────────────────────────────────────────────

_CREATE_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    intent       TEXT NOT NULL,
    tool_type    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'PENDING',
    priority     TEXT NOT NULL DEFAULT 'normal',
    context_json TEXT NOT NULL DEFAULT '{}',
    created_at   INTEGER NOT NULL,
    started_at   INTEGER NOT NULL DEFAULT 0,
    completed_at INTEGER NOT NULL DEFAULT 0,
    summary      TEXT NOT NULL DEFAULT '',
    error_detail TEXT NOT NULL DEFAULT '',
    notified     INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_REMINDERS = """
CREATE TABLE IF NOT EXISTS reminders (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    due_at      INTEGER NOT NULL,
    recurrence  TEXT NOT NULL DEFAULT '',
    priority    TEXT NOT NULL DEFAULT 'normal',
    context     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    notified_at INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_CALENDAR_EVENTS = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    start_at   INTEGER NOT NULL,
    end_at     INTEGER NOT NULL,
    location   TEXT NOT NULL DEFAULT '',
    attendees  TEXT NOT NULL DEFAULT '[]',
    source     TEXT NOT NULL DEFAULT 'apple_calendar',
    alert_mins INTEGER NOT NULL DEFAULT 10
);
"""

_CREATE_ROUTINES = """
CREATE TABLE IF NOT EXISTS routines (
    id           TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    time_pattern TEXT NOT NULL,
    days_active  TEXT NOT NULL DEFAULT '[]',
    confidence   REAL NOT NULL DEFAULT 0.0,
    source       TEXT NOT NULL DEFAULT 'learned',
    last_seen    INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_BEHAVIOUR_LOG = """
CREATE TABLE IF NOT EXISTS behaviour_log (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    recorded_at INTEGER NOT NULL
);
"""

_CREATE_NUDGES = """
CREATE TABLE IF NOT EXISTS nudges (
    id            TEXT PRIMARY KEY,
    trigger_type  TEXT NOT NULL,
    message       TEXT NOT NULL,
    fired_at      INTEGER NOT NULL DEFAULT 0,
    user_response TEXT NOT NULL DEFAULT ''
);
"""

ALL_DDL = [
    _CREATE_JOBS,
    _CREATE_REMINDERS,
    _CREATE_CALENDAR_EVENTS,
    _CREATE_ROUTINES,
    _CREATE_BEHAVIOUR_LOG,
    _CREATE_NUDGES,
]


# ── Connection ────────────────────────────────────────────────────────────────

@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    with _conn() as con:
        for ddl in ALL_DDL:
            con.execute(ddl)


# ── Table Helpers ─────────────────────────────────────────────────────────────

class JobsTable:
    def upsert(self, job: Job) -> None:
        with _conn() as con:
            con.execute("""
                INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    summary=excluded.summary,
                    error_detail=excluded.error_detail,
                    notified=excluded.notified
            """, (
                job.id, job.title, job.intent, job.tool_type,
                job.status, job.priority, job.context_str(),
                job.created_at, job.started_at, job.completed_at,
                job.summary, job.error_detail, job.notified,
            ))

    def get(self, job_id: str) -> Job | None:
        with _conn() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def list_since(self, since_ts: int) -> list[Job]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM jobs WHERE created_at >= ? ORDER BY created_at DESC", (since_ts,)
            ).fetchall()
        return [_row_to_job(r) for r in rows]

    def purge_older_than(self, days: int) -> None:
        cutoff = int(time.time()) - days * 86400
        with _conn() as con:
            con.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))


class RemindersTable:
    def upsert(self, r: Reminder) -> None:
        with _conn() as con:
            con.execute("""
                INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status, notified_at=excluded.notified_at
            """, (r.id, r.title, r.due_at, r.recurrence, r.priority, r.context, r.status, r.notified_at))

    def list_pending(self) -> list[Reminder]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM reminders WHERE status='pending' ORDER BY due_at"
            ).fetchall()
        return [_row_to_reminder(r) for r in rows]

    def mark_done(self, reminder_id: str) -> None:
        with _conn() as con:
            con.execute("UPDATE reminders SET status='done' WHERE id=?", (reminder_id,))


class RoutinesTable:
    def upsert(self, r: Routine) -> None:
        with _conn() as con:
            con.execute("""
                INSERT INTO routines VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    confidence=excluded.confidence,
                    last_seen=excluded.last_seen,
                    source=excluded.source
            """, (r.id, r.label, r.time_pattern, r.days_str(), r.confidence, r.source, r.last_seen))

    def list_confirmed(self) -> list[Routine]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM routines WHERE source IN ('user_confirmed','user_defined')"
            ).fetchall()
        return [_row_to_routine(r) for r in rows]

    def list_all(self) -> list[Routine]:
        with _conn() as con:
            rows = con.execute("SELECT * FROM routines ORDER BY confidence DESC").fetchall()
        return [_row_to_routine(r) for r in rows]


class CalendarEventsTable:
    def upsert(self, e: CalendarEvent) -> None:
        with _conn() as con:
            con.execute("""
                INSERT INTO calendar_events VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title, start_at=excluded.start_at,
                    end_at=excluded.end_at, location=excluded.location,
                    attendees=excluded.attendees, alert_mins=excluded.alert_mins
            """, (e.id, e.title, e.start_at, e.end_at, e.location, e.attendees_str(), e.source, e.alert_mins))

    def list_upcoming(self, from_ts: int, to_ts: int) -> list[CalendarEvent]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM calendar_events WHERE start_at BETWEEN ? AND ? ORDER BY start_at",
                (from_ts, to_ts),
            ).fetchall()
        return [_row_to_cal_event(r) for r in rows]


class BehaviourLogTable:
    def insert(self, e: BehaviourEvent) -> None:
        with _conn() as con:
            con.execute(
                "INSERT INTO behaviour_log VALUES (?,?,?,?)",
                (e.id, e.event_type, e.payload_str(), e.recorded_at),
            )

    def list_since(self, since_ts: int) -> list[BehaviourEvent]:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM behaviour_log WHERE recorded_at >= ? ORDER BY recorded_at",
                (since_ts,),
            ).fetchall()
        return [_row_to_behaviour(r) for r in rows]

    def purge_older_than(self, days: int) -> None:
        cutoff = int(time.time()) - days * 86400
        with _conn() as con:
            con.execute("DELETE FROM behaviour_log WHERE recorded_at < ?", (cutoff,))

    def purge_all(self) -> None:
        with _conn() as con:
            con.execute("DELETE FROM behaviour_log")


class NudgesTable:
    def insert(self, n: Nudge) -> None:
        with _conn() as con:
            con.execute(
                "INSERT INTO nudges VALUES (?,?,?,?,?)",
                (n.id, n.trigger_type, n.message, n.fired_at, n.user_response),
            )

    def update_response(self, nudge_id: str, response: str) -> None:
        with _conn() as con:
            con.execute(
                "UPDATE nudges SET user_response=? WHERE id=?", (response, nudge_id)
            )


# ── Row Mappers ───────────────────────────────────────────────────────────────

def _row_to_job(r: sqlite3.Row) -> Job:
    from config import JobStatus, JobPriority
    return Job(
        id=r["id"], title=r["title"], intent=r["intent"],
        tool_type=r["tool_type"], status=JobStatus(r["status"]),
        priority=JobPriority(r["priority"]),
        context_json=json.loads(r["context_json"] or "{}"),
        created_at=r["created_at"], started_at=r["started_at"],
        completed_at=r["completed_at"], summary=r["summary"],
        error_detail=r["error_detail"], notified=r["notified"],
    )

def _row_to_reminder(r: sqlite3.Row) -> Reminder:
    return Reminder(
        id=r["id"], title=r["title"], due_at=r["due_at"],
        recurrence=r["recurrence"], priority=r["priority"],
        context=r["context"], status=r["status"], notified_at=r["notified_at"],
    )

def _row_to_routine(r: sqlite3.Row) -> Routine:
    return Routine(
        id=r["id"], label=r["label"], time_pattern=r["time_pattern"],
        days_active=json.loads(r["days_active"] or "[]"),
        confidence=r["confidence"], source=r["source"], last_seen=r["last_seen"],
    )

def _row_to_cal_event(r: sqlite3.Row) -> CalendarEvent:
    return CalendarEvent(
        id=r["id"], title=r["title"], start_at=r["start_at"], end_at=r["end_at"],
        location=r["location"], attendees=json.loads(r["attendees"] or "[]"),
        source=r["source"], alert_mins=r["alert_mins"],
    )

def _row_to_behaviour(r: sqlite3.Row) -> BehaviourEvent:
    return BehaviourEvent(
        id=r["id"], event_type=r["event_type"],
        payload=json.loads(r["payload"] or "{}"),
        recorded_at=r["recorded_at"],
    )
