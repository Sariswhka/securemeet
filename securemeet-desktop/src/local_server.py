"""
Local HTTP Server for SecureMeet Desktop
Allows the Chrome extension to communicate with the Desktop app via localhost.

PRIVACY: All communication stays on localhost - nothing leaves your machine.
Port: 8765 (configurable)
"""
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable


# Default port for the local server
SERVER_PORT = 8765


class SecureMeetRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests from the Chrome extension"""

    # Reference to the app instance, set by SecureMeetLocalServer
    app = None

    def _set_cors_headers(self):
        """Set CORS headers to allow Chrome extension access"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, data: dict):
        """Send a JSON response"""
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/status":
            self._handle_status()
        elif self.path == "/transcript":
            self._handle_get_transcript()
        elif self.path == "/summary":
            self._handle_get_summary()
        elif self.path == "/devices":
            self._handle_get_devices()
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        """Handle POST requests"""
        if self.path == "/start":
            self._handle_start()
        elif self.path == "/stop":
            self._handle_stop()
        else:
            self._send_json(404, {"error": "Not found"})

    def _read_body(self) -> dict:
        """Read and parse JSON request body"""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # --- Endpoint handlers ---

    def _handle_status(self):
        """GET /status - Check if the Desktop app is running and its state"""
        app = self.__class__.app
        if app is None:
            self._send_json(200, {
                "running": True,
                "recording": False,
                "has_transcript": False,
                "has_summary": False,
                "version": "1.0.0"
            })
            return

        self._send_json(200, {
            "running": True,
            "recording": app.is_recording,
            "has_transcript": app.current_transcript is not None,
            "has_summary": app.current_summary is not None,
            "duration": app.audio_capture.get_duration() if app.is_recording else 0,
            "audio_level": app.audio_capture.get_audio_level() if app.is_recording else 0,
            "version": "1.0.0"
        })

    def _handle_start(self):
        """POST /start - Start recording"""
        app = self.__class__.app
        if app is None:
            self._send_json(503, {"error": "App not initialized"})
            return

        if app.is_recording:
            self._send_json(409, {"error": "Already recording"})
            return

        body = self._read_body()
        device_id = body.get("device_id")

        # Convert string device_id to int if provided
        if device_id is not None:
            try:
                device_id = int(device_id)
            except (ValueError, TypeError):
                device_id = None

        success = app.audio_capture.start_recording(device_id)
        if success:
            app.is_recording = True
            app.duration_timer.start(1000)
            # Update UI from server thread safely
            if hasattr(app, '_update_ui_recording_started'):
                app._update_ui_recording_started()
            self._send_json(200, {"success": True, "message": "Recording started"})
        else:
            self._send_json(500, {"error": "Failed to start recording. Check audio device."})

    def _handle_stop(self):
        """POST /stop - Stop recording, trigger transcription + summarization"""
        app = self.__class__.app
        if app is None:
            self._send_json(503, {"error": "App not initialized"})
            return

        if not app.is_recording:
            self._send_json(409, {"error": "Not recording"})
            return

        # Stop recording
        app.duration_timer.stop()
        audio_path = app.audio_capture.stop_recording()
        app.is_recording = False

        # Update UI
        if hasattr(app, '_update_ui_recording_stopped'):
            app._update_ui_recording_stopped()

        if audio_path:
            # Transcribe synchronously for the API response,
            # but in a background thread so we don't block forever
            self._send_json(200, {
                "success": True,
                "message": "Recording stopped. Transcription starting...",
                "audio_file": str(audio_path)
            })
            # Trigger transcription in the app (runs in background thread)
            app.transcribe_audio(audio_path)
        else:
            self._send_json(200, {
                "success": True,
                "message": "Recording stopped. No audio captured."
            })

    def _handle_get_transcript(self):
        """GET /transcript - Get the latest transcript"""
        app = self.__class__.app
        if app is None:
            self._send_json(503, {"error": "App not initialized"})
            return

        if app.current_transcript is None:
            self._send_json(200, {"ready": False, "message": "No transcript available"})
            return

        self._send_json(200, {
            "ready": True,
            "full_text": app.current_transcript.get("full_text", ""),
            "duration": app.current_transcript.get("duration", 0),
            "language": app.current_transcript.get("language", "en"),
            "segments": app.current_transcript.get("segments", [])
        })

    def _handle_get_summary(self):
        """GET /summary - Get the latest summary"""
        app = self.__class__.app
        if app is None:
            self._send_json(503, {"error": "App not initialized"})
            return

        if app.current_summary is None:
            self._send_json(200, {"ready": False, "message": "No summary available"})
            return

        self._send_json(200, {
            "ready": True,
            "meeting_title": app.current_summary.get("meeting_title", "Meeting"),
            "executive_summary": app.current_summary.get("executive_summary", ""),
            "key_discussion_points": app.current_summary.get("key_discussion_points", []),
            "decisions_made": app.current_summary.get("decisions_made", []),
            "action_items": app.current_summary.get("action_items", []),
            "next_steps": app.current_summary.get("next_steps", []),
            "model_used": app.current_summary.get("model_used", "unknown")
        })

    def _handle_get_devices(self):
        """GET /devices - List available audio devices"""
        app = self.__class__.app
        if app is None:
            self._send_json(503, {"error": "App not initialized"})
            return

        devices = app.audio_capture.get_audio_devices()
        loopback_id = app.audio_capture.get_loopback_device()

        device_list = []
        if loopback_id is not None:
            device_list.append({
                "id": loopback_id,
                "name": "System Audio (Recommended)",
                "is_loopback": True
            })

        for device in devices:
            device_list.append({
                "id": device["id"],
                "name": device["name"],
                "channels": device["channels"],
                "is_loopback": False
            })

        self._send_json(200, {"devices": device_list})

    def log_message(self, format, *args):
        """Suppress default HTTP logging to keep console clean"""
        pass


class SecureMeetLocalServer:
    """
    Manages the local HTTP server that bridges Chrome extension ↔ Desktop app.
    Runs in a background daemon thread so it doesn't block the UI.
    """

    def __init__(self, app=None, port: int = SERVER_PORT):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        SecureMeetRequestHandler.app = app

    def set_app(self, app):
        """Set the app reference (can be set after construction)"""
        SecureMeetRequestHandler.app = app

    def start(self):
        """Start the local HTTP server in a background thread"""
        try:
            self.server = HTTPServer(("127.0.0.1", self.port), SecureMeetRequestHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"SecureMeet local server started on http://127.0.0.1:{self.port}")
        except OSError as e:
            print(f"Failed to start local server on port {self.port}: {e}")
            # Port might be in use - try to continue without server
            self.server = None

    def stop(self):
        """Stop the local HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server = None
            self.thread = None
            print("SecureMeet local server stopped")

    def is_running(self) -> bool:
        """Check if the server is currently running"""
        return self.server is not None and self.thread is not None and self.thread.is_alive()
