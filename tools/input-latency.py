#!/usr/bin/env python3
"""Measure added input latency for a keyboard/mouse plugged into the Pi and forwarded to the laptop
(Moonlight -> Sunshine uinput).  Pure stdlib; runs unchanged on both machines (64-bit input_event = 24 B).

  capture DEV OUT            log every EV_KEY event of /dev/input/eventN: "t type code value" (kernel clock)
  echo [--port P]            UDP echo server (run on the laptop): appends its recv/send time.time()
  probe HOST OUT [--port P] [--hz N]
                             NTP-style clock probe (run on the Pi): logs "t1 t2 t3 t4" per sample
  analyze PI_LOG LAPTOP_LOG PROBE_LOG
                             pair nth (code,value) event on both sides, subtract the fitted clock offset

The offset is fitted from the lowest-delay 20 % of probe samples (linear in time, so clock drift is
handled).  Its uncertainty is about half the minimum round trip (path asymmetry).
"""
import os, socket, struct, sys, time, argparse, statistics

EV_FMT = "llHHi"                 # struct input_event on 64-bit: tv_sec, tv_usec, type, code, value
EV_SIZE = struct.calcsize(EV_FMT)
EV_KEY, EV_REL = 1, 2


def cmd_capture(a):
    fd = os.open(a.dev, os.O_RDONLY)
    rel = 0
    with open(a.out, "a", buffering=1) as out:
        out.write(f"# capture {a.dev} started {time.time():.6f}\n")
        while True:
            buf = os.read(fd, EV_SIZE * 64)
            for i in range(0, len(buf) - EV_SIZE + 1, EV_SIZE):
                sec, usec, typ, code, val = struct.unpack_from(EV_FMT, buf, i)
                if typ == EV_KEY:
                    out.write(f"{sec}.{usec:06d} {typ} {code} {val}\n")
                elif typ == EV_REL:
                    rel += 1
                    if rel % 1000 == 0:
                        out.write(f"# rel {rel} at {sec}.{usec:06d}\n")


def cmd_echo(a):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", a.port))
    while True:
        data, addr = s.recvfrom(256)
        t2 = time.time()
        s.sendto(data + f" {t2:.6f} {time.time():.6f}".encode(), addr)


def cmd_probe(a):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1.0)
    period = 1.0 / a.hz
    with open(a.out, "a", buffering=1) as out:
        while True:
            t1 = time.time()
            s.sendto(f"{t1:.6f}".encode(), (a.host, a.port))
            try:
                data, _ = s.recvfrom(256)
            except socket.timeout:
                out.write(f"# timeout {t1:.6f}\n")
                continue
            t4 = time.time()
            p = data.decode().split()
            if len(p) == 3 and abs(float(p[0]) - t1) < 1e-6:
                out.write(f"{t1:.6f} {p[1]} {p[2]} {t4:.6f}\n")
            time.sleep(max(0.0, period - (time.time() - t1)))


def read_events(path, keep_repeat=False):
    """Returns (events, capture_start).  value 2 = kernel autorepeat: the Pi kernel generates it, Moonlight
    does not forward it (the laptop side repeats on its own), so it is dropped unless keep_repeat."""
    ev = []; start = None
    for line in open(path):
        if line.startswith("# capture"):
            start = float(line.split()[-1]); continue
        if line.startswith("#") or not line.strip():
            continue
        t, typ, code, val = line.split()
        if int(val) == 2 and not keep_repeat:
            continue
        ev.append((float(t), int(code), int(val)))
    return ev, start


