"""
orchestrator/manager.py — Agent Orchestrator

The heart of Jarvis's parallelism. Manages the full job registry,
spawns agents as asyncio tasks, enforces priority scheduling, and
publishes completion/failure events back to the Proactive Surface.

Subscribes to: job.created
Publishes:     job.completed, job.blocked, job.failed
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from config import AgentType, JobPriority, JobStatus, AGENT_TIMEOUT_SECS
from db.models import Job
from db.schema import JobsTable
from events.bus import bus, Event
from orchestrator.lifecycle import assert_transition
from orchestrator.agents.claude_code import ClaudeCodeAgent
from orchestrator.agents.shell import ShellAgent
from orchestrator.agents.file_ops import FileOpsAgent
from orchestrator.agents.browser import BrowserAgent

logger = logging.getLogger(__name__)

# Priority ordering for task scheduling
_PRIORITY_ORDER = {
    JobPriority.URGENT: 0,
    JobPriority.NORMAL: 1,
    JobPriority.BACKGROUND: 2,
}

_AGENT_REGISTRY = {
    AgentType.CLAUDE_CODE: ClaudeCodeAgent,
    AgentType.SHELL: ShellAgent,
    AgentType.FILE_OPS: FileOpsAgent,
    AgentType.BROWSER: BrowserAgent,
}


class AgentOrchestrator:
    """
    Manages the lifecycle of all background agents.

    - Maintains an in-memory job registry (mirrored to SQLite via JobsTable).
    - Spawns agents as asyncio tasks with isolated event loops.
    - Routes job.created events to the correct agent class.
    - Fires proactive surface events on completion/failure/block.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}       # job_id → Job
        self._tasks: dict[str, asyncio.Task] = {}  # job_id → asyncio.Task
        self._db = JobsTable()

        bus.on("job.created", self._on_job_created)
        logger.info("AgentOrchestrator ready")

    # ── Event Handlers ────────────────────────────────────────────────────────

    async def _on_job_created(self, event: Event) -> None:
        p = event.payload
        job = Job(
            id=str(uuid.uuid4()),
            title=p.get("title", "Untitled job"),
            intent=p.get("intent", ""),
            tool_type=p.get("tool_type", AgentType.SHELL),
            status=JobStatus.PENDING,
            priority=JobPriority(p.get("priority", "normal")),
            context_json=p.get("params", {}),
            created_at=int(time.time()),
        )
        self._jobs[job.id] = job
        self._db.upsert(job)
        logger.info("Job created: %s [%s]", job.title, job.id)

        # Schedule based on priority
        task = asyncio.create_task(
            self._run_agent(job),
            name=f"agent-{job.id}",
        )
        self._tasks[job.id] = task

    # ── Agent Execution ───────────────────────────────────────────────────────

    async def _run_agent(self, job: Job) -> None:
        """Spawn, run, and handle the outcome of a single agent."""
        agent_cls = _AGENT_REGISTRY.get(AgentType(job.tool_type))
        if agent_cls is None:
            await self._fail_job(job, f"Unknown agent type: {job.tool_type}")
            return

        agent = agent_cls(job)
        await self._transition(job, JobStatus.RUNNING)

        try:
            summary = await asyncio.wait_for(
                agent.run(),
                timeout=AGENT_TIMEOUT_SECS,
            )
            await self._complete_job(job, summary)

        except asyncio.TimeoutError:
            # Give agent a grace period before hard-failing
            await self._request_timeout_decision(job, agent)

        except asyncio.CancelledError:
            await self._transition(job, JobStatus.CANCELLED)
            logger.info("Job cancelled: %s", job.id)

        except Exception as e:
            await self._fail_job(job, str(e))

    # ── Job State Helpers ─────────────────────────────────────────────────────

    async def _transition(self, job: Job, status: JobStatus, **kwargs: Any) -> None:
        assert_transition(job.status, status)
        job.status = status
        for k, v in kwargs.items():
            setattr(job, k, v)
        self._db.upsert(job)

    async def _complete_job(self, job: Job, summary: str) -> None:
        await self._transition(
            job, JobStatus.DONE,
            summary=summary,
            completed_at=int(time.time()),
        )
        logger.info("Job done: %s — %s", job.title, summary[:60])
        await bus.publish(Event("job.completed", {
            "job_id": job.id,
            "title": job.title,
            "summary": summary,
            "priority": job.priority,
        }))

    async def _fail_job(self, job: Job, error: str) -> None:
        await self._transition(
            job, JobStatus.FAILED,
            error_detail=error,
            completed_at=int(time.time()),
        )
        logger.error("Job failed: %s — %s", job.title, error)
        await bus.publish(Event("job.failed", {
            "job_id": job.id,
            "title": job.title,
            "error": error,
        }))

    async def _request_timeout_decision(self, job: Job, agent: Any) -> None:
        """Surface a BLOCKED event when an agent exceeds its timeout."""
        await self._transition(job, JobStatus.BLOCKED)
        elapsed_mins = int(AGENT_TIMEOUT_SECS / 60)
        await bus.publish(Event("job.blocked", {
            "job_id": job.id,
            "title": job.title,
            "reason": f"Job has been running for {elapsed_mins} minutes. Continue or cancel?",
        }))

    # ── Status Query Interface ────────────────────────────────────────────────

    def list_active(self) -> list[Job]:
        return [j for j in self._jobs.values() if j.status == JobStatus.RUNNING]

    def list_all_today(self) -> list[Job]:
        cutoff = int(time.time()) - 86400
        return [j for j in self._jobs.values() if j.created_at >= cutoff]

    def find_by_title(self, query: str) -> Job | None:
        """Fuzzy match a job by title (case-insensitive substring)."""
        query = query.lower()
        for job in self._jobs.values():
            if query in job.title.lower():
                return job
        return None

    async def cancel_job(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False
