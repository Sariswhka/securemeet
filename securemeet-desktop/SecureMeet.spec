# -*- mode: python ; coding: utf-8 -*-
#
# Two-executable build:
#   SecureMeet.exe        — Main Qt UI app (no ctranslate2/faster-whisper)
#   transcribe_worker.exe — Subprocess for Whisper transcription (no PyQt6)
#
# They must live in the same folder. The UI launches the worker as a subprocess
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
    datas=[],
    hiddenimports=['faster_whisper', 'scipy.io.wavfile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz_worker = PYZ(b.pure)

exe_worker = EXE(
    pyz_worker,
    b.scripts,
    b.binaries,
    b.datas,
    [],
    name='transcribe_worker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
