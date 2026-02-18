"""
SecureMeet Configuration
All settings and constants for the application
"""
import os
from pathlib import Path

# Application Info
APP_NAME = "SecureMeet"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Privacy-first meeting minutes"

# Paths
HOME_DIR = Path.home()
APP_DATA_DIR = HOME_DIR / ".securemeet"
RECORDINGS_DIR = APP_DATA_DIR / "recordings"
TRANSCRIPTS_DIR = APP_DATA_DIR / "transcripts"
SUMMARIES_DIR = APP_DATA_DIR / "summaries"

# Create directories if they don't exist
for dir_path in [APP_DATA_DIR, RECORDINGS_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Audio Settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1  # Mono for transcription
CHUNK_DURATION = 30  # Seconds per chunk for real-time processing

# Whisper Settings
WHISPER_MODEL = "base"  # Options: tiny, base, small, medium, large-v3
# Larger models = better quality but slower
# tiny: fastest, lowest quality
# base: good balance for most users
# small: better quality, still reasonably fast
# medium: high quality, slower
# large-v3: best quality, requires good hardware

# Claude API Settings
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Best for summaries
MAX_TRANSCRIPT_TOKENS = 100000  # Claude's context window

# Privacy Settings
ENCRYPT_LOCAL_DATA = True
AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION = True
AUDIO_RETENTION_HOURS = 0  # 0 = delete immediately after transcription

# UI Settings
WINDOW_WIDTH = 500
WINDOW_HEIGHT = 700
THEME = "dark"  # dark or light
