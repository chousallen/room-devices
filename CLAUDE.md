# room-devices – facts for future work

Pi: Raspberry Pi 4B, Ubuntu Server 22.04 (kernel 5.15 raspi), boots from a USB **HDD** (`/dev/sda`).
No desktop. User `sallen` has `Linger=yes`, so PipeWire user services run without a login.
Laptop: `sallen@192.168.0.193`, Ubuntu 24.04, GNOME 46 Wayland, PipeWire 1.0.5, on Wi-Fi.
Large files on the laptop go under `/media/sallen/SSD-Programs/` (root disk is nearly full).

## Audio (PipeWire 1.0.7 from ppa:pipewire-debian/pipewire-upstream + stock WirePlumber 0.4.8)
- The PPA upgrade (0.3.48 -> 1.0.7) went through `apt-get install pipewire pipewire-pulse
  libspa-0.2-bluetooth pipewire-audio-client-libraries gstreamer1.0-pipewire pipewire-alsa` with
  no removals; WirePlumber 0.4.8 keeps working with it (the PPA has no wireplumber for jammy).
  Rollback: `build/out/pre-ppa/packages.txt` + `ppa-purge`. Realtime still comes via RTKit
  (thread `pw-data-loop` at RR 20); `ps -eLo cls,rtprio,comm` shows the main thread as TS.
- Laptop -> Pi audio is **PipeWire RTP**, not the pulse tunnel: laptop `module-rtp-sink`
  (`laptop/60-pi-speaker-rtp.conf`, unicast S16BE to UDP 46000) -> Pi `module-rtp-source` in
  its own process, user unit `rtp-speaker.service` running `pipewire -c rtp-speaker.conf`.
  It must start *after* WirePlumber has the ALSA sink: loading rtp-source from the main
  daemon's `pipewire.conf.d` fails at boot with "stream error: no node available" and the
  module is gone (UDP port never opens). `sess.latency.msec = 200` (100 dipped 3x/2 min on
  Wi-Fi; 200 zero). `sess.ignore-ssrc = true` so laptop restarts keep working.
- The pulse tunnel (laptop 1.0.5 `module-pulse-tunnel`/`module-tunnel-sink`) was abandoned:
  once its buffer drifted it underflowed **every 2 s** (`mod.pulse-tunnel: underflow`), against
  both the 0.3.48 and the 1.0.7 server, with 0 % loss / 3 ms RTT. Only latency_msec=400
  (~150 ms real buffer) was gap-free. Details kept below for reference.
- **The bcm2835 jack cannot run at small periods.** With the graph at 256 frames (5 ms) the sink
  logged ~50 xruns/min (`pw-top` ERR 65 -> 1750 in 30 min) and *every* source stuttered; the
  pulse tunnel's server-side queue then filled to `maxlength` 4 MB = ~21 s of delay. Triggers:
  Moonlight's audio stream (asks 256) or any pulse client, because 0.3.48 floors the graph
  quantum to a power of two (a 480-frame request becomes 256). Fix: `default.clock.min-quantum
  = 1024` (+ `pulse.min.req/quantum = 1024/48000`); measured zero xruns at 1024 under 4x CPU
  load, and 3 in 2 min (all when streams joined) with Moonlight + RTP + a local tone. Moonlight's
  "Audio packet queue overflow" was 0/2 min at both 512 and 1024 once CPU pressure was normal; the
  bursts seen at 1024 coincided with PipeWire restarts. Live check: `pw-metadata -n settings 0`
  (a PipeWire restart resets live metadata to the config) / `pw-top` ERR column (cumulative).
- `apt update` was needed first: the universe index was missing, so `wireplumber`,
  `pipewire-pulse` etc. showed "Candidate: (none)".
- Both bcm2835 ALSA cards get the *same* `node.name`/`device.name`; match on
  `api.alsa.card.name` ("bcm2835 Headphones", "bcm2835 HDMI 1").
- `["node.disabled"] = true` in a WirePlumber 0.4.8 alsa rule breaks routing for *all*
  streams ("no node available"). Use `["device.disabled"] = true` on the device instead.
- `pipewire-pulse.conf.d/*.conf` fragments did **not** override `pulse.properties` in 0.3.48
  (a full `pipewire-pulse.conf` copy was needed). With 1.0.7 the drop-in
  `pipewire-pulse.conf.d/20-network.conf` works and the full copy must be **removed**, or it
  overrides the 1.0 default config.
- RTKit refused realtime for the headless user (no local seat). Fixed with a polkit `.pkla`
  allowing `org.freedesktop.RealtimeKit1.*` for `sallen` (`pi/etc/polkit-1/`).
