"""
skills/apps.py — Application control

Open, quit, and list running macOS applications via AppleScript / subprocess.
"""

import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)


class AppsSkill:
    async def open(self, app: str, **_) -> str:
        """Open an application by name."""
        logger.info("Opening app: %s", app)
        proc = await asyncio.create_subprocess_exec(
            "open", "-a", app,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return f"Could not open {app}: {stderr.decode().strip()}"
        return f"Opening {app}."

    async def quit(self, app: str, **_) -> str:
        """Quit an application by name via AppleScript."""
        logger.info("Quitting app: %s", app)
        script = f'tell application "{app}" to quit'
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return f"Could not quit {app}."
        return f"Closing {app}."

    async def list_running(self, **_) -> str:
        """List currently running applications."""
        script = 'tell application "System Events" to get name of every process where background only is false'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        apps = result.stdout.strip().split(", ")
        return "Running: " + ", ".join(apps[:10]) + ("…" if len(apps) > 10 else "")
