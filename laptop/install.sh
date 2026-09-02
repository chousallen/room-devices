#!/bin/bash
# Laptop side (Ubuntu 24.04, PipeWire 1.0.5, GNOME Wayland). Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Pi speaker as an output device (pulse-tunnel)"
install -d ~/.config/pipewire/pipewire.conf.d
install -m644 60-pi-speaker.conf ~/.config/pipewire/pipewire.conf.d/60-pi-speaker.conf
systemctl --user restart pipewire
sleep 3; pactl list sinks short | grep pi_speaker || echo "pi_speaker not up yet (is the Pi on? it reconnects every 5 s)"
echo "== pi-cast helper"
install -m755 pi-cast ~/.local/bin/pi-cast
echo "== Sunshine (screen sender): installed from LizardByte GitHub release .deb; see README"
command -v sunshine >/dev/null && sunshine --version | head -1 || echo "sunshine not installed"
echo "done"
