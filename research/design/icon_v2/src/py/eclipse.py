"""Liquidity Engine app icon, concept "Eclipse". A pure black disc with a vivid magenta-violet corona; a diamond-ring flare at the bottom of the limb
throws a horizontal cyan streak across the tile: the liquidity line touched at the low.
usage: python3 eclipse.py out.png [render_px] [save_px]"""
import sys
import numpy as np
from iconlib import grid, hexc, blur, bloom, finish, save, smoothstep, noise1d

out = sys.argv[1] if len(sys.argv) > 1 else 'eclipse.png'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
S = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
x, y = grid(N)
cx, cy, Rd = 0.0, 0.07, 0.43
dx, dy = x - cx, y - cy
r = np.sqrt(dx * dx + dy * dy)
th = np.arctan2(dy, dx)
d = r - Rd
img = np.zeros((N, N, 3), np.float32)

# background: deep violet bloom behind the disc, near-black corners
rb = np.sqrt(x * x + (y - 0.05) ** 2)
img += hexc('#2a0a5c', 1.0)[None, None] * np.exp(-(rb / 0.75) ** 2)[..., None] * 0.9
img += hexc('#0a0218')[None, None] * 0.6

# corona (outside the disc only)
o = (d > 0).astype(np.float32)
dd = np.maximum(d, 0)
streak = 1 + 0.55 * noise1d(th, 6, seed=7) * smoothstep(0.0, 0.18, dd)
fine = 1 + 0.25 * noise1d(th * 1.0 + 0.4, 7, seed=11) * smoothstep(0.0, 0.08, dd)
bias = 1 + 0.9 * np.clip(-np.sin(th), 0, 1) ** 2      # brighter toward the bottom (the sweep side)
tight = np.exp(-dd / 0.022)
mid = np.exp(-dd / 0.085) * streak * fine
wide = np.exp(-dd / 0.30) * streak
img += o[..., None] * bias[..., None] * (
    tight[..., None] * hexc('#ffc4f2', 2.2)
    + mid[..., None] * hexc('#ff2bd6', 1.25)
    + wide[..., None] * (hexc('#7c3aed', 0.55) * (1 - smoothstep(0.1, 0.6, dd))[..., None] + hexc('#2f5bff', 0.35) * smoothstep(0.1, 0.6, dd)[..., None]))
# chromosphere: thin hot rim right on the limb
img += (np.exp(-(d / 0.004) ** 2) * (d > -0.003))[..., None] * hexc('#ffe3fb', 3.0) * bias[..., None] ** 0.5

# the disc: black, faint violet limb so it reads as a sphere
inside = (d <= 0).astype(np.float32)
img = img * (1 - inside[..., None]) + inside[..., None] * (hexc('#120430', 0.25) * smoothstep(-0.25, 0.0, d)[..., None] ** 3)

# diamond ring + anamorphic streak (= the liquidity line) at the bottom of the limb
px, py = cx, cy - Rd - 0.004
qx, qy = x - px, y - py
D2 = qx * qx + qy * qy
img += np.exp(-D2 / 0.00025)[..., None] * hexc('#ffffff', 8.0)
img += np.exp(-D2 / 0.003)[..., None] * hexc('#c9fbff', 2.2)
img += np.exp(-D2 / 0.03)[..., None] * hexc('#22d3ee', 0.7)
img += (np.exp(-(qy / 0.0055) ** 2) * np.exp(-np.abs(qx) / 0.9))[..., None] * hexc('#e8fdff', 2.6)
img += (np.exp(-(qy / 0.02) ** 2) * np.exp(-np.abs(qx) / 0.55))[..., None] * hexc('#22d3ee', 0.8)
img += (np.exp(-(qx / 0.0045) ** 2) * np.exp(-np.abs(qy) / 0.12))[..., None] * hexc('#ffffff', 1.4)

img = bloom(img, threshold=0.9, sigmas=(3, 12, 40), weights=(0.5, 0.3, 0.2), strength=0.8)
im = save(finish(img, exposure=1.0, grain=0.006), out, S)
print(out, im.size)
