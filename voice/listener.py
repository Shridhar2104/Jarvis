"""
voice/listener.py — Always-on continuous voice listener

No wake word. Records whenever speech is detected, transcribes with
faster-whisper (base.en), and publishes voice.command directly.

Mutes itself while JARVIS is speaking (tts_active) to avoid feedback.
"""

import logging
import threading
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from events.bus import bus, Event
from voice.state import tts_active

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SECS = 0.1
ONSET_RMS = 100       # RMS above this triggers recording
SILENCE_RMS = 60      # RMS below this = silence during recording
SILENCE_SECS = 0.8    # end recording after this much silence
MIN_SPEECH_SECS = 0.4 # discard if too short (cough, noise)
MAX_DURATION = 30     # hard cap on recording length

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


class ContinuousListener:
    """
    Always-on listener. Speak naturally — no wake word needed.
    Publishes voice.command for every detected utterance.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        _get_model()  # preload to avoid latency on first utterance
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("ContinuousListener started — always-on mode")

    def stop(self) -> None:
        self._running = False

    def _listen_loop(self) -> None:
        model = _get_model()
        chunk_samples = int(CHUNK_SECS * SAMPLE_RATE)

        diagnostic_ticks = 0
        max_rms_seen = 0

        while self._running:
            # ── Wait for speech onset ──────────────────────────────────────────
            chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                           dtype="int16", blocking=True)

            # Ignore while JARVIS is speaking (avoid feedback)
            if tts_active.is_set():
                continue

            rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

            # Log peak RMS every 5s so threshold can be tuned
            max_rms_seen = max(max_rms_seen, rms)
            diagnostic_ticks += 1
            if diagnostic_ticks >= 50:
                logger.info("Mic RMS — ambient peak: %d  (onset threshold: %d)", max_rms_seen, ONSET_RMS)
                max_rms_seen = 0
                diagnostic_ticks = 0

            if rms < ONSET_RMS:
                continue

            # ── Speech detected — accumulate until silence ─────────────────────
            logger.info("Speech onset (RMS=%d)", rms)
            chunks = [chunk]
            silent_secs = 0.0
            elapsed = CHUNK_SECS

            while elapsed < MAX_DURATION:
                chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                               dtype="int16", blocking=True)

                if tts_active.is_set():
                    # JARVIS started speaking mid-recording — discard
                    chunks = []
                    break

                chunks.append(chunk)
                elapsed += CHUNK_SECS

                rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if rms < SILENCE_RMS:
                    silent_secs += CHUNK_SECS
                    if silent_secs >= SILENCE_SECS:
                        break
                else:
                    silent_secs = 0.0

            speech_secs = elapsed - silent_secs
            if not chunks or speech_secs < MIN_SPEECH_SECS:
                continue

            # ── Transcribe ────────────────────────────────────────────────────
            audio_np = np.concatenate(chunks, axis=0)
            audio_f32 = audio_np.flatten().astype(np.float32) / 32768.0

            try:
                segments, _ = model.transcribe(audio_f32, language="en", vad_filter=False)
                text = " ".join(seg.text for seg in segments).strip()
            except Exception:
                logger.exception("Transcription error")
                continue

            if not text:
                continue

            logger.info("Heard: '%s'", text)
            bus.publish_sync(Event("voice.command", {"text": text, "raw": text}))
