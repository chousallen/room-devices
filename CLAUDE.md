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
  (`laptop/pi-speaker-rtp.conf` in its own process `pi-speaker-rtp.service`, unicast S16BE to UDP 46000) -> Pi `module-rtp-source` in
  its own process, user unit `rtp-speaker.service` running `pipewire -c rtp-speaker.conf`.
  It must start *after* WirePlumber has the ALSA sink: loading rtp-source from the main
  daemon's `pipewire.conf.d` fails at boot with "stream error: no node available" and the
  module is gone (UDP port never opens). `sess.latency.msec = 200` (100 dipped 3x/2 min on
  Wi-Fi; 200 zero). `sess.ignore-ssrc = true` so laptop restarts keep working.
- **The laptop sender lives in its own process and exists only while the Pi is reachable.**
  `module-rtp-sink` creates and `connect()`s its UDP socket once at module load; after the laptop
  changes network (eduroam -> home) the socket keeps the old source address, every `sendmsg()` fails
  at *debug* log level only, the node stays "running", the sink stays IDLE, and the Pi gets zero
  packets. Nothing in the journal. So the sender is user unit `pi-speaker-rtp.service`
  (`pipewire -c pi-speaker-rtp.conf`, `laptop/`), not enabled at login; the 10 s user timer
  `pi-speaker-watch` starts it only while NetworkManager connection `sallen-router` is active *and*
  `ping 192.168.0.101` answers, stops it otherwise, and restarts it when the socket's local address
  (`ss -uanpH | grep :46000`) differs from `ip route get 192.168.0.101` src. While the sink is gone the
  *configured* default output is rewritten to another sink (seen: `sink-sunshine-stereo`) and is not
  restored by itself; the watch script restores `pi_speaker` as default only if it was the default
  when it stopped the sender. History: `journalctl --user -t pi-speaker-watch`.
  `audio.position = [ FL FR ]` is required in the rtp-sink args: without it the sink's channel map is
  `aux0,aux1` and GNOME Settings' speaker test shows no channel buttons. Pi-side check:
  `sudo tcpdump -ni eth0 udp port 46000` shows ~100 pkt/s (1932 B) while audio plays.
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
  choice). Fixes are physical: keep the phone near, or a USB Bluetooth dongle (in use since 2026-09-11,
  next bullet). Not a buffer issue.
