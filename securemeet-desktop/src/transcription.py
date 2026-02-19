"""
Transcription Module
Uses faster-whisper for 100% LOCAL transcription via a subprocess.
No audio data is ever sent to any server.

WHY SUBPROCESS?
PyQt6 and ctranslate2 (the C++ backend of faster-whisper) segfault together
on Windows due to a DLL conflict. Running transcription in a separate Python
process avoids this entirely.
"""
import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime

from config import (
    WHISPER_MODEL,
    TRANSCRIPTS_DIR,
    AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION
)

# When bundled by PyInstaller, sys.frozen is set and sys.executable points to
# the main SecureMeet.exe. The worker is a second bundled exe in the same folder.
# When running from source, use python + transcribe_worker.py directly.
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    # Worker lives in dist/transcribe_worker/transcribe_worker.exe (--onedir via COLLECT)
    _EXE_DIR = Path(sys.executable).parent
    _WORKER_CMD = [str(_EXE_DIR / "transcribe_worker" / "transcribe_worker.exe")]
else:
    # Running from source
    _WORKER_CMD = [sys.executable, str(Path(__file__).parent / "transcribe_worker.py")]


class LocalTranscriber:
    """
    Local transcription using faster-whisper — runs in a subprocess
    to avoid the PyQt6 + ctranslate2 DLL conflict on Windows.
    """

    def __init__(self, model_size: str = WHISPER_MODEL):
        self.model_size = model_size
        # Keep these for API compatibility — subprocess approach doesn't need them
        self.model = None
        self._is_loaded = True  # Always "ready" — subprocess handles model loading

    def load_model(self, on_progress: Optional[Callable] = None) -> bool:
        """No-op — model is loaded inside the subprocess on demand."""
        if on_progress:
            on_progress("Ready (transcription runs in isolated process)")
        return True

    def transcribe(
        self,
        audio_path: Path,
        on_progress: Optional[Callable] = None,
        language: str = "en"
    ) -> Optional[Dict]:
        """
        Transcribe audio file by spawning a subprocess.
        The subprocess loads faster-whisper without PyQt6, avoiding the segfault.
        """
        if on_progress:
            on_progress("Starting transcription process...")

        # Write result to a temp JSON file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            env = os.environ.copy()
            env["WHISPER_MODEL"] = self.model_size

            proc = subprocess.Popen(
                _WORKER_CMD + [str(audio_path), str(output_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            if on_progress:
                on_progress("Transcribing locally... (no data sent anywhere)")

            # Stream stderr progress lines while waiting
            for line in proc.stderr:
                msg = line.decode("utf-8", errors="replace").strip()
                if msg and on_progress:
                    on_progress(f"Transcribing: {msg}")

            proc.wait()

            if proc.returncode != 0:
                if on_progress:
                    on_progress("Transcription process failed")
                return None

            # Read result JSON
            if not output_path.exists():
                if on_progress:
                    on_progress("No output from transcription process")
                return None

            result = json.loads(output_path.read_text(encoding="utf-8"))

            if "error" in result:
                if on_progress:
                    on_progress(f"Transcription error: {result['error']}")
                return None

            if result.get("no_speech"):
                if on_progress:
                    on_progress("No speech detected in recording.")
                if AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION:
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
                return None

            # Build transcript dict
            transcript = {
                "audio_file": result.get("audio_file", audio_path.name),
                "language": result.get("language", "en"),
                "duration": result.get("duration", 0),
                "transcribed_at": result.get("transcribed_at", datetime.now().isoformat()),
                "full_text": result.get("full_text", ""),
                "segments": result.get("segments", []),
                "privacy": result.get("privacy", {
                    "processed_locally": True,
                    "data_sent_to_server": False,
                    "model": f"whisper-{self.model_size}"
                })
            }

            # Save transcript locally
            transcript_path = self._save_transcript(transcript, audio_path)
            transcript["transcript_file"] = str(transcript_path)

            # Delete audio for privacy
            if AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION:
                try:
                    os.remove(audio_path)
                    transcript["audio_deleted"] = True
                    if on_progress:
                        on_progress("Audio file deleted for privacy")
                except Exception:
                    pass

            if on_progress:
                on_progress("Transcription complete!")

            return transcript

        except Exception as e:
            print(f"Transcription failed: {e}")
            if on_progress:
                on_progress(f"Error: {e}")
            return None

        finally:
            # Clean up temp file
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _save_transcript(self, transcript: Dict, audio_path: Path) -> Path:
        """Save transcript to local file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_{timestamp}.json"
        filepath = TRANSCRIPTS_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, indent=2, ensure_ascii=False)

        return filepath

    def transcribe_realtime(
        self,
        audio_chunk,
        on_text: Callable
    ):
        """
        Real-time transcription for live captioning.
        Processes audio chunks as they come in.
        """
        if not self._is_loaded:
            return

        try:
            # For real-time, we use faster processing
            segments, _ = self.model.transcribe(
                audio_chunk,
                language="en",
                beam_size=1,  # Faster
                vad_filter=True  # Voice activity detection
            )

            for segment in segments:
                on_text(segment.text.strip())

        except Exception as e:
            print(f"Real-time transcription error: {e}")


def get_supported_languages() -> List[Dict]:
    """Get list of languages supported by Whisper"""
    return [
        {"code": "en", "name": "English"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
        {"code": "it", "name": "Italian"},
        {"code": "pt", "name": "Portuguese"},
        {"code": "nl", "name": "Dutch"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "zh", "name": "Chinese"},
        {"code": "ar", "name": "Arabic"},
        {"code": "hi", "name": "Hindi"},
        {"code": "ru", "name": "Russian"},
    ]
