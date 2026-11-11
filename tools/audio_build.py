"""OLYMPUS recorded sound layer: CC0 recordings -> small phone files (2026-11-11, docs/SOUND_API.md "Recorded layer").

Every source is CC0 (public domain), checked on its own page; each one has a row in docs/ASSETS_LICENSES.md (author + URL).
  python tools/audio_build.py --fetch --src <dir>   download the sources (opengameart.org pages + VCSL on GitHub) into <dir>/<slug>/
  python tools/audio_build.py --src <dir>           build tools/web_public/assets/audio/*.ogg + *.m4a + manifest.json, write the
                                                    manifest into olympus/sfx.js (between the AUDIO markers) and print the measurements
  python tools/audio_build.py --measure             measure the committed files again (no sources needed)
What it does to each sound: trim to the hit (onset - 5 ms), high-pass 30 Hz, short fades, peak -3 dBFS (one-shots), equal attack level
(harp notes, so the composer plays them evenly), beds: an equal-power crossfade folds the tail into the head (a seamless loop), loudness
-16 LUFS (BS.1770 gated) and a peak limiter to -3 dBFS. One-shots of a family are packed into one "sprite" file (one request, one decode),
segments 0.12 s apart. Encoded twice: Ogg Opus (Chrome, Firefox, Android, new Safari) and AAC in .m4a (every iPhone). Then both files are
decoded again with ffmpeg and measured: peak, loudness, the seam of every loop (sample jump vs the file's own 99.9th percentile step,
level step across the seam), spectral centroid and 85 % roll-off, size. Needs ffmpeg + numpy (+ scipy for the filters).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import zipfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools/web_public/assets/audio")
SFX = os.path.join(ROOT, "tools/web_public/olympus/sfx.js")
SR = 48000
OGA = "https://opengameart.org/content/"
OGAF = "https://opengameart.org/sites/default/files/"
VCSL = "https://raw.githubusercontent.com/sgossner/VCSL/master/"

# ------------------------------------------------------------------------------------------------ the sources (all CC0; licence read on each page)
SOURCES = {
    "fantozzis-footsteps-grasssand-stone": ("Fantozzi (submitted by qubodup)", ["Fantozzi-footsteps.7z"]),
    "different-steps-on-wood-stone-leaves-gravel-and-mud": ("TinyWorlds", ["%5Bkdd%5DDifferentSteps_0.zip"]),
    "51-ui-sound-effects-buttons-switches-and-clicks": ("Kenney", ["UI_SFX_Set.zip"]),
    "10-book-page-flips": ("StarNinjas", ["book_flips_-_starninjas.zip"]),
    "opening-and-closing-a-map-sounds": ("Spring Spring", ["snd_use_map.wav", "snd_close_map.wav"]),
    "rpg-sound-pack": ("artisticdude", ["rpg_sound_pack.zip"]),
    "fantasy-accessory-sfx-library": ("Vehicle (Jan Schupke)", ["accessory.zip"]),
    "100-cc0-metal-and-wood-sfx": ("rubberduck", ["100-CC0-wood-metal-SFX.zip"]),
    "blacksmiths-hammer": ("VishwaJai", ["blacksmithhammer.wav"]),
    "sack-of-gold": ("Amarikah", ["gold_sack.wav"]),
    "crowd-shoutingspeaking-ambience": ("StarNinjas", ["crowd_shouting_0.ogg"]),
    "applause-in-a-large-hall-or-church": ("eXpl0it3r", ["applause-clapping-church-crowd-immersive.wav"]),
    "fireplace-sound-loop": ("PagDev", ["fire.wav"]),
    "catching-fire": ("themightyglider", ["flame_0.ogg"]),
    "windy-ambient-noise": ("Some Weirdo", ["windy_ambiance_0.ogg"]),
    "park-ambiences": ("Thimras", ["park_ambience_wind.wav", "park_ambience_river.wav"]),
    "sea-and-river-wave-sounds": ("RandomMind", ["Vistula.zip"]),
    "beach-ocean-waves": ("jasinski (submitted by qubodup)", ["wave_0%d_cc0-18363__jasinski__alkaibeach.flac" % i for i in (1, 2, 3, 4)]),
    "solo-seagull-sound-effects": ("Rango Mango", ["Seagull%20Ambient%20" + str(i) + ".wav" for i in (2, 3, 4, 6, 7)]),
    "bird-chirping-sounds": ("syncopika", ["birdchirping071414.wav"]),
    "amb-morning-sounds-perfect-loop": ("Kresiek The Furry", ["amb_morning.wav"]),
    "crickets-ambient-noise-loopable": ("Wolfgang_", ["crickets_1.mp3"]),
    "door-open-door-close-set": ("qubodup", ["qubodup-DoorSet.7z"]),
    "pencil-sounds": ("AntumDeluge", ["pencil.zip"]),
    "20-rustles-dry-leaves": ("qubodup", ["qubodup-rustle.7z"]),
    "vcsl": ("Versilian Studios (VCSL, Versilian Community Sample Library)", []),
}
V = "vcsl/"
SI = V + "Idiophones/Struck Idiophones/"
HARP = V + "Chordophones/Composite Chordophones/Folk Harp/EWHarp_Normal_%s_v2_RR1.wav"
HARP_NOTES = {50: "D2", 52: "E2", 54: "F#2", 56: "G#2", 58: "A#2", 60: "C3", 62: "D3", 64: "E3", 66: "F#3", 68: "G#3", 70: "A#3", 72: "C4",
              74: "D4", 76: "E4", 78: "F#4", 80: "G#4", 82: "A#4", 84: "C5", 86: "D5"}      # VCSL names a note one octave low (D3 = MIDI 62, measured)
FX = "rpg-sound-pack/RPG Sound Pack/"
ACC = "fantasy-accessory-sfx-library/sfx/"
RD = "100-cc0-metal-and-wood-sfx/"
UI51 = "51-ui-sound-effects-buttons-switches-and-clicks/"
FZ = "fantozzis-footsteps-grasssand-stone/Fantozzi-footsteps/flac/Fantozzi-"
TW = "different-steps-on-wood-stone-leaves-gravel-and-mud/"


def seg(path, **o):
    o["p"] = path
    return o


# sprites: family -> {bank: [segments]}. A segment: p (source path), ss/t (window), max (seconds kept), onset (cut the n-th hit), rate (pitch).
SPRITES = {
    "ui": {
        "tap": [seg(SI + "Woodblock/wood_click_pp_rr%d.wav" % i, max=0.22) for i in (1, 2, 3)],
        "tick": [seg(UI51 + "click1.wav", max=0.06), seg(UI51 + "click2.wav", max=0.06)],
        "toggle": [seg(UI51 + "switch%d.wav" % i, max=0.2) for i in (11, 17, 19)],
        "paper": [seg("opening-and-closing-a-map-sounds/snd_use_map.wav", max=0.75), seg("opening-and-closing-a-map-sounds/snd_close_map.wav", max=0.7),
                  seg("10-book-page-flips/book_flip.4.ogg", max=0.55), seg("10-book-page-flips/book_flip.8.ogg", max=0.5)],
        "chime": [seg(SI + "Hand Chimes/sus_%s_r01_main.wav" % n, max=2.2, midi=m) for n, m in (("D5", 74), ("E5", 76), ("F#5", 78), ("A4", 69), ("G#5", 80))],
        "shimmer": [seg(SI + "Finger Cymbals/Fing_Cymb.wav", max=1.8)],
        "bell": [seg(SI + "Hand Bells, Nepalese/HB_1.wav", max=1.4), seg(SI + "Hand Bells, Nepalese/HB_2.wav", max=1.1)],
        "coin": [seg(FX + "inventory/coin.wav", max=0.5), seg(FX + "inventory/coin3.wav", max=0.3), seg(ACC + "coinflip-01.wav", max=0.35),
                 seg(ACC + "coinflip-02.wav", max=0.25), seg(ACC + "coinflip-03.wav", max=0.4)],
    },
    "harp": {"harp": [seg(HARP % n, max=1.9 if m < 76 else 1.5, midi=m, harp=True) for m, n in sorted(HARP_NOTES.items()) if m >= 62]},
    "harp-lo": {"harplo": [seg(HARP % n, max=2.6, midi=m, harp=True) for m, n in sorted(HARP_NOTES.items()) if m < 62]},
    "steps": {
        "step-stone": [seg(FZ + "Stone%s%d.flac" % (s, i), max=0.3) for s in "LR" for i in (1, 2, 3)] + [seg(TW + "stone01.ogg", max=0.28)],
        "step-sand": [seg(FZ + "Sand%s%d.flac" % (s, i), max=0.32) for s in "LR" for i in (1, 2, 3)],
        "step-wood": [seg(TW + "wood0%d.ogg" % i, max=0.24) for i in (1, 2, 3)],
        "step-leaves": [seg(TW + "leaves0%d.ogg" % i, max=0.38) for i in (1, 2)],
    },
    "forge": {
        "anvil": [seg(SI + "Anvil/Anvil_Hit%d_v%d_rr1_Mid.wav" % (h, v), max=1.3) for h in (1, 2, 3) for v in (2, 3)],
        "smith": [seg("blacksmiths-hammer/blacksmithhammer.wav", max=0.5)],
        "tool": [seg(RD + "metal_hit_0%d.ogg" % i, max=0.3) for i in (1, 2, 3)],
    },
    "scribe": {
        "quill": [seg("pencil-sounds/flac/pencil_write.flac", ss=0.0, t=0.62), seg("pencil-sounds/flac/pencil_write.flac", ss=0.62, t=0.75)],
        "page": [seg("10-book-page-flips/book_flip.%d.ogg" % i, max=0.9) for i in (2, 3, 5, 6)],
        "scroll": [seg("opening-and-closing-a-map-sounds/snd_use_map.wav", max=1.4)],
    },
    "house": {
        "door": [seg("door-open-door-close-set/qubodup-DoorSet/flac/qubodup-Door%s0%d.flac" % (k, i), max=0.95) for k in ("Open", "Close") for i in (1, 2, 3)],
        "crate": [seg(RD + "wood_slam_0%d.ogg" % i, max=0.45) for i in (1, 2, 3)] + [seg(RD + "wood_falling_01.ogg", max=0.6)],
        "whoosh": [seg("catching-fire/flame_0.ogg", max=0.45)],
    },
    "gear": {
        "keys": [seg(ACC + "keys-rattle-0%d.wav" % i, max=0.8) for i in (2, 3)] + [seg(RD + "keys_0%d.ogg" % i, max=0.5) for i in (1, 2, 5)],
        "metal": [seg(FX + "inventory/chainmail1.wav", max=0.5), seg(FX + "inventory/chainmail2.wav", max=0.6), seg(FX + "inventory/armor-light.wav", max=0.45)],
        "beads": [seg(FX + "inventory/beads.wav", max=0.45)],
        "cloth": [seg(FX + "inventory/cloth.wav", max=0.42), seg(FX + "inventory/cloth-heavy.wav", max=0.38)],
        "pouch": [seg(ACC + "coins-shake-0%d.wav" % i, max=0.6) for i in (6, 7)],
        "jingle": [seg(SI + "Sleigh Bells/Sleighbells_Hit_rr%d_Mid.wav" % i, max=0.9) for i in (1, 2)],
        "rustle": [seg("20-rustles-dry-leaves/rustle/rustle%02d.flac" % i, max=0.7) for i in (9, 10, 12)],
    },
    "coins": {
        "pour": [seg("sack-of-gold/gold_sack.wav", max=1.75), seg(ACC + "coin-spin-fall-01.wav", max=1.4)],
        "count": [seg(ACC + "coins-shake-0%d.wav" % i, max=0.9) for i in (2, 4)] + [seg(FX + "inventory/coin2.wav", max=0.7)],
    },
    "nature": {
        "gull": [seg("solo-seagull-sound-effects/Seagull Ambient %d.wav" % i, max=1.3) for i in (2, 3, 4, 6, 7)],
        "wave": [seg("beach-ocean-waves/wave_0%d_cc0-18363__jasinski__alkaibeach.flac" % i, max=3.4) for i in (1, 2, 4)],
        "chirp": [seg("bird-chirping-sounds/birdchirping071414.wav", onset=k, max=0.55) for k in (0, 1, 2, 3)],
    },
    "arena": {
        "clap": [seg(SI + "Claps/Clap_rr%d.wav" % i, max=0.3) for i in (1, 2, 3, 4)],
        "drum": [seg(V + "Membranophones/Struck Membranophones/Frame Drum/HDrumL_Hit_v%d_rr%d_Sum.wav" % (v, r), max=0.9) for v in (2, 3) for r in (1, 2)],
        "cheer": [seg("applause-in-a-large-hall-or-church/applause-clapping-church-crowd-immersive.wav", ss=6, t=2.6),
                  seg("crowd-shoutingspeaking-ambience/crowd_shouting_0.ogg", ss=8, t=2.4)],
    },
    "bells": {
        "camel": [seg(SI + "Hand Bells, Nepalese/HB_%d.wav" % i, max=1.2) for i in (1, 2, 3)] + [seg(SI + "Sleigh Bells/sleighbell2_hit_2.wav", max=0.9)],
        "windchime": [seg(SI + "Mark Trees/Legacy/windchimes_random.wav", ss=1.0, t=5.5), seg(SI + "Mark Trees/Legacy/windchimes_random.wav", ss=9.0, t=5.0)],
    },
}
# loops (beds): name -> source, window to search, length, channels
LOOPS = {
    "crowd": dict(p="crowd-shoutingspeaking-ambience/crowd_shouting_0.ogg", a=0.5, b=26.5, L=20.0),
    "applause": dict(p="applause-in-a-large-hall-or-church/applause-clapping-church-crowd-immersive.wav", a=1.0, b=32.0, L=14.0),
    "fire": dict(p="fireplace-sound-loop/fire.wav", a=0.5, b=28.5, L=18.0),
    "wind": dict(p="windy-ambient-noise/windy_ambiance_0.ogg", a=30.0, b=90.0, L=20.0),
    "gusts": dict(p="park-ambiences/park_ambience_wind.wav", a=100.0, b=160.0, L=22.0, hp=160.0),                  # an open-field recording: the mic's wind rumble goes
    "sea": dict(p="sea-and-river-wave-sounds/Vistula.mp3", a=2400.0, b=2480.0, L=22.0),
    "crickets": dict(p="crickets-ambient-noise-loopable/crickets_1.mp3", a=0.0, b=11.4, L=10.0),
    "birds": dict(p="amb-morning-sounds-perfect-loop/amb_morning.wav", a=0.0, b=60.0, L=22.0),
    "brook": dict(p="park-ambiences/park_ambience_river.wav", a=20.0, b=80.0, L=12.0),
}
GAP = 0.12
FMT = {"ogg": {1: ["-c:a", "libopus", "-b:a", "32k", "-vbr", "on", "-application", "audio"], 2: ["-c:a", "libopus", "-b:a", "48k", "-vbr", "on", "-application", "audio"]},
       "m4a": {1: ["-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart"], 2: ["-c:a", "aac", "-b:a", "72k", "-movflags", "+faststart"]}}
BUDGET_MB = 8.0


# ------------------------------------------------------------------------------------------------ audio helpers
def load(path, ch=1, ss=None, t=None):
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", str(ss)] if ss is not None else []) + (["-t", str(t)] if t is not None else [])
    cmd += ["-i", path, "-f", "f32le", "-ac", str(ch), "-ar", str(SR), "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise SystemExit("ffmpeg could not read %s: %s" % (path, r.stderr.decode()[:300]))
    x = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    return x.reshape(-1, ch) if ch > 1 else x


def db(v):
    return 20 * np.log10(max(float(v), 1e-12))


def biquad(x, b, a):
    from scipy.signal import lfilter
    return lfilter(b, a, x, axis=0)


def highpass(x, f=30.0):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, f, "highpass", fs=SR, output="sos"), x, axis=0)


def lufs(x):
    """integrated loudness, ITU-R BS.1770-4 (K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU relative gates)"""
    x = x if x.ndim == 2 else x[:, None]
    y = biquad(x, [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585])
    y = biquad(y, [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621])
    n, hop = int(0.4 * SR), int(0.1 * SR)
    if len(y) < n:
        ms = [float((y ** 2).mean(axis=0).sum())]
    else:
        ms = [float((y[i:i + n] ** 2).mean(axis=0).sum()) for i in range(0, len(y) - n + 1, hop)]
    ms = np.array(ms)
    L = -0.691 + 10 * np.log10(np.maximum(ms, 1e-20))
    g = ms[L > -70]
    if not len(g):
        return -70.0
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = ms[(L > -70) & (L > rel)]
    return float(-0.691 + 10 * np.log10(g2.mean())) if len(g2) else -70.0


def centroid(x):
    m = x.mean(axis=1) if x.ndim == 2 else x
    n = 4096
    if len(m) < n:
        m = np.pad(m, (0, n - len(m)))
    S = np.zeros(n // 2 + 1)
    for i in range(0, len(m) - n + 1, n // 2):
        S += np.abs(np.fft.rfft(m[i:i + n] * np.hanning(n))) ** 2
    f = np.fft.rfftfreq(n, 1 / SR)
    c = float((S * f).sum() / max(S.sum(), 1e-20))
    cs = np.cumsum(S) / max(S.sum(), 1e-20)
    return round(c), round(float(f[min(len(f) - 1, np.searchsorted(cs, 0.85))]))


def fade(x, a=0.002, b=0.03):
    x = x.copy()
    na, nb = max(1, int(a * SR)), max(1, min(len(x) // 2, int(b * SR)))
    x[:na] *= np.linspace(0, 1, na)[:, None] if x.ndim == 2 else np.linspace(0, 1, na)
    w = np.cos(np.linspace(0, np.pi / 2, nb)) ** 2
    x[-nb:] *= w[:, None] if x.ndim == 2 else w
    return x


def onsets(x, thr_db=-24.0, min_gap=0.18):
    a = np.abs(x)
    W = 240
    env = np.array([a[i:i + W].max() for i in range(0, len(a) - W, W)])
    pk = env.max()
    on, last = [], -1e9
    below = True
    for i, e in enumerate(env):
        if below and e > pk * 10 ** (thr_db / 20) and (i - last) * W / SR > min_gap:
            on.append(i * W)
            last = i
            below = False
        elif e < pk * 10 ** ((thr_db - 10) / 20):
            below = True
    return on


def shot(src, s):
    """one variation: cut, clean, fade; peak -3 dBFS (the harp: equal attack loudness, scaled later as a bank)"""
    x = load(os.path.join(src, s["p"]), 1, s.get("ss"), s.get("t"))
    x = highpass(x, 40.0 if s.get("harp") else 30.0)
    a = np.abs(x)
    pk = a.max()
    if pk <= 0:
        raise SystemExit("silent source " + s["p"])
    if "onset" in s:
        on = onsets(x)
        start = on[min(s["onset"], len(on) - 1)]
    else:
        start = int(np.argmax(a > pk * 0.05))
    start = max(0, start - int(0.005 * SR))
    x = x[start:]
    if s.get("max"):
        x = x[:int(s["max"] * SR)]
    a = np.abs(x)
    W = 480
    env = np.array([a[i:i + W].max() for i in range(0, max(1, len(a) - W), W)])
    keep = np.nonzero(env > a.max() * 10 ** (-52 / 20))[0]
    if len(keep):
        x = x[:min(len(x), (keep[-1] + 2) * W)]
    x = fade(x, 0.002, min(0.25, max(0.02, len(x) / SR * 0.3)))
    if s.get("harp"):
        att = x[:int(0.25 * SR)]
        return x / max(np.sqrt((att ** 2).mean()), 1e-9) * 0.1
    return x / np.abs(x).max() * 10 ** (-3 / 20)


def loud(x):
    """the loudest 50 ms (RMS, dB): how loud a short hit sounds"""
    n = int(0.05 * SR)
    if len(x) <= n:
        return db(np.sqrt((x ** 2).mean()))
    c = np.cumsum(np.concatenate([[0.0], x ** 2]))
    return db(np.sqrt(((c[n:] - c[:-n]) / n).max()))


def limit(x, ceil_db=-3.0):
    """a lookahead peak limiter (5 ms attack, 80 ms release) so no sample passes the ceiling"""
    c = 10 ** (ceil_db / 20)
    a = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    need = np.minimum(1.0, c / np.maximum(a, 1e-12))
    la = int(0.005 * SR)
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(need, size=2 * la + 1)
    rel = np.exp(-1 / (0.08 * SR))
    out = np.empty_like(g)
    cur = 1.0
    for i, v in enumerate(g):
        cur = v if v < cur else v + (cur - v) * rel
        out[i] = cur
    y = x * (out[:, None] if x.ndim == 2 else out)
    return np.clip(y, -c, c)


def seam(y):
    """loop seam: |y[0] - y[-1]| against the file's own 99.9th percentile sample step, and the level step across the seam (20 ms either side)"""
    m = y if y.ndim == 2 else y[:, None]
    d = np.abs(np.diff(m, axis=0))
    p999 = np.percentile(d, 99.9, axis=0)
    jump = np.abs(m[0] - m[-1])
    n = int(0.02 * SR)
    r1, r0 = np.sqrt((m[-n:] ** 2).mean()), np.sqrt((m[:n] ** 2).mean())
    return round(float((jump / np.maximum(p999, 1e-12)).max()), 3), round(abs(db(r1) - db(r0)), 2)


