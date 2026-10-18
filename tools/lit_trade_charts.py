"""TradingView-style Long/Short Position screenshots of every LIT replay trade (static PNGs, matplotlib).

Each chart is drawn from the trade's chart record (tools/lit_chart_data.py: the engine's own bars, prices and times):
5m candles from 2 h before the sweep to 1 h after the exit, the green (target) and red (stop) boxes from the fill to the exit
with the entry line, the R:R and the result in $, the stop / target / entry / exit prices on the right axis, the swept levels
(dashed, with their names), the inducement swing, the sweep extreme, the 5m CISD level, the limit, the breakeven move, the
exit, the Asia / London / NY boxes, and a 1m panel around the entry (tap, 1m CISD, fill). Times ET. Futures data only.

  python tools/lit_trade_charts.py                     # every 2026 LIT trade -> research/lab/trade_charts/<date>_<HHMM>_<side>.png
  python tools/lit_trade_charts.py --since 2021-01-01  # every LIT trade (2021-25 trades have no 1m panel: no 1m data)
  python tools/lit_trade_charts.py --curate            # also the 12 committed examples -> research/study/lit_charts/
  python tools/lit_trade_charts.py --ids 2026-10-14_0524_short
  python tools/lit_trade_charts.py --replays           # use research/lab/replays.json "charts" (no engine run; 2026 only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.lit_chart_data import unpack  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "trade_charts")
CURATED = os.path.join(ROOT, "research", "study", "lit_charts")
REPLAYS = os.path.join(ROOT, "research", "lab", "replays.json")

# the app's dark theme (tools/web_public/index.html :root)
C = {"page": "#07080c", "panel": "#0d1016", "grid": "#1a1f2b", "ink": "#eef1f8", "ink2": "#a9b1c3", "muted": "#6f788b",
     "up": "#2ebd8f", "dn": "#f0506e", "good": "#2ee59d", "bad": "#ff5a7a", "warn": "#f7b955", "gold": "#f2c35b",
     "accent": "#6d7cff", "teal": "#3ee0c8", "bsl": "#ff9b5c", "ssl": "#6d9bff", "entry": "#d7dbe6"}
BOX_C = {"Asia": "#6d7cff", "London": "#f7b955", "NY": "#3ee0c8"}
EXIT_C = {"TARGET": C["good"], "STOP": C["bad"], "BE": C["ink2"], "EOD": C["warn"]}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": C["grid"], "text.color": C["ink"],
                     "axes.labelcolor": C["ink2"], "xtick.color": C["muted"], "ytick.color": C["muted"]})


def fpx(p: float) -> str:
    return f"{round(float(p) * 4) / 4:,.2f}"


def fusd(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"${abs(v):,.0f}"


def fr(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.2f}R"


def et(t: int, off: int) -> dt.datetime:
    return dt.datetime.utcfromtimestamp(int(t) + off)


class XMap:
    """epoch seconds -> x (bar i spans [i, i+1); times inside a bar are placed proportionally)."""

    def __init__(self, bars, secs):
        self.t = [b[0] for b in bars]; self.s = secs

    def __call__(self, t):
        import bisect
        if t is None:
            return None
        i = bisect.bisect_right(self.t, t) - 1
        if i < 0:
            return (t - self.t[0]) / self.s
        if i == len(self.t) - 1:            # past the last bar: keep going (off the panel), never pile up on the edge
            return i + (t - self.t[i]) / self.s
        return i + min(1.0, (t - self.t[i]) / self.s)


def candles(ax, bars, w=0.62):
    for i, (t, o, h, l, c) in enumerate(bars):
        col = C["up"] if c >= o else C["dn"]
        ax.plot([i + 0.5, i + 0.5], [l, h], color=col, lw=0.7, solid_capstyle="butt", zorder=3)
        lo, hi = min(o, c), max(o, c)
        ax.add_patch(Rectangle((i + 0.5 - w / 2, lo), w, max(hi - lo, 0.25), facecolor=col, edgecolor=col, lw=0.4, zorder=3))


def tag(ax, y, text, col, x=1.0, ink="#0b0d12", side="right"):
    ax.annotate(text, xy=(x, y), xycoords=("axes fraction", "data"), xytext=(3 if side == "right" else -3, 0),
                textcoords="offset points", va="center", ha="left" if side == "right" else "right", fontsize=7, fontweight="bold",
                color=ink, annotation_clip=False, zorder=20,
                bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.25", fc=col, ec="none"))


def spread(ys, gap):
    """nudge sorted label y values apart by at least gap (keeps order)."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for a, b in zip(order, order[1:]):
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out


