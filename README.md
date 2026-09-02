# room-devices

The Raspberry Pi 4 (`sallen-pi`, 192.168.0.101) drives the room's HDMI monitor and the speaker
on its 3.5 mm jack, and lets devices on the LAN use both.

```
laptop desktop  --Sunshine-->  Moonlight on the Pi  -->  monitor (+ its audio into the mixer)
laptop apps     --"Room speaker (Pi)" output device-->  PipeWire on the Pi --mix--> speaker
Android phone   --Bluetooth (A2DP)------------------->        ^
laptop/anything --pi-cast <file|url>--> GStreamer player on the Pi --> monitor + speaker
```

PipeWire on the Pi is the single mixer: every source above ends up as a stream on the sink
`alsa_output.room_speaker`, so several devices can play at once.

## Daily use

**Laptop audio to the speaker.** In GNOME Sound settings pick the output "Room speaker (Pi)"
(node `pi_speaker`), or route a single app there with `pavucontrol`. Target delay is set by
`pulse.latency` in `laptop/60-pi-speaker.conf` (80 ms; the laptop is on Wi-Fi). Lower it in
steps of 20 and restart PipeWire (`systemctl --user restart pipewire`) until you hear dropouts,
then go back one step.

**Laptop screen on the monitor.** Moonlight runs full-screen on the Pi's HDMI output
(`moonlight.service`). Pick the laptop in its list. Sunshine runs on the laptop
(`app-dev.lizardbyte.app.Sunshine.service`, web UI https://localhost:47990). The stream carries
the laptop's audio too, so **do not also select "Room speaker (Pi)" while streaming**, or you
hear everything twice. Extended-desktop (second monitor) mode needs a dummy HDMI/DP plug on the
laptop and `output_name` set in Sunshine (GNOME 46 has no virtual-monitor tool).

**Play a video on the monitor with the original quality.** From the laptop:
`pi-cast movie.mkv` or `pi-cast https://youtu.be/...`; `pi-cast stop` ends it. This plays on
the Pi itself with hardware decoding, so picture quality and lip-sync do not depend on the
network. Moonlight is paused while a video plays and comes back afterwards.

**Phone audio.** Pair once with the Pi (it shows up as a Bluetooth speaker named `sallen-pi`);
afterwards it reconnects on its own. Bluetooth adds roughly 150–250 ms of delay by design.

## Layout

- `pi/` – everything installed on the Pi (`pi/install.sh` applies it): PipeWire/WirePlumber
  config, systemd units (`moonlight.service`, `pi-player.service`), `pi-play`, boot config copy.
- `laptop/` – laptop side (`laptop/install.sh`): the tunnel output device, `pi-cast`.
- `build/` – Docker recipe that builds `moonlight-qt` for Ubuntu 22.04 arm64 on the laptop
  (`build/out/` is not committed).

## Ports

- Pi 4713/tcp: PulseAudio protocol (no authentication; home LAN + Tailscale only).
- Laptop 47984-47990/tcp, 47998-48010/udp: Sunshine.
