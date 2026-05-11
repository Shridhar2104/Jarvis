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
        self._onset_rms = 400    # safe defaults until calibrate() is called
        self._silence_rms = 200
        # Calibration: set by calibrate(), consumed by _listen_loop
        self._calib_samples: list[int] = []
        self._calib_needed = 0
        self._calib_done = threading.Event()

    def start(self) -> None:
        _get_model()
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("ContinuousListener started — always-on mode")

    def calibrate(self) -> None:
        """
        Measure ambient noise floor using the already-running listener stream.
        Call this from main.py AFTER the greeting TTS finishes.
        Collects 30 chunks (3s) of ambient via the listener thread — no second
        stream needed, avoiding PortAudio's 'stream not stopped' error.
        """
        time.sleep(0.5)  # let reverb from greeting settle
        self._calib_samples = []
        self._calib_needed = 30
        self._calib_done.clear()
        # Block until the listener thread fills _calib_samples
        self._calib_done.wait(timeout=10)
        self._calib_needed = 0

        if not self._calib_samples:
            logger.warning("Calibration got no samples — keeping defaults")
            return

        noise_floor = int(np.percentile(self._calib_samples, 90))
        self._onset_rms   = max(200, int(noise_floor * 1.8))
        self._silence_rms = noise_floor + 20

        logger.info(
            "Calibrated noise floor: %d RMS → onset=%d  silence=%d",
            noise_floor, self._onset_rms, self._silence_rms,
        )

    def stop(self) -> None:
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        model = _get_model()
        chunk_samples = int(CHUNK_SECS * SAMPLE_RATE)

        while self._running:
            # ── Wait for speech onset ──────────────────────────────────────────
            chunk = sd.rec(chunk_samples, samplerate=SAMPLE_RATE, channels=1,
                           dtype="int16", blocking=True)

            if tts_active.is_set():
                continue

            rms = int(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

            # ── Feed calibration if requested ─────────────────────────────────
            if self._calib_needed > 0:
                self._calib_samples.append(rms)
                if len(self._calib_samples) >= self._calib_needed:
                    self._calib_done.set()
                continue

            if rms < self._onset_rms:
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
                if rms < self._silence_rms:
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
