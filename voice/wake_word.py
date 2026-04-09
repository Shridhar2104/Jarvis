"""
voice/wake_word.py — Always-on wake word detection

Listens on the microphone continuously. When the configured wake word is
detected, publishes a `voice.wake` event on the event bus so the STT layer
can begin transcribing.

v2.0: uses SpeechRecognition energy-threshold detection as a stand-in.
v2.5: swap in openwakeword for true offline, low-latency detection.
"""

import asyncio
import logging
import threading

import speech_recognition as sr

from config import WAKE_WORD
from events.bus import bus, Event

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Background thread that listens for the wake word.

    When detected, publishes Event("voice.wake", {}) on the bus.
    The VoiceLayer subscribes to voice.wake and triggers STT.
    """

    def __init__(self, wake_word: str = WAKE_WORD) -> None:
        self.wake_word = wake_word.lower()
        self._recognizer = sr.Recognizer()
        self._mic = sr.Microphone()
        self._thread: threading.Thread | None = None
        self._running = False

        # Calibrate ambient noise once at startup
        with self._mic as source:
            logger.info("Calibrating ambient noise for wake word detector…")
            self._recognizer.adjust_for_ambient_noise(source, duration=1)

    def start(self) -> None:
        """Start the background listener thread."""
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector started (keyword: '%s')", self.wake_word)

    def stop(self) -> None:
        self._running = False
        logger.info("Wake word detector stopped")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        with self._mic as source:
            while self._running:
                try:
                    audio = self._recognizer.listen(source, timeout=3, phrase_time_limit=4)
                    text = self._recognizer.recognize_google(audio).lower()
                    logger.debug("Wake word candidate: '%s'", text)
                    if self.wake_word in text:
                        logger.info("Wake word detected!")
                        bus.publish_sync(Event("voice.wake", {"raw_text": text}))
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    logger.warning("STT service error in wake word loop: %s", e)
                except Exception:
                    logger.exception("Unexpected error in wake word loop")

    # ── v2.5 stub ─────────────────────────────────────────────────────────────
    # TODO(v2.5): replace _listen_loop with openwakeword model inference
    # from openwakeword.model import Model
    # model = Model(wakeword_models=["hey_jarvis.tflite"])
