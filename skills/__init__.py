from .apps import AppsSkill
from .browser import BrowserSkill
from .files import FilesSkill
from .system import SystemSkill
from .mouse import MouseSkill
from .terminal import TerminalSkill
from .claude_code import ClaudeCodeSkill
from .calendar import CalendarSkill

__all__ = [
    "AppsSkill", "BrowserSkill", "FilesSkill", "SystemSkill",
    "MouseSkill", "TerminalSkill", "ClaudeCodeSkill", "CalendarSkill",
]


def build_skill_registry() -> dict:
    """Return the default skill registry for CommandRouter."""
    return {
        "apps":        AppsSkill(),
        "browser":     BrowserSkill(),
        "files":       FilesSkill(),
        "system":      SystemSkill(),
        "mouse":       MouseSkill(),
        "terminal":    TerminalSkill(),
        "claude_code": ClaudeCodeSkill(),
        "calendar":    CalendarSkill(),
    }
