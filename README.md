# SecureMeet

**Privacy-first meeting minutes generator for Windows.**

Records any meeting (Zoom, Teams, Google Meet, or any app), transcribes locally with Whisper AI, and generates a summary — all on your machine. Zero cloud. Zero cost.

---

## Download

**[Download SecureMeet-v1.0.zip](https://github.com/Sariswhka/securemeet/releases/latest)**

Unzip → double-click `SecureMeet.exe` → load the Chrome extension → record your first meeting.

No Python required. No accounts. No API keys.

---

## How It Works

```
Chrome Extension (remote control)
         ↕  localhost:8765
Desktop App (engine)
  ├── Audio capture    — system audio, microphone, or virtual cable
  ├── Transcription    — OpenAI Whisper, runs locally on your CPU
  └── Summarization    — extractive analysis, no AI API needed
```

Everything stays on your machine. The Chrome extension talks only to `localhost` — never to any external server.

---

## Features

- Records system audio from any meeting app
- Local transcription using [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Automatic summary: key points, action items, decisions, next steps
- Chrome extension for one-click control from any meeting tab
- Export summary as Markdown
- Optional: Claude AI summaries (API key required, text only — never audio)

---

## Installation

### Requirements
- Windows 10 or 11
- Google Chrome

### Steps

1. **[Download the latest release](https://github.com/Sariswhka/securemeet/releases/latest)**
2. Unzip the folder
3. Double-click **`SecureMeet.exe`**
   - If Windows SmartScreen appears → click "More info" → "Run anyway"
   - First launch takes ~15 seconds (one-time extraction)
4. In Chrome, go to `chrome://extensions` → enable **Developer mode**
5. Click **Load unpacked** → select the `chrome-extension` folder
6. Pin the SecureMeet icon in your toolbar

### Enable System Audio (for meeting capture)

1. Right-click speaker icon → **Sound settings** → **More sound settings**
2. **Recording** tab → right-click → **Show Disabled Devices**
3. Right-click **Stereo Mix** → **Enable**

> No Stereo Mix? Install [VB-Cable](https://vb-audio.com/Cable/) (free).

---

## Privacy

| What | Where | Cloud? |
|------|-------|--------|
| Audio recording | Your device | Never |
| Transcription | Your device (Whisper) | Never |
| Summarization | Your device | Never |
| Extension ↔ App | localhost only | Never |

---

## Project Structure

```
securemeet/
├── securemeet-desktop/
│   ├── src/
│   │   ├── main.py            Desktop app (PyQt6)
│   │   ├── audio_capture.py   System audio recording
│   │   ├── transcription.py   Whisper transcription
│   │   ├── summarization.py   Local + optional Claude summarizer
│   │   ├── local_server.py    localhost:8765 API
│   │   └── config.py          Settings
│   ├── assets/
│   │   └── securemeet.ico
│   ├── requirements.txt
│   ├── setup.bat
│   └── run.bat
└── clean-extension/
    ├── manifest.json
    ├── popup.html / popup.js
    ├── background.js
    └── content.js
```

---

## Build from Source

```bash
git clone https://github.com/Sariswhka/securemeet.git
cd securemeet/securemeet-desktop
setup.bat
venv\Scripts\python src\main.py
```

---

## Tech Stack

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — Desktop UI
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Local speech-to-text
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Audio capture
- [Anthropic Claude](https://anthropic.com) — Optional AI summarization
- Chrome Extension (Manifest V3) — Browser remote control

---

*Your meetings stay private. Always.*
