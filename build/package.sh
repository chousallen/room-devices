#!/bin/bash
# Runs inside the build container: wraps the built binary into a minimal .deb in /out.
set -euo pipefail
VER="${MOONLIGHT_VER:-6.1.0}"
REV="${PKG_REV:-ubuntu2204pi9}"   # pi9 = fork HEVC fprintf spam -> AV_LOG_TRACE; pi1 = plain v6.1.0 (system SDL, does not start); pi3 = static SDL 2.32 + patches/0001 DrmVsyncSource; pi8 = + Pi FFmpeg fork (zero-copy)
PKG=/tmp/pkg
rm -rf "$PKG"; mkdir -p "$PKG/DEBIAN" "$PKG/usr/local/bin" "$PKG/usr/local/lib" "$PKG/usr/share/applications"
install -m755 /src/app/moonlight "$PKG/usr/local/bin/moonlight-qt"
# Ship the Pi FFmpeg fork's shared libs (soname .so.60, distinct from jammy's .so.58 so both coexist).
# The binary carries an rpath of /usr/local/lib and postinst runs ldconfig.
cp -a /usr/local/lib/libav*.so* /usr/local/lib/libsw*.so* "$PKG/usr/local/lib/" 2>/dev/null || true
FFLIBS=$(ls "$PKG/usr/local/lib/" | tr '\n' ' ')
cat > "$PKG/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
ldconfig
POST
chmod 755 "$PKG/DEBIAN/postinst"
cat > "$PKG/DEBIAN/control" <<CTRL
Package: moonlight-qt-pi
Version: ${VER}-${REV}
Section: video
Priority: optional
Architecture: arm64
Maintainer: room-devices local build <root@localhost>
Depends: libqt5core5a, libqt5gui5, libqt5qml5, libqt5quick5, libqt5svg5, libqt5network5, libqt5widgets5, qml-module-qtquick-controls2, qml-module-qtquick-layouts, qml-module-qtquick-window2, qml-module-qtquick2, qml-module-qtqml, libfreetype6, libudev1, libopus0, libva2, libva-drm2, libva-wayland2, libvdpau1, libssl3, libegl1, libgl1, libdrm2, libgbm1, libxkbcommon0, zlib1g
Conflicts: moonlight-qt
Description: Moonlight game-streaming client, local build for Raspberry Pi 4 on Ubuntu 22.04
 Built from upstream tag v${VER} with CONFIG+=embedded CONFIG+=gpuslow against jammy's Qt 5,
 the patches in build/patches/, static SDL 2.32, and the jc-kynesim Pi FFmpeg fork bundled in
 /usr/local/lib for zero-copy DRM_PRIME video decode (${REV}). Bundled FFmpeg: ${FFLIBS}
CTRL
dpkg-deb --build --root-owner-group "$PKG" "/out/moonlight-qt-pi_${VER}-${REV}_arm64.deb"
ls -l /out
