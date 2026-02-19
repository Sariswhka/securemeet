# -*- mode: python ; coding: utf-8 -*-
#
# Two-executable build:
#   SecureMeet.exe              — Main Qt UI app (no ctranslate2/faster-whisper)
#   transcribe_worker/          — Subprocess for Whisper transcription (no PyQt6)
#     transcribe_worker.exe
#     (+ DLLs pre-extracted here — no extraction overhead on each call)
#
# SecureMeet.exe must live alongside the transcribe_worker/ folder.
# The UI launches transcribe_worker/transcribe_worker.exe as a subprocess
# to avoid the PyQt6 + ctranslate2 DLL segfault on Windows.

# ── Main application ──────────────────────────────────────────────────────────
a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['sounddevice', 'scipy.signal', 'anthropic', 'cryptography', 'dotenv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['faster_whisper', 'ctranslate2', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SecureMeet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\securemeet.ico'],
)

# ── Transcription worker (subprocess) ─────────────────────────────────────────
b = Analysis(
    ['src\\transcribe_worker.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        # Silero VAD model required by faster-whisper's vad_filter=True
        ('venv\\Lib\\site-packages\\faster_whisper\\assets\\silero_vad_v6.onnx',
         'faster_whisper\\assets'),
    ],
    hiddenimports=['faster_whisper', 'scipy.io.wavfile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz_worker = PYZ(b.pure)

# Worker exe — NOT onefile, so it doesn't extract on every run.
# All DLLs sit next to the exe permanently in dist/transcribe_worker/.
exe_worker = EXE(
    pyz_worker,
    b.scripts,
    [],
    exclude_binaries=True,   # binaries go into COLLECT, not into the exe
    name='transcribe_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_worker,
    b.binaries,
    b.zipfiles,
    b.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='transcribe_worker',   # creates dist/transcribe_worker/ folder
)
