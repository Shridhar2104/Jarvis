"""voice/state.py — Shared state for the voice layer."""
import threading

# Legacy: kept for compatibility but no longer used in always-on mode
stt_recording = threading.Event()

# Set by TTS while JARVIS is speaking; listener pauses to avoid feedback
tts_active = threading.Event()
