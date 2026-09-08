#!/usr/bin/env python3
"""Hold-time analysis of a slow-motion (120/240 fps) phone recording of testufo.com on the monitor.

Usage: ufo-slowmo-analysis.py record.mp4 band_y band_h [left_exclude_px]
Tracks the UFO x position in every camera frame (colour-saturation detector) and measures how many
camera frames each monitor frame is held. At 240 fps and 60 Hz a smooth display gives holds of 4
(3 or 5 at the camera/monitor beat); a repeated monitor frame gives 8, a skipped frame shows as a
position jump of two steps. Needs ffmpeg + numpy.
"""
import subprocess, sys, statistics, collections
import numpy as np
src, y, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
left = int(sys.argv[4]) if len(sys.argv) > 4 else 0
W = int(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width',
                                 '-of', 'csv=p=0', src]).split()[0])
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', f'crop={W}:{h}:0:{y},format=rgb24', '-f', 'rawvideo', '-'],
                     stdout=subprocess.PIPE)
pos = []  # per camera frame: list of blob centres
while True:
    buf = p.stdout.read(W * h * 3)
    if len(buf) < W * h * 3: break
    f = np.frombuffer(buf, dtype=np.uint8).reshape(h, W, 3).astype(np.int16)
    m = ((f.max(axis=2) - f.min(axis=2)) > 60) & (f.max(axis=2) > 90)
    col = m.sum(axis=0); col[:left] = 0
    xs = np.where(col >= 2)[0]; runs = []
    if len(xs):
        s = xs[0]; q = xs[0]
        for x in xs[1:]:
            if x - q > 12: runs.append((s, q)); s = x
            q = x
        runs.append((s, q))
    pos.append([(a + b) / 2 for a, b in runs if b - a >= 8])
n = len(pos)
# follow one blob: start with the leftmost blob in frame 0 that has a continuation
track = []; cur = None
for i in range(n):
    if cur is None:
        cands = pos[i]
        if cands: cur = min(cands)
        track.append(cur); continue
    nxt = [c for c in pos[i] if -4 <= c - cur <= 40]
    if nxt: cur = min(nxt, key=lambda c: abs(c - cur)); track.append(cur)
    else: track.append(None); cur = None
# hold lengths: consecutive frames where position changes by < 5 px
holds = []; jumps = []; run = 1; last = None
for i in range(1, n):
    a, b = track[i - 1], track[i]
    if a is None or b is None: continue
    d = b - a
    if abs(d) < 5: run += 1
    else:
        holds.append(run); run = 1; jumps.append(d)
steps = [j for j in jumps if j > 0]; med = statistics.median(steps) if steps else 0
print(f"camera frames {n}, tracked {sum(t is not None for t in track)}, monitor-frame changes seen {len(jumps)}, median step {med:.1f} px")
print("hold length (camera frames per monitor frame) -> count:", sorted(collections.Counter(holds).items()))
big = sum(1 for j in steps if j > 1.6 * med); print(f"steps > 1.6x median (skipped monitor frame): {big} of {len(steps)}")
print("hold sequence:", ' '.join(str(x) for x in holds[:200]))
