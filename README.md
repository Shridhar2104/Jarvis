# J.A.R.V.I.S
### Just A Rather Very Intelligent System

> *Ambient · Parallel · Persistent · Private*

Jarvis is not a voice command interface. It is a **persistent, parallel AI chief of staff** that lives on your Mac. It owns tasks. It learns patterns. It interrupts only when it matters.

---

## The North Star

> *Tony Stark never said "Hey Jarvis, open Spotify." He said "Jarvis, get me the schematics for the Mark IV reactor and start the simulation while I get coffee." Jarvis executed it. Reported back when done. Interrupted only when the building was on fire.*

That is the product. Not a smarter Siri. Not a voice-activated macro runner. A persistent, parallel, ambient intelligence that treats the user like Tony Stark — someone whose time is too valuable to babysit a computer.

---

## Core Beliefs

- **Jarvis owns tasks, not just executes commands.** Fire-and-forget is the default interaction model.
- **Parallelism is first-class.** Multiple agents run simultaneously. The user is never blocked waiting.
- **Proactive beats reactive.** Jarvis surfaces information before the user has to ask.
- **Privacy is non-negotiable.** Everything lives locally. No telemetry. No cloud brain.
- **Interruption is a privilege.** Jarvis earns the right to speak up. It never abuses it.
- **Memory makes it personal.** Jarvis learns routines, patterns, and preferences across time.

---

## What's New in v2.0

| Dimension | v1.0 | v2.0 |
|---|---|---|
| Execution | Synchronous, one tool at a time | Parallel agents, async job queue |
| Memory | In-session only, cleared on exit | Persistent SQLite brain, cross-session |
| Proactivity | Responds only when spoken to | Interrupts, nudges, reports back proactively |
| Calendar & time | Not supported | Native EventKit integration, focus modes |
| Behaviour learning | None | Routine detection, pattern nudging |
| Long-running jobs | 15-second shell timeout | Unbounded agents with status lifecycle |

---

## Architecture

Jarvis v2.0 is composed of **six subsystems** communicating over an internal `asyncio` event bus. No subsystem calls another directly — they publish events and subscribe to results.

