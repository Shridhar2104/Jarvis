"""
skills/system.py — System settings

Volume, brightness, WiFi, sleep, battery status via osascript / system_profiler.
"""

import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)


class SystemSkill:
    async def set_volume(self, level: int, **_) -> str:
        """Set volume 0–100."""
        level = max(0, min(100, int(level)))
        script = f"set volume output volume {level}"
        subprocess.run(["osascript", "-e", script])
        return f"Volume set to {level}%."

    async def get_volume(self, **_) -> str:
        result = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True,
        )
        return f"Volume is at {result.stdout.strip()}%."

    async def set_brightness(self, level: float, **_) -> str:
        """Set display brightness 0.0–1.0."""
        level = max(0.0, min(1.0, float(level)))
        script = f'tell application "System Events" to set brightness of display 1 to {level}'
        subprocess.run(["osascript", "-e", script])
        return f"Brightness set to {int(level * 100)}%."

    async def sleep(self, **_) -> str:
        subprocess.run(["pmset", "sleepnow"])
        return "Going to sleep."

    async def battery(self, **_) -> str:
        result = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True
        )
        lines = result.stdout.strip().splitlines()
        return lines[1].strip() if len(lines) > 1 else "Battery info unavailable."

    async def wifi_on(self, **_) -> str:
        subprocess.run(["networksetup", "-setairportpower", "en0", "on"])
        return "Wi-Fi turned on."

    async def wifi_off(self, **_) -> str:
        subprocess.run(["networksetup", "-setairportpower", "en0", "off"])
        return "Wi-Fi turned off."