- Laptop side: a static `libpipewire-module-pulse-tunnel` entry in `pipewire.conf.d` fails at
  laptop boot if the Pi is unreachable (needs `flags = [ nofail ]` or laptop audio breaks) and
  never retries; it also vanishes when the Pi reboots. So the tunnel is created by
  `laptop/pi-speaker-watch` (systemd user timer, every 20 s) via
  `pactl load-module module-tunnel-sink ... latency_msec=80`. pipewire-pulse splits module
  arguments on whitespace regardless of quoting, so `sink_properties=device.description=` cannot
  contain spaces (hence "Room-speaker-Pi"). `latency_msec=N` gives the Pi a tlength of only
  ~0.375·N (80 -> 30 ms, 200 -> 75 ms, 400 -> 150 ms; module halves it, the 0.3.48 server trims
  more). Below ~150 ms real buffer the laptop logs `mod.pulse-tunnel: underflow` every 2–50 s
  = audible gaps, with 0 % loss / 3 ms RTT on the LAN. 400 ms is the first clean value. Count
  gaps on the laptop with `journalctl --user -u pipewire-pulse -o cat | grep -c underflow`; the
  Pi-side mixer xruns are the ERR column of `pw-top` (cumulative since node start). The module's
  "failed to connect: Bad state" was the Pi-side `node.disabled` routing bug, not network.

## Bluetooth
- Phone→Pi (A2DP source, SBC) gaps only at distance/in a pocket while the Pi mixer shows zero
  xruns: radio link margin (onboard antenna shared with Wi-Fi, wlan0 stays connected by user
  choice). Fixes are physical: keep the phone near, or a USB Bluetooth dongle. Not a buffer issue.
- `hciuart`/`hciattach` fails ("Initialization timed out") on this board even with the
  `Requires=dev-serial1.device` fix. The device tree has a `bluetooth` node under the PL011
  UART; `dtparam=krnbt=on` makes the kernel (`hci_uart`+`btbcm`) bring up `hci0` instead.
  `hciuart.service` is disabled.

## Display
- `/boot/firmware/config.txt` needs `dtoverlay=vc4-kms-v3d` (in a `[pi4]` block); without it
  there is no `/dev/dri` and nothing but the text console can draw.
- `config.txt` has **no inline comments**: text after `dtoverlay=name` becomes part of the name and
  the overlay is silently skipped. Comments go on their own line.
- **Overlay order matters**: `dtoverlay=` lines must come *after* `dtparam=audio=on`. Putting
  the KMS overlay in the first `[pi4]` block (above the dtparams) made the "bcm2835 Headphones"
  ALSA card disappear entirely (no `/proc/device-tree/soc/audio`). See `pi/etc/config.txt`.
- HEVC: `dtoverlay=rpivid-v4l2` loads `rpivid_hevc` (`/dev/video19`), but jammy's GStreamer 1.20
  `v4l2codecs` plugin registers **0 elements** on this kernel (stateless HEVC support arrived in
  GStreamer 1.22), so **no HEVC hardware playback on the Pi**; play HEVC via Moonlight instead.
  H.264 (`/dev/video10`, `v4l2h264dec`, stateful) works: 1080p30 @ 8 Mbps plays at 30 fps with
  no drops via `kmssink`; a 27 Mbps 1080p60 clip drops ~10% (decoder/copy limit).
- Moonlight (Cloudsmith 6.1.0 jammy arm64) on this Pi: decoder `h264_v4l2m2m` on `/dev/video10`,
  "DrmRenderer", NV12 drm_prime zero-copy. Its bundled FFmpeg probes `hevc_v4l2request` and falls
  back to H.264. Stream settings live in `~/.config/Moonlight Game Streaming Project/Moonlight.conf`
  `[streaming]`; the `stream` CLI ignores them and defaults to 720p, so `moonlight-stream.service`
  passes flags: 1920x1080, **30 fps, 35000 kbps** (Sunshine keeps ~27 Mbps for video). Sharpness
  needs the laptop panel set to 1920x1080 too, or Sunshine downscales 1200→1080 and blurs text.
- Only one process can own the display (DRM master): `pi-player.service` and `moonlight.service`
  carry `Conflicts=`; the player's `ExecStopPost=+systemctl start moonlight` needs the `+`
  (root) prefix or it fails with "Interactive authentication required".
