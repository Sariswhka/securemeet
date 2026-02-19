"""
Standalone transcription worker — runs as a subprocess.
Kept completely separate from the main app so PyQt6 and ctranslate2
never share the same process (they segfault together on Windows).

Usage:
    python transcribe_worker.py <audio_path> <output_json_path>
"""
import sys
import json
import os
from pathlib import Path
from datetime import datetime

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: transcribe_worker.py <audio_path> <output_json>"}))
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not audio_path.exists():
        output_path.write_text(json.dumps({"error": f"Audio file not found: {audio_path}"}))
        sys.exit(1)

    try:
        from faster_whisper import WhisperModel

        model_size = os.environ.get("WHISPER_MODEL", "base")
        sys.stderr.write(f"Loading model ({model_size})...\n")
        sys.stderr.flush()

        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        sys.stderr.write("Model loaded. Transcribing...\n")
        sys.stderr.flush()

        segments, info = model.transcribe(
            str(audio_path),
            language="en",
            beam_size=1,
            word_timestamps=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500}
        )

        transcript_segments = []
        full_text_parts = []
        for segment in segments:
            text = segment.text.strip()
            transcript_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": text
            })
            full_text_parts.append(text)
            sys.stderr.write(f"  [{segment.end:.1f}s] {text[:60]}\n")
            sys.stderr.flush()

        full_text = " ".join(full_text_parts)

        # No speech guard
        if len(full_text.strip()) < 20:
            result = {"no_speech": True}
        else:
            result = {
                "no_speech": False,
                "full_text": full_text,
                "segments": transcript_segments,
                "language": info.language,
                "duration": info.duration,
                "transcribed_at": datetime.now().isoformat(),
                "audio_file": audio_path.name,
                "privacy": {
                    "processed_locally": True,
                    "data_sent_to_server": False,
                    "model": f"whisper-{model_size}"
                }
            }

        output_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        sys.stderr.write("Done.\n")
        sys.stderr.flush()

    except Exception as e:
        import traceback
        output_path.write_text(json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc()
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
