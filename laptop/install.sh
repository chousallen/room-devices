#!/bin/bash
# Laptop side (Ubuntu 24.04, PipeWire 1.0.5, GNOME Wayland). Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Pi speaker as an output device (PipeWire RTP sender)"
# old variants: static pulse tunnel, then a watchdog-managed pulse tunnel; both underflowed
rm -f ~/.config/pipewire/pipewire.conf.d/60-pi-speaker.conf \
      ~/.local/bin/pi-speaker-watch ~/.config/systemd/user/pi-speaker-watch.service \
      ~/.config/systemd/user/pi-speaker-watch.timer ~/.config/systemd/user/timers.target.wants/pi-speaker-watch.timer
install -d ~/.config/pipewire/pipewire.conf.d ~/.local/bin
install -m644 60-pi-speaker-rtp.conf ~/.config/pipewire/pipewire.conf.d/60-pi-speaker-rtp.conf
systemctl --user daemon-reload
systemctl --user restart pipewire
sleep 3; pactl list sinks short | grep pi_speaker || echo "pi_speaker sink missing: check journalctl --user -u pipewire"
echo "== pi-cast helper"
install -m755 pi-cast ~/.local/bin/pi-cast
echo "== Sunshine (screen sender): installed from the LizardByte GitHub release .deb; see README"
command -v sunshine >/dev/null && sunshine --version | head -1 || echo "sunshine not installed"
echo "done"
