#!/bin/bash
# Install/refresh the Pi side of room-devices. Idempotent. Run as the audio user (sallen) with sudo rights.
set -euo pipefail
cd "$(dirname "$0")"
U=${SUDO_USER:-$USER}; H=$(getent passwd "$U" | cut -d: -f6)

echo "== PipeWire >= 1.0 from the pipewire-upstream PPA (stock jammy 0.3.48 lacks rtp-source and"
echo "   floors the graph quantum to a power of two; WirePlumber stays the jammy 0.4.8)"
grep -rq pipewire-debian /etc/apt/sources.list.d/ 2>/dev/null || sudo add-apt-repository -y ppa:pipewire-debian/pipewire-upstream
sudo apt-get update
echo "== packages"
sudo apt-get install -y --no-install-recommends pipewire pipewire-pulse pipewire-alsa wireplumber pipewire-audio-client-libraries \
  libspa-0.2-bluetooth pulseaudio-utils bluez bluez-tools \
  gstreamer1.0-tools gstreamer1.0-plugins-base-apps gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-pipewire \
  qt6-qpa-plugins
sudo apt-get remove -y pipewire-media-session 2>/dev/null || true

echo "== user config (PipeWire / WirePlumber)"
install -d "$H/.config/pipewire/pipewire.conf.d" "$H/.config/pipewire/pipewire-pulse.conf.d" \
           "$H/.config/wireplumber/main.lua.d" "$H/.config/wireplumber/bluetooth.lua.d" "$H/.config/systemd/user"
rm -f "$H/.config/pipewire/pipewire-pulse.conf"        # 0.3.48-era full copy; 1.0 merges drop-ins
install -m644 config/pipewire/pipewire.conf.d/*.conf "$H/.config/pipewire/pipewire.conf.d/"
install -m644 config/pipewire/pipewire-pulse.conf.d/*.conf "$H/.config/pipewire/pipewire-pulse.conf.d/"
install -m644 config/pipewire/rtp-speaker.conf "$H/.config/pipewire/rtp-speaker.conf"
install -m644 config/wireplumber/main.lua.d/*.lua "$H/.config/wireplumber/main.lua.d/"
install -m644 config/wireplumber/bluetooth.lua.d/*.lua "$H/.config/wireplumber/bluetooth.lua.d/"
install -m644 systemd/user/rtp-speaker.service "$H/.config/systemd/user/rtp-speaker.service"

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
grep -nE 'vc4-kms-v3d|krnbt|rpivid' /boot/firmware/config.txt || echo "  see etc/config.txt: dtparam=krnbt=on, dtoverlay=vc4-kms-v3d, dtoverlay=rpivid-v4l2 AFTER the dtparam=audio line, no inline comments"

echo "== user services"
sudo loginctl enable-linger "$U"
systemctl --user disable --now pipewire-media-session 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user enable pipewire wireplumber pipewire-pulse.service pipewire-pulse.socket rtp-speaker.service
systemctl --user restart pipewire
sleep 3; systemctl --user restart rtp-speaker.service
sleep 2; systemctl --user --no-pager is-active pipewire wireplumber pipewire-pulse rtp-speaker | paste -sd' '
wpctl status | sed -n '/Sinks/,/Sink endpoints/p' | head -4
echo "done. Enable the monitor receiver with: sudo systemctl enable --now moonlight.service"
