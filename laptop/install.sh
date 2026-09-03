#!/bin/bash
# Laptop side (Ubuntu 24.04, PipeWire 1.0.5, GNOME Wayland). Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Pi speaker as an output device (watchdog-managed pulse tunnel)"
rm -f ~/.config/pipewire/pipewire.conf.d/60-pi-speaker.conf   # old static variant
install -d ~/.local/bin ~/.config/systemd/user
install -m755 pi-speaker-watch pi-cast pi-screen ~/.local/bin/
install -m644 pi-speaker-watch.service pi-speaker-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pi-speaker-watch.timer
systemctl --user start pi-speaker-watch.service
sleep 2; pactl list sinks short | grep pi_speaker || echo "pi_speaker not up yet (is the Pi on? checked every 20 s)"
echo "== Sunshine (screen sender): installed from the LizardByte GitHub release .deb; see README"
command -v sunshine >/dev/null && sunshine --version | head -1 || echo "sunshine not installed"
echo "done"
