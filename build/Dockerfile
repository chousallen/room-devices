# Builds moonlight-qt for Raspberry Pi 4 running Ubuntu 22.04 (arm64), using the Qt 5 stack
# that jammy ships. Run on any x86_64 host with qemu-user-static + Docker buildx:
#   docker build --platform linux/arm64 -t moonlight-pi-build build/
#   docker run --rm --platform linux/arm64 -v $PWD/out:/out moonlight-pi-build
FROM --platform=linux/arm64 ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential pkg-config \
    qtbase5-dev qtdeclarative5-dev libqt5svg5-dev qtquickcontrols2-5-dev \
    qml-module-qtquick-controls2 qml-module-qtquick-layouts qml-module-qtquick-window2 \
    qml-module-qtquick2 qml-module-qtqml qtwayland5 \
    libegl1-mesa-dev libgl1-mesa-dev libopus-dev libssl-dev \
    libva-dev libvdpau-dev libxkbcommon-dev \
    wayland-protocols libdrm-dev libgbm-dev \
  && rm -rf /var/lib/apt/lists/*

# --- Raspberry Pi FFmpeg fork (jc-kynesim/rpi-ffmpeg) ---------------------------------------
# jammy's stock FFmpeg 4.4 h264_v4l2m2m advertises no hwaccel and outputs software NV12 frames,
# so Moonlight's DrmRenderer must CPU-copy every frame into a slow uncached "dumb" buffer -> the
# Pi 4 can only paint ~30 of 60 fps and the pacer drops the rest (measured 2026-09-09). The Pi
# fork adds an AV_PIX_FMT_DRM_PRIME (dma-buf) output for v4l2m2m so the decoded frame is handed to
# KMS with no copy. This is exactly what Raspberry Pi OS ships and why Moonlight is smooth there.
# We install it to /usr/local (soname libavcodec.so.60, distinct from jammy's .so.58, so they
# coexist) and Moonlight links against it via pkg-config.
ARG FFMPEG_TAG=dev/6.1.1/rpi_import_1
RUN apt-get update && apt-get install -y --no-install-recommends \
      nasm libdrm-dev zlib1g-dev libudev-dev \
  && apt-get purge -y libavcodec-dev libavformat-dev libswscale-dev libavutil-dev libavfilter-dev 2>/dev/null; \
  apt-get autoremove -y; rm -rf /var/lib/apt/lists/* \
  && git clone --depth 1 --branch ${FFMPEG_TAG} https://github.com/jc-kynesim/rpi-ffmpeg /tmp/ff \
  && cd /tmp/ff \
  # The fork's v4l2-request HEVC path has raw fprintf(stderr) trace prints (6 per frame, ~340 lines/s at
  # 1080p60) that flooded the Pi's journal (rotated to ~4 h of history, 2026-09-10). Make them trace-level.
  && sed -i '/__func__/s/fprintf(stderr, /av_log(NULL, AV_LOG_TRACE, /' \
       libavcodec/v4l2_req_hevc_vx.c libavcodec/v4l2_request_hevc.c \
  && ! grep -q 'fprintf(stderr, "<<<' libavcodec/v4l2_req_hevc_vx.c \
  && ./configure \
       --prefix=/usr/local --libdir=/usr/local/lib \
       --enable-shared --disable-static --enable-pic \
       --enable-gpl --enable-v4l2-request --enable-libdrm --enable-libudev --enable-sand \
       --disable-mmal --disable-vaapi --disable-vdpau \
       --disable-programs --disable-doc --disable-encoders --disable-muxers --disable-debug \
  && make -j"$(nproc)" && make install && ldconfig \
  && rm -rf /tmp/ff \
  && pkg-config --modversion libavcodec

# --- SDL 2 built statically -----------------------------------------------------------------
# jammy's SDL 2.0.20 cannot start its KMSDRM video driver on the Pi ("SDL_InitSubSystem(SDL_INIT_VIDEO)
# failed: Failed loading udev_device_get_action ... undefined symbol: _udev_device_get_action", libsdl-org/SDL
# #4879); the vendor (Cloudsmith) package avoids it by linking its own SDL statically, so do the same.
ARG SDL_TAG=release-2.32.10
ARG SDLTTF_TAG=release-2.24.0
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake libudev-dev libasound2-dev libpulse-dev libpipewire-0.3-dev libdbus-1-dev \
    libgles2-mesa-dev libfreetype-dev \
  && rm -rf /var/lib/apt/lists/* \
  && git clone --depth 1 --branch ${SDL_TAG} https://github.com/libsdl-org/SDL /tmp/sdl \
  && cmake -S /tmp/sdl -B /tmp/sdl/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
       -DCMAKE_INSTALL_LIBDIR=lib -DSDL_SHARED=OFF -DSDL_STATIC=ON -DSDL_STATIC_PIC=ON \
       -DSDL_KMSDRM=ON -DSDL_X11=OFF -DSDL_WAYLAND=OFF -DSDL_TEST=OFF \
  && cmake --build /tmp/sdl/build -j"$(nproc)" && cmake --install /tmp/sdl/build \
  && git clone --depth 1 --branch ${SDLTTF_TAG} https://github.com/libsdl-org/SDL_ttf /tmp/sdlttf \
  && cmake -S /tmp/sdlttf -B /tmp/sdlttf/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
       -DCMAKE_INSTALL_LIBDIR=lib -DBUILD_SHARED_LIBS=OFF -DSDL2TTF_VENDORED=OFF -DSDL2TTF_HARFBUZZ=OFF \
       -DSDL2TTF_SAMPLES=OFF \
  && cmake --build /tmp/sdlttf/build -j"$(nproc)" && cmake --install /tmp/sdlttf/build \
  && rm -rf /tmp/sdl /tmp/sdlttf \
  # qmake asks pkg-config without --static: fold the private link flags into Libs: so the .a files link
  && for pc in /usr/local/lib/pkgconfig/sdl2.pc /usr/local/lib/pkgconfig/SDL2_ttf.pc; do \
       priv=$(sed -n 's/^Libs.private: *//p' "$pc"); sed -i "s|^Libs: .*|& $priv|" "$pc"; done \
  && sed -i 's|^Libs: .*|& -lfreetype|' /usr/local/lib/pkgconfig/SDL2_ttf.pc \
  && pkg-config --libs sdl2 SDL2_ttf

