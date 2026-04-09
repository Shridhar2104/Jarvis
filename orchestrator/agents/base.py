"""
orchestrator/agents/base.py — Abstract base class for all agents

Every agent:
  - Receives a Job at construction time
  - Implements run() → returns a completion summary string
  - Reports progress via _log(msg) which is streamed to the job log
  - Can set status to BLOCKED by raising AgentBlockedError
"""

import abc
import asyncio
import logging
from pathlib import Path

from config import DB_PATH
from db.models import Job

logger = logging.getLogger(__name__)


class AgentBlockedError(Exception):
    """Raise from run() to transition the job to BLOCKED status."""
    pass


class AgentFailedError(Exception):
    """Raise from run() to transition the job to FAILED status."""
    pass


class BaseAgent(abc.ABC):
    """
    Abstract base for all Jarvis agents.

    Subclasses must implement `run()`.
    """

    def __init__(self, job: Job) -> None:
        self.job = job
        self._log_path = DB_PATH.parent / "logs" / f"{job.id}.log"
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    @abc.abstractmethod
    async def run(self) -> str:
        """
        Execute the agent's task.

        Returns:
            A human-readable summary string Jarvis will speak on completion.

        Raises:
            AgentBlockedError: if human input is required to continue.
            AgentFailedError:  if the task cannot be completed.
        """
        ...

    def _log(self, message: str) -> None:
        """Append a progress line to the job's log file."""
        with self._log_path.open("a") as f:
            f.write(message + "\n")
        logger.debug("[%s] %s", self.job.id[:8], message)

    async def _stream_process(
        self,
        cmd: list[str],
        cwd: str | None = None,
    ) -> tuple[int, str]:
        """
        Run a subprocess and stream stdout/stderr to the job log.

        Returns:
            (return_code, combined_output)
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        output_lines: list[str] = []
        assert proc.stdout is not None

        async for line_bytes in proc.stdout:
            line = line_bytes.decode(errors="replace").rstrip()
            self._log(line)
            output_lines.append(line)

        return_code = await proc.wait()
        return return_code, "\n".join(output_lines)
