#!/bin/bash
set -e

echo "============================================"
echo "  wifi-cut macOS Compiler"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not found. Install with: brew install python"
    exit 1
fi

echo "[INFO] Python version:"
python3 --version
echo ""

# Create venv
if [ ! -d "venv" ]; then
    echo "[1/4] Creating virtual environment..."
    python3 -m venv venv
else
    echo "[1/4] Virtual environment exists, skipping..."
fi

# Activate
echo "[2/4] Activating virtual environment..."
source venv/bin/activate

# Install
echo "[3/4] Installing dependencies..."
pip install -e ".[dev]" --quiet
echo "       Done."
echo ""

# Build
echo "[4/4] Building wifi-cut with PyInstaller..."
pyinstaller wifi-cut.spec --clean -y --log-level WARN
echo ""

if [ -f "dist/wifi-cut" ]; then
    SIZE=$(ls -lh dist/wifi-cut | awk '{print $5}')
    echo "============================================"
    echo "  Output: dist/wifi-cut"
    echo "  Size:   $SIZE"
    echo "============================================"
    echo ""
    echo "Usage:"
    echo "  sudo ./dist/wifi-cut interactive"
    echo "  sudo ./dist/wifi-cut scan"
    echo "  sudo ./dist/wifi-cut cut 192.168.1.5"
    echo "  sudo ./dist/wifi-cut throttle 192.168.1.5 --bw 100Kbit/s"
else
    echo "[ERROR] Build completed but wifi-cut not found in dist/"
    exit 1
fi
