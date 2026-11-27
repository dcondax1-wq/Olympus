"""Red team 2026-11-26 (day-cards): a Telegram caption over 1024 characters never cuts the alert's $ lines (legend dropped first,
then the full text message); the chart reads NinjaTrader's files only when the bot's own history has no bars.
    python -X utf8 -m tests.test_trade_cards_rt
"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import alert_bus as AB      # noqa: E402
from engine import trade_card as TC     # noqa: E402

R = []


def check(name, ok, detail=""):
    R.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {detail}"), flush=True)


def decode(png: bytes):
    """Our own PNG reader (8-bit RGB, filters 0 / 2 as png_chart writes them) for the golden-image checks."""
    import struct
    import zlib
    import numpy as np
    w, h = struct.unpack(">II", png[16:24])
    pos, data = 8, b""
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        tag = png[pos + 4:pos + 8]
        if tag == b"IDAT":
            data += png[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = np.frombuffer(zlib.decompress(data), np.uint8).reshape(h, w * 3 + 1)
    img = np.zeros((h, w * 3), np.uint8)
    for y in range(h):
        f, row = raw[y, 0], raw[y, 1:]
        img[y] = row if f == 0 else (row + (img[y - 1] if y else 0)).astype(np.uint8)
    return img.reshape(h, w, 3)


def premium():
    """night-nq-cards 2026-11-27: time + size budgets, golden-image sanity, the 120-file cap, the text fallback."""
    import math
    import time
    import numpy as np
    from engine import png_chart as PC
    from engine import png_font as PF
    t0 = 1_764_082_320                                          # 2025-11-25 09:52 ET (any time works)
    rng = np.random.default_rng(7)
    B, px = [], 25500.0
    for i in range(360):                                        # 6 h of noisy 1-minute bars: the worst case for size
        o = px
        px += float(rng.normal(0, 4)) + math.sin(i / 7) * 2
        B.append((t0 - 7200 + 60 * i, o, max(o, px) + abs(float(rng.normal(0, 3))), min(o, px) - abs(float(rng.normal(0, 3))), px))
    entry = B[120][4]
    lines = [(entry + 60, PC.GREEN, t0, False, "TARGET"), (entry, PC.GOLD, t0, True, "ENTRY"), (entry - 20, PC.RED, t0, False, "STOP"),
             (entry - 19.75, PC.LILAC, None, True, "SWEEP")]
    head = {"bot": "LIT", "account": "Zlarior 50K", "side": "LONG", "qty": 2, "hero": "+$240", "hero_col": PC.UP, "sub": "+3.00R", "tag": "X"}
    kw = dict(head=head, foot="LIT: swept London low", zones=[(entry, entry + 60, t0, PC.UP), (entry, entry - 20, t0, PC.DOWN)])
    PC.render(B[:10], lines, [(t0, entry, PC.GOLD)], **kw)     # warm the cached page
    best, png = 9.9, None
    for _ in range(3):
        t = time.perf_counter()
        png = PC.render(B, lines, [(t0, entry, PC.GOLD, "entry"), (B[-1][0], B[-1][4], PC.WHITE, "exit")], **kw)
        best = min(best, time.perf_counter() - t)
    check(f"render time: {best * 1000:.0f} ms (budget 300 ms on a slow CPU; ~75 ms on the cloud box)", png and best < 0.300, best)
    check(f"size: {len(png or b'') // 1024} KB for 6 h of noisy bars (budget 300 KB)", png and len(png) < 300_000, len(png or b""))
    img = decode(png)
    check("golden: 1280 x 720, the page corner black, the card #16131e", img.shape == (720, 1280, 3) and int(img[2, 2].sum()) < 12
          and tuple(img[690, 640]) == (22, 19, 30), (img[2, 2], img[690, 640]))
    near = lambda c, ref, tol=40: all(abs(int(a) - int(b)) <= tol for a, b in zip(c, ref))   # noqa: E731
    tag_row = img[150:640, 1040:1250].reshape(-1, 3)
    has = lambda ref: any(near(c, ref, 12) for c in tag_row[::3])                             # noqa: E731
    check("golden: the tags in mint (target), gold (entry), rose (stop), lilac (sweep)",
          has(PC.UP) and has(PC.GOLD) and has(PC.DOWN) and has(PC.LILAC))
    hero = img[60:120, 900:1240].reshape(-1, 3)
    check("golden: the hero $ in mint (a winning exit)", any(near(c, PC.UP, 10) for c in hero[::2]))
    cyan = ((img[..., 2].astype(int) > 180) & (img[..., 1].astype(int) > 180) & (img[..., 0].astype(int) < 90)).sum()
    check("golden: no cyan anywhere (OLYMPUS NIGHT)", cyan == 0, cyan)
    aa = img[160:640, 52:1030].reshape(-1, 3)
    check("golden: anti-aliased (in-between shades, not 3-4 flat colours)", len({tuple(c) for c in aa[::7]}) > 500)
    check("font: every digit and $ + - . , : % has a glyph; unknown -> '?'",
          all(ch in PF.GLYPHS for ch in "0123456789$+-.,:%") and PF.mask("\u2603").shape == PF.mask("?").shape)
    check("font: a long line is cut to fit with '...'", PF.width(PF.fit("X" * 300, 200, 2), 2) <= 200)
    for bad in (None, [], [(1, 2, 3, 4, 5)], [("x", 1, 1, 1, 1)] * 5):
        if PC.render(bad, lines) is not None:
            check("bad bars -> None (text message)", False, bad)
            break
    else:
        check("bad bars -> None (the text message)", True)
    check("summary renders never raise", PC.render_day({"rows": [{"name": None, "today": "x"}]}) is not None
          and PC.render_week({"rows": "junk"}) is not None and PC.render_day(None) is None)
    d = tempfile.mkdtemp(prefix="cards_keep_")
    keep_dir = TC.CARD_DIR
    TC.CARD_DIR = d
    try:
        for i in range(150):
            open(os.path.join(d, f"f{i}.png"), "wb").close()
        TC._trim()
        check("logs/cards keeps the newest 120 files", len(os.listdir(d)) == 120, len(os.listdir(d)))
        orig = PC.render
        PC.render = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            c = TC.build({"key": f"fill:{t0}", "side": "LONG", "qty": 1, "entry": 1.0, "stop": 0.0, "target": 3.0}, "entry", now=t0,
                         bars_fn=lambda a, b: B[:30])
        finally:
            PC.render = orig
        check("a render that raises -> build() None, attach() keeps the text event", c is None and TC.attach({"kind": "entry"}, {}, "entry")
              == {"kind": "entry"}, c)
    finally:
        TC.CARD_DIR = keep_dir
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def main():
    calls = []
    op, ot = AB.send_telegram_photo, AB.send_telegram
    AB.send_telegram_photo = lambda c, p, cap, s: (calls.append(("photo", len(cap))), ("telegram:1", "ok"))[1]
    AB.send_telegram = lambda c, t, b, s: (calls.append(("text", len(t) + len(b))), ("telegram:2", "ok"))[1]
    os.environ["LE_TG_PRETTY"] = "0"            # day-tgpretty: the old one-photo-with-caption path stays behind its switch
    try:
        cfg = {"telegram": {"token": "x", "chat_id": "1"}}
        ev = {"photo": "p.png", "legend": "L" * 100}
        AB._one("telegram", cfg, ev, "T", "b" * 500, False)
        AB._one("telegram", cfg, ev, "T", "b" * 960, False)
        AB._one("telegram", cfg, ev, "T", "b" * 1100, False)
        os.environ.pop("LE_TG_PRETTY", None)
        new = []
        AB.send_telegram_photo = lambda c, p, cap, s: (new.append(("photo", cap)), ("telegram:1", "ok"))[1]
        AB.send_telegram = lambda c, t, b, s: (new.append(("text", t + "\n" + b)), ("telegram:2", "ok"))[1]
        AB._one("telegram", cfg, {"kind": "exit", "account": "Zlarior 50K", "usd": 1240.0, "reason": "target", "photo": "p.png"},
                "T", "b" * 1100, False)
        AB.drain(10)
    finally:
        os.environ.pop("LE_TG_PRETTY", None)
        AB.send_telegram_photo, AB.send_telegram = op, ot
    check("day-tgpretty: the short text first (the $ line is in it), then the photo with a one-line caption (never cut)",
          [k for k, _ in new] == ["text", "photo"] and "+$1,240" in new[0][1] and len(new[1][1]) < 200, new)
    check("short: the photo with the legend", calls[0] == ("photo", 1 + 1 + 500 + 1 + 100), calls)
    check("over 1024 with the legend: the photo WITHOUT the legend", calls[1] == ("photo", 1 + 1 + 960), calls)
    check("over 1024 without it: the full text message (no cut $ lines)", calls[2][0] == "text", calls)

    import pandas as pd
    nt_reads = []

    class Bot:
        cfg = {"sym": "NQ"}

        def _read_hist(self, sym, tf):
            return pd.DataFrame({"time": range(0, 600, 60), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    import engine.ninjatrader as NT
    orig = NT.NinjaTraderBars

    class Fake:
        def __init__(self, *_a):
            pass

        def recent_bars(self, *_a):
            nt_reads.append(1)
            return None, "x", None
    NT.NinjaTraderBars = Fake
    try:
        b = TC.bars(0, 600, Bot())
    finally:
        NT.NinjaTraderBars = orig
    check("history has the bars: NinjaTrader's files are not read", len(b) == 10 and not nt_reads, (len(b), nt_reads))
    premium()
    print(f"\ntrade cards red team: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    raise SystemExit(main())
