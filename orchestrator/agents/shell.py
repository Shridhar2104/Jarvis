"""
orchestrator/agents/shell.py — Long-running shell agent

For build pipelines, test suites, data processing scripts.
No 15-second timeout — ceiling is AGENT_TIMEOUT_SECS (default 30 min).

Params (from job.context_json):
    command:  str | list[str]  — shell command to run
    cwd:      str              — working directory (optional)
"""

import asyncio
import shlex

from orchestrator.agents.base import BaseAgent, AgentFailedError
from db.models import Job


class ShellAgent(BaseAgent):
    """Runs a long-lived shell command and reports stdout summary on completion."""

    async def run(self) -> str:
        ctx = self.job.context_json
        command = ctx.get("command", "")
        cwd = ctx.get("cwd", None)

        if not command:
            raise AgentFailedError("ShellAgent: no command provided in job context.")

        # Support both string and list commands
        if isinstance(command, str):
            cmd = shlex.split(command)
        else:
            cmd = list(command)

        self._log(f"Running: {' '.join(cmd)}")

        rc, output = await self._stream_process(cmd, cwd=cwd)

        lines = [l for l in output.splitlines() if l.strip()]
        tail = "\n".join(lines[-5:]) if lines else "(no output)"

        if rc != 0:
            raise AgentFailedError(
                f"Command exited with code {rc}. Last output:\n{tail}"
            )

        return f"Done. Exit 0. Last output: {lines[-1][:120] if lines else 'none'}"
