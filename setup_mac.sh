#!/bin/bash
# setup_mac.sh
# One-time setup script for macOS. Fixes the classic
# "fatal error: 'portaudio.h' file not found" PyAudio build failure
# by installing PortAudio via Homebrew BEFORE pip tries to build PyAudio,
# and by pointing pip at Homebrew's include/lib folders.
#
# Usage:
#   chmod +x setup_mac.sh
#   ./setup_mac.sh

set -e

echo "==> Checking for Homebrew..."
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Install it first from https://brew.sh then re-run this script."
    exit 1
fi

echo "==> Installing Python 3.12, Tkinter, PortAudio, and FLAC via Homebrew..."
brew install python@3.12 python-tk@3.12 portaudio flac

echo "==> Creating virtual environment (venv) with Python 3.12..."
rm -rf venv
"$(brew --prefix python@3.12)/bin/python3.12" -m venv venv
source venv/bin/activate

echo "==> Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

echo "==> Pointing the compiler at Homebrew's PortAudio headers..."
export CFLAGS="-I$(brew --prefix portaudio)/include"
export LDFLAGS="-L$(brew --prefix portaudio)/lib"

echo "==> Installing requirements..."
pip install -r requirements.txt

echo "==> Verifying PyAudio import..."
python -c "import pyaudio; print('PyAudio OK')"

echo ""
echo "Setup complete. To run the app:"
echo "  source venv/bin/activate"
echo "  python main.py"
