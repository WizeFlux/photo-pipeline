#!/bin/bash
# Build a Windows .exe launcher for Photo Pipeline.
#
# Creates a standalone PhotoPipeline.exe that runs the Qt app without
# requiring Python to be installed separately. Uses PyInstaller to bundle
# the Python interpreter + all dependencies + the app source + icon into
# a single .exe file.
#
# Requirements (run on Windows, or cross-compile via Wine):
#   - Python 3.10+ with pip
#   - All project deps installed (pip install -r requirements.txt)
#   - PyInstaller: pip install pyinstaller
#
# Usage (on Windows, from the project root):
#   assets/make_windows_exe.sh
#
# Output: dist/PhotoPipeline.exe (single-file, ~200MB with PyTorch)
#         or dist/PhotoPipeline/ folder (faster startup, multiple files)

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "=== Building PhotoPipeline.exe for Windows ==="

# Ensure PyInstaller is available
if ! python3 -c "import PyInstaller" &>/dev/null 2>/dev/null; then
    echo "Installing PyInstaller ..."
    pip install pyinstaller >/dev/null 2>&1 || {
        echo "✗ Cannot install PyInstaller. Run: pip install pyinstaller"
        exit 1
    }
fi

# Ensure icon exists (Windows .ico)
ICON_FLAG=""
if [ -f "assets/app.ico" ]; then
    ICON_FLAG="--icon=assets/app.ico"
    echo "Using icon: assets/app.ico"
elif [ -f "assets/icon_256.png" ]; then
    # PyInstaller can convert PNG to ico on the fly
    ICON_FLAG="--icon=assets/icon_256.png"
    echo "Using icon: assets/icon_256.png (will be embedded)"
else
    echo "⚠ No icon found — building without icon"
    echo "  Run assets/make_icons.sh first (requires ImageMagick on Windows)"
fi

# Clean previous builds
rm -rf build/ dist/ *.spec 2>/dev/null || true

echo ""
echo "Building with PyInstaller ..."
echo "  This may take 5-10 minutes (PyTorch is large) ..."
echo ""

# Build as single-file .exe
# --onefile: single .exe (slower startup, no folder needed)
# --windowed: no console window (GUI app)
# --name: output exe name
# Hidden imports: PySide6 + matplotlib backends sometimes need hints
pyinstaller \
    --onefile \
    --windowed \
    --name "PhotoPipeline" \
    $ICON_FLAG \
    --add-data "assets:assets" \
    --add-data "luts:luts" \
    --hidden-import "PySide6.QtWidgets" \
    --hidden-import "PySide6.QtCore" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "matplotlib.backends.backend_qtagg" \
    --hidden-import "torch" \
    --hidden-import "torchvision" \
    --collect-submodules "qt_app" \
    --collect-submodules "pipeline" \
    qt_app/main.py \
    2>&1 | tail -20

echo ""

if [ -f "dist/PhotoPipeline.exe" ]; then
    SIZE=$(du -sh dist/PhotoPipeline.exe 2>/dev/null | cut -f1)
    echo "✅ Build successful!"
    echo ""
    echo "   Output: dist/PhotoPipeline.exe ($SIZE)"
    echo "   Icon:   embedded"
    echo ""
    echo "   To distribute: copy dist/PhotoPipeline.exe to any Windows machine."
    echo "   No Python installation needed on the target machine."
    echo ""
    echo "   Note: First launch may take 10-20 seconds (PyInstaller"
    echo "   extracts the bundle to a temp folder)."
else
    echo "✗ Build failed — check PyInstaller output above"
    exit 1
fi

# Clean up build artifacts (keep dist/)
rm -rf build/ PhotoPipeline.spec 2>/dev/null || true