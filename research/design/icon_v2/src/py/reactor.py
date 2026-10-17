"""Liquidity Engine app icon, concept "Reactor" (the engine). A thick polished-chrome torus seen head-on reflects a neon studio (magenta left,
cyan right, white key on top); a neon lip rings a plasma core in which a white-hot candle burns.
Analytic render: per-pixel torus normals -> reflection vector -> procedural environment.
usage: python3 reactor.py out.png [render_px] [save_px]"""
import sys
import numpy as np
from iconlib import grid, hexc, blur, bloom, finish, save, smoothstep

out = sys.argv[1] if len(sys.argv) > 1 else 'reactor.png'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
S = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
x, y = grid(N)
px = 2.0 / N
Rm, rt = 0.555, 0.205                      # torus major radius, tube radius
rho = np.sqrt(x * x + y * y) + 1e-6
ux, uy = x / rho, y / rho

img = np.zeros((N, N, 3), np.float32)
# background
img += hexc('#240850', 1.0)[None, None] * np.exp(-(rho / 0.95) ** 2)[..., None]
img += hexc('#06020f')[None, None]

# ---- environment (direction -> radiance) ----
def lobe(rx, ry, rz, d, w):
    d = np.array(d, np.float32); d /= np.linalg.norm(d)
    c = rx * d[0] + ry * d[1] + rz * d[2]
    return np.exp(-(1 - c) / w)

def env(rx, ry, rz):
    e = np.zeros(rx.shape + (3,), np.float32)
    e += lobe(rx, ry, rz, (-1, 0.15, 0.25), 0.22)[..., None] * hexc('#ff2bd6', 2.4)
    e += lobe(rx, ry, rz, (1, -0.25, 0.25), 0.22)[..., None] * hexc('#22d3ee', 2.2)
    e += lobe(rx, ry, rz, (-0.35, 1, 0.55), 0.035)[..., None] * hexc('#ffffff', 5.0)
    e += lobe(rx, ry, rz, (0.1, 1, -0.2), 0.3)[..., None] * hexc('#8b5cf6', 1.2)
    e += lobe(rx, ry, rz, (0.0, -1, 0.3), 0.25)[..., None] * hexc('#3b2bd6', 1.1)
    e += hexc('#0a0418', 1.0)
    return e

# ---- torus ----
s = (rho - Rm) / rt
m = np.abs(s) < 1
sc = np.clip(s, -0.9999, 0.9999)
nz = np.sqrt(1 - sc * sc)
nx, ny = sc * ux, sc * uy
# reflect view (0,0,1): r = 2 nz n - v
rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
F0 = hexc('#e8e4ff', 0.92)
fres = F0 + (1 - F0) * ((1 - nz) ** 5)[..., None]
tor = env(rx, ry, rz) * fres
# soft occlusion where the tube turns into the core / background
tor *= (0.55 + 0.45 * smoothstep(-1.0, -0.55, sc))[..., None]
aa = np.clip((1 - np.abs(s)) * rt / px * 0.9, 0, 1)        # 1-px antialiased silhouette
shadow = np.exp(-((rho - Rm) / (rt * 1.25)) ** 2)            # contact darkening on the backdrop
img *= (1 - 0.65 * shadow)[..., None]
img = img * (1 - aa[..., None]) + tor * aa[..., None]

# ---- core ----
rin = Rm - rt
core = (rho < rin).astype(np.float32)
cg = np.clip(rho / rin, 0, 1)
corec = (hexc('#1b0b52', 0.9) * smoothstep(0.0, 1.0, cg)[..., None] + hexc('#2f6bff', 0.55) * (1 - cg)[..., None] ** 1.5
         + hexc('#22d3ee', 0.9) * np.exp(-(rho / 0.13) ** 2)[..., None])
ca = np.clip((rin - rho) / px, 0, 1)[..., None]
img = img * (1 - ca) + corec * ca

# neon lip around the core
lip = np.exp(-((rho - rin) / 0.011) ** 2)
img += lip[..., None] * hexc('#d36bff', 2.4)
img += np.exp(-((rho - rin) / 0.05) ** 2)[..., None] * hexc('#8b5cf6', 0.35) * (rho < rin + 0.02)[..., None]

# the candle: white-hot body + wicks, magenta halo
def rrect(cx, cy, w, h, r):
    qx = np.abs(x - cx) - (w / 2 - r); qy = np.abs(y - cy) - (h / 2 - r)
    d = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    return d
dB = rrect(0, 0.01, 0.13, 0.24, 0.022)
dW = rrect(0, 0.01, 0.034, 0.5, 0.017)
dC = np.minimum(dB, dW)
cand = np.clip(0.5 - dC / px, 0, 1)
glowc = np.exp(-np.maximum(dC, 0) / 0.03)
img += glowc[..., None] * hexc('#ff4fe0', 1.3) * core[..., None]
img = img * (1 - cand[..., None]) + cand[..., None] * (hexc('#fff3fd', 3.2) - (np.clip(np.abs(x) / 0.065, 0, 1) ** 2)[..., None] * hexc('#ff6ae6', 1.6))

# outer halo on the background
img += (np.exp(-((rho - (Rm + rt)) / 0.06) ** 2) * (rho > Rm + rt))[..., None] * hexc('#7c3aed', 0.25)

img = bloom(img, threshold=1.0, sigmas=(3, 10, 36), weights=(0.45, 0.3, 0.2), strength=0.75)
im = save(finish(img, exposure=1.0, grain=0.005), out, S)
print(out, im.size)
