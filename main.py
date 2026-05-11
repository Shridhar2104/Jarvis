"""
main.py — J.A.R.V.I.S entry point

Boots all subsystems in dependency order, then runs the asyncio event loop.

Startup sequence:
  1. init_db()             — create / migrate brain.db
  2. EventBus              — start async dispatch loop
  3. TextToSpeech          — greet the user
  4. WakeWordDetector      — begin listening for wake word
  5. SpeechToText          — wire STT to wake events
  6. AgentOrchestrator     — job registry + agent pool
  7. LifeOSEngine          — calendar, routines, nudges
  8. FocusMode             — focus state manager
  9. ProactiveSurface      — overlay + urgency routing
 10. CommandRouter         — intent classification + skill dispatch
 11. MobileAPI             — FastAPI server on :8765 for mobile companion

Usage:
  python main.py
"""

import asyncio
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis")


async def main() -> None:
    from db.schema import init_db
    from events.bus import bus
    from voice.tts import TextToSpeech
    from voice.wake_word import WakeWordDetector
    from voice.stt import SpeechToText
    from orchestrator.manager import AgentOrchestrator
    from life_os.engine import LifeOSEngine
    from proactive.focus import FocusMode
    from proactive.surface import ProactiveSurface
    from brain.router import CommandRouter
    from skills import build_skill_registry
    from skills.claude_code import _cli_available

    # ── 1. Database ───────────────────────────────────────────────────────────
    logger.info("Initialising brain.db…")
    init_db()

    # ── 2. TTS (needed by router and surface before any speech) ───────────────
    tts = TextToSpeech()

    # ── 3. Startup checks ─────────────────────────────────────────────────────
    if not _cli_available():
        logger.warning("Claude Code CLI not found — ClaudeCodeAgent will be unavailable")

    # ── 4. Core subsystems ────────────────────────────────────────────────────
    orchestrator = AgentOrchestrator()
    life_os = LifeOSEngine()
    focus = FocusMode()
    surface = ProactiveSurface(tts=tts, focus=focus)
    router = CommandRouter(tts=tts, skills=build_skill_registry())

    # ── 5. Voice Layer ────────────────────────────────────────────────────────
    wake_word = WakeWordDetector()
    stt = SpeechToText()
    wake_word.start()

    # ── 6. Greet ──────────────────────────────────────────────────────────────
    await tts.speak("J.A.R.V.I.S online. All systems nominal. How can I help, sir?")
    logger.info("J.A.R.V.I.S v2.0 ready")

    # ── 7. Run all background loops + event bus ───────────────────────────────
    from mobile_api.server import run_server as _run_mobile_api
    logger.info("Mobile API starting on port %s", __import__("os").getenv("JARVIS_API_PORT", "8765"))
    await asyncio.gather(
        bus.start(),
        life_os.start(),
        _focus_expiry_checker(focus, tts),
        _run_mobile_api(),
    )


async def _focus_expiry_checker(focus, tts) -> None:
    """Periodically warn before timed focus expires."""
    while True:
        await focus.check_expiry_warning(tts)
        await asyncio.sleep(60)


def _handle_shutdown(loop: asyncio.AbstractEventLoop) -> None:
    logger.info("Shutdown signal received — stopping J.A.R.V.I.S…")
    for task in asyncio.all_tasks(loop):
        task.cancel()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_shutdown, loop)

    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        logger.info("J.A.R.V.I.S offline.")
