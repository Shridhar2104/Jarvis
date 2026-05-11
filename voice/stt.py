"""
voice/stt.py — Speech-to-text transcription

Activated after wake word detection. Records audio until silence using
sounddevice, then transcribes locally with faster-whisper (base.en).

Publishes: Event("voice.command", {"text": "..."})
"""

import asyncio
import logging
import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import WAKE_WORD
from events.bus import bus, Event
from voice.state import stt_recording

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MAX_DURATION = 20       # seconds
SILENCE_SECS = 0.8      # stop recording after this much silence
SILENCE_RMS = 80        # RMS below this = silence
CHUNK_SECS = 0.1

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _get_model() -> WhisperModel:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading faster-whisper base.en model…")
            _model = WhisperModel("base.en", device="cpu", compute_type="int8")
            logger.info("faster-whisper base.en ready")
    return _model


class SpeechToText:
    """
    Listens for a single utterance and transcribes it with faster-whisper locally.

    Subscribes to `voice.wake`. On receipt, records the user's command
    and publishes it as `voice.command`.
    """

    def __init__(self) -> None:
        bus.on("voice.wake", self._on_wake)
        logger.info("STT initialised (faster-whisper base.en)")

    async def _on_wake(self, event: Event) -> None:
        logger.info("Wake received — listening for command…")
        text = await asyncio.to_thread(self._record_and_transcribe)
        if text:
            clean = text.lower().replace(WAKE_WORD, "").strip(" ,.")
            logger.info("Transcribed command: '%s'", clean)
            await bus.publish(Event("voice.command", {"text": clean, "raw": text}))
        else:
            logger.warning("STT returned empty transcription")

    def _record_and_transcribe(self) -> str:
        stt_recording.set()  # signal wake word loop to pause
        chunks: list[np.ndarray] = []
        silent_secs = 0.0
        elapsed = 0.0
        chunk_samples = int(SAMPLE_RATE * CHUNK_SECS)

        logger.info("Recording…")
        while elapsed < MAX_DURATION:
            chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                           dtype="int16", blocking=True)
            chunks.append(chunk)
            elapsed += CHUNK_SECS

            rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms < SILENCE_RMS:
                silent_secs += CHUNK_SECS
                if silent_secs >= SILENCE_SECS and elapsed > 0.5:
                    break
            else:
                silent_secs = 0.0

        if not chunks:
            stt_recording.clear()
            return ""

        audio_np = np.concatenate(chunks, axis=0)

        try:
            model = _get_model()
            audio_f32 = audio_np.flatten().astype(np.float32) / 32768.0
            segments, _ = model.transcribe(audio_f32, language="en")
            return " ".join(seg.text for seg in segments).strip()
        except Exception:
            logger.exception("STT transcription error")
            return ""
        finally:
            stt_recording.clear()  # always resume wake word loop
