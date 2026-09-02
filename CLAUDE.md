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
- Laptop side: `libpipewire-module-pulse-tunnel` needs `flags = [ nofail ]` or laptop audio
  breaks when the Pi is off. Its "failed to connect: Bad state" was the Pi-side routing bug
  above, not a network problem.

## Bluetooth
- `hciuart`/`hciattach` fails ("Initialization timed out") on this board even with the
  `Requires=dev-serial1.device` fix. The device tree has a `bluetooth` node under the PL011
  UART; `dtparam=krnbt=on` makes the kernel (`hci_uart`+`btbcm`) bring up `hci0` instead.
  `hciuart.service` is disabled.

## Display
- `/boot/firmware/config.txt` `[pi4]` needs `dtoverlay=vc4-kms-v3d`; without it there is no
  `/dev/dri` and nothing but the text console can draw.
- Moonlight: the Cloudsmith `moonlight-qt` jammy arm64 package is Qt 6 and does **not** pull
  in a platform plugin; install `qt6-qpa-plugins` (eglfs, eglfs_kms). Ubuntu-on-Pi is
  unsupported upstream. A Qt 5 build from source (`build/Dockerfile`, arm64 emulation on the
  laptop, ~10 min) is the fallback: `build/out/moonlight-qt-pi_*.deb`.
- `moonlight.service` needs `XDG_RUNTIME_DIR=/run/user/1000` or it has no sound.

## Commands
- Pi audio state: `wpctl status`, `pactl list sink-inputs`, `journalctl --user -u wireplumber`.
- Rebuild Moonlight on the laptop:
  `cd /media/sallen/SSD-Programs/room-devices-build && docker build --platform linux/arm64 -t moonlight-pi-build . && docker run --rm --platform linux/arm64 -v $PWD/out:/out moonlight-pi-build`
