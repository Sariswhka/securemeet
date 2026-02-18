"""
Transcription Module
Uses faster-whisper for 100% LOCAL transcription
No audio data is ever sent to any server
"""
import os
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime
import json

from config import (
    WHISPER_MODEL,
    TRANSCRIPTS_DIR,
    AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION
)


class LocalTranscriber:
    """
    Local transcription using faster-whisper.
    ALL PROCESSING HAPPENS ON YOUR MACHINE.
    """

    def __init__(self, model_size: str = WHISPER_MODEL):
        self.model_size = model_size
        self.model = None
        self._is_loaded = False

    def load_model(self, on_progress: Optional[Callable] = None) -> bool:
        """
        Load Whisper model locally.
        First run will download the model (~150MB for base).
        Model is cached locally for future use.
        """
        try:
            if on_progress:
                on_progress("Loading Whisper model locally...")

            from faster_whisper import WhisperModel

            # Use CPU by default (works everywhere)
            # Can use 'cuda' for NVIDIA GPU acceleration
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8"  # Optimized for CPU
            )

            self._is_loaded = True
            if on_progress:
                on_progress("Model loaded successfully!")

            return True

        except Exception as e:
            print(f"Failed to load model: {e}")
            return False

    def transcribe(
        self,
        audio_path: Path,
        on_progress: Optional[Callable] = None,
        language: str = "en"
    ) -> Optional[Dict]:
        """
        Transcribe audio file locally.

        Args:
            audio_path: Path to audio file
            on_progress: Callback for progress updates
            language: Language code (en, es, fr, etc.)

        Returns:
            Dict with transcript and metadata
        """
        if not self._is_loaded:
            if not self.load_model(on_progress):
                return None

        try:
            if on_progress:
                on_progress("Transcribing locally... (no data sent anywhere)")

            # Transcribe with timestamps
            segments, info = self.model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                word_timestamps=True
            )

            # Process segments
            transcript_segments = []
            full_text = []

            for segment in segments:
                segment_data = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                }
                transcript_segments.append(segment_data)
                full_text.append(segment.text.strip())

                if on_progress:
                    on_progress(f"Transcribed: {segment.end:.1f}s")

            # Create transcript object
            transcript = {
                "audio_file": str(audio_path.name),
                "language": info.language,
                "duration": info.duration,
                "transcribed_at": datetime.now().isoformat(),
                "full_text": " ".join(full_text),
                "segments": transcript_segments,
                "privacy": {
                    "processed_locally": True,
                    "data_sent_to_server": False,
                    "model": f"whisper-{self.model_size}"
                }
            }

            # Save transcript locally
            transcript_path = self._save_transcript(transcript, audio_path)
            transcript["transcript_file"] = str(transcript_path)

            # Optionally delete audio after transcription for privacy
            if AUTO_DELETE_AUDIO_AFTER_TRANSCRIPTION:
                try:
                    os.remove(audio_path)
                    transcript["audio_deleted"] = True
                    if on_progress:
                        on_progress("Audio file deleted for privacy")
                except:
                    pass

            if on_progress:
                on_progress("Transcription complete!")

            return transcript

        except Exception as e:
            print(f"Transcription failed: {e}")
            if on_progress:
                on_progress(f"Error: {e}")
            return None

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
