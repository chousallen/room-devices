# room-devices

The Raspberry Pi 4 (`sallen-pi`, 192.168.0.101) drives the room's HDMI monitor and the speaker
on its 3.5 mm jack, and lets devices on the LAN use both.

```
laptop desktop  --Sunshine-->  Moonlight on the Pi  -->  monitor (+ its audio into the mixer)
laptop apps     --"Room-speaker-Pi" output device-->  PipeWire on the Pi --mix--> speaker
Android phone   --Bluetooth (A2DP)------------------->        ^
laptop/anything --pi-cast <file|url>--> GStreamer player on the Pi --> monitor + speaker
```

PipeWire on the Pi is the single mixer: every source above ends up as a stream on the sink
`alsa_output.room_speaker`, so several devices can play at once.

## Daily use

**Laptop audio to the speaker.** In GNOME Sound settings pick the output "Room speaker (Pi)"
(node `pi_speaker`), or route a single app there with `pavucontrol`. The laptop sends the
audio as PipeWire RTP (plain UDP to the Pi, port 46000); the Pi's `rtp-speaker.service`
receives it into the mixer with a 200 ms jitter buffer, so the delay is a bit over 200 ms.
UDP needs no connection, so the device is always there and nothing breaks when the Pi is off.
Measured over two-minute runs: 100 ms buffer dipped 3 times, 200 ms never. To experiment, edit
`sess.latency.msec` in `~/.config/pipewire/rtp-speaker.conf` on the Pi and
`systemctl --user restart rtp-speaker`; dips show up as `underrun` lines in
`journalctl --user -u rtp-speaker`. For lip-synced laptop video use Moonlight, which carries
its own audio.

**Laptop screen on the monitor.** When nothing else is running the monitor shows the Pi Room
dashboard (`pi-dashboard.service`, repo `~/Dashboard`): a one-page web app in a kiosk browser that says whether the
laptop answers and whether Sunshine on it is reachable. With the keyboard plugged into the Pi,
**Enter** starts the stream and **R** checks again; **Ctrl+Alt+Shift+Q** during the stream quits
it and the dashboard comes back by itself; **Ctrl+Alt+F3** gives a text console, **Ctrl+Alt+F1**
the dashboard. From the laptop, `pi-screen start` / `stop` / `restart` do the same. Sunshine runs
on the laptop (`app-dev.lizardbyte.app.Sunshine.service`, web UI https://localhost:47990). The
stream carries the laptop's audio too, so **do not also select "Room-speaker-Pi" while streaming**,
or you hear everything twice. Moonlight's own menu is still installed as a fallback
(`sudo systemctl start moonlight.service` on the Pi). Extended-desktop (second monitor) mode needs
a dummy HDMI/DP plug on the laptop and `output_name` set in Sunshine (GNOME 46 has no
virtual-monitor tool).

**Play a video on the monitor with the original quality.** From the laptop:
`pi-cast movie.mkv` or `pi-cast https://host/video.mp4`; `pi-cast stop` ends it. YouTube-style
pages are **not** supported yet (yt-dlp needs a JavaScript runtime, and 1080p comes as separate
video and audio streams); watch those through Moonlight instead. This plays on
the Pi itself with hardware decoding, so picture quality and lip-sync do not depend on the
network. Moonlight is paused while a video plays and comes back afterwards. Files already on
the Pi play with `pi-play /path/file.mkv` over SSH. **Limit:** only H.264 has hardware decoding
on this Ubuntu 22.04 Pi (HEVC/H.265 files stutter); play HEVC content through Moonlight instead.
Measured: 1080p30 H.264 at 8 Mbps plays with no dropped frames.

**Phone audio.** Pair once with the Pi (it shows up as a Bluetooth speaker named `sallen-pi`);
afterwards it reconnects on its own. Bluetooth adds roughly 150–250 ms of delay by design.

## Layout

- `pi/` – everything installed on the Pi (`pi/install.sh` applies it): PipeWire/WirePlumber
  config, systemd units (`moonlight*.service`, `pi-player.service`), `pi-play`, boot config copy.
  The idle-screen dashboard (`pi-dashboard*.service`) is its own repo, `~/Dashboard`.
- `laptop/` – laptop side (`laptop/install.sh`): the tunnel output device, `pi-cast`.
- `build/` – Docker recipe that builds `moonlight-qt` for Ubuntu 22.04 arm64 on the laptop
  (`build/out/` is not committed).

## Ports

- Pi 4713/tcp: PulseAudio protocol (no authentication; home LAN + Tailscale only).
- Laptop 47984-47990/tcp, 47998-48010/udp: Sunshine.
