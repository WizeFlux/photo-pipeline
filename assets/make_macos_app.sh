#!/bin/bash
# Build a macOS .app bundle with the icon for proper Dock integration.
#
# macOS doesn't show custom Dock icons for plain Python scripts.
# This script wraps the app in a minimal .app bundle with Info.plist
# pointing to the .icns icon, so the Dock shows our icon.
#
# Usage: ./assets/make_macos_app.sh [output_dir]
#
# After running: open PhotoPipeline.app  (or double-click in Finder)

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT_DIR="${1:-.}"
APP_NAME="PhotoPipeline"
APP_PATH="$OUT_DIR/$APP_NAME.app"

echo "=== Building $APP_NAME.app bundle ==="

# Ensure icon exists
if [ ! -f "assets/app.icns" ]; then
    echo "⚠ assets/app.icns not found — generating icons first ..."
    ./assets/make_icons.sh
fi

# Bundle structure
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Copy icon
cp assets/app.icns "$APP_PATH/Contents/Resources/app.icns"

# Create the launcher script inside the bundle
# Hardcode the project root at build time (absolute path) so it works
# regardless of how the .app is launched (open, Finder, terminal).
PROJECT_ROOT="$ROOT"
cat > "$APP_PATH/Contents/MacOS/$APP_NAME" << LAUNCHER
#!/bin/bash
# Auto-generated launcher for PhotoPipeline.app
# Project root is hardcoded at build time.

PROJECT_ROOT="$PROJECT_ROOT"
LOG_FILE="\$HOME/.photo-pipeline-launch.log"

exec >> "\$LOG_FILE" 2>&1
echo "=== \$(date) ==="
echo "Launching from: \$PROJECT_ROOT"

cd "\$PROJECT_ROOT" || {
    echo "ERROR: Cannot cd to \$PROJECT_ROOT"
    exit 1
}

# Activate venv if present
if [ -f "\$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "\$PROJECT_ROOT/.venv/bin/activate"
    echo "Activated venv: \$(which python3)"
else
    echo "No .venv found, using system python3"
fi

# Launch — exec replaces the shell, so the app gets signals properly
exec python3 -m qt_app.main
LAUNCHER
chmod +x "$APP_PATH/Contents/MacOS/$APP_NAME"

# Create Info.plist
cat > "$APP_PATH/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>PhotoPipeline</string>
    <key>CFBundleDisplayName</key>
    <string>Photo Pipeline</string>
    <key>CFBundleIdentifier</key>
    <string>com.wizeflux.photo-pipeline</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
PLIST

echo ""
echo "✅ Created: $APP_PATH"
echo ""
echo "To launch:"
echo "  open $APP_PATH"
echo ""
echo "Note: The .app bundle expects the project source tree to be in"
echo "the same directory as the .app. Move both together if relocating."