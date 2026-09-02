#!/bin/bash
# Runs inside the build container: wraps the built binary into a minimal .deb in /out.
set -euo pipefail
VER="${MOONLIGHT_VER:-6.1.0}"
PKG=/tmp/pkg
rm -rf "$PKG"; mkdir -p "$PKG/DEBIAN" "$PKG/usr/local/bin" "$PKG/usr/share/applications"
install -m755 /src/app/moonlight "$PKG/usr/local/bin/moonlight-qt"
cat > "$PKG/DEBIAN/control" <<CTRL
Package: moonlight-qt-pi
Version: ${VER}-ubuntu2204pi1
Section: video
Priority: optional
Architecture: arm64
Maintainer: room-devices local build <root@localhost>
Depends: libqt5core5a, libqt5gui5, libqt5qml5, libqt5quick5, libqt5svg5, libqt5network5, libqt5widgets5, qml-module-qtquick-controls2, qml-module-qtquick-layouts, qml-module-qtquick-window2, qml-module-qtquick2, qml-module-qtqml, libsdl2-2.0-0, libsdl2-ttf-2.0-0, libopus0, libavcodec58, libavformat58, libswscale5, libva2, libva-drm2, libvdpau1, libssl3, libegl1, libgl1, libdrm2, libgbm1, libxkbcommon0
Conflicts: moonlight-qt
Description: Moonlight game-streaming client, local build for Raspberry Pi 4 on Ubuntu 22.04
 Built from upstream tag v${VER} with CONFIG+=embedded CONFIG+=gpuslow against jammy's Qt 5.
CTRL
dpkg-deb --build --root-owner-group "$PKG" "/out/moonlight-qt-pi_${VER}-ubuntu2204pi1_arm64.deb"
ls -l /out
