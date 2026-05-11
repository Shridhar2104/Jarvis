"""mobile_api/routes/jobs.py — Job management endpoints."""

import time

from fastapi import APIRouter, HTTPException

from db.schema import JobsTable
from events.bus import bus, Event

router = APIRouter()
_jobs = JobsTable()


@router.get("")
async def list_jobs(since_hours: int = 24):
    """List jobs created in the last N hours (default 24)."""
    since_ts = int(time.time()) - since_hours * 3600
    jobs = _jobs.list_since(since_ts)
    return [_job_dict(j) for j in jobs]


@router.get("/{job_id}")
async def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_dict(job)


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Publish a cancellation event; the orchestrator handles the actual cancel."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await bus.publish(Event("job.cancel_requested", {"job_id": job_id}))
    return {"status": "cancel_requested", "job_id": job_id}


def _job_dict(job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "intent": job.intent,
        "tool_type": job.tool_type,
        "status": job.status,
        "priority": job.priority,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "summary": job.summary,
        "error_detail": job.error_detail,
    }
