#!/usr/bin/env python3
"""Bytes per video frame in a Sunshine -> Moonlight capture.

Capture on the Pi:  sudo timeout 20 tcpdump -ni eth0 -w switch.pcap 'udp and src port 47998'
Analyse:            python3 tools/stream-frame-sizes.py switch.pcap [--from SEC] [--to SEC]

Sunshine's video RTP packets carry frameIndex as a little-endian u32 at UDP payload
offset 20 (Ethernet frame offset 62). Stdlib only (the Pi has no scapy/dpkt).
"""
import argparse
import struct
import sys
from collections import OrderedDict

PCAP_MAGIC = {0xA1B2C3D4: ("<", 1e-6), 0xD4C3B2A1: (">", 1e-6),
              0xA1B23C4D: ("<", 1e-9), 0x4D3CB2A1: (">", 1e-9)}
LINKTYPE_ETHERNET = 1
LINKTYPE_LINUX_SLL = 113


def read_pcap(path):
    with open(path, "rb") as f:
        hdr = f.read(24)
        magic = struct.unpack("<I", hdr[:4])[0]
        if magic not in PCAP_MAGIC:
            sys.exit("not a classic pcap file (pcapng is not supported; use tcpdump -w)")
        endian, frac = PCAP_MAGIC[magic]
        linktype = struct.unpack(endian + "I", hdr[20:24])[0]
        if linktype == LINKTYPE_ETHERNET:
            l2 = 14
        elif linktype == LINKTYPE_LINUX_SLL:
            l2 = 16
        else:
            sys.exit(f"unsupported link type {linktype}")
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                return
            sec, sub, caplen, _ = struct.unpack(endian + "IIII", rec)
            data = f.read(caplen)
            yield sec + sub * frac, data, l2


def frames(path):
    """Return OrderedDict frameIndex -> dict(t0, t1, bytes, pkts)."""
    out = OrderedDict()
    for ts, data, l2 in read_pcap(path):
        if len(data) < l2 + 20 + 8 + 24:
            continue
        ihl = (data[l2] & 0x0F) * 4
        udp = l2 + ihl
        payload = udp + 8
        idx = struct.unpack_from("<I", data, payload + 20)[0]
        udp_len = struct.unpack_from(">H", data, udp + 4)[0] - 8
        fr = out.get(idx)
        if fr is None:
            out[idx] = {"t0": ts, "t1": ts, "bytes": udp_len, "pkts": 1}
        else:
            fr["t1"] = ts
            fr["bytes"] += udp_len
            fr["pkts"] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap")
    ap.add_argument("--from", dest="t_from", type=float, default=0.0,
                    help="only list frames after this many seconds into the capture")
    ap.add_argument("--to", dest="t_to", type=float, default=1e9)
    ap.add_argument("--min-kb", type=float, default=0.0,
                    help="in the listing, print only frames at least this big")
    args = ap.parse_args()

    fr = frames(args.pcap)
    if not fr:
        sys.exit("no video packets found")
    t_start = next(iter(fr.values()))["t0"]
    sizes = [v["bytes"] for v in fr.values()]
    dur = max(v["t1"] for v in fr.values()) - t_start
    print(f"{len(fr)} frames in {dur:.2f} s ({len(fr) / dur:.1f} fps), "
          f"{sum(sizes) * 8 / dur / 1e6:.1f} Mbit/s average")
    srt = sorted(sizes)
    pct = lambda p: srt[min(len(srt) - 1, int(p / 100 * len(srt)))] / 1000
    print(f"frame size kB: min {srt[0] / 1000:.1f}  p50 {pct(50):.1f}  p90 {pct(90):.1f}  "
          f"p99 {pct(99):.1f}  max {srt[-1] / 1000:.1f}")

    print("\nhistogram (kB per frame):")
    edges = [0, 2, 5, 10, 20, 40, 60, 80, 100, 150, 200, 400, 800, 1e9]
    for lo, hi in zip(edges, edges[1:]):
        n = sum(1 for s in sizes if lo * 1000 <= s < hi * 1000)
        if n:
            label = f"{lo:>4.0f}-{hi:<4.0f}" if hi < 1e9 else f"{lo:>4.0f}+    "
            print(f"  {label} {n:5d} {'#' * min(60, n)}")

    print(f"\nframes between t={args.t_from}s and t={args.t_to}s (t, dt ms, kB, pkts):")
    prev = None
    for idx, v in fr.items():
        t = v["t0"] - t_start
        if t < args.t_from or t > args.t_to:
            continue
        dt = (v["t0"] - prev) * 1000 if prev is not None else 0
        prev = v["t0"]
        if v["bytes"] >= args.min_kb * 1000:
            print(f"  {t:8.3f} {dt:6.1f} {v['bytes'] / 1000:7.1f} {v['pkts']:4d}  #{idx}")


if __name__ == "__main__":
    main()
