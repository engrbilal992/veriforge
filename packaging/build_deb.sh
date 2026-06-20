#!/usr/bin/env bash
# Build the VeriForge .deb package.
# Run from the project root:  ./packaging/build_deb.sh
#
# Requires: dpkg-deb, fakeroot
# Produces: veriforge_1.0.0_amd64.deb (in the project root)

set -e
cd "$(dirname "$0")/.."   # project root

VERSION=$(grep "^Version:" packaging/DEBIAN/control | awk '{print $2}')
ARCH="amd64"
PKG="veriforge_${VERSION}_${ARCH}"
STAGING="/tmp/${PKG}"

echo "==> Cleaning staging area..."
rm -rf "$STAGING"

# ── directory tree ────────────────────────────────────────────────────────────
mkdir -p \
    "$STAGING/DEBIAN" \
    "$STAGING/opt/veriforge" \
    "$STAGING/usr/bin" \
    "$STAGING/usr/share/applications" \
    "$STAGING/usr/share/icons/hicolor/16x16/apps" \
    "$STAGING/usr/share/icons/hicolor/32x32/apps" \
    "$STAGING/usr/share/icons/hicolor/48x48/apps" \
    "$STAGING/usr/share/icons/hicolor/128x128/apps" \
    "$STAGING/usr/share/icons/hicolor/256x256/apps"

# ── copy source ───────────────────────────────────────────────────────────────
echo "==> Copying source files..."

cp -r app              "$STAGING/opt/veriforge/"
cp -r examples         "$STAGING/opt/veriforge/"
cp    main.py          "$STAGING/opt/veriforge/"
cp    veriforge        "$STAGING/opt/veriforge/"
cp    ide_veriforge    "$STAGING/opt/veriforge/"
cp    requirements.txt "$STAGING/opt/veriforge/"
cp    LICENSE          "$STAGING/opt/veriforge/"
cp -r icons            "$STAGING/opt/veriforge/"

# Remove any stale .pyc / __pycache__
find "$STAGING/opt/veriforge" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$STAGING/opt/veriforge" -name "*.pyc"       -delete 2>/dev/null || true

# ── DEBIAN control files ──────────────────────────────────────────────────────
echo "==> Installing DEBIAN control files..."
cp packaging/DEBIAN/control  "$STAGING/DEBIAN/control"
cp packaging/DEBIAN/postinst "$STAGING/DEBIAN/postinst"
cp packaging/DEBIAN/prerm    "$STAGING/DEBIAN/prerm"
chmod 755 "$STAGING/DEBIAN/postinst" "$STAGING/DEBIAN/prerm"

# ── launcher ─────────────────────────────────────────────────────────────────
echo "==> Creating /usr/bin/veriforge launcher..."
cat > "$STAGING/usr/bin/veriforge" << 'LAUNCHER'
#!/bin/bash
exec /opt/veriforge/.venv/bin/python3 /opt/veriforge/main.py "$@"
LAUNCHER
chmod 755 "$STAGING/usr/bin/veriforge"

# ── desktop entry + icons ────────────────────────────────────────────────────
echo "==> Installing .desktop and icons..."
cp packaging/veriforge.desktop "$STAGING/usr/share/applications/veriforge.desktop"

for size in 16 32 48 128 256; do
    cp "icons/veriforge_${size}.png" \
       "$STAGING/usr/share/icons/hicolor/${size}x${size}/apps/veriforge.png"
done

# ── build .deb ────────────────────────────────────────────────────────────────
DEB="${PKG}.deb"
echo "==> Building $DEB ..."
fakeroot dpkg-deb --build "$STAGING" "$DEB"

echo ""
echo "Done: $DEB"
echo ""
echo "Install with:"
echo "    sudo dpkg -i $DEB"
echo "    sudo apt-get install -f      # pull in iverilog + gtkwave if missing"
echo ""
echo "Package info:"
dpkg-deb -I "$DEB"
