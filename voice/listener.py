"""
voice/listener.py — Always-on continuous voice listener

Auto-calibrates noise floor on startup, then uses adaptive thresholds
so it works correctly regardless of ambient noise level.
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
CHUNK_SECS  = 0.1
SILENCE_SECS = 0.8     # stop recording after this much silence
MIN_SPEECH_SECS = 0.4  # discard clips shorter than this
MAX_DURATION = 30
NO_SPEECH_THRESHOLD = 0.6

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _get_model() -> WhisperModel:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading faster-whisper small.en model…")
            _model = WhisperModel("small.en", device="cpu", compute_type="int8")
            logger.info("faster-whisper small.en ready")
    return _model


class ContinuousListener:
    """Always-on listener with adaptive noise-floor calibration."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        _get_model()
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("ContinuousListener started — always-on mode")

    def stop(self) -> None:
        self._running = False

    # ── Calibration ───────────────────────────────────────────────────────────

    def _calibrate(self) -> tuple[int, int]:
        """
        Measure ambient noise floor after TTS greeting finishes.
        Returns (onset_rms, silence_rms) calibrated to this environment.
        """
        # Wait for startup TTS to finish before sampling ambient
        while tts_active.is_set():
            time.sleep(0.1)
        time.sleep(0.8)  # let room reverb settle

        chunk_samples = int(CHUNK_SECS * SAMPLE_RATE)
        rms_vals = []
        for _ in range(30):  # sample 3 seconds of ambient
            audio = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                           dtype="int16", blocking=True)
            rms_vals.append(int(np.sqrt(np.mean(audio.astype(np.float32) ** 2))))

        noise_floor = int(np.percentile(rms_vals, 90))  # 90th percentile = robust ceiling
        onset_rms   = max(200, int(noise_floor * 1.8))  # need 1.8× above floor to trigger
        silence_rms = noise_floor + 20                  # just above floor = silence

        logger.info(
            "Calibrated noise floor: %d RMS → onset=%d  silence=%d",
            noise_floor, onset_rms, silence_rms,
        )
        return onset_rms, silence_rms

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        model = _get_model()
        chunk_samples = int(CHUNK_SECS * SAMPLE_RATE)

        onset_rms, silence_rms = self._calibrate()

        while self._running:
            # ── Wait for speech onset ──────────────────────────────────────────
            chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                           dtype="int16", blocking=True)

            if tts_active.is_set():
                continue

            rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms < onset_rms:
                continue

            # ── Accumulate until silence ───────────────────────────────────────
            logger.info("Speech onset (RMS=%d)", rms)
            chunks = [chunk]
            silent_secs = 0.0
            elapsed = CHUNK_SECS

            while elapsed < MAX_DURATION:
                chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                               dtype="int16", blocking=True)

                if tts_active.is_set():
                    chunks = []
                    break

                chunks.append(chunk)
                elapsed += CHUNK_SECS

                rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if rms < silence_rms:
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
                segments, _ = model.transcribe(
                    audio_f32,
                    language="en",
                    vad_filter=False,
                    temperature=0,
                    condition_on_previous_text=False,
                    no_speech_threshold=NO_SPEECH_THRESHOLD,
                )
                kept = [seg.text for seg in segments if seg.no_speech_prob < NO_SPEECH_THRESHOLD]
                text = " ".join(kept).strip()
            except Exception:
                logger.exception("Transcription error")
                continue

            if not text:
                logger.info("Transcription empty — skipping")
                continue

            logger.info("Heard: '%s'", text)
            bus.publish_sync(Event("voice.command", {"text": text, "raw": text}))
