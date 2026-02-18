"""
Audio Capture Module
Captures system audio from any application (Zoom, Teams, Meet, etc.)
All processing happens locally - no data leaves your machine
"""
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
import threading
import queue
import time
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from config import SAMPLE_RATE, CHANNELS, RECORDINGS_DIR


class AudioCapture:
    """Captures system audio locally for transcription"""

    def __init__(self, on_audio_chunk: Optional[Callable] = None):
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.recorded_data = []
        self.on_audio_chunk = on_audio_chunk
        self.stream = None
        self.recording_thread = None
        self.start_time = None

    def get_audio_devices(self) -> list:
        """Get list of available audio input devices"""
        devices = sd.query_devices()
        input_devices = []

        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })

        return input_devices

    def get_loopback_device(self) -> Optional[int]:
        """
        Find system loopback device for capturing system audio.
        On Windows: Look for 'Stereo Mix', 'What U Hear', or WASAPI loopback
        On Mac: Requires BlackHole or similar virtual audio device
        """
        devices = sd.query_devices()

        # Common loopback device names
        loopback_names = [
            'stereo mix',
            'what u hear',
            'loopback',
            'blackhole',
            'soundflower',
            'virtual cable',
            'wasapi',
            'system audio'
        ]

        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if device['max_input_channels'] > 0:
                for name in loopback_names:
                    if name in device_name:
                        return i

        return None

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream - runs in separate thread"""
        if status:
            print(f"Audio status: {status}")

        # Copy audio data
        audio_chunk = indata.copy()
        self.audio_queue.put(audio_chunk)
        self.recorded_data.append(audio_chunk)

        # Notify listener if callback provided
        if self.on_audio_chunk:
            self.on_audio_chunk(audio_chunk)

    def start_recording(self, device_id: Optional[int] = None) -> bool:
        """
        Start capturing audio.

        Args:
            device_id: Specific device to use, or None for default/loopback

        Returns:
            True if recording started successfully
        """
        if self.is_recording:
            return False

        try:
            # Try to find loopback device if none specified
            if device_id is None:
                device_id = self.get_loopback_device()

            # Configure stream
            self.stream = sd.InputStream(
                device=device_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=self._audio_callback,
                blocksize=int(SAMPLE_RATE * 0.5)  # 500ms blocks
            )

            self.recorded_data = []
            self.start_time = datetime.now()
            self.stream.start()
            self.is_recording = True

            print(f"Recording started on device: {device_id}")
            return True

        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> Optional[Path]:
        """
        Stop recording and save audio file locally.

        Returns:
            Path to saved audio file, or None if failed
        """
        if not self.is_recording:
            return None

        try:
            self.is_recording = False
            self.stream.stop()
            self.stream.close()

            # Combine all audio chunks
            if not self.recorded_data:
                return None

            audio_data = np.concatenate(self.recorded_data, axis=0)

            # Generate filename with timestamp
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            filename = f"meeting_{timestamp}.wav"
            filepath = RECORDINGS_DIR / filename

            # Save locally (never uploaded)
            audio_normalized = (audio_data * 32767).astype(np.int16)
            wavfile.write(str(filepath), SAMPLE_RATE, audio_normalized)

            duration = len(audio_data) / SAMPLE_RATE
            print(f"Recording saved: {filepath} ({duration:.1f}s)")

            return filepath

        except Exception as e:
            print(f"Failed to save recording: {e}")
            return None

    def get_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self.is_recording or not self.start_time:
            return 0.0
        return (datetime.now() - self.start_time).total_seconds()

    def get_audio_level(self) -> float:
        """Get current audio level (0-1) for visualization"""
        try:
            if not self.audio_queue.empty():
                chunk = self.audio_queue.get_nowait()
                return float(np.abs(chunk).mean())
        except:
            pass
        return 0.0


class MicrophoneCapture(AudioCapture):
    """Captures audio from microphone (for speaker's own voice)"""

    def get_default_microphone(self) -> Optional[int]:
        """Get default microphone device"""
        try:
            return sd.default.device[0]  # Default input device
        except:
            return None

    def start_recording(self, device_id: Optional[int] = None) -> bool:
        """Start recording from microphone"""
        if device_id is None:
            device_id = self.get_default_microphone()
        return super().start_recording(device_id)


class MixedCapture(AudioCapture):
    """
    Captures system audio + microphone simultaneously and mixes them.
    Ensures both sides of a conversation are captured:
      - System audio (Stereo Mix / loopback) → other participants
      - Microphone → your own voice
    """

    def __init__(self, on_audio_chunk: Optional[Callable] = None):
        super().__init__(on_audio_chunk)
        self.mic_stream = None
        self.mic_data = []

    def _mic_callback(self, indata, frames, time_info, status):
        """Callback for microphone stream"""
        self.mic_data.append(indata.copy())

    def start_recording(self, device_id: Optional[int] = None) -> bool:
        """Start system audio + microphone streams simultaneously"""
        self.mic_data = []

        # Start system audio (loopback) via parent
        loopback_id = self.get_loopback_device()
        system_ok = super().start_recording(loopback_id)

        # Start microphone stream independently
        try:
            mic_id = sd.default.device[0]
            self.mic_stream = sd.InputStream(
                device=mic_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=self._mic_callback,
                blocksize=int(SAMPLE_RATE * 0.5)
            )
            self.mic_stream.start()
            print("Microphone stream started")
        except Exception as e:
            print(f"Microphone stream failed (system audio only): {e}")
            self.mic_stream = None

        return system_ok

    def stop_recording(self) -> Optional[Path]:
        """Stop both streams, mix audio, save combined file"""
        if not self.is_recording:
            return None

        self.is_recording = False

        # Stop system audio stream
        try:
            self.stream.stop()
            self.stream.close()
        except Exception as e:
            print(f"Error stopping system stream: {e}")

        # Stop microphone stream
        if self.mic_stream:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception as e:
                print(f"Error stopping mic stream: {e}")
            self.mic_stream = None

        if not self.recorded_data and not self.mic_data:
            return None

        # Build system audio array
        system_audio = np.concatenate(self.recorded_data, axis=0) if self.recorded_data else None

        # Build microphone audio array
        mic_audio = np.concatenate(self.mic_data, axis=0) if self.mic_data else None

        # Mix: average both signals aligned to shortest length
        if system_audio is not None and mic_audio is not None:
            min_len = min(len(system_audio), len(mic_audio))
            mixed = system_audio[:min_len] * 0.6 + mic_audio[:min_len] * 0.4
        elif system_audio is not None:
            mixed = system_audio
        else:
            mixed = mic_audio

        # Save mixed audio file
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"meeting_{timestamp}.wav"
        filepath = RECORDINGS_DIR / filename

        audio_normalized = (mixed * 32767).astype(np.int16)
        wavfile.write(str(filepath), SAMPLE_RATE, audio_normalized)

        duration = len(mixed) / SAMPLE_RATE
        print(f"Mixed recording saved: {filepath} ({duration:.1f}s)")

        return filepath