def loop(src, spec):
    """the best window (the two ends sound alike), its tail crossfaded into its head (equal power, 1.2 s): a seamless loop at -16 LUFS"""
    full = load(os.path.join(src, spec["p"]), 2, spec["a"], spec["b"] - spec["a"])
    full = highpass(full, spec.get("hp", 30.0))
    L, X = int(spec["L"] * SR), int(1.2 * SR)
    best, bs = None, None
    n = int(0.5 * SR)
    for s in range(0, max(1, len(full) - L - X), int(0.25 * SR)):
        h, t = full[s + X:s + X + n], full[s + L:s + L + n]
        if len(t) < n:
            break
        sc = abs(db(np.sqrt((h ** 2).mean())) - db(np.sqrt((t ** 2).mean()))) + 0.2 * abs(db(np.abs(full[s:s + L + X]).max()))
        if bs is None or sc < bs:
            best, bs = s, sc
    s = best or 0
    seg_ = full[s:s + L + X].copy()
    y = seg_[:L].copy()
    w = np.linspace(0, 1, X)[:, None]
    y[:X] = seg_[:X] * np.sqrt(w) + seg_[L:L + X] * np.sqrt(1 - w)
    y = y * 10 ** ((-16.0 - lufs(y)) / 20)
    y = limit(y, -3.2)
    return y, round(spec["a"] + s / SR, 2)


