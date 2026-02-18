"""
SecureMeet Desktop - Main Application
Privacy-first meeting minutes generator

HOW IT WORKS:
1. Captures system audio locally (Zoom, Teams, Meet, any app)
2. Transcribes using Whisper (runs on YOUR machine)
3. Generates summary using Claude API (only text sent, never audio)
4. All data stored locally, audio deleted after transcription
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QProgressBar, QComboBox,
    QLineEdit, QTabWidget, QGroupBox, QMessageBox, QFileDialog,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QAction

from config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT,
    SUMMARIES_DIR, TRANSCRIPTS_DIR
)
from audio_capture import AudioCapture
from transcription import LocalTranscriber
from summarization import MeetingSummarizer, format_summary_for_display
from local_server import SecureMeetLocalServer


class WorkerThread(QThread):
    """Background worker for long-running tasks"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class SecureMeetApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize components
        self.audio_capture = AudioCapture()
        self.transcriber = LocalTranscriber()
        self.summarizer = MeetingSummarizer()

        # State
        self.is_recording = False
        self.current_transcript = None
        self.current_summary = None

        # Setup UI
        self.init_ui()
        self.apply_dark_theme()

        # Timer for recording duration
        self.duration_timer = QTimer()
        self.duration_timer.timeout.connect(self.update_duration)

        # Start local HTTP server for Chrome extension bridge
        self.local_server = SecureMeetLocalServer(app=self)
        self.local_server.start()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel(f"🔒 {APP_NAME}")
        header.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Privacy badge
        privacy_label = QLabel("✓ Audio never leaves your device")
        privacy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        privacy_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        layout.addWidget(privacy_label)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_record_tab(), "📹 Record")
        tabs.addTab(self.create_summary_tab(), "📋 Summary")
        tabs.addTab(self.create_settings_tab(), "⚙️ Settings")
        tabs.addTab(self.create_history_tab(), "📁 History")
        layout.addWidget(tabs)

        # Status bar
        self.status_label = QLabel("Ready to record")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(self.status_label)

    def create_record_tab(self) -> QWidget:
        """Create the recording tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Audio device selection
        device_group = QGroupBox("Audio Source")
        device_layout = QVBoxLayout(device_group)

        self.device_combo = QComboBox()
        self.refresh_devices()
        device_layout.addWidget(self.device_combo)

        refresh_btn = QPushButton("🔄 Refresh Devices")
        refresh_btn.clicked.connect(self.refresh_devices)
        device_layout.addWidget(refresh_btn)

        layout.addWidget(device_group)

        # Recording controls
        control_group = QGroupBox("Recording")
        control_layout = QVBoxLayout(control_group)

        # Duration display
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("Courier", 32, QFont.Weight.Bold))
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(self.duration_label)

        # Audio level indicator
        self.level_bar = QProgressBar()
        self.level_bar.setMaximum(100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setStyleSheet("""
            QProgressBar { border: none; background: #333; height: 10px; border-radius: 5px; }
            QProgressBar::chunk { background: #4CAF50; border-radius: 5px; }
        """)
        control_layout.addWidget(self.level_bar)

        # Record button
        self.record_btn = QPushButton("🎤 Start Recording")
        self.record_btn.setMinimumHeight(60)
        self.record_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background: #45a049; }
            QPushButton:pressed { background: #3d8b40; }
        """)
        control_layout.addWidget(self.record_btn)

        layout.addWidget(control_group)

        # Privacy notice
        privacy_text = QLabel(
            "🔒 Privacy: Audio is recorded locally and transcribed on your device.\n"
            "Audio files are automatically deleted after transcription."
        )
        privacy_text.setWordWrap(True)
        privacy_text.setStyleSheet("color: #888; font-size: 11px; padding: 10px;")
        layout.addWidget(privacy_text)

        layout.addStretch()
        return tab

    def create_summary_tab(self) -> QWidget:
        """Create the summary tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Meeting title
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Meeting Title:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter meeting title...")
        title_layout.addWidget(self.title_input)
        layout.addLayout(title_layout)

        # Summary mode selector
        mode_group = QGroupBox("Summary Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Local (100% Offline - No API needed)", "local")
        self.mode_combo.addItem("Claude API (AI-powered - requires API key)", "claude")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        self.mode_info = QLabel("All processing happens on your device. Nothing is sent anywhere.")
        self.mode_info.setStyleSheet("color: #4CAF50; font-size: 11px;")
        self.mode_info.setWordWrap(True)
        mode_layout.addWidget(self.mode_info)

        layout.addWidget(mode_group)

        # Progress
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888;")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Generate button
        self.generate_btn = QPushButton("✨ Generate Summary (Local)")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.clicked.connect(self.generate_summary)
        self.generate_btn.setEnabled(False)
        layout.addWidget(self.generate_btn)

        # Summary display
        self.summary_display = QTextEdit()
        self.summary_display.setReadOnly(True)
        self.summary_display.setPlaceholderText(
            "Summary will appear here after recording and processing..."
        )
        layout.addWidget(self.summary_display)

        # Export button
        export_btn = QPushButton("📄 Export Summary")
        export_btn.clicked.connect(self.export_summary)
        layout.addWidget(export_btn)

        return tab

    def create_settings_tab(self) -> QWidget:
        """Create the settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # API Key
        api_group = QGroupBox("Claude API Key")
        api_layout = QVBoxLayout(api_group)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addWidget(self.api_key_input)

        save_key_btn = QPushButton("Save API Key")
        save_key_btn.clicked.connect(self.save_api_key)
        api_layout.addWidget(save_key_btn)

        api_note = QLabel(
            "Get your API key from console.anthropic.com\n"
            "Your key is stored locally and never shared."
        )
        api_note.setStyleSheet("color: #888; font-size: 11px;")
        api_layout.addWidget(api_note)

        layout.addWidget(api_group)

        # Whisper model selection
        model_group = QGroupBox("Transcription Quality")
        model_layout = QVBoxLayout(model_group)

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny - Fastest, basic quality",
            "base - Good balance (recommended)",
            "small - Better quality, slower",
            "medium - High quality, slow",
            "large-v3 - Best quality, requires good hardware"
        ])
        self.model_combo.setCurrentIndex(1)
        model_layout.addWidget(self.model_combo)

        layout.addWidget(model_group)

        # Privacy info
        privacy_group = QGroupBox("Privacy Information")
        privacy_layout = QVBoxLayout(privacy_group)

        privacy_info = QLabel(
            "🔒 How your data is protected:\n\n"
            "• Audio is recorded and stored ONLY on your device\n"
            "• Transcription runs LOCALLY using Whisper AI\n"
            "• Audio is deleted immediately after transcription\n"
            "• Only text transcripts are sent to Claude API\n"
            "• Anthropic does NOT train on API data\n"
            "• All summaries are saved locally on your device"
        )
        privacy_info.setWordWrap(True)
        privacy_info.setStyleSheet("color: #4CAF50;")
        privacy_layout.addWidget(privacy_info)

        layout.addWidget(privacy_group)

        layout.addStretch()
        return tab

    def create_history_tab(self) -> QWidget:
        """Create the history tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Summaries list
        layout.addWidget(QLabel("Recent Summaries:"))

        self.history_list = QTextEdit()
        self.history_list.setReadOnly(True)
        layout.addWidget(self.history_list)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_history)
        layout.addWidget(refresh_btn)

        # Open folder button
        folder_btn = QPushButton("📁 Open Summaries Folder")
        folder_btn.clicked.connect(lambda: os.startfile(str(SUMMARIES_DIR)))
        layout.addWidget(folder_btn)

        self.refresh_history()
        return tab

    def apply_dark_theme(self):
        """Apply dark theme to application"""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a2e;
                color: #eee;
            }
            QGroupBox {
                border: 1px solid #333;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: #16213e;
                border: 1px solid #333;
                border-radius: 5px;
                padding: 8px;
                color: #eee;
            }
            QPushButton {
                background: #0f3460;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background: #1a4a7a;
            }
            QPushButton:disabled {
                background: #333;
                color: #666;
            }
            QTabWidget::pane {
                border: 1px solid #333;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #16213e;
                color: #888;
                padding: 10px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #0f3460;
                color: #fff;
            }
            QProgressBar {
                border: none;
                background: #333;
                height: 20px;
                border-radius: 10px;
            }
            QProgressBar::chunk {
                background: #4CAF50;
                border-radius: 10px;
            }
        """)

    def on_mode_changed(self, index):
        """Handle summary mode change"""
        mode = self.mode_combo.currentData()
        if mode == "local":
            self.summarizer.set_mode(use_local=True)
            self.mode_info.setText("All processing happens on your device. Nothing is sent anywhere.")
            self.mode_info.setStyleSheet("color: #4CAF50; font-size: 11px;")
            self.generate_btn.setText("✨ Generate Summary (Local)")
        else:
            self.summarizer.set_mode(use_local=False)
            self.mode_info.setText("Transcript text will be sent to Claude API. Audio stays local.")
            self.mode_info.setStyleSheet("color: #FFA726; font-size: 11px;")
            self.generate_btn.setText("✨ Generate Summary (Claude AI)")

    def refresh_devices(self):
        """Refresh audio device list"""
        self.device_combo.clear()
        devices = self.audio_capture.get_audio_devices()

        # Add loopback option first
        loopback_id = self.audio_capture.get_loopback_device()
        if loopback_id is not None:
            self.device_combo.addItem("🔊 System Audio (Recommended)", loopback_id)

        for device in devices:
            self.device_combo.addItem(f"🎤 {device['name']}", device['id'])

        if self.device_combo.count() == 0:
            self.device_combo.addItem("No audio devices found", None)

    def toggle_recording(self):
        """Start or stop recording"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording"""
        device_id = self.device_combo.currentData()

        if self.audio_capture.start_recording(device_id):
            self.is_recording = True
            self.record_btn.setText("⏹️ Stop Recording")
            self.record_btn.setStyleSheet("""
                QPushButton {
                    background: #f44336;
                    color: white;
                    border: none;
                    border-radius: 10px;
                }
                QPushButton:hover { background: #da190b; }
            """)
            self.duration_timer.start(1000)
            self.status_label.setText("Recording... Audio stays on your device")
            self.generate_btn.setEnabled(False)
        else:
            QMessageBox.warning(
                self,
                "Recording Error",
                "Failed to start recording.\n\n"
                "Try selecting a different audio device.\n"
                "On Windows: Enable 'Stereo Mix' in Sound settings.\n"
                "On Mac: Install BlackHole for system audio capture."
            )

    def stop_recording(self):
        """Stop recording and start transcription"""
        self.duration_timer.stop()
        audio_path = self.audio_capture.stop_recording()

        self.is_recording = False
        self.record_btn.setText("🎤 Start Recording")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background: #45a049; }
        """)

        if audio_path:
            self.status_label.setText("Transcribing locally...")
            self.transcribe_audio(audio_path)
        else:
            self.status_label.setText("No audio recorded")

    def update_duration(self):
        """Update recording duration display"""
        duration = self.audio_capture.get_duration()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        self.duration_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # Update audio level
        level = self.audio_capture.get_audio_level() * 100
        self.level_bar.setValue(int(min(level * 5, 100)))

    def transcribe_audio(self, audio_path):
        """Transcribe audio in background thread"""
        def do_transcribe():
            return self.transcriber.transcribe(
                audio_path,
                on_progress=lambda msg: self.worker.progress.emit(msg)
            )

        self.worker = WorkerThread(do_transcribe)
        self.worker.progress.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_transcription_complete)
        self.worker.error.connect(lambda e: self.status_label.setText(f"Error: {e}"))
        self.worker.start()

    def on_transcription_complete(self, transcript):
        """Handle completed transcription - auto-generate summary"""
        self.current_transcript = transcript
        if transcript:
            self.generate_btn.setEnabled(True)
            self.summary_display.setText(
                f"Transcript ready ({transcript.get('duration', 0):.1f}s)\n\n"
                f"Preview:\n{transcript.get('full_text', '')[:500]}..."
            )
            # Auto-generate summary
            self.status_label.setText("Generating summary...")
            self.generate_summary()
        else:
            self.status_label.setText("Transcription failed")

    def generate_summary(self):
        """Generate meeting summary"""
        if not self.current_transcript:
            return

        title = self.title_input.text() or "Meeting"
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.generate_btn.setEnabled(False)

        def do_summarize():
            return self.summarizer.summarize(
                self.current_transcript,
                meeting_title=title,
                on_progress=lambda msg: self.worker.progress.emit(msg)
            )

        self.worker = WorkerThread(do_summarize)
        self.worker.progress.connect(self.progress_label.setText)
        self.worker.finished.connect(self.on_summary_complete)
        self.worker.error.connect(self.on_summary_error)
        self.worker.start()

    def on_summary_complete(self, summary):
        """Handle completed summary"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.current_summary = summary

        if summary:
            self.status_label.setText("Summary generated!")
            display_text = format_summary_for_display(summary)
            self.summary_display.setText(display_text)
        else:
            self.status_label.setText("Summary generation failed")

    def on_summary_error(self, error):
        """Handle summary error"""
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error}")

        if "api_key" in error.lower() or "unauthorized" in error.lower():
            QMessageBox.warning(
                self,
                "API Key Required",
                "Please add your Anthropic API key in Settings tab."
            )

    def save_api_key(self):
        """Save API key"""
        key = self.api_key_input.text().strip()
        if key:
            self.summarizer.set_api_key(key)
            # Save to .env file
            env_path = Path(__file__).parent.parent / ".env"
            with open(env_path, 'w') as f:
                f.write(f"ANTHROPIC_API_KEY={key}\n")
            QMessageBox.information(self, "Saved", "API key saved successfully!")
        else:
            QMessageBox.warning(self, "Error", "Please enter an API key")

    def export_summary(self):
        """Export summary to file"""
        if not self.current_summary:
            QMessageBox.warning(self, "No Summary", "Generate a summary first")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Summary",
            str(SUMMARIES_DIR / "meeting_summary.md"),
            "Markdown (*.md);;Text (*.txt);;JSON (*.json)"
        )

        if filepath:
            # Already saved, just show location
            QMessageBox.information(
                self,
                "Exported",
                f"Summary saved to:\n{self.current_summary.get('summary_file', filepath)}"
            )

    def _update_ui_recording_started(self):
        """Update UI when recording is started via the local server (Chrome extension)"""
        self.record_btn.setText("⏹️ Stop Recording")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background: #da190b; }
        """)
        self.status_label.setText("Recording via Chrome extension... Audio stays on your device")
        self.generate_btn.setEnabled(False)

    def _update_ui_recording_stopped(self):
        """Update UI when recording is stopped via the local server (Chrome extension)"""
        self.record_btn.setText("🎤 Start Recording")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover { background: #45a049; }
        """)

    def closeEvent(self, event):
        """Stop the local server when the app is closed"""
        self.local_server.stop()
        super().closeEvent(event)

    def refresh_history(self):
        """Refresh history list"""
        summaries = list(SUMMARIES_DIR.glob("*.md"))
        summaries.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        history_text = []
        for summary_file in summaries[:20]:  # Last 20
            history_text.append(f"📄 {summary_file.name}")

        if history_text:
            self.history_list.setText("\n".join(history_text))
        else:
            self.history_list.setText("No summaries yet. Record a meeting to get started!")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = SecureMeetApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