ARG MOONLIGHT_TAG=v6.1.0
WORKDIR /src
RUN git clone --depth 1 --branch ${MOONLIGHT_TAG} --recurse-submodules --shallow-submodules \
      https://github.com/moonlight-stream/moonlight-qt .
# Local patches on top of the tag (build/patches/*.patch, applied in name order).
# 0001: DrmVsyncSource = real frame pacing on bare KMS (see CLAUDE.md).
COPY patches/ /patches/
RUN set -e; for p in /patches/*.patch; do echo "applying $p"; git apply --index "$p"; done
# embedded = single-purpose device UI/behaviour; gpuslow = prefer direct KMS/DRM output.
# disable-libvdpau/x11/wayland: our SDL has only KMSDRM, and vdpau.cpp uses SDL x11 fields unguarded.
# rpath /usr/local/lib so the binary finds the Pi FFmpeg fork's .so.60 (ahead of jammy's .so.58).
RUN qmake "CONFIG+=embedded" "CONFIG+=gpuslow" "CONFIG+=disable-libvdpau" "CONFIG+=disable-x11" "CONFIG+=disable-wayland" \
      "QMAKE_LFLAGS+=-Wl,-rpath,/usr/local/lib" moonlight-qt.pro && make -j"$(nproc)" release \
  && echo "=== FFmpeg linkage:" && ldd app/moonlight | grep -iE "libav|libsw" \
  && (ldd app/moonlight | grep -i sdl && echo "WARNING: SDL dynamic" || echo "SDL linked statically")
COPY package.sh /package.sh
CMD ["/bin/bash", "/package.sh"]
