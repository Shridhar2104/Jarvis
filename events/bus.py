"""
events/bus.py — Internal asyncio event bus for J.A.R.V.I.S

All subsystems communicate exclusively through this bus.
No subsystem may import or call another directly.

Published events:
  voice.command       Voice Layer      → LLM Brain
  job.created         LLM Brain        → Agent Orchestrator
  job.completed       Agent Orchestrator → Proactive Surface, Life OS Engine
  job.blocked         Agent Orchestrator → Proactive Surface
  job.failed          Agent Orchestrator → Proactive Surface
  reminder.triggered  Life OS Engine   → Proactive Surface
  focus.changed       Voice Layer      → Proactive Surface, Life OS Engine
  routine.detected    Life OS Engine   → LLM Brain (context injection)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """A single event published on the bus."""
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)


# Subscriber type: async callable that receives an Event
Subscriber = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Lightweight pub/sub event bus backed by asyncio queues.

    Usage:
        bus = EventBus()

        # Subscribe
        @bus.subscribe("voice.command")
        async def on_command(event: Event):
            print(event.payload)

        # Publish
        await bus.publish(Event("voice.command", {"text": "open Chrome"}))

        # Start dispatch loop
        await bus.start()
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Registration ──────────────────────────────────────────────────────────

    def subscribe(self, topic: str) -> Callable[[Subscriber], Subscriber]:
        """Decorator that registers an async handler for a topic."""
        def decorator(fn: Subscriber) -> Subscriber:
            self._subscribers.setdefault(topic, []).append(fn)
            logger.debug("Subscribed %s → %s", fn.__qualname__, topic)
            return fn
        return decorator

    def on(self, topic: str, handler: Subscriber) -> None:
        """Imperative form of subscribe (for runtime wiring)."""
        self._subscribers.setdefault(topic, []).append(handler)

    # ── Publishing ────────────────────────────────────────────────────────────

    async def publish(self, event: Event) -> None:
        """Enqueue an event for delivery to all subscribers of its topic."""
        logger.debug("Published event: %s %s", event.topic, event.payload)
        await self._queue.put(event)

    def publish_sync(self, event: Event) -> None:
        """Thread-safe publish from non-async contexts (e.g. background threads)."""
        loop = self._loop or asyncio.get_running_loop()
        loop.call_soon_threadsafe(self._queue.put_nowait, event)

    # ── Dispatch Loop ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Run the dispatch loop until stop() is called."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        logger.info("EventBus started")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.exception("EventBus dispatch error")

    async def stop(self) -> None:
        self._running = False
        logger.info("EventBus stopped")

    async def _dispatch(self, event: Event) -> None:
        handlers = self._subscribers.get(event.topic, [])
        if not handlers:
            logger.debug("No subscribers for topic: %s", event.topic)
            return
        tasks = [asyncio.create_task(h(event)) for h in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r, h in zip(results, handlers):
            if isinstance(r, Exception):
                logger.error("Handler %s raised: %s", h.__qualname__, r)


# Module-level singleton — import and use directly across subsystems
bus = EventBus()
