#!/bin/bash
# Uninstall Vociferous desktop entry from Linux application launchers

set -e

# XDG paths
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "Uninstalling Vociferous desktop entry..."

# Remove desktop entry
if [ -f "$APPLICATIONS_DIR/vociferous.desktop" ]; then
    rm "$APPLICATIONS_DIR/vociferous.desktop"
    echo "  ✓ Removed desktop entry"
else
    echo "  - Desktop entry not found (already removed?)"
fi

# Remove icons
removed_icons=0

if [ -f "$ICONS_DIR/512x512/apps/vociferous.png" ]; then
    rm "$ICONS_DIR/512x512/apps/vociferous.png"
    ((removed_icons++))
fi

if [ -f "$ICONS_DIR/192x192/apps/vociferous.png" ]; then
    rm "$ICONS_DIR/192x192/apps/vociferous.png"
    ((removed_icons++))
fi

if [ -f "$ICONS_DIR/48x48/apps/vociferous.png" ]; then
    rm "$ICONS_DIR/48x48/apps/vociferous.png"
    ((removed_icons++))
fi

if [ $removed_icons -gt 0 ]; then
    echo "  ✓ Removed $removed_icons icon(s)"
else
    echo "  - No icons found (already removed?)"
fi

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
echo "Uninstall complete!"
echo ""
echo "Vociferous has been removed from your application launcher."
echo "Note: This does not remove the application files, only the launcher entry."
