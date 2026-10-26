#!/bin/bash
# Laptop side (Ubuntu 24.04, PipeWire 1.0.5, GNOME Wayland). Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
echo "== Pi speaker as an output device (PipeWire RTP sender, own process, reachability-gated)"
# old variants: static pulse tunnel, watchdog-managed pulse tunnel (both underflowed), rtp-sink
# loaded inside the main daemon (went silently dead after every network change), root
# NetworkManager dispatcher restart hook (replaced by the user timer below)
rm -f ~/.config/pipewire/pipewire.conf.d/60-pi-speaker.conf \
      ~/.config/pipewire/pipewire.conf.d/60-pi-speaker-rtp.conf \
      ~/.local/bin/pi-speaker-rtp-restart \
      ~/.config/systemd/user/default.target.wants/pi-speaker-rtp.service
sudo rm -f /etc/NetworkManager/dispatcher.d/90-pi-speaker-rtp
install -d ~/.config/pipewire ~/.config/systemd/user ~/.local/bin
install -m644 pi-speaker-rtp.conf ~/.config/pipewire/pi-speaker-rtp.conf
install -d ~/.config/pipewire/pipewire.conf.d ~/.config/pipewire/pipewire-pulse.conf.d
install -m644 pipewire.conf.d/50-min-quantum.conf ~/.config/pipewire/pipewire.conf.d/
install -m644 pipewire-pulse.conf.d/50-min-quantum.conf ~/.config/pipewire/pipewire-pulse.conf.d/
install -m644 systemd/user/pi-speaker-rtp.service ~/.config/systemd/user/pi-speaker-rtp.service
install -m644 systemd/user/pi-speaker-watch.service systemd/user/pi-speaker-watch.timer ~/.config/systemd/user/
install -m755 pi-speaker-watch ~/.local/bin/pi-speaker-watch
systemctl --user daemon-reload
# one-time: drop the in-daemon rtp-sink if the old conf.d file was loaded by the running daemon
if pw-cli ls Module 2>/dev/null | grep -q libpipewire-module-rtp-sink; then systemctl --user restart pipewire; sleep 2; fi
systemctl --user enable --now pi-speaker-watch.timer
~/.local/bin/pi-speaker-watch
sleep 1; pactl list sinks short | grep pi_speaker || echo "pi_speaker sink absent (Pi unreachable or not on home wifi?): journalctl --user -t pi-speaker-watch"
echo "== pi-cast helper"
install -m755 pi-cast ~/.local/bin/pi-cast
echo "== Sunshine (screen sender): installed from the LizardByte GitHub release .deb; see README"
command -v sunshine >/dev/null && sunshine --version | head -1 || echo "sunshine not installed"
echo "done"