# ------------------------------------------------------------------------------------------------ encode + measure
def encode(x, stem):
    ch = 2 if x.ndim == 2 else 1
    raw = x.astype(np.float32).tobytes()
    out = {}
    for ext, args in FMT.items():
        p = os.path.join(OUT, stem + "." + ext)
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", str(ch), "-i", "-", "-ar", str(SR)] + args[ch] + ["-map_metadata", "-1", p],
                           input=raw, capture_output=True)
        if r.returncode:
            raise SystemExit("encode failed %s: %s" % (p, r.stderr.decode()[:300]))
        out[ext] = p
    return out


def encode_safe(x, stem, ceil=-3.0):
    """encode; the codecs overshoot on sharp transients, so decode both files and lower the input until every decoded peak is <= ceil"""
    ch = 2 if x.ndim == 2 else 1
    for _ in range(6):
        encode(x, stem)
        pk = max(db(np.abs(load(os.path.join(OUT, stem + "." + e), ch)).max()) for e in FMT)
        if pk <= ceil:
            return x
        x = x * 10 ** ((ceil - 0.25 - pk) / 20)
    return x


def measure(stem, ch, kind, segs=None, nominal=None):
    row = {"file": stem, "ch": ch, "kind": kind}
    for ext in FMT:
        p = os.path.join(OUT, stem + "." + ext)
        y = load(p, ch)
        if nominal:
            row[ext + "_pad_ms"] = round((len(y) / SR - nominal) * 1000, 1)
            if kind == "loop":
                y = y[:int(round(nominal * SR))]                       # the engine loops the nominal length (AAC pads its last frame)
        row[ext + "_kb"] = round(os.path.getsize(p) / 1024, 1)
        row[ext + "_s"] = round(len(y) / SR, 3)
        row[ext + "_peak"] = round(db(np.abs(y).max()), 2)
        if ext == "ogg":
            row["lufs"] = round(lufs(y), 1)
            row["centroid"], row["rolloff85"] = centroid(y)
            if kind == "loop":
                row["seam_jump"], row["seam_step_db"] = seam(y)
            if segs:
                pk = [round(db(np.abs(y[int(a * SR):int((a + d) * SR)]).max()), 1) for a, d in [s_[:2] for s_ in segs]]
                row["seg_peaks"] = [min(pk), max(pk)]
        elif kind == "loop":
            row["m4a_seam_jump"], row["m4a_seam_step_db"] = seam(y)
    return row


