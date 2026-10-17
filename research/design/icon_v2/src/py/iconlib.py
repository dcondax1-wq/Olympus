"""Tiny numpy toolkit for procedural icon renders (linear-light HDR -> filmic tone map -> sRGB -> LANCZOS).

Everything works on float32 arrays shaped (H, W, 3) in linear light. Coordinates: x right, y up, both in [-1, 1].
"""
import numpy as np
from PIL import Image


def grid(n):
    c = (np.arange(n, dtype=np.float32) + 0.5) / n * 2 - 1
    x, y = np.meshgrid(c, -c)
    return x, y


def hexc(h, k=1.0):
    """'#rrggbb' -> linear RGB float32 (sRGB decoded) times k."""
    h = h.lstrip('#')
    s = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)
    lin = np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)
    return (lin * k).astype(np.float32)


def blur(img, sigma):
    """Gaussian blur (sigma in pixels) via FFT with zero padding (no wrap-around)."""
    if sigma <= 0:
        return img
    pad = int(3 * sigma) + 2
    a = img if img.ndim == 3 else img[..., None]
    H, W, C = a.shape
    P = np.zeros((H + 2 * pad, W + 2 * pad, C), np.float32)
    P[pad:pad + H, pad:pad + W] = a
    fy = np.fft.fftfreq(P.shape[0])[:, None]
    fx = np.fft.rfftfreq(P.shape[1])[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2)).astype(np.float32)
    out = np.empty_like(P)
    for c in range(C):
        out[..., c] = np.fft.irfft2(np.fft.rfft2(P[..., c]) * g, s=P.shape[:2])
    out = out[pad:pad + H, pad:pad + W]
    return out if img.ndim == 3 else out[..., 0]


def bloom(img, threshold=1.0, sigmas=(4, 16, 48), weights=(0.6, 0.35, 0.2), strength=1.0):
    """Add glow from the parts brighter than threshold (sigmas are relative to a 1024 canvas)."""
    n = img.shape[0] / 1024
    lum = img.max(axis=2, keepdims=True)
    hi = img * np.clip((lum - threshold) / np.maximum(lum, 1e-6), 0, None)
    acc = np.zeros_like(img)
    for s, w in zip(sigmas, weights):
        acc += blur(hi, s * n) * w
    return img + acc * strength


def tonemap(img, exposure=1.0):
    """ACES fit (Narkowicz), per channel: saturated neon stays saturated until it blows out to white."""
    x = img * exposure
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def finish(img, exposure=1.0, grain=0.0, seed=1):
    out = to_srgb(tonemap(img, exposure))
    if grain:
        rng = np.random.default_rng(seed)
        out = out + (rng.random(out.shape[:2], dtype=np.float32)[..., None] - 0.5) * grain
    return np.clip(out, 0, 1)


def save(srgb, path, size=None):
    im = Image.fromarray((np.clip(srgb, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')
    if size and im.size[0] != size:
        im = im.resize((size, size), Image.LANCZOS)
    im.save(path)
    return im


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(t, stops):
    """t (H,W) in [0,1] -> colour from [(pos, rgb), ...] stops (linear interpolation)."""
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), np.float32)
    for (p0, c0), (p1, c1) in zip(stops[:-1], stops[1:]):
        m = (t >= p0) & (t <= p1)
        f = ((t - p0) / max(p1 - p0, 1e-6))[..., None]
        out = np.where(m[..., None], c0 * (1 - f) + c1 * f, out)
    return out


def noise1d(theta, octaves=5, seed=3):
    """Smooth periodic noise over an angle, in [-1, 1]."""
    rng = np.random.default_rng(seed)
    v = np.zeros_like(theta)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        f = 3 * 2 ** o + rng.integers(0, 3)
        v += amp * np.sin(f * theta + rng.random() * 6.283)
        tot += amp
        amp *= 0.55
    return v / tot
