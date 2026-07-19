#!/bin/bash
# Generate platform icon files from the SVG source.
#
# macOS:  requires iconutil (macOS only) → app.icns
# Windows: requires ImageMagick          → app.ico
# Linux:  nothing needed — use icon_512.png directly
#
# Usage: ./assets/make_icons.sh

set -e
cd "$(dirname "$0")/.."
ASSETS="assets"

echo "=== Icon Generation ==="

# ─── PNG sizes (always, all platforms) ──────────────────────────────────────
# Ensure cairosvg is available (in the active venv)
if ! python3 -c "import cairosvg" &>/dev/null; then
    echo "Installing cairosvg (one-time) ..."
    pip install cairosvg >/dev/null 2>&1 || {
        echo "⚠ Cannot install cairosvg. Trying rsvg-convert fallback ..."
        if command -v rsvg-convert &>/dev/null; then
            echo "Generating PNG sizes via rsvg-convert ..."
            for s in 16 32 64 128 256 512 1024; do
                rsvg-convert -w "$s" -h "$s" "$ASSETS/icon.svg" -o "$ASSETS/icon_${s}.png"
            done
            echo "  ✓ PNG: 16, 32, 64, 128, 256, 512, 1024 (via rsvg-convert)"
            SKIP_CAIROSVG=1
        else
            echo "✗ No SVG renderer found. Install one of:"
            echo "    pip install cairosvg    (recommended)"
            echo "    brew install librsvg    (provides rsvg-convert)"
            exit 1
        fi
    }
fi

if [ "${SKIP_CAIROSVG:-0}" != "1" ]; then
    echo "Generating PNG sizes from $ASSETS/icon.svg ..."
    for s in 16 32 64 128 256 512 1024; do
        python3 -c "import cairosvg; cairosvg.svg2png(url='$ASSETS/icon.svg', write_to='$ASSETS/icon_${s}.png', output_width=$s, output_height=$s)"
    done
    echo "  ✓ PNG: 16, 32, 64, 128, 256, 512, 1024"
fi

# ─── macOS .icns (iconutil — macOS only) ────────────────────────────────────
if command -v iconutil &>/dev/null; then
    echo "Generating macOS .icns ..."
    ICONSET="$ASSETS/icon.iconset"
    mkdir -p "$ICONSET"
    cp "$ASSETS/icon_16.png"  "$ICONSET/icon_16x16.png"
    cp "$ASSETS/icon_32.png"  "$ICONSET/icon_16x16@2x.png"
    cp "$ASSETS/icon_32.png"  "$ICONSET/icon_32x32.png"
    cp "$ASSETS/icon_64.png"  "$ICONSET/icon_32x32@2x.png"
    cp "$ASSETS/icon_128.png" "$ICONSET/icon_128x128.png"
    cp "$ASSETS/icon_256.png" "$ICONSET/icon_128x128@2x.png"
    cp "$ASSETS/icon_256.png" "$ICONSET/icon_256x256.png"
    cp "$ASSETS/icon_512.png" "$ICONSET/icon_256x256@2x.png"
    cp "$ASSETS/icon_512.png" "$ICONSET/icon_512x512.png"
    cp "$ASSETS/icon_1024.png" "$ICONSET/icon_512x512@2x.png"
    iconutil -c icns "$ICONSET" -o "$ASSETS/app.icns"
    rm -rf "$ICONSET"
    echo "  ✓ $ASSETS/app.icns (macOS)"
else
    echo "  ⚠ iconutil not found (not macOS) — skip .icns"
    echo "    Run this script on macOS to generate app.icns"
fi

# ─── Windows .ico (ImageMagick) ─────────────────────────────────────────────
if command -v convert &>/dev/null; then
    echo "Generating Windows .ico ..."
    convert "$ASSETS/icon_16.png" "$ASSETS/icon_32.png" "$ASSETS/icon_48.png" \
            "$ASSETS/icon_64.png" "$ASSETS/icon_128.png" "$ASSETS/icon_256.png" \
            "$ASSETS/app.ico" 2>/dev/null || \
    convert "$ASSETS/icon_256.png" "$ASSETS/app.ico"
    echo "  ✓ $ASSETS/app.ico (Windows)"
else
    echo "  ⚠ ImageMagick 'convert' not found — skip .ico"
    echo "    Install ImageMagick: brew install imagemagick"
fi

echo ""
echo "✅ Done! Icon files in $ASSETS/"
echo "   SVG source: $ASSETS/icon.svg"
echo "   PNG:        $ASSETS/icon_{16,32,64,128,256,512,1024}.png"
echo "   macOS:      $ASSETS/app.icns (if iconutil available)"
echo "   Windows:    $ASSETS/app.ico (if ImageMagick available)"