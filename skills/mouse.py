"""
skills/mouse.py — Mouse, keyboard, and screen automation via PyAutoGUI

Capabilities: click, type, hotkeys, screenshot, scroll.
Requires Accessibility permission granted in System Settings.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MouseSkill:
    def __init__(self) -> None:
        try:
            import pyautogui
            self._gui = pyautogui
            self._gui.FAILSAFE = True   # move mouse to corner to abort
        except ImportError:
            self._gui = None
            logger.warning("pyautogui not installed — MouseSkill unavailable")

    async def click(self, x: int, y: int, **_) -> str:
        if not self._gui:
            return "Mouse control unavailable."
        await asyncio.to_thread(self._gui.click, x, y)
        return f"Clicked at ({x}, {y})."

    async def type_text(self, text: str, interval: float = 0.05, **_) -> str:
        if not self._gui:
            return "Keyboard control unavailable."
        await asyncio.to_thread(self._gui.typewrite, text, interval=interval)
        return f"Typed: {text[:40]}"

    async def hotkey(self, *keys: str, **_) -> str:
        if not self._gui:
            return "Keyboard control unavailable."
        await asyncio.to_thread(self._gui.hotkey, *keys)
        return f"Hotkey: {'+'.join(keys)}"

    async def scroll(self, clicks: int = 3, direction: str = "down", **_) -> str:
        if not self._gui:
            return "Mouse control unavailable."
        amount = -clicks if direction == "down" else clicks
        await asyncio.to_thread(self._gui.scroll, amount)
        return f"Scrolled {direction} {clicks} clicks."

    async def screenshot(self, save_path: str = "~/Desktop", **_) -> str:
        if not self._gui:
            return "Screenshot unavailable."
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(save_path).expanduser() / f"screenshot_{ts}.png"
        img = await asyncio.to_thread(self._gui.screenshot)
        await asyncio.to_thread(img.save, str(path))
        return f"Screenshot saved: {path.name}"