LABELS = []
FIXED = []


def label(ax, x, y, text, col, ha="left", va="bottom", dy=2, fs=6.6, bold=False, bg=True, prio=2, dx=0, box=None):
    a = ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=fs, color=col,
                fontweight="bold" if bold else "normal", zorder=15, annotation_clip=True,
                bbox=box or (dict(boxstyle="round,pad=0.18", fc=C["panel"], ec="none", alpha=0.78) if bg else None))
    LABELS.append((prio, len(LABELS), a))
    return a


def declutter(fig, fixed=()):
    """move each registered label up/down (in steps) until it overlaps no earlier label nor a fixed artist."""
    rr = fig.canvas.get_renderer()
    placed = [f.get_window_extent(rr).padded(2) for f in fixed]
    for _p, _i, a in sorted(LABELS, key=lambda z: z[:2]):
        base = tuple(a.xyann)
        best = None
        for k in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 8, -8):
            a.xyann = (base[0], base[1] + k * 7.5)
            bb = a.get_window_extent(rr).padded(2.5)
            ab = a.axes.bbox
            inside = bb.y0 >= ab.y0 - 1 and bb.y1 <= ab.y1 + 1
            if inside and not any(bb.overlaps(p) for p in placed):
                best = bb
                break
        if best is None:
            a.xyann = base; best = a.get_window_extent(rr).padded(2.5)
        placed.append(best)
    LABELS.clear()