```
┌─────────────────────────────────────────────────────────────┐
│                        J.A.R.V.I.S                          │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │ Voice Layer  │   │  LLM Brain   │   │    Agent       │  │
│  │              │   │              │   │  Orchestrator  │  │
│  │ Wake word    │   │ Intent class │   │                │  │
│  │ STT / TTS    │   │ Tool routing │   │ Parallel jobs  │  │
│  └──────┬───────┘   └──────┬───────┘   └───────┬────────┘  │
│         │                  │                   │           │
│         └──────────────────┴───────────────────┘           │
│                         Event Bus                          │
│         ┌──────────────────┬───────────────────┐           │
│         │                  │                   │           │
│  ┌──────┴───────┐   ┌──────┴───────┐   ┌───────┴────────┐  │
│  │  Life OS     │   │  Proactive   │   │     Tool       │  │
│  │  Engine      │   │  Surface     │   │  Dispatcher    │  │
│  │              │   │              │   │                │  │
│  │ SQLite brain │   │ Overlay UI   │   │ Apps/Files/    │  │
│  │ Routines     │   │ Focus mode   │   │ Shell/Browser  │  │
│  │ Calendar     │   │ Urgency score│   │                │  │
│  └──────────────┘   └──────────────┘   └────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Event Bus

| Event | Publisher | Subscriber(s) |
|---|---|---|
| `voice.command` | Voice Layer | LLM Brain |
| `job.created` | LLM Brain | Agent Orchestrator |
| `job.completed` | Agent Orchestrator | Proactive Surface, Life OS Engine |
| `reminder.triggered` | Life OS Engine | Proactive Surface |
| `focus.changed` | Voice Layer | Proactive Surface, Life OS Engine |
| `routine.detected` | Life OS Engine | LLM Brain (context injection) |

---

## Project Structure

```
jarvis/
├── main.py                      # Entry point — boots all subsystems
├── config.py                    # Env vars, constants, permission levels
├── .env.example                 # Required environment variables
├── requirements.txt
│
├── events/
│   ├── __init__.py
│   └── bus.py                   # asyncio event bus (publish / subscribe)
│
├── voice/
│   ├── __init__.py
│   ├── wake_word.py             # Always-on wake word detection (openwakeword)
│   ├── stt.py                   # Speech-to-text (Google / faster-whisper)
│   └── tts.py                   # Text-to-speech (pyttsx3 / edge-tts)
│
├── brain/
│   ├── __init__.py
│   ├── intent.py                # Intent classification via LLM
│   └── router.py                # Routes intent → tool dispatcher or orchestrator
│
├── orchestrator/
│   ├── __init__.py
│   ├── manager.py               # Job registry, asyncio task pool, priority queue
│   ├── lifecycle.py             # PENDING → RUNNING → DONE/FAILED/CANCELLED
│   └── agents/
│       ├── __init__.py
│       ├── base.py              # Abstract Agent base class
│       ├── claude_code.py       # Claude Code CLI agent
│       ├── shell.py             # Long-running shell agent
│       ├── file_ops.py          # Bulk file operations agent
│       └── browser.py          # Multi-step browser research agent
│
├── life_os/
│   ├── __init__.py
│   ├── engine.py                # Main Life OS loop — polls calendar, fires nudges
│   ├── routine_detector.py      # Nightly behaviour analysis, confidence scoring
│   └── nudge.py                 # Nudge types, trigger conditions, queue logic
│
├── proactive/
│   ├── __init__.py
│   ├── surface.py               # NSPanel overlay via PyObjC
│   ├── focus.py                 # Focus mode state, timed focus, queue gating
│   ├── urgency.py               # Urgency scoring (1–10 scale)
│   └── queue.py                 # Notification queue, flush-on-focus-exit
│
├── skills/
│   ├── __init__.py
│   ├── apps.py                  # Open, quit, list running applications
│   ├── browser.py               # Open URL, search, tab management
│   ├── files.py                 # List, create, delete, move files
│   ├── system.py                # Volume, brightness, WiFi, sleep, battery
│   ├── mouse.py                 # Click, type, hotkeys, screenshot, scroll
│   ├── terminal.py              # Shell execution — 4-level permission model
│   ├── claude_code.py           # Launch & monitor Claude Code sessions
│   └── calendar.py              # Apple Calendar + Reminders via EventKit
│
└── db/
    ├── __init__.py
    ├── schema.py                # SQLite table definitions (CREATE TABLE)
    └── models.py                # Typed dataclasses for all DB rows
```

---

## Subsystems

### 1. Agent Orchestrator

Transforms Jarvis from a synchronous command runner into a true **parallel task manager**.

**Job Lifecycle:**

```
PENDING → RUNNING → DONE
                 ↘ FAILED
                 ↘ BLOCKED  (needs human input — surfaced as URGENT)
                 ↘ CANCELLED
