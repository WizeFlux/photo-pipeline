#!/bin/bash
# Photo Pipeline — setup script
# Creates venv inside project dir, installs all deps
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Photo Pipeline Setup ==="

# Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "Usage:"
echo "  source .venv/bin/activate"
echo ""
echo "  # Desktop GUI (recommended)"
echo "  python -m qt_app.main"
echo ""
echo "  # CLI — batch process a folder"
echo "  python -m pipeline process <input_dir> -o <output_dir> -p profiles/default.yaml"
echo ""
echo "  # CLI — preview a single image (before/after)"
echo "  python -m pipeline preview <input_file> -p profiles/default.yaml"