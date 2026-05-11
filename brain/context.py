"""
brain/context.py — Ambient context for JARVIS situational awareness

Gets the frontmost macOS app so JARVIS can make witty, contextual remarks.
"""

import subprocess
import logging

logger = logging.getLogger(__name__)


def get_active_app() -> str:
    """Returns the name of the frontmost macOS application, or empty string."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_context_line() -> str:
    """One-line context string for injection into the LLM prompt."""
    app = get_active_app()
    return f"User is currently in: {app}" if app else ""
