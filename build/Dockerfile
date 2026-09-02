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
    libegl1-mesa-dev libgl1-mesa-dev libopus-dev libsdl2-dev libsdl2-ttf-dev libssl-dev \
    libavcodec-dev libavformat-dev libswscale-dev libva-dev libvdpau-dev libxkbcommon-dev \
    wayland-protocols libdrm-dev libgbm-dev \
  && rm -rf /var/lib/apt/lists/*
ARG MOONLIGHT_TAG=v6.1.0
WORKDIR /src
RUN git clone --depth 1 --branch ${MOONLIGHT_TAG} --recurse-submodules --shallow-submodules \
      https://github.com/moonlight-stream/moonlight-qt .
# embedded = single-purpose device UI/behaviour; gpuslow = prefer direct KMS/DRM output
RUN qmake "CONFIG+=embedded" "CONFIG+=gpuslow" moonlight-qt.pro && make -j"$(nproc)" release
COPY package.sh /package.sh
CMD ["/bin/bash", "/package.sh"]