def fit_offset(path):
    """Return (offset_fn(t) -> laptop_time - pi_time, min_rtt_ms, n_used)."""
    samp = []
    for line in open(path):
        if line.startswith("#"):
            continue
        t1, t2, t3, t4 = map(float, line.split())
        samp.append(((t1 + t4) / 2, ((t2 - t1) + (t3 - t4)) / 2, (t4 - t1) - (t3 - t2)))
    if not samp:
        raise SystemExit("no probe samples")
    samp.sort(key=lambda s: s[2])
    best = samp[: max(5, len(samp) // 5)]
    xs = [s[0] for s in best]; ys = [s[1] for s in best]
    x0 = statistics.mean(xs); y0 = statistics.mean(ys)
    sxx = sum((x - x0) ** 2 for x in xs)
    slope = sum((x - x0) * (y - y0) for x, y in zip(xs, ys)) / sxx if sxx > 0 else 0.0
    resid = [abs(y - (y0 + slope * (x - x0))) * 1000 for x, y in zip(xs, ys)]
    print(f"clock offset (laptop - pi): {y0*1000:+.3f} ms at midpoint, drift {slope*1e6:+.2f} us/s, "
          f"fit residual p90 {sorted(resid)[int(0.9*(len(resid)-1))]:.3f} ms, "
          f"from {len(best)}/{len(samp)} lowest-delay probes; min RTT {samp[0][2]*1000:.3f} ms")
    return (lambda t: y0 + slope * (t - x0)), samp[0][2] * 1000, len(best)


def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def cmd_analyze(a):
    off, min_rtt, _ = fit_offset(a.probe)
    pi, pi_start = read_events(a.pi, a.keep_repeat); lap, lap_start = read_events(a.laptop, a.keep_repeat)
    # only events after BOTH captures were running can be paired
    t_from = max(pi_start or 0, (lap_start or 0) - off(lap_start or 0)) + 0.05
    n0 = (len(pi), len(lap))
    pi = [e for e in pi if e[0] >= t_from]; lap = [e for e in lap if e[0] - off(e[0]) >= t_from]
    print(f"events (autorepeat dropped): pi {n0[0]} laptop {n0[1]}; after both captures were up: pi {len(pi)} laptop {len(lap)}")
    # pair in order per (code, value); unmatched ones are reported
    from collections import defaultdict, deque
    q = defaultdict(deque)
    for t, c, v in lap:
        q[(c, v)].append(t)
    lat = []; unmatched = 0
    for t, c, v in pi:
        if q[(c, v)]:
            tl = q[(c, v)].popleft()
            lat.append((t, (tl - t - off(t)) * 1000, c, v))
        else:
            unmatched += 1
    left = sum(len(d) for d in q.values())
    print(f"paired {len(lat)}, pi-only {unmatched}, laptop-only {left}")
    if not lat:
        return
    def show(name, rows):
        v = [r[1] for r in rows]
        if not v:
            return
        print(f"{name:28s} n={len(v):4d}  min {min(v):6.2f}  median {statistics.median(v):6.2f}  "
              f"p90 {pct(v,90):6.2f}  p99 {pct(v,99):6.2f}  max {max(v):6.2f} ms")
    show("all EV_KEY", lat)
    show("  presses (value 1)", [r for r in lat if r[3] == 1])
    show("  releases (value 0)", [r for r in lat if r[3] == 0])
    if a.split:
        ts = a.split
        show(f"  before t={ts:.0f}", [r for r in lat if r[0] < ts])
        show(f"  after  t={ts:.0f}", [r for r in lat if r[0] >= ts])
    neg = [r for r in lat if r[1] < 0]
    if neg:
        print(f"WARNING: {len(neg)} negative latencies (offset error or mis-pairing); most negative {min(r[1] for r in neg):.2f} ms")
    print(f"offset uncertainty about +-{min_rtt/2:.2f} ms (half the minimum round trip)")
    if a.dump:
        for t, l, c, v in lat:
            print(f"{t:.6f} code={c} val={v} {l:7.3f} ms")


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sp = ap.add_subparsers(dest="cmd", required=True)
p = sp.add_parser("capture"); p.add_argument("dev"); p.add_argument("out"); p.set_defaults(f=cmd_capture)
p = sp.add_parser("echo"); p.add_argument("--port", type=int, default=46010); p.set_defaults(f=cmd_echo)
p = sp.add_parser("probe"); p.add_argument("host"); p.add_argument("out")
p.add_argument("--port", type=int, default=46010); p.add_argument("--hz", type=float, default=10); p.set_defaults(f=cmd_probe)
p = sp.add_parser("analyze"); p.add_argument("pi"); p.add_argument("laptop"); p.add_argument("probe")
p.add_argument("--split", type=float, help="unix time separating phase 1 / phase 2")
p.add_argument("--dump", action="store_true"); p.add_argument("--keep-repeat", action="store_true")
p.set_defaults(f=cmd_analyze)
args = ap.parse_args(); args.f(args)
