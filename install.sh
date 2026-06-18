#!/usr/bin/env bash
# VeriForge installer: sets up a Python virtualenv with the GUI dependencies.
set -e
cd "$(dirname "$0")"

echo "==> Checking for Icarus Verilog..."
if ! command -v iverilog >/dev/null 2>&1; then
  echo "    WARNING: 'iverilog' not found. Install it with:"
  echo "        sudo apt install iverilog"
fi

echo "==> Creating virtual environment (.venv)..."
python3 -m venv .venv
. .venv/bin/activate

echo "==> Installing Python dependencies..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo ""
echo "Done. Launch VeriForge with:"
echo "    ./veriforge"
