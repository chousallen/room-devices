#!/usr/bin/env python3
"""Measure motion evenness of a hand-held phone recording of testufo.com on the Pi's monitor.

Usage: ufo-step-analysis.py record.mp4 [band_y=435] [band_h=70]
Crops the band holding the top (full-rate) UFO row, finds the UFO by colour saturation (the page's
white guide lines and camera sway do not register), tracks its x position per recorded frame and
classifies each step: 1 = normal, 0 = repeated frame, 2/3 = double/triple step (a skipped frame).
A 59 fps phone filming a 60 Hz monitor inherently adds ~1 double step per second. Needs ffmpeg+numpy.
"""
import subprocess, sys, statistics
import numpy as np

src = sys.argv[1]
y = int(sys.argv[2]) if len(sys.argv) > 2 else 435
h = int(sys.argv[3]) if len(sys.argv) > 3 else 70
W = 1920
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'crop={W}:{h}:0:{y},format=rgb24',
                      '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
centers = []
while True:
    buf = p.stdout.read(W * h * 3)
    if len(buf) < W * h * 3: break
    f = np.frombuffer(buf, dtype=np.uint8).reshape(h, W, 3).astype(np.int16)
    sat = f.max(axis=2) - f.min(axis=2)
    col = ((sat > 70) & (f.max(axis=2) > 90)).sum(axis=0); col[:260] = 0
    on = col >= 3; runs = []; start = None
    for x in range(W):
        if on[x] and start is None: start = x
        if (not on[x] or x == W - 1) and start is not None:
            if x - start >= 10: runs.append((start + x) / 2)
            start = None
    # merge runs closer than 25 px (UFO body + dome may split)
    merged = []
    for c in runs:
        if merged and c - merged[-1] < 25: merged[-1] = (merged[-1] + c) / 2
        else: merged.append(c)
    centers.append(merged)
n = len(centers)
dx = []
for i in range(1, n):
    best = None
    for c in centers[i]:
        prev = [q for q in centers[i - 1] if -6 <= c - q <= 90]
        if prev:
            v = c - min(prev, key=lambda q: abs(c - q))
            if best is None or abs(v - 18) < abs(best - 18): best = v
    dx.append(best)
valid = [v for v in dx if v is not None]; med = statistics.median(valid)
cls = ['.' if v is None else ('0' if v < 0.35 * med else ('1' if v < 1.6 * med else ('2' if v < 2.6 * med else '3'))) for v in dx]
print(f"frames {n}, tracked {len(valid)}/{len(dx)}, median step {med:.1f} px/frame")
for k in range(0, len(cls), 100): print(f"{k:4d}: " + ' '.join(cls[k:k + 100]))
rep = cls.count('0'); dbl = cls.count('2') + cls.count('3')
print(f"repeats: {rep} ({rep / len(dx) * 100:.1f} %), double/triple steps: {dbl} ({dbl / len(dx) * 100:.1f} %) "
      f"-> a 59 fps camera alone gives ~{len(dx) // 60} double steps")
s = cls[120:]; print(f"after frame 120: repeats {s.count('0')}, doubles {s.count('2') + s.count('3')}, untracked {s.count('.')} in {len(s)} steps")
