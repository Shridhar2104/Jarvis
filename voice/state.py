"""voice/state.py — Shared state between wake word detector and STT."""
import threading

# Set by STT while it is recording; wake word loop pauses during this time
# to avoid two simultaneous sounddevice streams on the same device.
stt_recording = threading.Event()
