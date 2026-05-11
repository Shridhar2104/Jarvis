"""
voice/wake_word.py — Always-on wake word detection

Listens on the microphone continuously using sounddevice (replaces pyaudio).
When the configured wake word is detected in Google STT output, publishes
a `voice.wake` event so the STT layer can begin transcribing.

v2.0: energy-threshold + Google STT keyword matching.
v2.5: swap in openwakeword for true offline, low-latency detection.
"""

import logging
import threading
import time

import numpy as np
import sounddevice as sd
import speech_recognition as sr

from config import WAKE_WORD
from events.bus import bus, Event
from voice.state import stt_recording

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_DURATION = 3      # seconds to record per loop iteration
SILENCE_THRESHOLD = 80   # RMS below this = silence, skip STT call


class WakeWordDetector:
    """
    Background thread that listens for the wake word using sounddevice.

    Records CHUNK_DURATION-second clips, checks energy, sends to Google STT
    if speech is detected, then checks for the wake word keyword.
    """

    def __init__(self, wake_word: str = WAKE_WORD) -> None:
        self.wake_word = wake_word.lower()
        self._recognizer = sr.Recognizer()
        self._thread: threading.Thread | None = None
        self._running = False
        logger.info("WakeWordDetector initialised (keyword: '%s')", self.wake_word)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("Wake word detector started")

    def stop(self) -> None:
        self._running = False

    def _listen_loop(self) -> None:
        while self._running:
            # Pause while STT is using the mic
            if stt_recording.is_set():
                time.sleep(0.1)
                continue
            try:
                audio_np = sd.rec(
                    int(CHUNK_DURATION * SAMPLE_RATE),
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="int16",
                    blocking=True,
                )
                rms = int(np.sqrt(np.mean(audio_np.astype(np.float32) ** 2)))
                if rms < SILENCE_THRESHOLD:
                    continue

                audio_data = sr.AudioData(audio_np.tobytes(), SAMPLE_RATE, 2)
                text = self._recognizer.recognize_google(audio_data).lower()
                logger.debug("Wake word candidate: '%s'", text)

                if self.wake_word in text:
                    logger.info("Wake word detected!")
                    bus.publish_sync(Event("voice.wake", {"raw_text": text}))

            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logger.warning("STT service error in wake word loop: %s", e)
            except Exception:
                logger.exception("Unexpected error in wake word loop")
