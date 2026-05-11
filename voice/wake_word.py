"""
voice/wake_word.py — Always-on wake word detection

Uses faster-whisper (tiny.en) locally — no network latency.
1.5-second chunks with energy gating for fast, offline detection.
"""

import logging
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import WAKE_WORD
from events.bus import bus, Event
from voice.state import stt_recording

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_DURATION = 1.5    # seconds per transcription window (was 3s with Google)
SILENCE_THRESHOLD = 80  # RMS below this = silence, skip transcription

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _get_model() -> WhisperModel:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading faster-whisper tiny.en model…")
            _model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logger.info("faster-whisper tiny.en ready")
    return _model


class WakeWordDetector:
    """
    Background thread that listens for the wake word using faster-whisper locally.

    Records CHUNK_DURATION-second clips, skips silence, transcribes offline,
    then checks for the wake word keyword.
    """

    def __init__(self, wake_word: str = WAKE_WORD) -> None:
        self.wake_word = wake_word.lower()
        self._thread: threading.Thread | None = None
        self._running = False
        logger.info("WakeWordDetector initialised (keyword: '%s')", self.wake_word)

    def start(self) -> None:
        _get_model()  # preload now to avoid first-detection delay
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector started")

    def stop(self) -> None:
        self._running = False

    def _listen_loop(self) -> None:
        model = _get_model()
        chunk_samples = int(CHUNK_DURATION * SAMPLE_RATE)

        while self._running:
            if stt_recording.is_set():
                time.sleep(0.05)
                continue
            try:
                audio_np = sd.rec(
                    chunk_samples,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocking=True,
                )
                rms = int(np.sqrt(np.mean(audio_np.astype(np.float32) ** 2)))
                if rms < SILENCE_THRESHOLD:
                    continue

                audio_f32 = audio_np.flatten().astype(np.float32) / 32768.0
                # vad_filter=False: we already gate on RMS; VAD strips short words like "Jarvis"
                segments, _ = model.transcribe(audio_f32, language="en", vad_filter=False)
                text = " ".join(seg.text for seg in segments).strip().lower()

                if not text:
                    continue

                logger.debug("Wake word candidate: '%s'", text)

                if self.wake_word in text:
                    logger.info("Wake word detected!")
                    # Non-blocking earcon so STT starts immediately
                    subprocess.Popen(
                        ["afplay", "/System/Library/Sounds/Tink.aiff"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    bus.publish_sync(Event("voice.wake", {"raw_text": text}))

            except Exception:
                logger.exception("Unexpected error in wake word loop")