def draw_panel(ax, r, bars, secs, main=True):
    d = r["d"]
    X = XMap(bars, secs)
    n = len(bars)
    ax.set_facecolor(C["panel"])
    for s in ax.spines.values():
        s.set_color(C["grid"])
    lows = [b[3] for b in bars]; highs = [b[2] for b in bars]
    in_win = r["exit"]["t"] <= bars[-1][0]
    ys = lows + highs + [r["stop"], r["entry"]["px"]] + ([r["target"]] if (main or (in_win and r["exit_kind"] == "TARGET")) else [])
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.06 + 2
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(0, n + (6 if main else 2))
    ax.grid(axis="y", color=C["grid"], lw=0.5, zorder=0)
    ax.yaxis.tick_right()
    ax.tick_params(axis="both", length=0, labelsize=6.5, pad=2)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    # x ticks: every hour on 5m (every 30 min when short), every 10 min on 1m
    step = (1800 if n > 70 else 900) if secs == 60 else (7200 if n > 150 else 3600 if n > 60 else 1800)
    ticks = [(i, b[0]) for i, b in enumerate(bars) if (b[0] + r["off"]) % step == 0 and 2 <= i <= n - 2]
    ax.set_xticks([i for i, _ in ticks]); ax.set_xticklabels([et(t, r["off"]).strftime("%H:%M") for _, t in ticks])
    # session boxes
    for bx in r["boxes"]:
        x0, x1 = X(bx["t0"]), X(bx["t1"])
        if x1 is None or x1 <= 0 or x0 >= n:
            continue
        x0 = max(x0, 0); col = BOX_C.get(bx["k"], C["muted"])
        ax.add_patch(Rectangle((x0, bx["lo"]), x1 - x0, bx["hi"] - bx["lo"], facecolor=col, alpha=0.06, edgecolor=col, lw=0.6,
                               ls=(0, (2, 2)), zorder=1))
        if main:
            label(ax, x0, bx["hi"], bx["k"], col, dx=2, dy=2, fs=6.2, bg=False, prio=4)
    candles(ax, bars, w=0.62 if secs == 300 else 0.66)
    # position boxes: fill -> exit
    xe, xx = X(r["entry"]["t"]), X(r["exit"]["t_end"])
    xx = max(xx, xe + 0.6)
    ent = r["entry"]["px"]
    tg_c, st_c = C["good"], C["bad"]
    ax.add_patch(Rectangle((xe, min(ent, r["target"])), xx - xe, abs(r["target"] - ent), facecolor=tg_c, alpha=0.15, edgecolor=tg_c,
                           lw=0.6, zorder=2))
    ax.add_patch(Rectangle((xe, min(ent, r["stop"])), xx - xe, abs(r["stop"] - ent), facecolor=st_c, alpha=0.15, edgecolor=st_c,
                           lw=0.6, zorder=2))
    ax.plot([xe, xx], [ent, ent], color=C["entry"], lw=0.9, zorder=6)
    # the trade path (entry -> exit) like TradingView's closed-position line
    ax.plot([xe, X(r["exit"]["t"]) + 0.5], [ent, r["exit"]["px"]], color=EXIT_C.get(r["exit_kind"], C["ink2"]), lw=0.8, ls=(0, (3, 2)), zorder=7)
    if main:
        tgt_y = r["target"]; stp_y = r["stop"]
        xm = xe + 0.6
        label(ax, xm, tgt_y, f"Target {fpx(tgt_y)} · {r['plan_rr']:.2f}R", C["good"], va="top" if d == 1 else "bottom",
              dy=-3 if d == 1 else 3, prio=1, bg=False)
        label(ax, xm, stp_y, f"Stop {fpx(stp_y)} · {r['risk_pts']:.2f} pts · ${r['risk_usd']:,.0f}", C["bad"], va="bottom" if d == 1 else "top",
              dy=3 if d == 1 else -3, prio=1, bg=False)
    # swept levels (levels at the same price share one line and one label)
    merged = {}
    for lv in r["levels"]:
        m = merged.setdefault(lv["px"], {**lv, "names": []})
        m["names"].append(lv["label"])
        if lv.get("t") and (not m.get("t") or lv["t"] < m["t"]):
            m["t"] = lv["t"]
    for lv in merged.values():
        lv = {**lv, "label": " / ".join(lv["names"])}
        col = C["bsl"] if d == -1 else C["ssl"]
        x0 = X(lv["t"]) if lv.get("t") else 0
        x0 = max(0, x0 or 0)
        xs = X(r["sweep"]["ext_t"]) + 1
        if xs <= 1:
            continue
        ax.plot([x0, max(xs, x0 + 1)], [lv["px"], lv["px"]], color=col, lw=0.9, ls=(0, (4, 2.5)), zorder=5)
        if main:
            label(ax, x0 + 0.3, lv["px"], f"{lv['label']} {fpx(lv['px'])}", col, va="bottom" if d == 1 else "top", dy=2 if d == 1 else -2)
    # inducement swings
    for z in r["idm"]:
        x0 = X(z["t"]) + 0.5
        x1 = (X(z["taken_t"]) + 0.5) if z.get("taken_t") else x0 + 3
        if x1 < 0:
            continue
        ax.plot([x0, x1], [z["px"], z["px"]], color=C["gold"], lw=0.8, ls=(0, (1, 1.5)), zorder=5)
        ax.plot([x0], [z["px"]], marker="v" if d == -1 else "^", ms=4, color=C["gold"], zorder=8, clip_on=True)
        if main:
            label(ax, x0, z["px"], "IDM", C["gold"], ha="center", va="top" if d == 1 else "bottom", dy=-4 if d == 1 else 4, fs=6.2, bg=False)
    # sweep extreme
    xs = X(r["sweep"]["ext_t"]) + 0.5
    ax.plot([xs], [r["sweep"]["ext_px"]], marker="o", ms=5, mfc="none", mec=C["warn"], mew=1.2, zorder=9, clip_on=True)
    if main:
        label(ax, xs, r["sweep"]["ext_px"], f"sweep {fpx(r['sweep']['ext_px'])}", C["warn"], ha="center",
              va="top" if d == 1 else "bottom", dy=-6 if d == 1 else 6)
    # 5m CISD level (from the run's open to the trigger close)
    c5 = r["cisd5"]
    x0, x1 = X(c5["ref_t"]), X(c5["t"]) + 1
    ax.plot([x0, x1], [c5["px"], c5["px"]], color=C["accent"], lw=1.1, zorder=6)
    if main:
        label(ax, x1, c5["px"], f"CISD 5m {fpx(c5['px'])}", C["accent"], ha="right", va="top" if d == 1 else "bottom", dy=-2 if d == 1 else 2)
    # limit at the CISD level: from its placement to the tap (or the expiry)
    lim = r["limit"]
    x0 = X(lim["t0"]); x1 = X(lim["tap_t"] or lim["t1"]) + (0.5 if lim.get("tap_t") else 0)
    ax.plot([x0, x1], [lim["px"], lim["px"]], color=C["teal"], lw=0.9, ls=(0, (2, 1.5)), zorder=6)
    if lim.get("tap_t"):
        ax.plot([x1], [lim["px"]], marker="D", ms=3.2, color=C["teal"], zorder=9, clip_on=True)
    if not main:
        label(ax, x0, lim["px"], f"limit {fpx(lim['px'])}", C["teal"], ha="left", va="bottom" if d == -1 else "top", dy=2 if d == -1 else -2)
    # 1m CISD confirmation
    c1 = r.get("cisd1")
    if c1 and secs == 60:
        x0, x1 = X(c1["ref_t"]), X(c1["t"]) + 1
        ax.plot([x0, x1], [c1["px"], c1["px"]], color=C["accent"], lw=1.0, ls=(0, (3, 1.5)), zorder=6)
        label(ax, x1, c1["px"], f"CISD 1m {fpx(c1['px'])}", C["accent"], ha="left", va="center", dy=0)
    # entry marker
    ax.plot([xe], [ent], marker=">" , ms=5, color=C["entry"], zorder=10, clip_on=True)
    if not main:
        label(ax, xe, ent, f"fill {fpx(ent)}", C["entry"], ha="right", va="bottom" if d == 1 else "top", dy=3 if d == 1 else -3)
    # breakeven move
    if r.get("be"):
        xb = X(r["be"]["t"]) + 0.5
        if 0 <= xb <= n + 0.6:
            ax.plot([xb], [ent], marker="s", ms=3.6, color=C["ink"], zorder=10, clip_on=True)
            if main:
                label(ax, xb, ent, "BE", C["ink"], ha="center", va="bottom" if d == -1 else "top", dy=4 if d == -1 else -4, fs=6.2, bg=False)
    # exit
    xk = X(r["exit"]["t"]) + 0.5
    ec = EXIT_C.get(r["exit_kind"], C["ink2"])
    if 0 <= xk <= n + 0.6:
        ax.plot([xk], [r["exit"]["px"]], marker="X", ms=5.5, color=ec, mec=C["page"], mew=0.6, zorder=11, clip_on=True)
        if main:
            res = f"{r['exit_kind']} {fusd(r['pnl'])} · {fr(r['r'])}"
            right = xk > 0.7 * (n + 6)
            label(ax, xk, r["exit"]["px"], res, "#0b0d12", ha="right" if right else "left", va="center", dy=0, dx=-7 if right else 7,
                  fs=7, bold=True, prio=0, box=dict(boxstyle="round,pad=0.3,rounding_size=0.3", fc=ec, ec="none"))
    # right-axis price tags (TradingView style), nudged apart
    items = [(r["target"], fpx(r["target"]), C["good"]), (ent, fpx(ent), C["entry"]), (r["stop"], fpx(r["stop"]), C["bad"])]
    y0, y1 = ax.get_ylim()
    gap = (y1 - y0) * (0.045 if main else 0.05)
    ys = spread([y for y, _, _ in items], gap)
    for (y, txt, col), yy in zip(items, ys):
        tag(ax, yy, txt, col)