def build(src):
    os.makedirs(OUT, exist_ok=True)
    man = {"v": 1, "built": "2026-11-11", "fmt": ["ogg", "m4a"], "files": {}, "banks": {}, "loops": {}}
    rows = []
    for fam, banks in SPRITES.items():
        parts, t = [np.zeros(int(GAP * SR))], GAP
        harp = []
        for bank, segs in banks.items():
            lst = []
            xs = [shot(src, s) for s in segs]
            if len(xs) > 1 and not segs[0].get("harp"):            # a family plays evenly: every variation at the bank's median loudness (+/- 6 dB at most)
                ld = [loud(x) for x in xs]
                med = float(np.median(ld))
                xs = [x * 10 ** (float(np.clip(med - l, -6, 6)) / 20) for x, l in zip(xs, ld)]
                pk = max(np.abs(x).max() for x in xs)
                xs = [x / pk * 10 ** (-3 / 20) for x in xs]
            for s, x in zip(segs, xs):
                if s.get("harp"):
                    harp.append(x)
                parts.append(x)
                ent = [round(t, 4), round(len(x) / SR, 4)] + ([s["midi"]] if "midi" in s else [])
                lst.append(ent)
                t += len(x) / SR + GAP
                parts.append(np.zeros(int(GAP * SR)))
            man["banks"][bank] = [fam, lst]
        y = np.concatenate(parts)
        y = y / np.abs(y).max() * 10 ** (-3.2 / 20)                      # the harp family: one gain for all its notes
        encode_safe(y, fam)
        man["files"][fam] = {"ch": 1}
        rows.append(measure(fam, 1, "sprite", [e for b in banks for e in man["banks"][b][1]], nominal=len(y) / SR))
    for name, spec in LOOPS.items():
        y, at = loop(src, spec)
        stem = "loop-" + name
        encode_safe(y, stem)
        man["files"][stem] = {"ch": 2}
        man["loops"][name] = [stem, round(len(y) / SR, 3)]
        r = measure(stem, 2, "loop", nominal=len(y) / SR)
        r["from_s"] = at
        rows.append(r)
    for r in rows:
        f = man["files"][r["file"]]
        f["kb"] = {"ogg": r["ogg_kb"], "m4a": r["m4a_kb"]}
        f["dur"] = r["ogg_s"]
    man["measure"] = rows
    man["total_kb"] = round(sum(r["ogg_kb"] + r["m4a_kb"] for r in rows), 1)
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    embed(man)
    licences()
    report(man)


