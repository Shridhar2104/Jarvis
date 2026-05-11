"""
skills/browser.py — Browser control

Open URLs, search Google, manage tabs.
Uses AppleScript to control the default browser.
"""

import asyncio
import logging
import urllib.parse

logger = logging.getLogger(__name__)


class BrowserSkill:
    async def open_url(self, url: str, **_) -> str:
        """Open a URL in the default browser."""
        if not url.startswith("http"):
            url = "https://" + url
        proc = await asyncio.create_subprocess_exec("open", url)
        await proc.communicate()
        return f"Opening {url}."

    async def search(self, query: str, **_) -> str:
        """Perform a Google search."""
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        return await self.open_url(url)

    async def new_tab(self, url: str = "about:blank", **_) -> str:
        """Open a new tab in Chrome."""
        script = f'tell application "Google Chrome" to open location "{url}"'
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        return "New tab opened."

    async def close_tab(self, **_) -> str:
        """Close the active tab in Chrome."""
        script = 'tell application "Google Chrome" to close active tab of front window'
        proc = await asyncio.create_subprocess_exec("osascript", "-e", script)
        await proc.communicate()
        return "Tab closed."
