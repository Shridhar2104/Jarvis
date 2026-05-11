"""
brain/router.py — Command router

Subscribes to `voice.command`, classifies intent, then either:
  1. Dispatches directly to a skill (quick, synchronous tools), or
  2. Publishes `job.created` for the Agent Orchestrator (long-running tasks).

Also handles status queries, focus mode commands, and Life OS queries.
"""

import logging

from events.bus import bus, Event
from brain.intent import IntentClassifier, Intent
from config import AgentType

logger = logging.getLogger(__name__)


class CommandRouter:
    """
    The central nervous system of Jarvis.

    Wires voice.command → intent classification → skill dispatch or agent spawn.
    """

    def __init__(self, tts, skills: dict) -> None:
        """
        Args:
            tts:    TextToSpeech instance for immediate acknowledgements.
            skills: dict mapping tool_type strings to skill module instances.
                    e.g. {"apps": AppsSkill(), "calendar": CalendarSkill(), ...}
        """
        self._tts = tts
        self._skills = skills
        self._classifier = IntentClassifier()

        bus.on("voice.command", self._on_command)
        bus.on("routine.detected", self._on_routine_detected)
        logger.info("CommandRouter ready")

    # ── Event Handlers ────────────────────────────────────────────────────────

    async def _on_command(self, event: Event) -> None:
        text: str = event.payload.get("text", "")
        if not text:
            return

        intent = await self._classifier.classify(text)

        # Speak the acknowledgement immediately so the user isn't left hanging
        await self._tts.speak(intent.spoken_ack)

        # chat is a pure conversational response — spoken_ack is the full reply
        if intent.tool_type == "chat":
            return

        if intent.is_long_running:
            await self._spawn_agent(intent)
        else:
            await self._dispatch_skill(intent)

    async def _on_routine_detected(self, event: Event) -> None:
        context: str = event.payload.get("context", "")
        self._classifier.update_routine_context(context)

    # ── Routing Logic ─────────────────────────────────────────────────────────

    async def _spawn_agent(self, intent: Intent) -> None:
        """Publish job.created for the Agent Orchestrator to handle."""
        await bus.publish(Event("job.created", {
            "tool_type": intent.tool_type,
            "title": _title_from_intent(intent),
            "intent": intent.raw_text,
            "params": intent.params,
            "priority": intent.priority,
        }))
        logger.info("Agent job created: %s", intent.tool_type)

    async def _dispatch_skill(self, intent: Intent) -> None:
        """Execute a quick synchronous tool and speak the result."""
        skill = self._skills.get(intent.tool_type)
        if skill is None:
            logger.warning("No skill registered for tool_type: %s", intent.tool_type)
            await self._tts.speak("I don't have a skill for that yet, sir.")
            return

        try:
            handler = getattr(skill, intent.action, None)
            if handler is None:
                logger.warning("Skill %s has no action: %s", intent.tool_type, intent.action)
                await self._tts.speak("I'm not sure how to do that.")
                return

            result = await handler(**intent.params)

            if result:
                await self._tts.speak(str(result))

        except Exception:
            logger.exception("Skill dispatch error: %s.%s", intent.tool_type, intent.action)
            await self._tts.speak("Something went wrong with that, sir. Check the logs.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _title_from_intent(intent: Intent) -> str:
    """Generate a human-readable job title from an intent."""
    goal = intent.params.get("goal", "")
    if goal:
        return goal[:80]
    return f"{intent.tool_type}: {intent.action}"
