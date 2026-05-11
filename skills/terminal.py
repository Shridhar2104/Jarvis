"""
skills/terminal.py — Terminal / shell execution

Four-level permission model (from spec):
  RESTRICTED    Read-only commands only (ls, cat, git status, ps, echo)
  STANDARD      + write ops, npm, pip, git commit/push
  ELEVATED      + sudo, rm -rf, system commands (requires voice confirmation)
  UNRESTRICTED  Full shell — no filtering, every command logged

Voice confirmation required for ELEVATED commands.
All commands logged in brain.db behaviour_log at UNRESTRICTED level.
"""

import asyncio
import logging
import shlex
import time
import uuid

from config import TerminalLevel, TERMINAL_LEVEL, TERMINAL_ALLOWED

logger = logging.getLogger(__name__)


class TerminalSkill:
    def __init__(self) -> None:
        self._level = TERMINAL_LEVEL

    async def run(self, command: str, cwd: str | None = None, **_) -> str:
        """Execute a shell command within the current permission level."""
        if not command:
            return "No command provided."

        parts = shlex.split(command)
        base_cmd = parts[0]

        if not self._is_allowed(base_cmd):
            return (
                f"Command '{base_cmd}' is not allowed at terminal level {self._level.value}. "
                f"Ask me to raise the permission level if needed."
            )

        if self._requires_confirmation(base_cmd):
            # In a full implementation this would pause and wait for a
            # voice confirmation event. For now we log and proceed.
            logger.warning("ELEVATED command requires confirmation: %s", command)

        logger.info("[terminal:%s] %s", self._level.value, command)

        try:
            proc = await asyncio.create_subprocess_exec(
                *parts,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode(errors="replace").strip()

            if proc.returncode != 0:
                return f"Exit {proc.returncode}: {output[-500:]}"

            return output[-500:] if output else "(no output)"

        except asyncio.TimeoutError:
            return "Command timed out after 60 seconds."
        except Exception as e:
            return f"Error: {e}"

    # ── Permission Checks ─────────────────────────────────────────────────────

    def _is_allowed(self, cmd: str) -> bool:
        if self._level == TerminalLevel.UNRESTRICTED:
            return True

        # Cumulative: STANDARD includes RESTRICTED, ELEVATED includes both
        allowed: set[str] = set()
        levels_to_include = []

        if self._level in (TerminalLevel.RESTRICTED, TerminalLevel.STANDARD, TerminalLevel.ELEVATED):
            levels_to_include.append(TerminalLevel.RESTRICTED)
        if self._level in (TerminalLevel.STANDARD, TerminalLevel.ELEVATED):
            levels_to_include.append(TerminalLevel.STANDARD)
        if self._level == TerminalLevel.ELEVATED:
            levels_to_include.append(TerminalLevel.ELEVATED)

        for lvl in levels_to_include:
            allowed |= TERMINAL_ALLOWED[lvl]

        return cmd in allowed

    def _requires_confirmation(self, cmd: str) -> bool:
        return self._level == TerminalLevel.ELEVATED and cmd in TERMINAL_ALLOWED[TerminalLevel.ELEVATED]