```

**Agent Types:**

| Agent | Use Case |
|---|---|
| `ClaudeCodeAgent` | Delegate coding tasks — spawns Claude Code CLI, monitors stdout |
| `ShellAgent` | Build pipelines, test suites, data processing (no 15s timeout) |
| `FileOpsAgent` | Mass rename, directory reorg, search-and-replace across repos |
| `BrowserAgent` | Multi-step web research, structured report output |

**Voice Interface:**
```
"Jarvis, what are you working on?"         → lists all active jobs
"Jarvis, how is the auth feature going?"   → fuzzy match → current step
"Jarvis, cancel the file rename task"      → graceful agent shutdown
"Jarvis, show me what you completed today" → DONE jobs from today
```

### 2. Life OS Engine

Jarvis's **long-term memory and temporal intelligence**. Everything stored in a local SQLite database at `~/Library/Application Support/Jarvis/brain.db`. Nothing leaves the machine.

**Capabilities:**
- **Calendar** — reads/writes Apple Calendar via PyObjC EventKit; voice-driven event management
- **Routine Detection** — nightly analysis of `behaviour_log`; surfaces patterns when confidence >= 0.75 across 5+ days
- **Nudge System** — proactive prompts based on missed routines, idle time, stale goals, health breaks, and meeting prep

**Nudge Types:**

| Nudge | Trigger | Example |
|---|---|---|
| Routine miss | Expected routine +30 min late | *"You usually review PRs around 10am, sir."* |
| Idle too long | No input > 90 minutes | *"Been quiet for a while. Anything I can move forward?"* |
| Goal stale | Linked job untouched > 48h | *"The auth feature hasn't been touched in 2 days."* |
| Health break | Continuous focus > 90 min | *"You've been at it for two hours. Step away for a bit?"* |
| Meeting prep | Calendar event within 15 min | *"Your 3pm call is in 12 minutes, sir."* |

### 3. Proactive Surface Layer

How Jarvis speaks when **the user hasn't spoken first**.

- Native `NSPanel` overlay — top-right corner, 380px wide, never steals focus
- Dark navy + Arc Reactor blue, animated waveform, text transcript
- Auto-dismisses 5s after speaking unless action required
- **Focus Mode** — gates non-urgent notifications; CRITICAL events always fire

**Urgency Scoring:**

| Event | Score | Focus Mode Behaviour |
|---|---|---|
| Meeting in < 10 minutes | 10 CRITICAL | Always fires |
| Agent BLOCKED | 9 URGENT | Always fires |
| Agent FAILED | 8 URGENT | Always fires |
| Urgent reminder | 8 URGENT | Always fires |
| Agent DONE | 5 NORMAL | Queued |
| Standard reminder | 5 NORMAL | Queued |
| Routine nudge | 3 LOW | Queued (max 1/session) |
| Health break nudge | 2 LOW | Dropped silently |

---

## Voice Command Reference

### Task Delegation
```
"Start building the auth feature, repo is Desktop/src"
→ ClaudeCode agent: "On it, sir. I'll get back to you when the scaffold is ready."

"Rename all test files in Desktop/api to snake_case"
→ FileOps agent: "Starting that now. Should take a couple of minutes."

"Run the full test suite and tell me what fails"
→ Shell agent: "Running tests now. I'll interrupt when results are in."

"Research our top 3 competitors' auth implementations"
→ Browser agent: "On it. I'll have a summary ready in a few minutes."
```

### Life OS
```
"What does my day look like?"        → today's calendar events
"Remind me at 5pm about the deploy"  → creates reminder
"Set a meeting with Rahul at 2pm"    → creates Apple Calendar event
"What did I ask you to do today?"    → job registry + reminders summary
"What have you completed so far?"    → DONE jobs with summaries
```

### Focus Mode
```
"Jarvis, focus mode on"                          → queue all non-urgent
"Focus until 5pm"                                → timed focus, warns at 4:50pm
"Don't disturb me unless the tests fail"         → focus with urgency override
"Jarvis, focus mode off"                         → flush queue, batched summary
"What did I miss?"                               → replay queue summary
```

### Data & Privacy
```
"Show me everything you know about my routines"  → formatted routine list
"Delete my behaviour history"                    → purges behaviour_log
"Wipe my memory"                                 → drops all tables (with confirm)
"Export my data"                                 → dumps brain.db to Desktop JSON
```

---

## Setup

### Requirements

- macOS 13+ (Ventura or later)
- Python 3.11+
- Claude Code CLI installed and authenticated

### Installation

```bash
git clone https://github.com/your-org/jarvis.git
cd jarvis

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your API keys
```

### macOS Permissions

Grant the following in **System Settings → Privacy & Security**:

| Permission | Required By |
|---|---|
| Microphone | Wake word, STT |
| Accessibility | PyAutoGUI |
| Screen Recording | Screenshot tool |
| Automation | AppleScript |
| Full Disk Access | File management |
| Calendars | Life OS Engine (v2.0+) |
| Reminders | Life OS Engine (v2.0+) |

### Run

```bash
python main.py
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | **required** | LLM API — GPT-4o |
| `ANTHROPIC_API_KEY` | optional | Alternative LLM — Claude |
| `JARVIS_WAKE_WORD` | `jarvis` | Configurable wake word |
| `JARVIS_MODEL` | `gpt-4o` | LLM model name |
| `JARVIS_VOICE` | `samantha` | macOS TTS voice |
| `JARVIS_TERMINAL_LEVEL` | `STANDARD` | `RESTRICTED` / `STANDARD` / `ELEVATED` / `UNRESTRICTED` |
| `JARVIS_STT` | `google` | STT backend: `google` / `whisper` |
| `JARVIS_AGENT_TIMEOUT` | `1800` | Max seconds per agent (default 30 min) |
| `JARVIS_NUDGE_ENABLED` | `true` | Enable/disable nudge system globally |
| `JARVIS_DB_PATH` | `~/Library/Application Support/Jarvis/brain.db` | Override SQLite path |