def compact(man):
    """the part sfx.js needs: files (channels, kB), banks (family + segments), loops (file + length)"""
    return {"v": man["v"], "files": {k: [v["ch"], v["kb"]["ogg"], v["kb"]["m4a"]] for k, v in man["files"].items()},
            "banks": man["banks"], "loops": man["loops"]}


def embed(man):
    js = open(SFX, encoding="utf-8").read()
    body = json.dumps(compact(man), separators=(",", ":"))
    new = re.sub(r"/\*AUDIO\*/.*?/\*/AUDIO\*/", lambda m: "/*AUDIO*/" + body + "/*/AUDIO*/", js, flags=re.S)
    if new == js and "/*AUDIO*/" not in js:
        raise SystemExit("sfx.js has no /*AUDIO*/ ... /*/AUDIO*/ marker")
    with open(SFX, "w", encoding="utf-8") as fh:
        fh.write(new)


def report(man):
    print("| file | ch | ogg kB | m4a kB | length s | peak dBFS (ogg / m4a) | LUFS | centroid Hz | roll-off 85 % Hz | loop seam (jump / level dB) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in man["measure"]:
        sm = ("%s / %s (m4a %s / %s)" % (r["seam_jump"], r["seam_step_db"], r["m4a_seam_jump"], r["m4a_seam_step_db"])) if r["kind"] == "loop" else "-"
        print("| %s | %d | %.1f | %.1f | %.2f | %.1f / %.1f | %.1f | %d | %d | %s |" % (r["file"], r["ch"], r["ogg_kb"], r["m4a_kb"], r["ogg_s"], r["ogg_peak"], r["m4a_peak"],
                                                                                     r["lufs"], r["centroid"], r["rolloff85"], sm))
    ogg = sum(r["ogg_kb"] for r in man["measure"])
    m4a = sum(r["m4a_kb"] for r in man["measure"])
    print("\ntotal: ogg %.0f kB + m4a %.0f kB = %.2f MB (budget %.0f MB; a phone downloads one format)" % (ogg, m4a, (ogg + m4a) / 1024, BUDGET_MB))


LIC = os.path.join(ROOT, "docs/ASSETS_LICENSES.md")


def licences():
    """the audio rows of docs/ASSETS_LICENSES.md (between the AUDIO markers): every source, its author, page, licence and the files it is in"""
    used = {}
    for fam, banks in SPRITES.items():
        for b in banks.values():
            for s_ in b:
                used.setdefault(s_["p"].split("/")[0], set()).add(fam)
    for name, spec in LOOPS.items():
        used.setdefault(spec["p"].split("/")[0], set()).add("loop-" + name)
    rows = ["| asset | author | source | licence | files (tools/web_public/assets/audio/, .ogg + .m4a) |", "|---|---|---|---|---|"]
    for slug, (author, _) in SOURCES.items():
        if slug not in used:
            continue
        url = "https://github.com/sgossner/VCSL (README: CC0 1.0)" if slug == "vcsl" else OGA + slug
        title = "VCSL: folk harp, anvil, hand chimes, bells, claps, frame drum, woodblock" if slug == "vcsl" else slug.replace("-", " ")
        rows.append("| %s | %s | %s | CC0 | %s |" % (title, author, url, ", ".join(sorted(used[slug]))))
    body = "\n".join(rows)
    head = "# Asset licences\n\nEvery downloaded asset in OLYMPUS is CC0 (public domain) and listed here (docs/NIGHT_BRIEF.md Round 5).\n"
    txt = open(LIC, encoding="utf-8").read() if os.path.exists(LIC) else head
    block = ("<!-- AUDIO:BEGIN (tools/audio_build.py writes this block) -->\n## Audio (sound engine, olympus/sfx.js)\n\n"
             "Licence checked on each source page (opengameart.org shows \"License(s): CC0\"; VCSL's README says CC0 1.0). "
             "Processed (trimmed, cleaned, normalised, looped, re-encoded) by tools/audio_build.py.\n\n" + body + "\n<!-- AUDIO:END -->")
    if "<!-- AUDIO:BEGIN" in txt:
        txt = re.sub(r"<!-- AUDIO:BEGIN.*?<!-- AUDIO:END -->", lambda m: block, txt, flags=re.S)
    else:
        txt = txt.rstrip("\n") + "\n\n" + block + "\n"
    with open(LIC, "w", encoding="utf-8") as fh:
        fh.write(txt)


def fetch(src):
    os.makedirs(src, exist_ok=True)
    for slug, (_, files) in SOURCES.items():
        for f in files:
            d = os.path.join(src, "_dl", slug, urllib.parse.unquote(f))
            if not os.path.exists(d):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                subprocess.run(["curl", "-sS", "--fail", "--max-time", "300", "-L", OGAF + f, "-o", d], check=True)
            out = os.path.join(src, slug)
            os.makedirs(out, exist_ok=True)
            if d.endswith(".zip"):
                with zipfile.ZipFile(d) as z:
                    for m in z.namelist():
                        if ".." not in m and not m.startswith("/") and "__MACOSX" not in m and not m.endswith("/"):
                            z.extract(m, out)
            elif d.endswith(".7z"):
                import py7zr                                            # pip install py7zr (only for --fetch)
                with py7zr.SevenZipFile(d) as z:
                    z.extractall(out)
            else:
                dst = os.path.join(out, os.path.basename(d))
                if not os.path.exists(dst):
                    os.link(d, dst)
    want = sorted({s["p"] for fam in SPRITES.values() for b in fam.values() for s in b if s["p"].startswith(V)})
    for p in want:
        d = os.path.join(src, p)
        if not os.path.exists(d):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            subprocess.run(["curl", "-sS", "--fail", "--max-time", "120", "-L", VCSL + urllib.parse.quote(p[len(V):]), "-o", d], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.environ.get("OLYMPUS_AUDIO_SRC", ""))
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--licences", action="store_true")
    a = ap.parse_args()
    if a.licences:
        licences()
        return
    if a.measure:
        man = json.load(open(os.path.join(OUT, "manifest.json"), encoding="utf-8"))
        man["measure"] = [measure(stem, f["ch"], "loop" if stem.startswith("loop-") else "sprite", nominal=f["dur"]) for stem, f in man["files"].items()]
        report(man)
        return
    if not a.src:
        sys.exit("--src <dir> (the downloaded CC0 sources) is needed; --fetch downloads them")
    if a.fetch:
        fetch(a.src)
    build(a.src)


if __name__ == "__main__":
    main()
