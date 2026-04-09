"""
skills/claude_code.py — Claude Code Launcher

Primary integration point between the CommandRouter and the
Agent Orchestrator's ClaudeCodeAgent type.

This skill handles *quick queries* about Claude Code sessions
(get status, list sessions, get log tail). Long-running spawns
go through the Agent Orchestrator via brain/router.py → job.created.

Validates Claude Code CLI at startup and warns if missing.
"""

import asyncio
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _cli_available() -> bool:
    return shutil.which("claude") is not None


class ClaudeCodeSkill:
    def __init__(self) -> None:
        if not _cli_available():
            logger.warning(
                "Claude Code CLI not found on PATH. "
                "Install it from https://claude.ai/code and authenticate."
            )

    async def launch(self, repo_path: str, goal: str, constraints: list[str] | None = None, **_) -> str:
        """
        Initiates a Claude Code agent job via the Agent Orchestrator.

        In normal operation this is called from the CommandRouter when
        is_long_running=True. Exposed here for direct skill invocation.
        """
        if not _cli_available():
            return "Claude Code CLI is not installed. I can't start that job."

        from events.bus import bus, Event
        await bus.publish(Event("job.created", {
            "tool_type": "claude_code",
            "title": goal[:80],
            "intent": goal,
            "params": {
                "repo_path": repo_path,
                "goal": goal,
                "constraints": constraints or [],
            },
            "priority": "normal",
        }))
        return f"On it, sir. Starting work on: {goal[:60]}"

    async def status(self, **_) -> str:
        """Quick status check — returns CLI version."""
        if not _cli_available():
            return "Claude Code CLI not available."
        proc = await asyncio.create_subprocess_exec(
            "claude", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        return f"Claude Code CLI: {stdout.decode().strip()}"
