#!/bin/bash
# Install/refresh the Pi side of room-devices. Idempotent. Run as the audio user (sallen) with sudo rights.
set -euo pipefail
cd "$(dirname "$0")"
U=${SUDO_USER:-$USER}; H=$(getent passwd "$U" | cut -d: -f6)

echo "== packages"
sudo apt-get install -y --no-install-recommends pipewire pipewire-pulse wireplumber pipewire-audio-client-libraries \
  libspa-0.2-bluetooth pulseaudio-utils bluez bluez-tools \
  gstreamer1.0-tools gstreamer1.0-plugins-base-apps gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-pipewire \
  qt6-qpa-plugins
sudo apt-get remove -y pipewire-media-session 2>/dev/null || true

echo "== user config (PipeWire / WirePlumber)"
install -d "$H/.config/pipewire/pipewire.conf.d" "$H/.config/wireplumber/main.lua.d" "$H/.config/wireplumber/bluetooth.lua.d"
install -m644 config/pipewire/pipewire.conf.d/*.conf "$H/.config/pipewire/pipewire.conf.d/"
install -m644 config/pipewire/pipewire-pulse.conf "$H/.config/pipewire/pipewire-pulse.conf"
install -m644 config/wireplumber/main.lua.d/*.lua "$H/.config/wireplumber/main.lua.d/"
install -m644 config/wireplumber/bluetooth.lua.d/*.lua "$H/.config/wireplumber/bluetooth.lua.d/"

echo "== system files"
sudo install -m644 etc/polkit-1/50-rtkit-sallen.pkla /etc/polkit-1/localauthority/50-local.d/50-rtkit-sallen.pkla
sudo install -d /etc/systemd/system/hciuart.service.d
sudo install -m644 etc/systemd/hciuart.service.d/override.conf /etc/systemd/system/hciuart.service.d/override.conf
sudo install -m644 etc/bluetooth/main.conf /etc/bluetooth/main.conf
sudo install -m644 systemd/moonlight.service systemd/pi-player.service systemd/bt-agent.service /etc/systemd/system/
sudo install -m755 bin/pi-play bin/pi-player-run bin/bt-speaker-setup /usr/local/bin/
sudo systemctl daemon-reload
sudo systemctl disable hciuart 2>/dev/null || true      # kernel (krnbt) handles Bluetooth
sudo systemctl enable bluetooth bt-agent

echo "== boot config: check by hand (needs reboot):"
grep -nE 'vc4-kms-v3d|krnbt' /boot/firmware/config.txt || echo "  add dtoverlay=vc4-kms-v3d and dtparam=krnbt=on under [pi4] (see etc/config.txt)"

echo "== user services"
sudo loginctl enable-linger "$U"
systemctl --user disable --now pipewire-media-session 2>/dev/null || true
systemctl --user enable pipewire wireplumber pipewire-pulse.service pipewire-pulse.socket
systemctl --user restart pipewire
sleep 2; systemctl --user --no-pager is-active pipewire wireplumber pipewire-pulse | paste -sd' '
wpctl status | sed -n '/Sinks/,/Sink endpoints/p' | head -4
echo "done. Enable the monitor receiver with: sudo systemctl enable --now moonlight.service"
