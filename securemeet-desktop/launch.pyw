"""
SecureMeet Desktop Launcher
Double-click this file (or a shortcut to it) to start the app.
Uses .pyw extension so no console window appears on Windows.
"""
import subprocess
import sys
import os
from pathlib import Path

# Get the project root (where this file lives)
project_root = Path(__file__).parent
venv_python = project_root / "venv" / "Scripts" / "pythonw.exe"
main_script = project_root / "src" / "main.py"

# Fall back to regular python if pythonw not found in venv
if not venv_python.exists():
    venv_python = project_root / "venv" / "Scripts" / "python.exe"

if not venv_python.exists():
    # No venv — try system python
    venv_python = sys.executable

# Launch the app
os.chdir(str(project_root))
subprocess.Popen(
    [str(venv_python), str(main_script)],
    cwd=str(project_root),
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
)
