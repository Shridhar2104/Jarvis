"""
voice/tts.py — Text-to-speech output

Converts Jarvis's response text to spoken audio using macOS native TTS
(pyttsx3 / Samantha voice by default).

v2.5: swap in edge-tts for higher quality output.
"""

import asyncio
import logging

import pyttsx3

from config import TTS_VOICE

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Speaks text aloud using the configured TTS engine.

    Thread-safe: pyttsx3 is synchronous, so speech is dispatched to a
    dedicated thread via asyncio.to_thread to avoid blocking the event loop.
    """

    def __init__(self, voice: str = TTS_VOICE) -> None:
        self._engine = pyttsx3.init()
        self._set_voice(voice)
        logger.info("TTS initialised (voice: %s)", voice)

    async def speak(self, text: str) -> None:
        """Speak text asynchronously (non-blocking to the event loop)."""
        logger.info("Speaking: %s", text[:80])
        await asyncio.to_thread(self._speak_sync, text)

    def _speak_sync(self, text: str) -> None:
        self._engine.say(text)
        self._engine.runAndWait()

    def _set_voice(self, voice_name: str) -> None:
        voices = self._engine.getProperty("voices")
        for v in voices:
            if voice_name.lower() in v.name.lower():
                self._engine.setProperty("voice", v.id)
                return
        # Fallback to first available voice
        if voices:
            self._engine.setProperty("voice", voices[0].id)
            logger.warning("Voice '%s' not found — using '%s'", voice_name, voices[0].name)

    # ── v2.5 stub ─────────────────────────────────────────────────────────────
    # TODO(v2.5): replace with edge-tts for higher quality neural voice
    # import edge_tts
    # async def speak(self, text: str) -> None:
    #     communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
    #     await communicate.save("/tmp/jarvis_tts.mp3")
    #     # play with afplay on macOS
