#!/bin/bash
# Install Vociferous desktop entry for Linux application launchers
# Works with GNOME, KDE, XFCE, and other XDG-compliant environments

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# XDG paths
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "Installing Vociferous desktop entry..."

# Create directories if they don't exist
mkdir -p "$APPLICATIONS_DIR"
mkdir -p "$ICONS_DIR/512x512/apps"
mkdir -p "$ICONS_DIR/192x192/apps"
mkdir -p "$ICONS_DIR/48x48/apps"

# Copy icons
if [ -f "$PROJECT_DIR/icons/512x512.png" ]; then
    cp "$PROJECT_DIR/icons/512x512.png" "$ICONS_DIR/512x512/apps/vociferous.png"
    echo "  ✓ Installed 512x512 icon"
fi

if [ -f "$PROJECT_DIR/icons/192x192.png" ]; then
    cp "$PROJECT_DIR/icons/192x192.png" "$ICONS_DIR/192x192/apps/vociferous.png"
    echo "  ✓ Installed 192x192 icon"
fi

# Create 48x48 from 192x192 if ImageMagick is available
if command -v convert &> /dev/null && [ -f "$PROJECT_DIR/icons/192x192.png" ]; then
    convert "$PROJECT_DIR/icons/192x192.png" -resize 48x48 "$ICONS_DIR/48x48/apps/vociferous.png"
    echo "  ✓ Created 48x48 icon"
elif [ -f "$PROJECT_DIR/icons/192x192.png" ]; then
    cp "$PROJECT_DIR/icons/192x192.png" "$ICONS_DIR/48x48/apps/vociferous.png"
    echo "  ✓ Installed 48x48 icon (from 192x192)"
fi

# Create desktop entry
cat > "$APPLICATIONS_DIR/vociferous.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Vociferous
Comment=Speech-to-text dictation using Whisper
Exec=$PROJECT_DIR/vociferous.sh
Icon=vociferous
Terminal=false
Categories=AudioVideo;Audio;Utility;
Keywords=speech;dictation;transcription;whisper;voice;
StartupNotify=true
StartupWMClass=vociferous
EOF

echo "  ✓ Created desktop entry"

# Make desktop entry executable (required by some DEs)
chmod +x "$APPLICATIONS_DIR/vociferous.desktop"

# Update icon cache if possible
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$ICONS_DIR" 2>/dev/null || true
    echo "  ✓ Updated icon cache"
fi

# Update desktop database if possible
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null || true
    echo "  ✓ Updated desktop database"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Vociferous should now appear in your application launcher."
echo "If it doesn't appear immediately, try logging out and back in."
echo ""
echo "To uninstall, run: ./scripts/uninstall-desktop-entry.sh"
