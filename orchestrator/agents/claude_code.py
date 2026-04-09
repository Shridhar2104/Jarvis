"""
orchestrator/agents/claude_code.py — Claude Code CLI agent

Spawns a Claude Code session via CLI, monitors stdout for progress markers,
and detects completion. Runs in its own terminal session.

Usage:
    jarvis.launch_claude_code(
        repo_path   = "~/Desktop/src/my-app",
        goal        = "Scaffold the auth feature with JWT, login, logout, refresh",
        constraints = ["Do not modify database schema", "Use existing UserModel"]
    )

NOTE: Requires Claude Code CLI installed and authenticated.
      Jarvis validates this at startup and warns if missing.
"""

import asyncio
import shutil
import logging
from pathlib import Path

from orchestrator.agents.base import BaseAgent, AgentFailedError
from db.models import Job

logger = logging.getLogger(__name__)


def validate_claude_code_cli() -> bool:
    """Check that the Claude Code CLI is installed and on PATH."""
    return shutil.which("claude") is not None


class ClaudeCodeAgent(BaseAgent):
    """
    Delegates a coding task to Claude Code CLI.

    Params (from job.context_json):
        repo_path:   str  — path to the repository
        goal:        str  — natural language description of the task
        constraints: list[str] — hard constraints Claude Code must respect
    """

    async def run(self) -> str:
        if not validate_claude_code_cli():
            raise AgentFailedError(
                "Claude Code CLI not found. Install it and authenticate first."
            )

        ctx = self.job.context_json
        repo_path = Path(ctx.get("repo_path", ".")).expanduser()
        goal: str = ctx.get("goal", self.job.intent)
        constraints: list[str] = ctx.get("constraints", [])

        if not repo_path.exists():
            raise AgentFailedError(f"Repo path not found: {repo_path}")

        # Build the Claude Code prompt
        prompt = goal
        if constraints:
            constraint_block = "\n".join(f"- {c}" for c in constraints)
            prompt += f"\n\nConstraints:\n{constraint_block}"

        self._log(f"Starting Claude Code in: {repo_path}")
        self._log(f"Goal: {goal}")

        cmd = ["claude", "--print", "--dangerously-skip-permissions", prompt]

        rc, output = await self._stream_process(cmd, cwd=str(repo_path))

        if rc != 0:
            raise AgentFailedError(
                f"Claude Code exited with code {rc}. Log: {self._log_path}"
            )

        # Summarise modified files
        summary = await self._summarise_changes(repo_path)
        return summary or f"Task complete: {goal[:60]}"

    async def _summarise_changes(self, repo_path: Path) -> str:
        """Return a git diff --stat summary of what Claude Code changed."""
        try:
            rc, output = await self._stream_process(
                ["git", "diff", "--stat", "HEAD"],
                cwd=str(repo_path),
            )
            if output.strip():
                lines = output.strip().splitlines()
                return f"Done. {lines[-1]}"  # e.g. "3 files changed, 127 insertions"
        except Exception:
            logger.debug("Could not get git diff for %s", repo_path)
        return ""

    def get_session_log(self) -> str:
        """Return the last 50 lines of the agent's log."""
        if self._log_path.exists():
            lines = self._log_path.read_text().splitlines()
            return "\n".join(lines[-50:])
        return ""
