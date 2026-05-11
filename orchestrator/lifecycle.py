"""
orchestrator/lifecycle.py — Job lifecycle state machine

Valid transitions:
  PENDING   → RUNNING
  RUNNING   → DONE | FAILED | BLOCKED | CANCELLED
  BLOCKED   → RUNNING | CANCELLED
  DONE/FAILED/CANCELLED → (terminal — no further transitions)
"""

from config import JobStatus

VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING:   {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING:   {JobStatus.DONE, JobStatus.FAILED, JobStatus.BLOCKED, JobStatus.CANCELLED},
    JobStatus.BLOCKED:   {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.DONE:      set(),
    JobStatus.FAILED:    set(),
    JobStatus.CANCELLED: set(),
}


def can_transition(current: JobStatus, next_status: JobStatus) -> bool:
    return next_status in VALID_TRANSITIONS.get(current, set())


def assert_transition(current: JobStatus, next_status: JobStatus) -> None:
    if not can_transition(current, next_status):
        raise ValueError(
            f"Invalid job status transition: {current} → {next_status}"
        )
