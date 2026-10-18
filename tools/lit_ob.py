"""LIT order blocks (owner, 2026-10-18: "Order blocks are huge, implement these too. I want you trading all of LIT.").

The detector is engine/lit_ob.py (pure functions, no look-ahead; the dashboard can draw the same blocks). This wrapper puts the
blocks into the live LIT trade (engine/lit.py is not edited; its run loop is re-implemented here with OB hooks, and with no
OB option it reproduces run lit_live trade for trade, see `check`):

  1. POI      the sweep extreme runs INTO an unmitigated 15m / 1H / 4H order block (first touch during the sweep leg, the
              extreme no deeper than tol ATR past its far edge): require it, size up when present, or skip / half when the
              extreme is far from every fresh HTF block.
  2. entry    after the 5m CISD, the 5m block that made it (the down-close run into the extreme = the CISD run; body top = the
              CISD level = today's limit) or the 1m block of the 1m CISD: a limit at its mean threshold / edge, only when
              that level is within x of the stop distance from today's entry, else today's entry.
  3. target   the nearest opposing unmitigated HTF block (proximal edge) alone, or the nearer of it and the VIX band;
     obstacle skip / half when an opposing fresh HTF block sits < 1.5R from the entry.
  4. OB-only  an extra LIT setup type: inducement swept INTO a fresh HTF block + displacement + 5m CISD + the 1m entry, no
              session-level sweep needed; one trade a day, the first setup of the day that fills (main or OB) is the trade.
Scoring: unit trades at 1 micro (exact), then the live sizes: eval ($800 up to a 25-pt stop + 60% room cap,
tools/lit_tightstop.score) and two_week (live_model.json lit_sizing.two_week = config C, tools/lit_2wk.run_eval, fresh eval on
every session + back-to-back with a reset after 10 sessions). Pick on 2026 H1, check on 2026 H2, 2021-25 reference (5m).

  python tools/lit_ob.py detector     # 20 detected / rejected blocks drawn -> research/study/lit_ob/detector_*.png
  python tools/lit_ob.py check        # no OB option == run lit_live (120 trades 2026, +$41,734)
  python tools/lit_ob.py grid         # every test -> research/lit/ob_results.json
  python tools/lit_ob.py save         # rl.save runs lit_ob_* (family other, tags lit, lit_ob)
  python tools/lit_ob.py charts       # 6 example trades with the POI block -> research/study/lit_ob/trade_*.png
Paper only. 1 CPU process.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pickle
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import lit_ob as O  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as T  # noqa: E402
from tools import runlib as rl  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = os.path.join(ROOT, "research", "study", "lit_ob")
OUT = os.path.join(ROOT, "research", "lit", "ob_results.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
SESS, SPAN, LIVE = T.SESS, T.SPAN, T.LIVE
PV, COMM, SLIP, MAXQ = lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS
TFS = ("5m", "15m", "1h", "4h")
BULL, BEAR = "#2a78d6", "#eb6834"         # validated pair (dataviz validate_palette: CVD dE 28.5)
INK, MUTED, GRID = "#1f1f1d", "#6b6b66", "#e6e5e1"


# ================================================================================================ blocks on the history
_OB = {}


def market():
    return F.market(LIVE["ref"], LIVE["extra_boxes"])


def htf(M, tf):
    return O.resample(M.t, M.o, M.h, M.l, M.c, tf, M.mod, M.day_of)


def blocks(M, tf, cfg=None, kind="body"):
    """Every block of tf with its 5m clock: k5 = the 5m bar whose close makes it known, mit5 = first 5m touch of the proximal
    edge after that, brk5 = the 5m bar closing the tf candle that closed through the far edge (breaker known), bmit5 = first 5m
    touch of the breaker's proximal edge after that."""
    key = (tf, json.dumps(cfg or {}, sort_keys=True), kind)
    if key in _OB:
        return _OB[key]
    p = os.path.join(CACHE, f"lit_ob_{tf}_{kind}_{abs(hash(key[1])) % 10 ** 8}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        _OB[key] = pickle.load(open(p, "rb"))
        return _OB[key]
    B = htf(M, tf)
    obs = O.detect(B["o"], B["h"], B["l"], B["c"], cfg, tf, t=B["t"])
    O.lifecycle(obs, B["h"], B["l"], B["c"], kind)
    last = B["last"]
    for ob in obs:
        bt, tp = O.zone(ob, kind)
        ob["bot"], ob["top"] = bt, tp
        ob["k5"] = int(last[ob["conf"]])
        m5, _, _ = O.touch_and_break(ob["dir"], bt, tp, M.h, M.l, M.c, ob["k5"] + 1)
        ob["mit5"] = m5
        ob["brk5"] = int(last[ob["brk"]]) if ob["brk"] is not None else None
        if ob["brk5"] is not None:
            # the breaker (opposite role, same zone): first 5m touch of its proximal edge after the break is known
            d2 = -ob["dir"]
            _, _, _ = None, None, None
            hs = M.h[ob["brk5"] + 1:]; ls = M.l[ob["brk5"] + 1:]
            msk = (hs >= bt) if d2 == -1 else (ls <= tp)
            j = int(np.argmax(msk)) if len(msk) else 0
            ob["bmit5"] = ob["brk5"] + 1 + j if len(msk) and msk[j] else None
        else:
            ob["bmit5"] = None
        ob["t_known"] = int(M.t[ob["k5"]]) + 300
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(obs, open(p, "wb"))
    _OB[key] = obs
    return obs


def et(ts):
    return dt.datetime.fromtimestamp(int(ts), ET)


# ================================================================================================ detector charts
def _candles(ax, o, h, l, c, x0=0, w=0.6):
    from matplotlib.patches import Rectangle
    for i in range(len(o)):
        x = x0 + i
        up = c[i] >= o[i]
        ax.plot([x, x], [l[i], h[i]], color=INK, lw=0.8, zorder=3)
        lo, hi = min(o[i], c[i]), max(o[i], c[i])
        ax.add_patch(Rectangle((x - w / 2, lo), w, max(hi - lo, 1e-6), facecolor="#ffffff" if up else "#4a4a46",
                               edgecolor=INK, lw=0.8, zorder=4))


def draw_block(path, B, tfname, ob, title, sub="", note="", pad_l=30, pad_r=40, rejected=None, kind="body", extra=None,
               win=None):
    """One block on its own timeframe. ob: a detected block (indices on B) or, with rejected, the rejected candidate.
    win = (a, z) bar range to show (default: pad_l before the block, pad_r after it is known)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    s = ob["s"]
    end_i = ob.get("conf", ob.get("u", s))
    a, z = win if win else (max(0, s - pad_l), min(len(B["o"]), end_i + pad_r))
    o, h, l, c = (B[k][a:z] for k in ("o", "h", "l", "c"))
    span = float(max(h) - min(l)) or 1.0
    fig, ax = plt.subplots(figsize=(11, 5.4), dpi=110)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    _candles(ax, o, h, l, c)
    d = ob["dir"]
    col = BULL if d == 1 else BEAR
    tag = lambda x, y, txt, va="center", ha="left", color=INK: ax.text(x, y, txt, fontsize=7.5, color=color, va=va, ha=ha, zorder=6,
                                                                     bbox=dict(facecolor="#fcfcfb", edgecolor="none", alpha=0.85, pad=0.8))
    if rejected is None:
        bt, tp = O.zone(ob, kind)
        mit = ob.get("mit")
        xe = (mit - a) if mit is not None and mit < z else (z - a - 1)
        x0 = s - a - 0.45
        ax.add_patch(Rectangle((x0, bt), xe - x0 + 0.45, tp - bt, facecolor=col, alpha=0.20, edgecolor=col, lw=1.2, zorder=1))
        wb, wt = O.zone(ob, "wick" if kind == "body" else "body")
        ax.add_patch(Rectangle((x0, wb), (ob["e"] - s) + 0.9, wt - wb, facecolor="none", edgecolor=col, lw=0.9, ls=":", zorder=2))
        ax.plot([x0, xe + 0.45], [ob["mt"]] * 2, color=col, lw=1.0, ls="--", zorder=2)
        tag(xe + 0.8, ob["mt"], "MT 50%", color=MUTED)
        tag(xe + 0.8, tp if d == 1 else bt, ("OB " + kind), va="bottom" if d == 1 else "top", color=INK)
        if ob.get("fvg"):
            fl, fh_ = ob["fvg"]
            ax.add_patch(Rectangle((ob["u"] - a - 0.45, fl), ob["conf"] - ob["u"] + 1.4, fh_ - fl, facecolor="#9a9a94", alpha=0.3, lw=0, zorder=1))
            tag(ob["conf"] - a + 1.2, 0.5 * (fl + fh_), "FVG", color=MUTED)
        if ob.get("bos") is not None:
            xb = max(0, s - a - 10)
            ax.plot([xb, ob["bos_i"] - a + 0.45], [ob["bos"]] * 2, color=INK, lw=1.1, zorder=2)
            tag(xb, ob["bos"], "swing broken", va="bottom" if d == 1 else "top")
        ax.axvline(ob["conf"] - a + 0.5, color=MUTED, lw=0.8, ls=":", zorder=0)
        tag(ob["conf"] - a + 0.6, max(h) + 0.02 * span, "known (candle closed)", va="top", color=MUTED)
        if mit is not None and mit < z:
            y = tp if d == 1 else bt
            ax.plot([mit - a], [y], marker="o", ms=6, mfc="none", mec=INK, zorder=7)
            tag(mit - a + 0.8, y - d * 0.06 * span, "1st touch = mitigated", va="top" if d == 1 else "bottom")
        brk = ob.get("brk")
        if brk is not None and brk < z:
            ax.plot([brk - a], [c[brk - a]], marker="x", ms=7, color=INK, zorder=7)
            tag(brk - a + 0.8, c[brk - a] - d * 0.10 * span, "close through = breaker", va="top" if d == 1 else "bottom")
    else:
        e = ob["e"]
        bt = float(min(np.minimum(B["o"][s:e + 1], B["c"][s:e + 1]))); tp = float(max(np.maximum(B["o"][s:e + 1], B["c"][s:e + 1])))
        ax.add_patch(Rectangle((s - a - 0.45, bt), (e - s) + 0.9 + 6, tp - bt, facecolor="none", edgecolor=MUTED, lw=1.3, ls="--", zorder=1))
        tag(s - a + 7, 0.5 * (bt + tp), "not an order block", color=INK)
        if ob.get("bos_lvl") is not None:
            lv = ob["bos_lvl"] if d == 1 else -ob["bos_lvl"]
            ax.plot([max(0, s - a - 10), z - a - 1], [lv] * 2, color=INK, lw=0.9, ls=":")
            tag(max(0, s - a - 10), lv, "swing it had to close beyond", va="bottom" if d == 1 else "top")
    if extra:
        extra(ax, a)
    n = z - a
    step = max(1, n // 9)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([et(B["t"][a + i]).strftime("%m-%d %H:%M") for i in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED); ax.tick_params(axis="x", colors=MUTED)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_xlim(-1, n + 4)
    ax.set_ylim(min(l) - 0.05 * span, max(h) + 0.06 * span)
    ax.set_title(title + ("\n" + sub if sub else ""), fontsize=9.5, color=INK, loc="left")
    if note:
        fig.text(0.01, 0.012, note, fontsize=7.2, color=MUTED)
    fig.tight_layout(rect=(0, 0.035 if note else 0, 1, 1))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def detector(seed=11):
    """20 blocks on 5m / 15m / 1H 2026 charts: clear ones, edge cases, and candidates the rules reject."""
    M, _ = market()
    os.makedirs(STUDY, exist_ok=True)
    rng = np.random.default_rng(seed)
    picks = []
    y26 = int(np.searchsorted(M.dates, "2026-01-01"))
    for tf in ("5m", "15m", "1h"):
        B = htf(M, tf)
        rej = []
        obs = O.detect(B["o"], B["h"], B["l"], B["c"], None, tf, rejects=rej, t=B["t"])
        O.lifecycle(obs, B["h"], B["l"], B["c"])
        a26 = int(np.searchsorted(B["last"], y26))
        obs = [x for x in obs if x["s"] >= a26 and x["conf"] + 45 < len(B["o"])]
        rej = [x for x in rej if x["s"] >= a26 and x["u"] + 45 < len(B["o"])]
        neutral = lambda i: (B["h"][i] - B["l"][i] <= 0) or abs(B["c"][i] - B["o"][i]) <= 0.1 * (B["h"][i] - B["l"][i])
        cats = collections.OrderedDict()
        cats["clear"] = [x for x in obs if x["swept"] and x["bos"] is not None and x["kind"] == "extreme" and x["disp_atr"] >= 1.2]
        cats["doji in the run"] = [x for x in obs if any(neutral(i) for i in range(x["s"], x["e"] + 1)) or x["u"] - x["e"] > 1]
        cats["inside bar"] = [x for x in obs if x["n_run"] == 1 and B["h"][x["s"]] <= B["h"][x["s"] - 1] and B["l"][x["s"]] >= B["l"][x["s"] - 1]]
        cats["gap"] = [x for x in obs if (B["t"][x["u"]] - B["t"][x["e"]]) > 3 * O.TF_SECS[tf] or
                       x["dir"] * (B["o"][x["u"]] - B["c"][x["e"]]) > 0.5 * (B["h"][x["e"]] - B["l"][x["e"]])]
        by_conf = collections.defaultdict(list)
        for x in obs:
            by_conf[x["dir"]].append(x)
        b2b = []
        for d, L in by_conf.items():
            for p, q in zip(L, L[1:]):
                if 0 < q["s"] - p["e"] <= 4:
                    b2b.append(q)
        cats["back to back"] = b2b
        cats["rejected: no FVG"] = [x for x in rej if x["why"] == "no FVG" and x["bos_lvl"] is not None]
        cats["rejected: no structure break"] = [x for x in rej if x["why"] == "no structure break" and x["fvg"]]
        cats["rejected: session break inside the move (an opening gap)"] = [x for x in rej if x["why"].startswith("session break")]
        cats["rejected: weak move"] = [x for x in rej if x["why"].startswith("weak move")]
        cats["rejected: price went back below the block first"] = [x for x in rej if x["why"].startswith("price went back")]
        want = {"5m": {"clear": 2, "doji in the run": 1, "inside bar": 1, "gap": 1, "back to back": 1, "rejected: weak move": 1},
                "15m": {"clear": 2, "doji in the run": 1, "back to back": 1, "rejected: no structure break": 1,
                        "rejected: price went back below the block first": 1},
                "1h": {"clear": 3, "inside bar": 1, "gap": 1, "rejected: no FVG": 1, "rejected: session break inside the move (an opening gap)": 1}}[tf]
        for cat, k in want.items():
            L = cats.get(cat) or []
            if not L:
                continue
            for j in rng.choice(len(L), size=min(k, len(L)), replace=False):
                picks.append((tf, B, cat, L[int(j)]))
    out = []
    for n, (tf, B, cat, ob) in enumerate(picks[:20], 1):
        nm = f"detector_{n:02d}_{tf}_{cat.replace(':', '').replace(' ', '_')}.png"
        day = et(B["t"][ob["s"]]).strftime("%Y-%m-%d %H:%M ET")
        side = "bullish" if ob["dir"] == 1 else "bearish"
        if cat.startswith("rejected"):
            why = ob["why"]
            draw_block(os.path.join(STUDY, nm), B, tf, ob, f"{n}. {tf} {side} candidate REJECTED: {why} - {day}",
                       sub="the last opposite-colour run before a move, but the move does not qualify",
                       rejected=why, note="Dashed box: the run a chart reader might mark. The detector does not count it: " + why + ".")
        else:
            bt, tp = O.zone(ob, "body")
            sub = (f"{side} order block, {ob['kind']}{', took liquidity' if ob['swept'] else ''}, body {bt:.2f}-{tp:.2f} "
                   f"({tp - bt:.1f} pts), {ob['n_run']} candle{'s' if ob['n_run'] > 1 else ''}, biggest move body {ob['disp_atr']:.1f} ATR"
                   f"{', broke swing ' + format(ob['bos'], '.2f') if ob['bos'] is not None else ', liquidity + CISD close (no swing above)'}")
            draw_block(os.path.join(STUDY, nm), B, tf, ob, f"{n}. {tf} {cat} - {day}", sub=sub,
                       note="Shaded = block body (the zone), dotted = its wick range, dashed = mean threshold (50%), grey = the FVG of the "
                            "move. The zone stops at the first touch (mitigation); x = a close through it (breaker).")
        out.append({"file": nm, "tf": tf, "case": cat, "dir": ob["dir"], "start": day})
    json.dump(out, open(os.path.join(STUDY, "detector_index.json"), "w"), indent=1)
    print("\n".join(f"{x['file']}" for x in out))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    globals()[cmd]()