def row(fig, x, y, parts, gap=0.012):
    """texts side by side (measured), for the title line."""
    rr = fig.canvas.get_renderer()
    W = fig.get_window_extent(rr).width
    for txt, col, fs, fw in parts:
        t = fig.text(x, y, txt, fontsize=fs, fontweight=fw, color=col, va="center")
        x += t.get_window_extent(rr).width / W + gap


def render(r, path, dpi=220):
    b5 = unpack(r["b5"]); b1 = unpack(r.get("b1"))
    two = bool(b1)
    fig = plt.figure(figsize=(8.0, 4.6), dpi=dpi, facecolor=C["page"])
    if two:
        gs = fig.add_gridspec(1, 2, width_ratios=[2.35, 1], wspace=0.2, left=0.012, right=0.915, top=0.84, bottom=0.075)
        ax = fig.add_subplot(gs[0]); ax1 = fig.add_subplot(gs[1])
    else:
        ax = fig.add_axes([0.012, 0.075, 0.9, 0.765]); ax1 = None
    draw_panel(ax, r, b5, 300, main=True)
    if ax1 is not None:
        draw_panel(ax1, r, b1, 60, main=False)
        ax1.set_title("1m · entry", fontsize=7, color=C["ink2"], loc="left", pad=3)
        # mark the 1m window on the 5m chart
        X = XMap(b5, 300)
        x0, x1 = X(b1[0][0]), X(b1[-1][0] + 60)
        ax.axvspan(x0, x1, color=C["ink"], alpha=0.035, zorder=0, lw=0)
    ax.set_title("5m", fontsize=7, color=C["ink2"], loc="left", pad=3)
    # title + subtitle
    e = et(r["entry"]["t"], r["off"])
    side_c = C["good"] if r["side"] == "LONG" else C["bad"]
    res_c = EXIT_C.get(r["exit_kind"], C["ink"])
    x = 0.014
    row(fig, x, 0.955, [(f"{e:%a %Y-%m-%d} · {e:%H:%M} ET", C["ink"], 10, "bold"), (r["side"], side_c, 10, "bold"),
                         (f"{r['qty']} MNQ · ${r['risk_usd']:,.0f} at risk", C["ink2"], 9, "normal")])
    fig.text(0.985, 0.955, f"{r['exit_kind']}  {fusd(r['pnl'])} · {fr(r['r'])}", fontsize=10, fontweight="bold", color=res_c,
             va="center", ha="right")
    lv = r["levels"]
    swept = ", ".join(f"{z['label']} {fpx(z['px'])}" for z in lv[:3]) + (f" (+{len(lv) - 3})" if len(lv) > 3 else "")
    sub = (f"LIT · swept {swept} · sweep {fpx(r['sweep']['ext_px'])} ({r['sweep']['depth_atr']:.2f} ATR) · "
           f"{len(r['idm'])} IDM · {r['entry_kind']} entry · target {r['target_label']}")
    if r.get("size_why"):
        sub += " · " + "; ".join(r["size_why"])
    fs = 6.6 if len(sub) <= 150 else max(5.4, 6.6 * 150 / len(sub))
    fig.text(x, 0.905, sub, fontsize=fs, color=C["muted"], va="center")
    fig.text(0.985, 0.022, "CME NQ1! futures (TradingView export) · times ET · paper backtest", fontsize=5.6, color=C["muted"], ha="right")
    declutter(fig, FIXED)
    FIXED.clear()
    fig.savefig(path, dpi=dpi, facecolor=C["page"])
    plt.close(fig)