- **Speaker adapter since 2026-09-11: TP-Link UB500 Plus** (Realtek RTL8761BU, USB `2357:0604`, firmware
  `rtl_bt/rtl8761bu_fw.bin` + `_config.bin` from jammy's linux-firmware, loads with no errors; full-speed
  USB, on the USB 2.0 hub port `1-1.3`). The onboard Broadcom radio is removed with `dtoverlay=disable-bt`
  (`pi/etc/config.txt`, replaces the old `dtparam=krnbt=on`), so the dongle is the only adapter (`hci0`
  after a reboot). Pairings live under `/var/lib/bluetooth/<adapter MAC>/` and cannot move between
  adapters: the phone and laptop were re-paired to `58:04:4F:D8:12:75`; the old onboard entries under
  `D8:3A:DD:78:3B:0F/` are dead. `pi/bin/bt-speaker-setup` (ExecStartPre of `bt-agent.service`) picks
  the adapter whose sysfs device path contains `/usb` and configures it over D-Bus
  (`busctl set-property org.bluez /org/bluez/hciN org.bluez.Adapter1 Alias|Discoverable|Pairable|Powered`);
  one-shot `bluetoothctl <cmd>` acts on the *first-listed* controller, which with two adapters was the
  dongle by accident. `/sys/class/bluetooth/` also holds `hciN:M` entries for open connections, so globs
  for adapters must skip names with `:`. History: `hciuart`/`hciattach` failed ("Initialization timed
  out") on this board; `dtparam=krnbt=on` (kernel `hci_uart`+`btbcm`) was the fix until the dongle.
  `hciuart.service` stays disabled; pi-bluetooth's `bthelper@hci0` logs "Dependency failed" at boot and
  never runs - harmless. `btusb` USB autosuspend is left at default (`power/control=auto`): during the
  10 min test the dongle stayed `active` and no stutter was seen, so nothing was added.
- **WirePlumber 0.4.8 removes the Bluetooth A2DP sink endpoint whenever no logind session of `sallen` is
  *active*** (`scripts/monitors/bluez.lua`: monitor created only on `logind get-state == "active"`; with
  `Linger=yes` and no SSH login the state is "lingering"; the Moonlight tty8 session counts as "online", not
  active). Symptom: the phone connects/plays only while someone is SSHed in; `bluetoothd` logs
  `Endpoint registered/unregistered` at exactly the `systemd-logind` New/Removed session times, and
  `bluetoothctl show` loses the "Audio Sink" UUID. Fix: `pi/config/wireplumber/bluetooth.lua.d/52-headless-no-logind.lua`
  redefines `bluez_monitor.enable()` without `load_optional_module("logind")`. Check it is in effect:
  `grep -c logind /proc/$(systemctl --user show -p MainPID --value wireplumber)/maps` prints 0.
- Any WirePlumber restart kills the RTP receiver stream in `rtp-speaker.service` ("stream error: no
  node available", the module is gone, but the process and the unit stay `active`, UDP 46000 closed).
  Since 2026-09-10 the unit has `PartOf=wireplumber.service` + a 30 s wait loop for the speaker node
  in ExecStartPre, so it restarts with WirePlumber (tested: `systemctl --user kill -s KILL wireplumber`
  -> receiver back with packets in < 10 s). Quick check when the laptop plays and nothing is heard:
  `ss -uanpH | grep :46000` (must show the pipewire socket) and `journalctl --user -u rtp-speaker`.
  On 2026-09-10 17:48 WirePlumber died of an external SIGKILL (no OOM, no sudo, nothing in the
  journal); sender unknown.

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
  passes flags: 1920x1080, **60 fps, 50000 kbps**. Smooth 60 fps needs the local build's Pi FFmpeg fork (zero-copy, below); with it the Pi renders 60/60 frames, 0 drops, render thread ~2% CPU. History: 30 fps/35000 until 2026-09-08; 60 fps/50000 on stock FFmpeg jittered (rendered only ~30/60) until the fork build 2026-09-09. At 60 fps with the DrmRenderer Moonlight uses ~1 core total (PacerRender thread ~50 %), CPU pressure `some` avg60 ~11-14 %, zero decode queue overflows after the first 15 s; laptop encodes with `h264_vaapi` (Intel VCS ~15 %, sunshine ~25 % CPU). Measured glass-to-glass delay at 1080p60/50000 (phone photos of laptop + monitor showing `laptop/latency-clock.html`, 10 shots, 2026-09-09): typically 83 ms (5 frames), range 67-101 ms. Sharpness
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
- Refresh rates: Pi HDMI mode is exactly 60.000 Hz (148.5 MHz / 2200x1125; the monitor EDID's only
  1080p detailed timing). Laptop panel modes: 1920x1200@60.002 (preferred), 1920x1200@59.950,
  1920x1080@59.934 (no 1080p@60.000). At 1080p the two clocks slip one frame every ~15 s.
- Sunshine video RTP (src port 47998 -> random Pi port): 12 B RTP header + 4 reserved B, then
  NV_VIDEO_PACKET; `frameIndex` is at UDP-payload offset 20 (Ethernet frame offset 62). Grouping a
  tcpdump by it gives frames/s, per-frame size and arrival jitter (measured: 60.1 fps, stdev 1.35 ms).
  A period-5 pattern in frame sizes = 24 fps video content (2-3-2-3 cadence on a 60 Hz desktop).
  Moonlight prints no per-session frame stats to the journal (the unit kills it, so the destructor's
  "Global video stats" line never appears); the overlay does not work on DRM either.
- Moonlight logs go to the journal by process (`journalctl _COMM=moonlight-qt`), not the unit.
- Moonlight's performance overlay (Ctrl+Alt+Shift+S) does **not** work with the DRM renderer on
  the Pi (known upstream limitation); keyboard input itself is forwarded fine.
- **`--frame-pacing` is a no-op with the DRM renderer.** moonlight-qt only has a vsync source on Windows
  and Wayland (pacer.cpp: "Platforms without a VsyncSource will just render frames immediately");
  on bare KMS each frame is shown at the first vblank after decode because `drmModeSetPlane()` blocks
  (maintainer, issue #1514). So display timing = arrival + decode time quantised to 60 Hz; when that
  phase drifts near a vblank boundary, frames alternate slots (repeat + skip) = visible jitter on
  60 fps motion (testufo.com), while the same monitor fed directly from the laptop is smooth.
  Measured 2026-09-09: Sunshine stamps frames at a free-running 60.000 Hz (RTP ts, 90 kHz, +-0.3 ms);
  network jitter to the Pi stdev 1.7 ms, p99 +-4 ms, max 7 ms; Wi-Fi ping max 28 ms/600.
  **Fixed 2026-09-09 with a local build** (`moonlight-qt-pi` 6.1.0-ubuntu2204pi6, `/usr/local/bin/moonlight-qt`;
  both units point there; the Cloudsmith `moonlight-qt` is removed by `Conflicts:`). Patches in `build/patches/`:
  0001 `DrmVsyncSource` (IVsyncSource that blocks in `drmWaitVBlank()` on the CRTC of the connected connector,
  selected for `SDL_SYSWM_KMSDRM`; log line "DrmVsyncSource: pacing to vblank of CRTC 94 (pipe 3)"; thread
  `PacerVsync`); 0002 skips `*_cuvid` decoders (jammy libavcodec 4.4 segfaults in `avcodec_open2()` when
  libnvcuvid is missing, seen with gdb) and accepts `*_v4l2m2m` when the one-frame test decode yields
  EAGAIN/EOF (FFmpeg 4.4's wrapper never outputs the tiny test frame, even after draining; this was the
  old "Test decode failed: Resource temporarily unavailable" -> SdlRenderer fallback, now gone).
  Build facts: jammy's SDL 2.0.20 KMSDRM cannot start ("Failed loading udev_device_get_action ...
  undefined symbol: _udev_device_get_action", libsdl-org/SDL#4879) so the Dockerfile builds SDL 2.32.10 +
  SDL_ttf 2.24.0 statically (`Libs.private` folded into the .pc files because qmake calls pkg-config
  without `--static`); `CONFIG+=disable-libvdpau disable-x11 disable-wayland` (vdpau.cpp uses SDL x11
  fields unguarded). Package deps needed `libva-wayland2`, `libfreetype6`, `libudev1`. Rollback:
  `sudo apt-get install ./<cloudsmith moonlight-qt_6.1.0-4_arm64.deb>` (apt-get download moonlight-qt)
  and ExecStart back to `/usr/bin/moonlight-qt` in both units. Run a candidate binary under gdb with the
  units stopped before installing: `pi-screen stop; sudo systemctl stop moonlight; QT_QPA_PLATFORM=eglfs
  ... gdb -batch -ex run -ex bt --args <bin> stream ...` (crashes here cost the screen otherwise).
  Vendor-build comparison, main thread CPU: SdlRenderer fallback ~63 %, DrmRenderer ~15-18 %.
  Objective smoothness check: phone-record testufo.com on the monitor at 60 fps, then
  `tools/ufo-step-analysis.py record.mp4` (per-frame UFO step: repeats/doubles; a 59 fps phone adds ~1
  double/s). Before the fix (pacer on but SdlRenderer fallback, 2026-09-09 03:09): 20.7 % repeated frames,
  9.7 % double steps.
  **Remaining bottleneck (measured 2026-09-09 with the 0003 stats log, MOONLIGHT_STATS_INTERVAL=5):**
  the pacer works but the Pi renders only ~30 of 60 fps (stats: received/decoded 302/5s = 60, rendered
  133-181, pacerDropped 120-170, netDropped 0). Render-thread gdb stacks are in `DrmRenderer::mapSoftwareFrame`
  -> `memcpy` (a 1080p NV12 CPU copy per frame) + blocking `drmModeSetPlane`, > 16.7 ms/frame, so half the
  frames are dropped = the residual jitter. Cause: the h264_v4l2m2m *drm_prime* (zero-copy) hwaccel path
  fails its 1-frame test decode (EAGAIN "Resource temporarily unavailable" on jammy FFmpeg 4.4), so Moonlight
  uses the non-hwaccel v4l2m2m decoder that outputs software NV12. DrmRenderer *does* have a zero-copy import
  (drm.cpp:1126, `drmPrimeFDToHandle` when frame->format==DRM_PRIME) - it's just not being fed drm_prime frames.
  **Solved 2026-09-09 (pi8 build) by replacing the FFmpeg.** Root cause: jammy's stock FFmpeg 4.4 h264_v4l2m2m
  advertises no hwaccel and only outputs software NV12 (`ffmpeg -h decoder=h264_v4l2m2m` shows no hw config;
  a CLI decode picks `capture=YU12`), so DrmRenderer always took the copy path. The `build/Dockerfile` now
  builds the **jc-kynesim/rpi-ffmpeg fork** (branch `dev/6.1.1/rpi_import_1`) which adds an AV_PIX_FMT_DRM_PRIME
  (dma-buf) output for v4l2m2m - the same FFmpeg Raspberry Pi OS ships. Configure:
  `--enable-shared --enable-gpl --enable-v4l2-request --enable-libdrm --enable-libudev --enable-sand
  --disable-mmal --disable-vaapi --disable-vdpau --disable-programs --disable-doc --disable-encoders
  --disable-muxers` (v4l2-request REQUIRES libudev-dev, or configure errors). It installs to /usr/local
  (soname libavcodec.so.60, distinct from jammy's .so.58 - they coexist); Moonlight links it via pkg-config
  after purging jammy's libav*-dev, and carries `-rpath /usr/local/lib`. package.sh ships the fork's
  libav*/libsw* .so into the deb's /usr/local/lib with a postinst `ldconfig`; deb is ~16 MB (vs ~9). With the
  fork the render thread hands drm_prime frames straight to drmModeSetPlane (no mapSoftwareFrame/memcpy),
  render-thread CPU ~2% (was ~50%), and 1080p60 renders 60/60 with 0 drops. Verify zero-copy: gdb the
  PacerRender thread - it must NOT be in `DrmRenderer::mapSoftwareFrame`/memcpy.
    Abandoned alternatives: PR moonlight-qt#1139 "minimum-latency" (timer release, not vblank-locked), a Wayland
  kiosk compositor (cage) for WaylandVsyncSource.
- Monitor: ASUS VY229HE (IPS, 75 Hz, HDMI). Direct laptop->monitor mirroring runs at 75 Hz.
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
  Copy `build/Dockerfile`, `build/package.sh`, `build/patches/` there first; `-e PKG_REV=ubuntu2204pi2`
  names the .deb. **arm64 containers fail with `exec /bin/sh: no such file or directory` while Waydroid
  is running**: its Android init registers binfmt entries `arm64_exe`/`arm64_dyn` (interpreter
  `/system/bin/houdini64`, exists only inside the Android container) that shadow `qemu-aarch64`
  (binfmt_misc tries the newest entry first). Fix for the build:
  `for e in arm64_exe arm64_dyn; do echo 0 | sudo tee /proc/sys/fs/binfmt_misc/$e; done`, re-enable
  with `echo 1` afterwards (Waydroid needs them for arm apps). Check: `docker run --rm --platform
  linux/arm64 ubuntu:22.04 uname -m` prints `aarch64`.

## Sunshine / Moonlight pairing (laptop)
- `sunshine --creds USER PASS` writes credentials, but the running service must be
  restarted before the web UI/API stops redirecting to `/welcome`.
- Headless pairing from the Pi: `QT_QPA_PLATFORM=offscreen moonlight-qt pair <laptop> --pin 4321`
  in the background, then `curl -k -u USER:PASS -X POST https://<laptop>:47990/api/pin -d '{"pin":"4321","name":"sallen-pi"}'`.
  The pair command hangs after success (kill it); `moonlight-qt list <laptop>` confirms.
- Web UI credentials are in `build/out/sunshine-creds.txt` on the Pi (not committed).

## Bluetooth speaker: range and stationary mutes (measured 2026-09-10)
- The Pi sits in a **metal heatsink case (top/bottom blocks, open sides), kept for cooling**. The Pi 4
  antenna is a PCB slot at the display-connector corner, under the block: dominant range loss, accepted.
  No board mod (external antenna). **Superseded 2026-09-11 by the TP-Link UB500 Plus USB dongle** (see
  the Bluetooth section above); the measurements below describe the onboard radio and are kept as history.
- **Dongle test 2026-09-11 23:00-23:11 (phone still, < 1 m, aptX, onboard radio powered off, USB autosuspend
  at default):** 626 s, no missing second, no second below 40 pkt/s, steady 66-70 pkt/s. Failed Contact
  Counter (HCI `0x05 0x0001`) stayed 0. From 23:06:51 the laptop also paired and streamed (~109 pkt/s, SBC)
  at the same time with no gaps on either link. The phone's AFH map excluded channels 10-47 (2412-2449 MHz,
  Wi-Fi channels 1-6), i.e. a 2.4 GHz network was present during the test (Wi-Fi channels 1 and 4 visible).
  Realtek-specific: `hcitool lq` always returns 0 (not implemented) and `hcitool rssi` reports real dBm
  (-4 to -36, median about -16) instead of Broadcom's "0 = golden range", so the old lq recipe does not
  apply; use the packet-gap count and the Failed Contact Counter.
- Onboard Wi-Fi is **on again** since 2026-09-11 (Bluetooth no longer shares its antenna): `disable-wifi`
  removed from `pi/etc/config.txt`, `nmcli radio wifi on` live; autoconnect did not fire by itself, an
  explicit `nmcli con up netplan-wlan0-sallen-router` did (5 GHz ch 161, -45 dBm, 192.168.0.138 next to
  eth0 192.168.0.101, route metric 600 vs 100). History: it was off 2026-09-10/11 because, while on but
  *not associated*, NetworkManager ran a full 2.4+5 GHz scan (2.8 s) every 120 s (`iw event -t`) on the
  shared antenna; a 5 min `btmon` capture showed no packet loss across three scans, so the scans were not
  the multi-second mutes.
- **60 min capture 2026-09-10 11:14-11:55 (phone still, < 1 m, streaming over Wi-Fi):** packets from
  the phone stop for 1-4 s in clusters (11:36:08-11:37:28: nine gaps) and then arrive in a burst (up to
  358 pkt/s = the "jump"). Every multi-second gap falls inside a period where `hcitool lq` had collapsed
  (205 -> 4 within 30 s, `rssi` still 0); bad periods lasted 11:36-11:43 and 11:52-11:55, good periods
  had only isolated 1 s hiccups. None of the 30 Wi-Fi scans lined up with a gap, and this Claude session
  was idle during the worst cluster. **Two kinds of gap, told apart by the AVDTP signalling channel**:
  gaps preceded by a phone-sent SUSPEND (signal id 0x09) and ended by START (0x07) are the music app
  pausing (track change / rebuffer, 2-6 s, 3-4 per 30 min, happen with headphones too); gaps with *no*
  SUSPEND are radio stalls. The 11:36-11:37 cluster (six gaps) had no SUSPEND and coincided with the lq
  collapse = radio. Recipe: `btmon -T -r cap.btsnoop | awk '/^[<>] ACL Data/{ts=$NF;d=$1}
  /Channel: 64 len/{w=1;next} w{if($1~/^[0-9a-f][0-9a-f]$/)print substr(ts,1,12),d,$1,$2,$3; w=0}' |
  awk '$5=="09"||$5=="07"'` (channel 64 was the AVDTP signalling CID in both captures; check yours).
- **Router 2.4 GHz switched off (user, 2026-09-10 ~14:15):** 39 min captured (14:19-14:58): zero radio
  stalls, every gap was an app SUSPEND/START, lq never below 130 (medians 135-197, no collapse). With
  2.4 GHz on, 41 min had two lq-collapse episodes and one radio-stall cluster. Strong indication that
  2.4 GHz Wi-Fi traffic in the room was the interferer and the Pi (antenna under the heatsink) the only
  victim; headphones on the same phone were fine. Not yet proven over a longer period.
- Ruled out for the stationary mutes: CPU load (4 cores burned, `pw-top` ERR stayed 0 on the bluez
  source and the ALSA sink; PipeWire data threads are RR 20), Bluetooth UART overruns
  (`/proc/tty/driver/ttyAMA` shows none), USB 3 HDD noise (190 MB/s raw read: `hcitool lq` 205 -> 197),
  Bluetooth firmware (`BCM4345C0 003.001.025 build 0370`, newer than the Cypress fix 0339), Wi-Fi NVRAM
  (`btc_mode=1` + Cypress params already), laptop Moonlight traffic (laptop is on 5 GHz ch 161).
- `hcitool lq <phone>` (255 best, updates every ~5 s) is **bimodal** with the phone still < 1 m away:
  minutes at 175-215, minutes at 9-55, while `hcitool rssi` stays 0 (= strong level). Low quality at
  strong level = bit errors from interference, not distance. The phone side is *not* the weak link: the
  same phone, same desk, same Wi-Fi streaming feeds Bluetooth headphones with no dropouts. So the Pi's
  receiver is what fails: thin margin (antenna under the heatsink block) plus 2.4 GHz noise near it.
  Candidates still untested, each needs a 10 min `hcitool lq` log on/off with the phone still:
  HDMI output / Moonlight (cheap HDMI cables radiate broadband noise; `pi-screen stop` vs start),
  the USB 3 HDD and its cable (minor at strong signal), the monitor itself, a microwave oven
  (episodes lasted 3-7 min).
- Measurement recipes: link quality loop `hcitool lq $P; hcitool rssi $P` each second (Broadcom only, see
  the dongle note above; add `-i hciN` when more than one adapter exists). Packet rate from the phone:
  `sudo btmon [-i hciN] -w cap.btsnoop`, then `tools/btsnoop-gaps.py cap.btsnoop` prints, per ACL
  connection handle, the pkt/s distribution, missing seconds and seconds below 40 pkt/s (aptX: 66-70 pkt/s
  of dlen 660; a mute = missing/low seconds). It reads btmon's monitor format (datalink 2001, opcode 5 =
  ACL RX) directly, because `btmon -T -r` abbreviates the handle to "H.." when stdout is not a wide tty
  (also under `script`/a pty it crawled at a few KB/min on a 48 MB file). **Do not pipe live `btmon` to
  grep**: stdout is block-buffered (lost on timeout). Do not `pkill -f` a pattern that appears in your
  own command line.
- Codec: phone negotiates **aptX** (`api.bluez5.codec` on the bluez_input node). libspa-bluez5 1.0.7 has
  `bluez5.codecs` (e.g. `"[ sbc ]"`) but no SBC bitpool cap.

## SSH exposure
- The router forwards TCP 22 from the internet to the Pi (brute-force probes arrive on eth0, ~900/day
  from one host on 2026-09-10). sshd reads `sshd_config.d/*.conf` in name order and the **first** value
  of a keyword wins: `50-cloud-init.conf` (`PasswordAuthentication yes`) beats
  `60-cloudimg-settings.conf` (`no`), so password login was effectively on. `pi/etc/ssh/sshd_config.d/
  10-hardening.conf` sorts first (`PermitRootLogin no`; root has an empty authorized_keys). Check the
  effective values with `sudo sshd -T | grep -E 'passwordauth|permitroot'`; `sshd -t` then
  `systemctl reload ssh` applies without dropping sessions. Keys in `~/.ssh/authorized_keys`: the
  laptop (chouallenno@gmail.com) and the Pi itself. Tailscale is also up (100.111.120.67).


## Bluetooth speaker: what the Pi records when the phone drops out (checked 2026-09-11 23:50)
- **Nothing, unless `btmon` is running.** For a 5 min dropout reported by the user, the Pi had zero kernel,
  bluetoothd, PipeWire or WirePlumber lines; `pw-top` ERR stayed 0 on the bluez source and the ALSA sink
  (missing radio packets are not xruns); `/proc/pressure/cpu` avg300 was 5 %; `hciconfig` RX/TX errors 0.
  Only a capture at the time of the event can tell an app SUSPEND/START pause from a radio stall.
- Dongle USB autosuspend (`/sys/bus/usb/devices/1-1.3/power/runtime_suspended_time`, ms): suspends only
  while the phone is connected but idle (593 s of the first 32 min after boot); 0 ms growth during 45 s of
  streaming. So autosuspend can only glitch the start of playback, not a running stream.
- `tools/btsnoop-gaps.py` reports a false "missing seconds" entry when a capture crosses midnight
  (per-second keys are (h, m, s) tuples; the day is not part of the key).
- `sudo iw dev wlan0 scan` while NetworkManager holds wlan0 associated returned nothing, and
  `nmcli dev wifi rescan` produced no `iw event` scan lines either, so "does a Pi Wi-Fi scan next to the
  dongle cause a gap" is untested.
- First undervoltage on this board: `hwmon: Undervoltage detected!` 2026-09-11 23:32:15-19 (4 s), first boot
  with the UB500 dongle + USB HDD; `vcgencmd get_throttled` = 0x50000 (undervoltage + throttling occurred
  since boot). The previous 17 h boot had none.

## Moonlight HEVC log flood (2026-09-11 06:33 -> fixed 2026-09-12 with the pi9 build)
- With the rpi-ffmpeg fork, `hevc_v4l2request` passes its test decode, so Sunshine now streams
  **HEVC Main 10** ("Video stream: 1920x1080 60.00 FPS (Codec: HEVC)", `rpivid_h265_start` in dmesg).
- Cause: the fork's `libavcodec/v4l2_req_hevc_vx.c` (7) and `v4l2_request_hevc.c` (1) have raw
  `fprintf(stderr, "<<< %s...", __func__)` prints, 6 per frame (`start_frame`, `end_frame`, `decode_slice`,
  `frame_post_process`, `alloc_frame`, `free_frame_priv`) = ~360 journal lines/s at 1080p60, a 128 MB user
  journal file every 7 min, journal 3.9 GB, `systemd-journald` ~26 % + `rsyslogd` ~16 % of a core. They bypass
  av_log, so Moonlight's log level cannot filter them. Fix: `build/Dockerfile` seds every `__func__` fprintf
  in those two files into `av_log(NULL, AV_LOG_TRACE, ...)` (a `! grep` guard fails the build if one is left),
  package `moonlight-qt-pi 6.1.0-ubuntu2204pi9` (`build/out/`). Measured after install + `pi-screen restart`:
  12 lines per 5 s in steady state (the 0003 stats block), stream 60/60 rendered, 0 drops.
- What still logs at stream start (~1000 lines in the first 7 s, then stops): moonlight-qt sets
  `av_log_set_level(AV_LOG_DEBUG)` while it probes decoders (ffmpeg.cpp) and back to INFO afterwards, so the
  fork's debug lines (`Buf caps ... insufficient` x420, `probe_video_device`, `Format drm_prime chosen by
  get_format()`, `<<< v4l2_request_hevc_init/uninit` via av_log) appear once per session. The 176 "Could not
  queue DRM page flip (Permission denied)" lines are the menu->stream DRM master handover, unrelated.
- `journalctl` over the flooded boots (before 2026-09-12 00:07) takes minutes (kill with `pkill -x journalctl`,
  never `pkill -f`); filter with `grep -v '<<<'`. Rate check: `journalctl _COMM=moonlight-qt --since -60s -o cat | wc -l` (expect ~144, the
  stats block); a piped `journalctl -f` killed by `timeout` can return nothing, do not count with it.
- Journal capped at 1 GB since 2026-09-12 (`pi/etc/systemd/journald.conf.d/10-size.conf`, `SystemMaxUse=1G`;
  default was 4 GB = min(10 % of /, 4 GB)). Applying it vacuumed 4.1 GB -> 1.0 GB at once; history before
  the cut is gone. rsyslogd keeps a second plain-text copy in `/var/log/syslog` (no size cap, `/etc/logrotate.d/rsyslog` rotates **weekly**,
  4 rotations kept, checked by the daily logrotate.timer) - separate space, not affected by this cap.

## Keyboard/mouse plugged into the Pi, forwarded to the laptop (measured 2026-09-12 00:40-00:50)
- Works with nothing added: while `moonlight-stream` runs, Moonlight (SDL KMSDRM, evdev via udev hotplug) opens
  every `/dev/input/event*` and sends key/button/motion to Sunshine, which injects them on the laptop through
  uinput devices named `Mouse passthrough` / `Keyboard passthrough` (numbers change per connection; look them up
  by name in `/proc/bus/input/devices`). Stream stopped = input dead. Ctrl+Alt+Shift+<key> combos are Moonlight's.
- **Added delay (Pi kernel timestamp -> laptop uinput timestamp, clock offset removed, +-0.5 ms):** mouse buttons
  n=248: median 1.9 ms, p90 2.8, p99 5.0, max 21 ms (same still or moving); keys n=134: median 2.0 ms, p90 3.0,
  two outliers 28/37 ms. Ping Pi->laptop during the run: median 1.5, p99 5.7, max 12.5 ms (laptop on 5 GHz Wi-Fi).
  The outliers are Wi-Fi tail, not the software path. Mouse and keyboard poll at 1 ms (1000 Hz) on both hosts.
- Recipe: `tools/input-latency.py` (stdlib only, same file on both machines; the Pi has no `evtest` and no
  python-evdev). Laptop: `echo` + `capture /dev/input/eventN out`; Pi: `capture`, `probe <laptop> out` (NTP-style
  UDP clock offset, port 46010, offset fitted from the lowest-delay 20 %), then `analyze pi.log laptop.log probe.log
  [--split T]`. Only EV_KEY events are paired (motion is batched by Moonlight). Kernel autorepeat (value 2) exists
  on the Pi side only; Moonlight does not forward it, so `analyze` drops it. Raw logs: `build/out/input-latency-2026-09-12/`.
- Killing the captures: `pkill -f 'input-latenc[y].py'` - a plain `pkill -f input-latency` matched the calling
  shell's own command line and killed it (exit 144).
- Decision 2026-09-12: only the **keyboard** lives on the Pi; the mouse stays on the laptop (short wireless range,
  and pointer motion is the latency-sensitive input).