- **`Conflicts=` gives no ordering.** A unit that conflicts with the menu must also list it in
  `After=` (`moonlight-stream.service`, `pi-player.service` do), or systemd starts it while the menu
  is still exiting; Qt opens `/dev/dri/card0` in the first ~100 ms, gets a non-master fd, and DRM
  master is never handed over. Symptom: unit `active`, `pi-screen status` fine, monitor frozen,
  `journalctl _COMM=moonlight-qt` loops "Video decode unit queue overflow" / "Waiting for IDR frame"
  every 0.5 s. `pi-screen restart` hit it every time (ExecStopPost had just relaunched the menu, which
  ignores SIGTERM for ~6 s while starting). The `drmModeObjectSetProperty(...) failed: 13` lines are
  *not* the tell: they also appear in every working run (connector properties this kernel rejects).
- The DrmRenderer test decode for `h264_v4l2m2m` sometimes fails with "Resource temporarily
  unavailable" and Moonlight falls back to `SdlRenderer` (opengles2 copy path, main thread ~50-90 %
  CPU) for that whole session. Before 2026-09-07 this hit ~1 in 7 sessions; on 2026-09-07 all 4 runs
  fell back (cause not found; the picture works, only CPU is higher). Unrelated to the race above.
  Check with `journalctl _PID=$(systemctl show -p MainPID --value moonlight-stream) -o cat | grep Chose`.
- Moonlight logs go to the journal by process (`journalctl _COMM=moonlight-qt`), not the unit.
- Moonlight's performance overlay (Ctrl+Alt+Shift+S) does **not** work with the DRM renderer on
  the Pi (known upstream limitation); keyboard input itself is forwarded fine.
- Mirroring latency was caused by CPU starvation on the Pi, not the network (RTT ~3 ms):
  `/proc/pressure/cpu` some ~50 %, "Audio packet queue overflow" in Moonlight's log. Fixes:
  `Nice=-10` in `moonlight*.service`, laptop Wi-Fi power save off
  (`/etc/NetworkManager/conf.d/wifi-powersave.conf`), `app-net-monitor --interval 30`
  (drop-in in `pi/etc/systemd/app-net-monitor.service.d/`; 5 s cost ~65 % of a core).
- Do not `systemctl restart moonlight-stream`: its ExecStopPost starts the menu unit, which
  `Conflicts=` the queued stream start and cancels it. Use `pi-screen stop` then `start`
  (`pi-screen restart` does this).
- `cmdline.txt` has `video=HDMI-A-1:1920x1080@60D` so HDMI0 is treated as connected even when
  the monitor is off/asleep (the monitor is shared with the laptop). HDMI0 = port next to USB-C.
- Moonlight: the Cloudsmith `moonlight-qt` jammy arm64 package is Qt 6 and does **not** pull
  in a platform plugin; install `qt6-qpa-plugins` (eglfs, eglfs_kms). Ubuntu-on-Pi is
  unsupported upstream. A Qt 5 build from source (`build/Dockerfile`, arm64 emulation on the
  laptop, ~10 min) is the fallback: `build/out/moonlight-qt-pi_*.deb`.
- `moonlight.service` needs `XDG_RUNTIME_DIR=/run/user/1000` or it has no sound.

## Commands
- Pi audio state: `wpctl status`, `pactl list sink-inputs`, `journalctl --user -u wireplumber`.
- `pi-cast` serves laptop files with a byte-range capable Python server; `python3 -m http.server`
  has no Range support and GStreamer's `souphttpsrc` refuses MP4 without it. Port 8765.
- YouTube via `pi-play`/yt-dlp (2026.08) fails: "No supported JavaScript runtime" (needs deno) and
  `-g` single-file formats top out at 360p; proper support would need deno + a two-stream
  (video+audio) GStreamer pipeline. Not done.
- Rebuild Moonlight on the laptop:
  `cd /media/sallen/SSD-Programs/room-devices-build && docker build --platform linux/arm64 -t moonlight-pi-build . && docker run --rm --platform linux/arm64 -v $PWD/out:/out moonlight-pi-build`

## Sunshine / Moonlight pairing (laptop)
- `sunshine --creds USER PASS` writes credentials, but the running service must be
  restarted before the web UI/API stops redirecting to `/welcome`.
- Headless pairing from the Pi: `QT_QPA_PLATFORM=offscreen moonlight-qt pair <laptop> --pin 4321`
  in the background, then `curl -k -u USER:PASS -X POST https://<laptop>:47990/api/pin -d '{"pin":"4321","name":"sallen-pi"}'`.
  The pair command hangs after success (kill it); `moonlight-qt list <laptop>` confirms.
- Web UI credentials are in `build/out/sunshine-creds.txt` on the Pi (not committed).