def curate(recs):
    """the 12 committed examples: 4 biggest wins, 4 typical losses (STOP, nearest the median loss, spread over the year),
    2 breakevens, 2 end-of-day exits (the biggest |$| of each)."""
    R = sorted(recs.values(), key=lambda r: r["entry"]["t"])
    wins = sorted([r for r in R if r["pnl"] > 0], key=lambda r: -r["pnl"])[:4]
    losses = [r for r in R if r["exit_kind"] == "STOP"]
    med = sorted(r["pnl"] for r in losses)[len(losses) // 2] if losses else 0
    near = sorted(losses, key=lambda r: abs(r["pnl"] - med))[:12]
    near = sorted(near, key=lambda r: r["entry"]["t"])
    typ = [near[int(i * (len(near) - 1) / 3)] for i in range(4)] if len(near) >= 4 else near
    be = sorted([r for r in R if r["exit_kind"] == "BE"], key=lambda r: -r["entry"]["t"])[:2]
    eod = sorted([r for r in R if r["exit_kind"] == "EOD"], key=lambda r: -abs(r["pnl"]))[:2]
    pick = [("biggest win", r) for r in wins] + [("typical loss", r) for r in typ] + [("breakeven", r) for r in be] + [("end of day", r) for r in eod]
    return pick


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-01-01")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--curate", action="store_true")
    ap.add_argument("--replays", action="store_true", help="read research/lab/replays.json charts instead of running the engine")
    ap.add_argument("--dpi", type=int, default=220)
    a = ap.parse_args()
    if a.replays:
        recs = (json.load(open(REPLAYS, encoding="utf-8")).get("charts") or {})
        recs = {k: v for k, v in recs.items() if v["day"] >= a.since}
    else:
        from tools.lit_chart_data import build
        recs = build(a.since)
    if a.ids:
        recs = {k: v for k, v in recs.items() if k in set(a.ids)}
    os.makedirs(a.out, exist_ok=True)
    for i, (k, r) in enumerate(sorted(recs.items())):
        render(r, os.path.join(a.out, k + ".png"), a.dpi)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(recs)}", flush=True)
    print(f"{len(recs)} charts -> {a.out}")
    if a.curate:
        os.makedirs(CURATED, exist_ok=True)
        for n in os.listdir(CURATED):
            if n.endswith(".png"):
                os.remove(os.path.join(CURATED, n))
        idx = []
        for why, r in curate(recs):
            src = os.path.join(a.out, r["id"] + ".png")
            shutil.copy(src, os.path.join(CURATED, r["id"] + ".png"))
            idx.append({"id": r["id"], "why": why, "side": r["side"], "exit": r["exit_kind"], "pnl": r["pnl"], "r": r["r"],
                        "qty": r["qty"], "risk_usd": r["risk_usd"], "entry": r["entry"]["px"], "stop": r["stop"], "target": r["target"]})
        with open(os.path.join(CURATED, "index.json"), "w", encoding="utf-8") as fh:
            json.dump({"what": "12 example LIT trade charts (python tools/lit_trade_charts.py --curate): 4 biggest wins, 4 typical "
                               "losses, 2 breakevens, 2 end-of-day exits; all charts: research/lab/trade_charts/ (not committed)",
                       "charts": idx}, fh, indent=1)
        print(f"curated {len(idx)} -> {CURATED}")


if __name__ == "__main__":
    main()
