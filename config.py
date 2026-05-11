"""
config.py — Central configuration for J.A.R.V.I.S
Loads environment variables, defines constants and enums used across all subsystems.
"""

import os
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]
OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL") or None  # set for DeepSeek etc.
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Core ──────────────────────────────────────────────────────────────────────
WAKE_WORD: str = os.getenv("JARVIS_WAKE_WORD", "jarvis").lower()
LLM_MODEL: str = os.getenv("JARVIS_MODEL", "gpt-4o")
TTS_VOICE: str = os.getenv("JARVIS_VOICE", "samantha")
STT_BACKEND: str = os.getenv("JARVIS_STT", "google")  # google | whisper

# ── Database ──────────────────────────────────────────────────────────────────
_default_db = Path.home() / "Library" / "Application Support" / "Jarvis" / "brain.db"
DB_PATH: Path = Path(os.getenv("JARVIS_DB_PATH", str(_default_db)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Agent Orchestrator ────────────────────────────────────────────────────────
AGENT_TIMEOUT_SECS: int = int(os.getenv("JARVIS_AGENT_TIMEOUT", "1800"))  # 30 min
AGENT_GRACE_PERIOD_SECS: int = 300  # 5 min grace before FAILED

# ── Nudge System ─────────────────────────────────────────────────────────────
NUDGE_ENABLED: bool = os.getenv("JARVIS_NUDGE_ENABLED", "true").lower() == "true"
NUDGE_ROUTINE_MISS_MINS: int = 30
NUDGE_IDLE_MINS: int = 90
NUDGE_GOAL_STALE_HOURS: int = 48
NUDGE_HEALTH_BREAK_MINS: int = 90
NUDGE_MEETING_PREP_MINS: int = 15

# ── Proactive Surface ─────────────────────────────────────────────────────────
OVERLAY_WIDTH_PX: int = 380
OVERLAY_MARGIN_PX: int = 20
OVERLAY_AUTODISMISS_SECS: int = 5
QUEUE_OLD_ITEM_HOURS: int = 2  # items older than this are batched in summary

# ── Life OS ───────────────────────────────────────────────────────────────────
CALENDAR_POLL_SECS: int = 300          # 5 minutes
ROUTINE_ANALYSER_HOUR: int = 2        # 2am nightly
ROUTINE_CONFIDENCE_THRESHOLD: float = 0.75
ROUTINE_MIN_DAYS: int = 5

# ── Data Retention ────────────────────────────────────────────────────────────
RETENTION_JOBS_DAYS: int = 90
RETENTION_BEHAVIOUR_LOG_DAYS: int = 30
RETENTION_CALENDAR_PAST_DAYS: int = 30
RETENTION_NUDGES_DAYS: int = 30


# ── Enums ─────────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobPriority(str, Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    BACKGROUND = "background"


class AgentType(str, Enum):
    CLAUDE_CODE = "claude_code"
    SHELL = "shell"
    FILE_OPS = "file_ops"
    BROWSER = "browser"


class TerminalLevel(str, Enum):
    RESTRICTED = "RESTRICTED"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"
    UNRESTRICTED = "UNRESTRICTED"


TERMINAL_LEVEL: TerminalLevel = TerminalLevel(
    os.getenv("JARVIS_TERMINAL_LEVEL", "STANDARD").upper()
)

# Commands allowed at each permission level (cumulative)
TERMINAL_ALLOWED: dict[TerminalLevel, set[str]] = {
    TerminalLevel.RESTRICTED: {"ls", "cat", "git", "ps", "echo", "pwd", "which", "env"},
    TerminalLevel.STANDARD: {
        "npm", "npx", "pip", "pip3", "python", "python3", "node",
        "git", "mkdir", "touch", "cp", "mv", "find", "grep", "curl",
    },
    TerminalLevel.ELEVATED: {"sudo", "rm", "chmod", "chown", "kill", "pkill"},
    TerminalLevel.UNRESTRICTED: set(),  # no filter — all commands allowed
}


class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"   # score 9-10 — always fires through Focus Mode
    URGENT = "URGENT"       # score 7-8  — always fires through Focus Mode
    NORMAL = "NORMAL"       # score 4-6  — queued during Focus Mode
    LOW = "LOW"             # score 1-3  — queued or dropped during Focus Mode


class NudgeType(str, Enum):
    ROUTINE_MISS = "routine_miss"
    IDLE_TOO_LONG = "idle_too_long"
    GOAL_STALE = "goal_stale"
    HEALTH_BREAK = "health_break"
    MEETING_PREP = "meeting_prep"


class RoutineSource(str, Enum):
    USER_DEFINED = "user_defined"
    LEARNED = "learned"
    USER_CONFIRMED = "user_confirmed"


class BehaviourEventType(str, Enum):
    APP_OPENED = "app_opened"
    COMMAND_ISSUED = "command_issued"
    FOCUS_STARTED = "focus_started"
    IDLE_DETECTED = "idle_detected"