### Terminal Permission Levels

| Level | Allowed Commands | Use Case |
|---|---|---|
| `RESTRICTED` | Read-only: `ls`, `cat`, `git status`, `ps`, `echo` | First-time users |
| `STANDARD` | + write ops, `npm`, `pip`, `git commit/push` | Default for developers |
| `ELEVATED` | + `sudo`, system commands, `rm -rf` | Requires voice confirmation per command |
| `UNRESTRICTED` | Full shell — no filtering | Explicit opt-in. Every command logged. |

---

## Data Architecture & Privacy

All persistent data lives in a single SQLite file:
```
~/Library/Application Support/Jarvis/brain.db
```

| Table | Retention | Contains |
|---|---|---|
| `jobs` | 90 days | Agent jobs, status, summaries, error logs |
| `reminders` | Until dismissed | Reminders, recurrences, notification status |
| `calendar_events` | 30 days past | Synced Apple Calendar events |
| `routines` | Permanent | Learned routines with confidence scores |
| `behaviour_log` | 30 days | App opens, commands, idle periods, focus blocks |
| `nudges` | 30 days | All nudges fired + user responses |

**Privacy Guarantees:**
- No audio ever written to disk — microphone data processed in memory only
- Zero telemetry — no command history sent to any analytics service
- LLM API calls send command text to OpenAI/Anthropic per their published data policies
- `brain.db` is owned entirely by the user and can be deleted at any time
- API keys stored in `.env` only — never written to `brain.db`

---

## Error Handling

| Scenario | User Hears |
|---|---|
| Claude Code crashes | *"The auth feature job ran into an error. Log saved to Desktop."* |
| Agent timeout (>30 min) | *"The test run has been going 35 minutes. Let it run or cancel it?"* |
| Agent needs decision | *"I need your input. There are two conflicting patterns — which should I use?"* |
| LLM API error mid-job | *"I lost my connection during the file rename. Want me to retry?"* |

---

## Roadmap

### v2.0 — This Release
- [x] Agent Orchestrator — parallel execution, full job lifecycle
- [x] Life OS Engine — SQLite brain, routine learning, nudge system
- [x] Calendar & Reminders via Apple EventKit
- [x] Proactive Surface Layer — overlay, Focus Mode, Urgency Scoring
- [x] Claude Code Launcher module
- [x] Four-level terminal permission model

### v2.5 — Intelligence
- [ ] Screen vision — GPT-4o Vision contextual awareness
- [ ] Persistent cross-session conversation memory with semantic search
- [ ] Smarter routine learning — time-of-day x application context
- [ ] User-defined skill plugins — drop a `.py` into `~/Jarvis/skills/`
- [ ] Offline mode — faster-whisper STT + local Ollama LLM

### v3.0 — Platform
- [ ] Menubar app with live active-agent count
- [ ] Multi-step task planning ("Set up my dev environment from scratch")
- [ ] Jarvis Skill Marketplace — community-contributed tool modules
- [ ] Mobile companion app — trigger agents and monitor jobs remotely
- [ ] Windows and Linux port
- [ ] Google Calendar two-way sync

---

## Dependencies

| Library | Purpose | License |
|---|---|---|
| `openai` | LLM API client — GPT-4o | MIT |
| `anthropic` | Alternative LLM — Claude | MIT |
| `SpeechRecognition` | STT wrapper (Google + Whisper) | BSD |
| `faster-whisper` | Offline STT | MIT |
| `pyttsx3` | TTS engine — macOS Samantha | MPL2 |
| `pyautogui` | Mouse + keyboard automation | BSD |
| `pyobjc` | macOS native APIs (EventKit, NSPanel) | MIT |
| `pyinstaller` | Standalone `.app` packaging | GPL + exception |
| `openwakeword` | Always-on offline wake word (v2.5) | Apache 2.0 |
| `edge-tts` | Higher quality TTS (v2.5) | MIT |

---

*April 2026 — Confidential — Internal Use Only*
