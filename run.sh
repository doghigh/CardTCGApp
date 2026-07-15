#!/usr/bin/env bash
# Lorebox launcher for Linux / macOS. (Windows users: run.bat)
#
# Creates a local virtualenv on first run, installs dependencies, and starts
# the app. Physical (TWAIN) scanning is Windows-only; on Linux/macOS use the
# file/PDF batch-import workflow instead.
set -e
cd "$(dirname "$0")"

echo "================================================"
echo "   Lorebox"
echo "   Privacy-First TCG Collection App"
echo "================================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 is not installed or not on PATH." >&2
    echo "Install Python 3 from your package manager or https://python.org" >&2
    exit 1
fi

# Create the virtual environment on first run.
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing / updating dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Starting Lorebox... (Ctrl+C to stop)"
python main.py

deactivate 2>/dev/null || true
