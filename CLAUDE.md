# room-devices – facts for future work

Pi: Raspberry Pi 4B, Ubuntu Server 22.04 (kernel 5.15 raspi), boots from a USB **HDD** (`/dev/sda`).
No desktop. User `sallen` has `Linger=yes`, so PipeWire user services run without a login.
Laptop: `sallen@192.168.0.193`, Ubuntu 24.04, GNOME 46 Wayland, PipeWire 1.0.5, on Wi-Fi.
Large files on the laptop go under `/media/sallen/SSD-Programs/` (root disk is nearly full).

## Audio (PipeWire 0.3.48 + WirePlumber 0.4.8, stock jammy)
- `apt update` was needed first: the universe index was missing, so `wireplumber`,
  `pipewire-pulse` etc. showed "Candidate: (none)".
- Both bcm2835 ALSA cards get the *same* `node.name`/`device.name`; match on
  `api.alsa.card.name` ("bcm2835 Headphones", "bcm2835 HDMI 1").
- `["node.disabled"] = true` in a WirePlumber 0.4.8 alsa rule breaks routing for *all*
  streams ("no node available"). Use `["device.disabled"] = true` on the device instead.
- `pipewire-pulse.conf.d/*.conf` fragments do **not** override `pulse.properties` in 0.3.48;
  the full `pipewire-pulse.conf` is copied to `~/.config/pipewire/` and edited.
- RTKit refused realtime for the headless user (no local seat). Fixed with a polkit `.pkla`
  allowing `org.freedesktop.RealtimeKit1.*` for `sallen` (`pi/etc/polkit-1/`).
- Laptop side: a static `libpipewire-module-pulse-tunnel` entry in `pipewire.conf.d` fails at
  laptop boot if the Pi is unreachable (needs `flags = [ nofail ]` or laptop audio breaks) and
  never retries; it also vanishes when the Pi reboots. So the tunnel is created by
  `laptop/pi-speaker-watch` (systemd user timer, every 20 s) via
  `pactl load-module module-tunnel-sink ... latency_msec=80`. pipewire-pulse splits module
  arguments on whitespace regardless of quoting, so `sink_properties=device.description=` cannot
  contain spaces (hence "Room-speaker-Pi"). The module's
  "failed to connect: Bad state" was the Pi-side `node.disabled` routing bug, not network.

## Bluetooth
- `hciuart`/`hciattach` fails ("Initialization timed out") on this board even with the
  `Requires=dev-serial1.device` fix. The device tree has a `bluetooth` node under the PL011
  UART; `dtparam=krnbt=on` makes the kernel (`hci_uart`+`btbcm`) bring up `hci0` instead.
  `hciuart.service` is disabled.

## Display
- `/boot/firmware/config.txt` needs `dtoverlay=vc4-kms-v3d` (in a `[pi4]` block); without it
  there is no `/dev/dri` and nothing but the text console can draw.
- **Overlay order matters**: `dtoverlay=` lines must come *after* `dtparam=audio=on`. Putting
  the KMS overlay in the first `[pi4]` block (above the dtparams) made the "bcm2835 Headphones"
  ALSA card disappear entirely (no `/proc/device-tree/soc/audio`). See `pi/etc/config.txt`.
- HEVC hardware decode needs `dtoverlay=rpivid-v4l2` (creates `/dev/video19`, GStreamer
  `v4l2slh265dec`). H.264 (`/dev/video10`, `v4l2h264dec`) works without it.
- `cmdline.txt` has `video=HDMI-A-1:1920x1080@60D` so HDMI0 is treated as connected even when
  the monitor is off/asleep (the monitor is shared with the laptop). HDMI0 = port next to USB-C.
- Moonlight: the Cloudsmith `moonlight-qt` jammy arm64 package is Qt 6 and does **not** pull
  in a platform plugin; install `qt6-qpa-plugins` (eglfs, eglfs_kms). Ubuntu-on-Pi is
  unsupported upstream. A Qt 5 build from source (`build/Dockerfile`, arm64 emulation on the
  laptop, ~10 min) is the fallback: `build/out/moonlight-qt-pi_*.deb`.
- `moonlight.service` needs `XDG_RUNTIME_DIR=/run/user/1000` or it has no sound.

## Commands
- Pi audio state: `wpctl status`, `pactl list sink-inputs`, `journalctl --user -u wireplumber`.
- Rebuild Moonlight on the laptop:
  `cd /media/sallen/SSD-Programs/room-devices-build && docker build --platform linux/arm64 -t moonlight-pi-build . && docker run --rm --platform linux/arm64 -v $PWD/out:/out moonlight-pi-build`

## Sunshine / Moonlight pairing (laptop)
- `sunshine --creds USER PASS` writes credentials, but the running service must be
  restarted before the web UI/API stops redirecting to `/welcome`.
- Headless pairing from the Pi: `QT_QPA_PLATFORM=offscreen moonlight-qt pair <laptop> --pin 4321`
  in the background, then `curl -k -u USER:PASS -X POST https://<laptop>:47990/api/pin -d '{"pin":"4321","name":"sallen-pi"}'`.
  The pair command hangs after success (kill it); `moonlight-qt list <laptop>` confirms.
- Web UI credentials are in `build/out/sunshine-creds.txt` on the Pi (not committed).
