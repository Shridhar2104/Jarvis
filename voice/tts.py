"""
voice/tts.py — Text-to-speech output

Uses Microsoft edge-tts (en-GB-RyanNeural) for natural, high-quality speech.
Audio is saved to a temp file and played via macOS `afplay`.
"""

import asyncio
import logging
import os
import tempfile

import edge_tts

from config import TTS_VOICE

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Speaks text aloud using edge-tts neural voice.

    Async-native: generates mp3 with edge-tts then plays with afplay.
    """

    def __init__(self, voice: str = TTS_VOICE) -> None:
        self._voice = voice
        logger.info("TTS initialised (voice: %s)", voice)

    async def speak(self, text: str) -> None:
        """Speak text asynchronously (non-blocking to the event loop)."""
        logger.info("Speaking: %s", text[:80])
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            communicate = edge_tts.Communicate(text, self._voice)
            await communicate.save(tmp_path)
            proc = await asyncio.create_subprocess_exec(
                "afplay", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            logger.exception("TTS error")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
