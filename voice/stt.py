"""
voice/stt.py — Speech-to-text transcription

Activated after wake word detection. Records audio until silence, then
transcribes using the configured backend (Google or faster-whisper).

Publishes: Event("voice.command", {"text": "..."})
"""

import asyncio
import logging

import speech_recognition as sr

from config import STT_BACKEND, WAKE_WORD
from events.bus import bus, Event

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Listens for a single utterance and transcribes it.

    Subscribes to `voice.wake`. On receipt, records the user's command
    and publishes it as `voice.command`.
    """

    def __init__(self) -> None:
        self._recognizer = sr.Recognizer()
        self._mic = sr.Microphone()
        self._backend = STT_BACKEND

        bus.on("voice.wake", self._on_wake)
        logger.info("STT initialised (backend: %s)", self._backend)

    async def _on_wake(self, event: Event) -> None:
        """Triggered when wake word is detected — record and transcribe."""
        logger.info("Wake received — listening for command…")
        text = await asyncio.to_thread(self._record_and_transcribe)
        if text:
            # Strip the wake word itself from the transcription if present
            clean = text.lower().replace(WAKE_WORD, "").strip(" ,.")
            logger.info("Transcribed command: '%s'", clean)
            await bus.publish(Event("voice.command", {"text": clean, "raw": text}))
        else:
            logger.warning("STT returned empty transcription")

    def _record_and_transcribe(self) -> str:
        """Blocking: record one phrase and return transcribed text."""
        with self._mic as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=20)
            except sr.WaitTimeoutError:
                logger.debug("STT: no speech detected within timeout")
                return ""

        try:
            if self._backend == "whisper":
                return self._transcribe_whisper(audio)
            else:
                return self._transcribe_google(audio)
        except sr.UnknownValueError:
            logger.debug("STT: speech not understood")
            return ""
        except Exception:
            logger.exception("STT transcription error")
            return ""

    def _transcribe_google(self, audio: sr.AudioData) -> str:
        return self._recognizer.recognize_google(audio)

    def _transcribe_whisper(self, audio: sr.AudioData) -> str:
        # TODO(v2.5): use faster-whisper directly for offline transcription
        # from faster_whisper import WhisperModel
        # model = WhisperModel("base.en", device="cpu")
        # segments, _ = model.transcribe(audio_path)
        return self._recognizer.recognize_whisper(audio, model="base.en")
