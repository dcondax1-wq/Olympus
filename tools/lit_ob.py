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
    for tf in ("5m", "15m", "1h", "4h"):
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
                "1h": {"clear": 3, "inside bar": 1, "gap": 1, "rejected: no FVG": 1, "rejected: session break inside the move (an opening gap)": 1},
                "4h": {"clear": 1, "back to back": 1}}[tf]
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


# ================================================================================================ fast block queries
# A block counts for at most this many 5m bars after it is known (15m: 2 days, 1h: 10 days, 4h: 30 days, 1d: 60 days).
AGE = {"5m": 288, "15m": 576, "1h": 2880, "4h": 8640, "1d": 17280}   # 1d: 60 days
INF = 10 ** 12
_IX = {}


_FL = set()


def flags(M, tf, kind="body", peak_lb=48):
    """Owner's LIT mitigation notes: peak = the block holds the extreme of the last peak_lb candles of its timeframe up to
    the bar that made it known (the OB of the INITIAL break of structure off the peak); fvg_adj = the move's FVG starts right
    at the block's last candle (the inefficiency sits directly above / below the block). Stored on the block dicts."""
    if (tf, kind) in _FL:
        return
    B = htf(M, tf)
    for ob in blocks(M, tf, None, kind):
        a = max(0, ob["conf"] - peak_lb)
        if ob["dir"] == 1:
            ob["peak"] = bool(ob["wick_bot"] <= B["l"][a:ob["conf"] + 1].min())
            ob["fvg_adj"] = bool(ob["fvg"] is not None and abs(ob["fvg"][0] - B["h"][ob["e"]]) < 1e-9)
        else:
            ob["peak"] = bool(ob["wick_top"] >= B["h"][a:ob["conf"] + 1].max())
            ob["fvg_adj"] = bool(ob["fvg"] is not None and abs(ob["fvg"][1] - B["l"][ob["e"]]) < 1e-9)
    _FL.add((tf, kind))


def block_of(M, nm, kind="body"):
    """The block dict behind an OB-only / OB-inside level name (ob<tf>#<q> or obin<tf>#<q>@<f>)."""
    head, rest = nm.split("#")
    tf = head[4:] if head.startswith("obin") else head[2:]
    flags(M, tf, kind)
    return blocks(M, tf, None, kind)[int(rest.split("@")[0])]


def ob_index(M, tf, kind="body"):
    """{d: arrays} of the blocks of direction d (k5, mit5, top, bot, swept, extreme, brk5, bmit5) + touch order."""
    key = (tf, kind)
    if key in _IX:
        return _IX[key]
    obs = blocks(M, tf, None, kind)
    flags(M, tf, kind)
    out = {}
    for d in (1, -1):
        L = [x for x in obs if x["dir"] == d]
        A = {"ob": L,
             "k5": np.array([x["k5"] for x in L], dtype=np.int64),
             "mit5": np.array([x["mit5"] if x["mit5"] is not None else INF for x in L], dtype=np.int64),
             "top": np.array([x["top"] for x in L]), "bot": np.array([x["bot"] for x in L]),
             "swept": np.array([x["swept"] for x in L], bool), "ext": np.array([x["kind"] == "extreme" for x in L], bool),
             "brk5": np.array([x["brk5"] if x["brk5"] is not None else INF for x in L], dtype=np.int64),
             "bmit5": np.array([x["bmit5"] if x["bmit5"] is not None else INF for x in L], dtype=np.int64)}
        A["by_mit"] = np.argsort(A["mit5"], kind="stable"); A["mit_sorted"] = A["mit5"][A["by_mit"]]
        A["by_bmit"] = np.argsort(A["bmit5"], kind="stable"); A["bmit_sorted"] = A["bmit5"][A["by_bmit"]]
        out[d] = A
    _IX[key] = out
    return out


def poi_hits(M, z, Q):
    """Fresh blocks (and breakers if Q["breaker"]) of the trade's direction that the sweep ran INTO: first touch between
    `pre` 5m bars before the first breach of the swept level and the extreme, known before that touch, at most AGE old,
    and the extreme no deeper than tol x ATR(5m) past the far edge."""
    d = z["dir"]; ee = z["ext_i"]; sb = z["sweep_i"]; ext = z["ext_d"] * d; at = z["atr_ext"]
    kind, tol, pre = Q.get("zone", "body"), Q.get("tol", 0.5), Q.get("pre", 12)
    hits = []
    for tf in Q["tfs"]:
        I = ob_index(M, tf, kind)
        X = I[d]
        a = int(np.searchsorted(X["mit_sorted"], sb - pre)); b = int(np.searchsorted(X["mit_sorted"], ee, side="right"))
        for j in X["by_mit"][a:b]:
            if ee - X["k5"][j] > AGE[tf]:
                continue
            if Q.get("only") == "extreme" and not X["ext"][j]:
                continue
            if Q.get("only") == "decisional" and X["ext"][j]:
                continue
            if Q.get("swept") and not X["swept"][j]:
                continue
            if Q.get("peak") and not X["ob"][j].get("peak"):
                continue
            if Q.get("fvg_adj") and not X["ob"][j].get("fvg_adj"):
                continue
            if (d == 1 and ext < X["bot"][j] - tol * at) or (d == -1 and ext > X["top"][j] + tol * at):
                continue
            if Q.get("clean_liq") and liq_beyond(M, z, X["bot"][j] if d == 1 else X["top"][j], Q["clean_liq"]):
                continue
            if Q.get("clean_fvg") and fvg_beyond(M, z, tf, X["bot"][j] if d == 1 else X["top"][j], Q["clean_fvg"]):
                continue
            hits.append((tf, "ob", int(j)))
        if Q.get("breaker"):
            Y = I[-d]                       # a failed opposite block = a breaker of the trade's direction
            a = int(np.searchsorted(Y["bmit_sorted"], sb - pre)); b = int(np.searchsorted(Y["bmit_sorted"], ee, side="right"))
            for j in Y["by_bmit"][a:b]:
                if ee - Y["brk5"][j] > AGE[tf]:
                    continue
                if (d == 1 and ext < Y["bot"][j] - tol * at) or (d == -1 and ext > Y["top"][j] + tol * at):
                    continue
                hits.append((tf, "breaker", int(j)))
    return hits


def liq_beyond(M, z, distal, k_atr):
    """Chapter 12 'liquidity beyond the zone': a LIT level of the swept side (session box, PDL/PWL/PML, gap edge, build-up),
    known before the extreme and still untaken at the extreme, within k_atr x ATR beyond the block's far edge."""
    d = z["dir"]; ee = z["ext_i"]; at = z["atr_ext"]
    lo_d = M.l if d == 1 else -M.h
    dist_d = distal * d
    for side, px, ki, nm, cls in M.levels(z["k"]):
        if (side == "low") != (d == 1) or ki >= ee:
            continue
        p = px * d
        if not (dist_d - k_atr * at <= p < dist_d):
            continue
        st = max(int(ki), M.ctx[z["k"]]["s"] - 600)
        if lo_d[st + 1:ee + 1].min() >= p:
            return True
    return False


_FV = {}


def fvgs(M, tf):
    """FVGs of tf from the 5m file: arrays lo, hi, k5 (known at that 5m close)."""
    if tf not in _FV:
        B = htf(M, tf)
        h, l = B["h"], B["l"]
        j = np.arange(2, len(h))
        up = l[j] > h[j - 2]; dn = h[j] < l[j - 2]
        lo = np.r_[h[j - 2][up], h[j][dn]]; hi = np.r_[l[j][up], l[j - 2][dn]]
        k5 = np.r_[B["last"][j][up], B["last"][j][dn]]
        o = np.argsort(k5, kind="stable")
        _FV[tf] = (lo[o], hi[o], k5[o])
    return _FV[tf]


def fvg_beyond(M, z, tf, distal, k_atr):
    """Chapter 12 'imbalance beyond the zone': an FVG of the block's timeframe, known before the extreme, lying within k_atr x
    ATR beyond the block's far edge and not yet fully traded through by the extreme (price may still want it: the expected
    mitigation would pass through the stop)."""
    d = z["dir"]; ee = z["ext_i"]; at = z["atr_ext"]
    lo, hi, k5 = fvgs(M, tf)
    b = int(np.searchsorted(k5, ee))
    a = int(np.searchsorted(k5, ee - AGE[tf]))
    for q in range(a, b):
        if d == 1:
            if not (distal - k_atr * at <= hi[q] <= distal):
                continue
            if M.l[k5[q] + 1:ee + 1].min() > lo[q]:
                return True
        else:
            if not (distal <= lo[q] <= distal + k_atr * at):
                continue
            if M.h[k5[q] + 1:ee + 1].max() < hi[q]:
                return True
    return False


def poi_dist(M, z, Q):
    """ATR(5m) distance from the sweep extreme to the nearest block of the trade's direction that was fresh when the sweep
    leg started (0 = the extreme is inside one); inf = none within AGE."""
    d = z["dir"]; ee = z["ext_i"]; t0 = z["sweep_i"] - Q.get("pre", 12); ext = z["ext_d"] * d; at = max(z["atr_ext"], 1e-9)
    best = np.inf
    for tf in Q["tfs"]:
        X = ob_index(M, tf, Q.get("zone", "body"))[d]
        m = (X["k5"] < t0) & (X["mit5"] >= t0) & (ee - X["k5"] <= AGE[tf])
        if not m.any():
            continue
        top, bot = X["top"][m], X["bot"][m]
        dist = np.where((ext >= bot) & (ext <= top), 0.0, np.minimum(np.abs(ext - top), np.abs(ext - bot)))
        best = min(best, float(dist.min()) / at)
    return best


def opp_dists(M, z, ep, Q, i=None):
    """Distances (direction space, from the limit price ep) to the proximal edge of every opposing block that is fresh at the
    trigger bar i and lies beyond ep, nearest first."""
    d = z["dir"]; i = z["i"] if i is None else i
    out = []
    for tf in Q["tfs"]:
        Y = ob_index(M, tf, Q.get("zone", "body"))[-d]
        m = (Y["k5"] <= i) & (Y["mit5"] > i) & (i - Y["k5"] <= AGE[tf])
        if not m.any():
            continue
        prox = (Y["bot"][m] if d == 1 else -Y["top"][m])      # direction space
        dist = prox - ep
        out.extend(float(x) for x in dist[dist > 0])
    return sorted(out)


def cisd_block(M, z):
    """The 5m block that made the 5m CISD: the down-close run into the extreme (direction space). body top = the CISD level
    (today's limit), body bottom, wick top / bottom of the run."""
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)
    ee, st = z["ext_i"], z["ref_i"]
    j = ee
    while j > ee - 3 and not (c_d[j] < o_d[j]):
        j -= 1
    seg = slice(st, j + 1)
    top = float(o_d[st]); bot = float(np.minimum(o_d[seg], c_d[seg]).min())
    return {"top": top, "bot": bot, "mt": 0.5 * (top + bot), "wtop": float(hi_d[seg].max()), "wbot": float(lo_d[seg].min()),
            "wmt": 0.5 * (float(hi_d[seg].max()) + float(lo_d[seg].min()))}


# ================================================================================================ OB-only setups
class _OBM:
    """engine.lit.Market whose liquidity levels are the proximal edges of fresh HTF blocks (OB-only setups)."""

    def __init__(self, M, lv):
        self._M, self._lv = M, lv

    def __getattr__(self, k):
        return getattr(self._M, k)

    def levels(self, k):
        return self._lv.get(k, [])


_OC = {}


def ob_cands(M, tfs=("1h", "4h"), kind="body"):
    """LIT candidates (engine.lit.candidates, unchanged) where the 'swept liquidity' is the proximal edge of a fresh HTF block:
    price trades INTO the block (first touch = the sweep), then the inducement / displacement / 5m CISD rules as usual."""
    key = (tuple(tfs), kind)
    if key in _OC:
        return _OC[key]
    p = os.path.join(CACHE, f"lit_ob_cands_{'-'.join(tfs)}_{kind}_v1_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        _OC[key] = pickle.load(open(p, "rb"))
        return _OC[key]
    lv = collections.defaultdict(list)
    names = {}
    for tf in tfs:
        for q, ob in enumerate(blocks(M, tf, None, kind)):
            k5, m5 = ob["k5"], ob["mit5"]
            endk = min(m5 if m5 is not None else INF, k5 + AGE[tf], M.n - 1)
            nm = f"ob{tf}#{q}"
            names[nm] = (ob["dir"], ob["top"], ob["bot"], tf)
            prox = ob["top"] if ob["dir"] == 1 else ob["bot"]
            for k in range(int(M.day_of[k5]), int(M.day_of[endk]) + 1):
                lv[k].append(("low" if ob["dir"] == 1 else "high", float(prox), int(k5), nm, "ob"))
    C2 = lit.candidates(_OBM(M, lv), ref=LIVE["ref"])
    for z in C2:
        z["src"] = "ob"
        z["ob_names"] = [n for n in z["swept"] if n in names]
        z["ob_zones"] = [names[n] for n in z["ob_names"]]
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(C2, open(p, "wb"))
    _OC[key] = C2
    return C2


def ob_inside_cands(M, tfs=("1h", "4h", "1d"), kind="body", visit=72):
    """LIT candidates for a sweep INSIDE a fresh HTF block: once price first enters the block, every 5m swing low it makes
    inside the zone (during that first visit: within `visit` 5m bars of the first touch, no 5m close beyond the far edge) is a
    liquidity level; engine.lit.candidates then needs the usual sweep of that internal low + inducement + displacement +
    5m CISD. Mirror for shorts (swing highs inside a bearish block)."""
    key = ("in", tuple(tfs), kind, visit)
    if key in _OC:
        return _OC[key]
    p = os.path.join(CACHE, f"lit_ob_inside_{'-'.join(tfs)}_{kind}_{visit}_v1_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        _OC[key] = pickle.load(open(p, "rb"))
        return _OC[key]
    lv = collections.defaultdict(list)
    names = {}
    for tf in tfs:
        for q, ob in enumerate(blocks(M, tf, None, kind)):
            m5 = ob["mit5"]
            if m5 is None or m5 - ob["k5"] > AGE[tf]:
                continue
            d, top, bot = ob["dir"], ob["top"], ob["bot"]
            end = min(M.n - 3, m5 + visit)
            cl = M.c[m5:end + 1]
            dead = np.flatnonzero(cl < bot) if d == 1 else np.flatnonzero(cl > top)
            if len(dead):
                end = m5 + int(dead[0])
            sw = M.fl if d == 1 else M.fh
            a = int(np.searchsorted(sw, m5)); b = int(np.searchsorted(sw, end, side="right"))
            for f in sw[a:b]:
                f = int(f)
                px = float(M.l[f] if d == 1 else M.h[f])
                if not (bot <= px <= top):
                    continue
                nm = f"obin{tf}#{q}@{f}"
                names[nm] = (d, top, bot, tf)
                for k in range(int(M.day_of[f + 2]), min(len(M.days) - 1, int(M.day_of[f + 2]) + 1) + 1):
                    lv[k].append(("low" if d == 1 else "high", px, f + 2, nm, "obin"))
    C2 = lit.candidates(_OBM(M, lv), ref=LIVE["ref"])
    for z in C2:
        z["src"] = "obin"
        z["ob_names"] = [n for n in z["swept"] if n in names]
        z["ob_zones"] = [names[n] for n in z["ob_names"]]
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(C2, open(p, "wb"))
    _OC[key] = C2
    return C2


# ================================================================================================ executor (unit size)
def osim(M, B, z, entry_px, tgt_lvl, fb, stop0, P, e1=None):
    """tools/lit_tightstop.tsim (stop 1 tick beyond the sweep extreme) with one option: e1 = {"level": "edge" | "mt",
    "x": share} = after the 1m CISD, a limit at the 1m block (the down-close 1m run into the 1m low; edge = its body top =
    the 1m CISD level, mt = the middle of its body) when that level is within x of the stop distance from the confirming
    close, valid e1 "wait" 1m bars (cancelled if the target trades or the extreme breaks); else the next 1m open (today)."""
    if e1 is None:
        return T.tsim(M, B, z, entry_px, tgt_lvl, fb, stop0, P)
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]; wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    limit_fill, fill, tapped, kconf, lowk = True, None, None, None, None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop0:
            break
        if tapped is None and lo_d[k] <= entry_px:
            tapped = k
        if tapped is None and hi_d[k] >= tgt_lvl:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                kconf = k
                break
        k += 1
    if kconf is None:
        return None
    cz = lit._cisd_level(c_d, o_d, lowk)
    st1 = cz[1]
    j = lowk
    while j > lowk - 3 and not (c_d[j] < o_d[j]):
        j -= 1
    top = float(o_d[st1]); bot = float(np.minimum(o_d[st1:j + 1], c_d[st1:j + 1]).min()) if j >= st1 else top
    L = top if e1["level"] == "edge" else 0.5 * (top + bot)
    L = min(L, float(c_d[kconf]))
    near = (float(c_d[kconf]) - L) <= e1["x"] * (float(c_d[kconf]) - stop0) and L > stop0
    e_px = None
    if not near:
        fill = kconf + 1; entry = float(o_d[kconf + 1]) + SLIP; limit_fill = False
    else:
        e_px = L
        for b in range(kconf + 1, min(B.n, kconf + 1 + e1.get("wait", 10))):
            if B.day[b] != s_day or B.mod[b] >= flat or B.mod[b] >= 1080:
                break
            if lo_d[b] <= stop0:
                break
            if lo_d[b] <= L:
                fill = b; entry = min(L, float(o_d[b])); limit_fill = True
                break
            if hi_d[b] >= tgt_lvl:
                break
        if fill is None:
            return None
    risk = entry - stop0
    if risk <= 0 or lit.qty_for(risk) < 1:
        return None
    if fb:
        tg = entry + P["fallback_rr"] * risk
    else:
        dist = tgt_lvl - entry
        if dist < P["min_rr"] * risk:
            return None
        tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    be_d = None if P["be_r"] is None else P["be_r"] * risk
    cur, be_done, mfe, mae, worst = stop0, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_d is not None and not be_done and hi_d[k] >= entry + be_d:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "risk0": round(risk, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False, "stop_src": "ext",
            "entry_px": round(entry * d, 2), "stop_px": round(stop0 * d, 2), "stop0_px": round(stop0 * d, 2),
            "target_px": round(tg * d, 2), "e2_px": round(e_px * d, 2) if e_px is not None else None,
            "limit_fill": limit_fill, "swept": z["swept"], "tf": B.secs // 60, "i": z["i"], "ext_i": z["ext_i"]}


# ================================================================================================ the run loop
OBDEF = {"poi": None, "obt": None, "obx": None, "obe": None, "obe1": None, "obonly": None}


def orun(P=None, sessions=SESS):
    """Unit-size trades of one OB variant on the live LIT settings (tools/lit_tightstop.trun + the OB hooks)."""
    P = {**T.P_of(), **OBDEF, **(P or {})}
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = market()
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    Q5 = P["obonly"]
    if Q5:
        main = {(z["day"], z["dir"], z["ext_i"]) for z in C
                if lit.setup_ok(z, P, names) and not (P.get("monday") and lit.monday_block(M, z))}
        src_c = (ob_inside_cands(M, Q5["tfs"], Q5.get("zone", "body")) if Q5.get("mode") == "inside" else
                 ob_cands(M, Q5["tfs"], Q5.get("zone", "body")))
        C2 = [z for z in src_c if (z["day"], z["dir"], z["ext_i"]) not in main]
        if Q5.get("mode") == "inside" and Q5.get("both"):
            C2 += [z for z in ob_cands(M, Q5["tfs"], Q5.get("zone", "body")) if (z["day"], z["dir"], z["ext_i"]) not in main]
        C = sorted(list(C) + C2, key=lambda z: (z["entry_t"], -z["dir"]))
    out, busy, per_day = [], -1, collections.Counter()
    day_ob = collections.Counter()
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        src = z.get("src", "main")
        cap = P["max_per_day"] + (1 if (Q5 and Q5.get("second") and src != "main") else 0)
        if z["entry_i"] <= busy or per_day[z["day"]] >= cap:
            continue
        if Q5 and Q5.get("second") and src != "main" and day_ob[z["day"]]:
            continue                        # at most one OB trade a day
        if Q5 and Q5.get("second") and src == "main" and per_day[z["day"]] - day_ob[z["day"]] >= 1:
            continue                        # the main model keeps its one trade a day
        if src in ("ob", "obin"):
            if not lit.setup_ok(z, {**P, "depth": Q5.get("depth", 0.0), "disp": Q5.get("disp", P["disp"])}, None):
                continue
            tol = Q5.get("tol", 0.5) * z["atr_ext"]
            ext = z["ext_d"] * z["dir"]
            if not any((dd == 1 and ext >= bt - tol) or (dd == -1 and ext <= tp + tol) for dd, tp, bt, _ in z["ob_zones"]):
                continue
            if Q5.get("peak") or Q5.get("fvg_adj") or Q5.get("clean_liq"):
                ok = False
                for nm_ in z["ob_names"]:
                    ob_ = block_of(M, nm_, Q5.get("zone", "body"))
                    if Q5.get("peak") and not ob_.get("peak"):
                        continue
                    if Q5.get("fvg_adj") and not ob_.get("fvg_adj"):
                        continue
                    if Q5.get("clean_liq") and liq_beyond(M, z, ob_["bot"] if ob_["dir"] == 1 else ob_["top"], Q5["clean_liq"]):
                        continue
                    ok = True; break
                if not ok:
                    continue
        elif not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        mult, why = 1.0, []
        Q = P["poi"]
        hits = None
        if Q:
            hits = poi_hits(M, z, Q)
            md = Q.get("mode", "require")
            if md == "require" and not hits:
                continue
            if md == "size" and hits:
                mult *= Q["mult"]; why.append("poi")
            if md in ("skip_far", "half_far"):
                if poi_dist(M, z, Q) > Q["far"]:
                    if md == "skip_far":
                        continue
                    mult *= Q.get("mult", 0.5); why.append("far")
            if md == "half_without" and not hits:
                mult *= Q.get("mult", 0.5); why.append("no poi")
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        classes = list(P["classes"])
        Qt = P["obt"]
        if Qt:
            od = opp_dists(M, z, ep, Qt)
            TT["obt"] = od
            classes = ["obt"] if Qt.get("pick") == "alone" else classes + ["obt"]
        best = None
        for c in classes:
            mr = (Qt.get("min_r", P["min_rr"]) if (Qt and c == "obt") else P["min_rr"])
            for dist in sorted(TT.get(c, [])):
                if dist >= mr * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        Qx = P["obx"]
        if Qx:
            od = opp_dists(M, z, ep, Qx)
            if od and od[0] < Qx.get("rr", 1.5) * risk:
                if Qx.get("mode", "skip") == "skip":
                    continue
                mult *= Qx.get("mult", 0.5); why.append("obstacle")
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        ep_use, Pu = ep, P
        Qe = P["obe"]
        if Qe:
            cb = cisd_block(M, z)
            L = cb[Qe["level"]]
            if (ep - L) <= Qe["x"] * (ep - stop0) and L - stop0 >= P["min_stop"] and L != ep:
                ep_use = min(L, z["trig_c"])
                if Qe.get("how") == "limit":
                    Pu = {**P, "cisd1m": None}
        t = osim(M, B, z, ep_use, ep + tp, fb, stop0, Pu, P["obe1"])
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        day_ob[z["day"]] += src != "main"
        t["ob_m"] = mult; t["ob_why"] = why; t["src"] = src
        t["poi"] = list(hits) if hits else []
        out.append(t)
    return out


# ================================================================================================ scoring (both live sizes)
EVAL = ("lit", 800, 25.0)
ROOM = 0.6
_orig_qty_of = T.qty_of


def _qty_capped(t, rule, room=None, room_k=None):
    """tools/lit_tightstop.qty_of (weekly stop x OB multiplier in one rounding, room cap) with the 40-micro cap restored for
    size-ups (> 1)."""
    mi, mn = _orig_qty_of(t, rule, room, room_k)
    return min(mi, MAXQ), mn


T.qty_of = _qty_capped
TWC = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing", {}).get("two_week") or \
    {"base": "need", "need_buf": 1.0, "room_f": 0.6, "wk": False, "dll_cap": True, "stop_at_target": True}


def marks(U):
    T.wk_marks(U)
    for t in U:
        t["wk_raw"] = t["wk_m"]
        t["wk_m"] = t["wk_m"] * t.get("ob_m", 1.0)
    return U


def tw_by(U):
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        tg = abs(float(t["target_px"]) - float(t["entry_px"]))
        by[t["day"]].append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "risk": t["risk_pts"],
                             "tgt": round(tg, 2), "pts": float(t["legs"][0][1]), "w1": float(t["w1"]), "exit": t["exit"],
                             "wk_m": t.get("wk_raw", 1.0), "size_mult": t.get("ob_m", 1.0), "tf": t["tf"]})
    return [by.get(s, []) for s in SESS]


def tw_score(U, cfg=None, spans=("H1", "H2", "2026", "2021-25")):
    """two_week mode: a fresh eval on every session of the span (only starts that can see 10 / 20 sessions count), plus the
    back-to-back path (a new eval after a pass, a fail or 10 sessions) for the $ columns."""
    from tools import lit_2wk as L2
    cfg = dict(cfg or TWC)
    if any(t.get("ob_m", 1.0) < 1 for t in U):
        cfg["wk"] = True                    # size_mult = the OB multiplier only (config C ignores the weekly stop)
    by = tw_by(U)
    out = {}
    for sp in spans:
        a0, z0 = SPAN[sp]
        ix = [i for i, d in enumerate(SESS) if a0 <= d <= z0]
        a, z = ix[0], ix[-1] + 1
        res = [L2.run_eval(cfg, list(range(i, min(z, i + 20))), by, "50k", 20) for i in range(a, z)]
        o = L2.summarize(res, "50k", [z - i for i in range(a, z)])
        k, path, n = a, [], collections.Counter()
        while k < z:
            r, used, _, _ = L2.run_eval(cfg, list(range(k, min(z, k + 10))), by, "50k", 10, keep=path)
            if r == "OPEN" and k + used >= z and used < 10:
                break
            n[r] += 1; k += used
        st = T.stats(path, sp)
        out[sp] = {**st, "p10": o["p10"], "f10": o["f10"], "p20": o["p20"], "f20": o["f20"], "pass_med": o["pass_med"],
                   "cost": o["cost"], "n10": o["n10"], "b2b": f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}"}
    return out, path


def ev_score(U):
    return T.score(U, EVAL, room_k=ROOM)


def both(U):
    return {"eval": ev_score(U), "two_week": tw_score(U)[0]}


def line(o, sp):
    s = o.get(sp) or {}
    if not s.get("n"):
        return "n=0"
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
            f"2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']}")


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        _U[key] = marks(orun(P))
    return _U[key]


def check():
    U = unit()
    T0 = T.sized([dict(t, wk_m=t["wk_raw"]) for t in U], ("lit", 800, 20.0))
    n26 = [t for t in T0 if t["day"] >= "2026"]
    print(f"lit_ob no-OB run: {len(T0)} trades, 2026 {len(n26)} net {sum(t['pnl'] for t in n26):+,.0f} (run lit_live: 120, +41,734)")
    o = both(U)
    for m in ("eval", "two_week"):
        for sp in ("H1", "H2", "2021-25"):
            print(m, sp, line(o[m], sp))
    return len(n26) == 120 and abs(sum(t["pnl"] for t in n26) - 41734) < 2


# ================================================================================================ the grid
H3 = ["15m", "1h", "4h"]
H2T = ["1h", "4h"]


def variants():
    V = collections.OrderedDict()
    V["base: live LIT"] = {}
    # ---- 2. OB as the point of interest
    poi = {"tfs": H3, "zone": "body", "pre": 36, "tol": 1.0}
    V["POI require 15m/1h/4h body"] = {"poi": {**poi, "mode": "require"}}
    V["POI require 15m/1h/4h wick"] = {"poi": {**poi, "zone": "wick", "mode": "require"}}
    V["POI require 1h/4h body"] = {"poi": {**poi, "tfs": H2T, "mode": "require"}}
    V["POI require loose (3h-6h leg, 2 ATR)"] = {"poi": {**poi, "pre": 72, "tol": 2.0, "mode": "require"}}
    V["POI require + breakers"] = {"poi": {**poi, "breaker": True, "mode": "require"}}
    V["POI require extreme OB only"] = {"poi": {**poi, "only": "extreme", "pre": 72, "tol": 2.0, "mode": "require"}}
    V["POI require decisional OB only"] = {"poi": {**poi, "only": "decisional", "pre": 72, "tol": 2.0, "mode": "require"}}
    V["POI x1.25 when present"] = {"poi": {**poi, "mode": "size", "mult": 1.25}}
    V["POI x1.5 when present"] = {"poi": {**poi, "mode": "size", "mult": 1.5}}
    V["POI x1.5 when present (loose)"] = {"poi": {**poi, "pre": 72, "tol": 2.0, "mode": "size", "mult": 1.5}}
    V["POI x1.25 when present (wick, loose)"] = {"poi": {**poi, "zone": "wick", "pre": 72, "tol": 2.0, "mode": "size", "mult": 1.25}}
    V["POI half size without one"] = {"poi": {**poi, "mode": "half_without", "mult": 0.5}}
    V["POI skip when > 1 ATR from any fresh HTF OB"] = {"poi": {**poi, "mode": "skip_far", "far": 1.0}}
    V["POI skip when > 3 ATR from any fresh HTF OB"] = {"poi": {**poi, "mode": "skip_far", "far": 3.0}}
    V["POI half when > 3 ATR from any fresh HTF OB"] = {"poi": {**poi, "mode": "half_far", "far": 3.0, "mult": 0.5}}
    # ---- 3. OB as the entry
    for lv, nm in (("mt", "5m OB mean threshold"), ("wmt", "5m OB wick middle")):
        for x in (0.25, 0.5):
            V[f"entry {nm} (tap + 1m CISD) if within {x:g} of the stop"] = {"obe": {"level": lv, "x": x, "how": "tap"}}
        V[f"entry {nm} (plain limit) if within 0.5 of the stop"] = {"obe": {"level": lv, "x": 0.5, "how": "limit"}}
    V["entry 5m OB wick top (shallower tap)"] = {"obe": {"level": "wtop", "x": 1.0, "how": "tap"}}
    for lv, nm in (("edge", "1m OB body edge"), ("mt", "1m OB mean threshold")):
        for x in (0.15, 0.3):
            V[f"entry {nm} after the 1m CISD if within {x:g} of the stop"] = {"obe1": {"level": lv, "x": x, "wait": 10}}
    # ---- 4. OB as the target / obstacle
    V["target opposing 1h/4h OB alone"] = {"obt": {"tfs": H2T, "pick": "alone"}}
    V["target opposing 15m/1h/4h OB alone"] = {"obt": {"tfs": H3, "pick": "alone"}}
    V["target nearer of 1h/4h OB and VIX band"] = {"obt": {"tfs": H2T, "pick": "nearer"}}
    V["target nearer of 15m/1h/4h OB and VIX band"] = {"obt": {"tfs": H3, "pick": "nearer"}}
    V["obstacle skip: opposing 1h/4h OB < 1.5R"] = {"obx": {"tfs": H2T, "rr": 1.5, "mode": "skip"}}
    V["obstacle skip: opposing 15m/1h/4h OB < 1.5R"] = {"obx": {"tfs": H3, "rr": 1.5, "mode": "skip"}}
    V["obstacle half: opposing 1h/4h OB < 1.5R"] = {"obx": {"tfs": H2T, "rr": 1.5, "mode": "half", "mult": 0.5}}
    V["obstacle half: opposing 15m/1h/4h OB < 1.5R"] = {"obx": {"tfs": H3, "rr": 1.5, "mode": "half", "mult": 0.5}}
    # ---- chapter 12 of the second report (qualify the origin, one job per block, first opposition)
    lo_ = {"tfs": H3, "zone": "body", "pre": 72, "tol": 2.0}
    V["ch12 POI x1.5, origin took liquidity"] = {"poi": {**lo_, "swept": True, "mode": "size", "mult": 1.5}}
    V["ch12 POI x1.5, no liquidity beyond the zone"] = {"poi": {**lo_, "clean_liq": 2.0, "mode": "size", "mult": 1.5}}
    V["ch12 POI x1.5, no imbalance beyond the zone"] = {"poi": {**lo_, "clean_fvg": 2.0, "mode": "size", "mult": 1.5}}
    V["ch12 POI x1.5, all origin checks"] = {"poi": {**lo_, "swept": True, "clean_liq": 2.0, "clean_fvg": 2.0, "mode": "size", "mult": 1.5}}
    V["ch12 POI require, all origin checks"] = {"poi": {**lo_, "swept": True, "clean_liq": 2.0, "clean_fvg": 2.0, "mode": "require"}}
    V["ch12 POI half without a clean POI"] = {"poi": {**lo_, "clean_liq": 2.0, "clean_fvg": 2.0, "mode": "half_without", "mult": 0.5}}
    V["ch12 target first opposition 15m/1h/4h if >= 1R, else VIX"] = {"obt": {"tfs": H3, "pick": "nearer", "min_r": 1.0}}
    V["ch12 target first opposition 1h/4h if >= 1R, else VIX"] = {"obt": {"tfs": H2T, "pick": "nearer", "min_r": 1.0}}
    # ---- neighbours of the obstacle rule (the one OB idea that helped the live two_week mode in H1)
    for tfs, tn in ((H3, "15m/1h/4h"), (["15m"], "15m"), (["15m", "1h"], "15m/1h")):
        for rr in (1.0, 1.5, 2.0):
            nm = f"obstacle skip: opposing {tn} OB < {rr:g}R"
            if nm not in V:
                V[nm] = {"obx": {"tfs": tfs, "rr": rr, "mode": "skip"}}
    for rr in (2.5, 3.0):
        V[f"obstacle skip: opposing 15m/1h OB < {rr:g}R"] = {"obx": {"tfs": ["15m", "1h"], "rr": rr, "mode": "skip"}}
    V["obstacle half: opposing 15m/1h OB < 2R"] = {"obx": {"tfs": ["15m", "1h"], "rr": 2.0, "mode": "half", "mult": 0.5}}
    V["obstacle skip: opposing 15m/1h/4h OB (wick zone) < 1.5R"] = {"obx": {"tfs": H3, "rr": 1.5, "mode": "skip", "zone": "wick"}}
    # ---- 5. OB-only setups (extra setup type)
    for tfs, tn in ((H2T, "1h/4h"), (H3, "15m/1h/4h")):
        for dp in (0.0, 0.25):
            for tol in (0.5, 1.0):
                V[f"OB-only setups {tn} depth {dp:g} tol {tol:g}"] = {"obonly": {"tfs": tfs, "depth": dp, "tol": tol}}
    # ---- owner 2026-10-18 (evening): HTF blocks incl. daily as LIT POIs and as an extra entry source
    H4 = ["1h", "4h", "1d"]
    V["POI require loose 1h/4h/1d"] = {"poi": {"tfs": H4, "zone": "body", "pre": 72, "tol": 2.0, "mode": "require"}}
    V["POI require loose 15m/1h/4h/1d"] = {"poi": {"tfs": H3 + ["1d"], "zone": "body", "pre": 72, "tol": 2.0, "mode": "require"}}
    for tfs, tn in ((H4, "1h/4h/1d"), (H3 + ["1d"], "15m/1h/4h/1d")):
        V[f"OB-only setups {tn} depth 0 tol 1"] = {"obonly": {"tfs": tfs, "depth": 0.0, "tol": 1.0}}
        for dp in (0.25, 0.5):
            V[f"OB-inside setups {tn} depth {dp:g}"] = {"obonly": {"tfs": tfs, "mode": "inside", "depth": dp, "tol": 1.0}}
        V[f"OB-inside + OB-only setups {tn} depth 0.5"] = {"obonly": {"tfs": tfs, "mode": "inside", "both": True, "depth": 0.5, "tol": 1.0}}
    V["OB setups (into + inside) 15m/1h/4h/1d as a 2nd trade a day"] = {"obonly": {"tfs": H3 + ["1d"], "mode": "inside", "both": True,
                                                                                  "depth": 0.0, "tol": 0.5, "second": True}}
    V["OB setups 15m/1h/4h/1d, displacement 0.5 ATR, as a 2nd trade a day"] = {"obonly": {"tfs": H3 + ["1d"], "mode": "inside", "both": True,
                                                                                     "depth": 0.0, "tol": 0.5, "second": True, "disp": 0.5}}
    # ---- owner's LIT group notes on mitigation (research/lit/owner_lit_notes.md)
    SEC = {"tfs": H3 + ["1d"], "mode": "inside", "both": True, "depth": 0.0, "tol": 0.5, "second": True}
    V["mit: OB setups 2nd trade, initial-BoS (peak) blocks only"] = {"obonly": {**SEC, "peak": True}}
    V["mit: OB setups 2nd trade, FVG right next to the block"] = {"obonly": {**SEC, "fvg_adj": True}}
    V["mit: OB setups 2nd trade, trap rule (no untaken liquidity beyond)"] = {"obonly": {**SEC, "clean_liq": 2.0}}
    V["mit: OB setups 2nd trade, all three"] = {"obonly": {**SEC, "peak": True, "fvg_adj": True, "clean_liq": 2.0}}
    V["mit: OB setups 2nd trade, full mitigation box (wick zone)"] = {"obonly": {**SEC, "zone": "wick"}}
    V["mit: orderflow continuation, 5m/15m OB-inside as 2nd trade"] = {"obonly": {"tfs": ["5m", "15m"], "mode": "inside", "depth": 0.0,
                                                                              "tol": 0.5, "second": True}}
    V["mit: POI require, initial-BoS + FVG next to it + trap rule (loose)"] = {"poi": {"tfs": H3 + ["1d"], "zone": "body", "pre": 72, "tol": 2.0,
                                                                                    "peak": True, "fvg_adj": True, "clean_liq": 2.0, "mode": "require"}}
    V["OB setups (into + inside) 1h/4h/1d as a 2nd trade a day"] = {"obonly": {"tfs": H4, "mode": "inside", "both": True,
                                                                             "depth": 0.0, "tol": 0.5, "second": True}}
    return V


def _load():
    return json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}


def summary(o):
    return {m: {sp: {k: o[m][sp].get(k) for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20",
                                                  "pass_rate", "pass_med", "b2b", "cost", "worst_day", "med_stop")}
                for sp in o[m]} for m in o}


def grid(only=None):
    V = variants()
    res = _load()
    for nm, P in V.items():
        if only and not any(k in nm for k in only):
            continue
        if not only and nm in res and res[nm].get("P") == json.loads(json.dumps(P)):
            continue
        U = unit(P)
        o = summary(both(U))
        o["extra"] = {"n_ob_src": sum(1 for t in U if t.get("src") in ("ob", "obin") and t["day"] >= "2026"),
                      "n_mult": sum(1 for t in U if t.get("ob_m", 1.0) != 1.0 and t["day"] >= "2026"),
                      "n_obe": sum(1 for t in U if t.get("e2_px") is not None and t["day"] >= "2026")}
        res[nm] = {"P": P, **o}
        json.dump(res, open(OUT, "w"), indent=1, default=float)
        b = res.get("base: live LIT")
        dl = ""
        if b and nm != "base: live LIT":
            g = lambda m, sp, k: (o[m][sp].get(k) or 0) - (b[m][sp].get(k) or 0)
            dl = " | d eval H1 {:+,} H2 {:+,} | d 2wk H1 {:+.1f} H2 {:+.1f}".format(
                g("eval", "H1", "net"), g("eval", "H2", "net"), g("two_week", "H1", "p10"), g("two_week", "H2", "p10"))
        w = lambda sp: f"{o['two_week'][sp].get('p10')}/{o['two_week'][sp].get('f10')}"
        print(f"{nm[:62]:62s} EVAL H1[{line(o['eval'], 'H1')}] H2[{line(o['eval'], 'H2')}] | 2WK H1 {w('H1')} H2 {w('H2')} "
              f"{o['extra']}{dl}", flush=True)
    return res


# ================================================================================================ example trades
LOOSE = {"tfs": H3, "zone": "body", "pre": 72, "tol": 2.0, "mode": "size", "mult": 1.0}


def draw_trade(path, M, t, z, hits, title, sub):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    ee, ei = z["ext_i"], int(np.searchsorted(M.t, t["entry_t"], side="right") - 1)
    xi = int(t["exit_i"])
    a = max(0, ee - 70); zz = min(M.n, max(xi, ei) + 25)
    o, h, l, c = M.o[a:zz], M.h[a:zz], M.l[a:zz], M.c[a:zz]
    span = float(h.max() - l.min()) or 1.0
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=110)
    fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    _candles(ax, o, h, l, c)
    tag = lambda x, y, txt, va="center", ha="left", color=INK: ax.text(x, y, txt, fontsize=7.5, color=color, va=va, ha=ha, zorder=8,
                                                                     bbox=dict(facecolor="#fcfcfb", edgecolor="none", alpha=0.85, pad=0.8))
    lo_v, hi_v = float(l.min()), float(h.max())
    for tf, kd, j in hits:
        I = ob_index(M, tf, "body")
        X = I[t["dir"]] if kd == "ob" else I[-t["dir"]]
        ob = X["ob"][j]
        col = BULL if t["dir"] == 1 else BEAR
        x0 = max(ob["k5"] - a, -1) + 0.5
        ax.add_patch(Rectangle((x0, ob["bot"]), zz - a - x0, ob["top"] - ob["bot"], facecolor=col, alpha=0.18, edgecolor=col, lw=1.2, zorder=1))
        tag(max(x0, 0), ob["top"] if t["dir"] == 1 else ob["bot"], f"fresh {tf} {'order block' if kd == 'ob' else 'breaker'} (known {et(M.t[ob['k5']] + 300).strftime('%m-%d %H:%M')})",
            va="bottom" if t["dir"] == 1 else "top")
        lo_v, hi_v = min(lo_v, ob["bot"]), max(hi_v, ob["top"])
    cb = cisd_block(M, z)
    d = t["dir"]
    ax.add_patch(Rectangle((z["ref_i"] - a - 0.45, min(cb["top"], cb["bot"]) * 1 if d == 1 else -max(cb["top"], cb["bot"])),
                           (ee - z["ref_i"]) + 0.9, abs(cb["top"] - cb["bot"]), facecolor="none", edgecolor=MUTED, lw=1.0, ls="--", zorder=2))
    tag(z["ref_i"] - a - 0.45, cb["top"] * d, "5m OB = CISD run", va="bottom" if d == 1 else "top", color=MUTED)
    ax.plot([ee - a], [z["ext_d"] * d], marker="^" if d == 1 else "v", ms=8, color=INK, zorder=7)
    tag(ee - a + 0.8, z["ext_d"] * d, "sweep extreme", va="top" if d == 1 else "bottom")
    x1, x2 = ei - a, xi - a
    for px, lab, ls in ((t["entry_px"], "entry", "-"), (t["stop_px"], "stop", ":"), (t["target_px"], "target", "--")):
        ax.plot([x1, x2 + 0.5], [px, px], color=INK, lw=1.1, ls=ls, zorder=6)
        tag(x2 + 1, px, f"{lab} {px:.2f}")
        lo_v, hi_v = min(lo_v, px), max(hi_v, px)
    n = zz - a
    step = max(1, n // 9)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks); ax.set_xticklabels([et(M.t[a + i]).strftime("%m-%d %H:%M") for i in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED); ax.tick_params(axis="x", colors=MUTED)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_xlim(-1, n + 10)
    pad = 0.05 * (hi_v - lo_v)
    ax.set_ylim(lo_v - pad, hi_v + pad)
    ax.set_title(title + "\n" + sub, fontsize=9.5, color=INK, loc="left")
    fig.text(0.01, 0.012, "5m candles. Shaded = the fresh higher-timeframe order block the sweep ran into (POI). Dashed box = the 5m "
                          "block that made the 5m CISD (its top is the limit). Lines = entry, stop (1 tick beyond the sweep extreme), target.",
             fontsize=7.2, color=MUTED)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def charts(n_each=3):
    """6 live LIT trades of 2026 whose sweep ran into a fresh HTF order block (loose POI definition), 3 winners and 3 losers."""
    M, C = market()
    cz = {(z["day"], z["ext_i"]): z for z in C}
    U = unit({"poi": LOOSE})
    os.makedirs(STUDY, exist_ok=True)
    P26 = [t for t in U if t["day"] >= "2026" and t["poi"]]
    T8 = {(x["day"], x["entry_t"]): x for x in T.sized(U, EVAL)}
    win = sorted([t for t in P26 if t["legs"][0][1] > 0], key=lambda t: -t["legs"][0][1] / t["risk_pts"])[:n_each]
    los = [t for t in P26 if t["exit"] == "STOP"][:n_each]
    out = []
    for lab, L in (("winner", win), ("loser", los)):
        for t in L:
            z = cz[(t["day"], t["ext_i"])]
            r = t["legs"][0][1] / t["risk_pts"]
            x = T8.get((t["day"], t["entry_t"]))
            nm = f"trade_{t['day']}_{'long' if t['dir'] == 1 else 'short'}_{lab}.png"
            tfs = ", ".join(sorted({h[0] for h in t["poi"]}))
            draw_trade(os.path.join(STUDY, nm), M, t, z, t["poi"],
                       f"{t['day']} LIT {'long' if t['dir'] == 1 else 'short'} into a fresh {tfs} order block - {lab} ({t['exit']}, {r:+.2f}R)",
                       f"swept {', '.join(z['swept'])}; stop {t['risk_pts']:.1f} pts; eval size {x['qty'] if x else '?'} micros "
                       f"{('$%+,.0f' % x['pnl']) if x else ''}")
            out.append({"file": nm, "day": t["day"], "dir": t["dir"], "exit": t["exit"], "r": round(r, 2), "poi": [h[:2] for h in t["poi"]]})
    json.dump(out, open(os.path.join(STUDY, "trades_index.json"), "w"), indent=1)
    print("\n".join(x["file"] for x in out))
    return out


# ================================================================================================ store the runs
def _slug(nm):
    import re
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", nm.lower())).strip("_")[:48]


def _h(s):
    if not s or not s.get("n"):
        return "no trades"
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; "
            f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']}")


def save(names=None, status_of=None, why_of=None):
    """rl.save one run per variant: id lit_ob_<slug>, trades = the eval-mode path ($800 up to a 25-pt stop, 60% room cap,
    back-to-back evals) in 2026 + 2021-25; the verdict carries both live sizes (eval and two_week) per half."""
    V = variants()
    res = _load()
    status_of = status_of or {}
    why_of = why_of or {}
    for nm in (names or V):
        P = V[nm]
        U = unit(P)
        Tr = T.evals(U, EVAL, "2026", ROOM)[1] + T.evals(U, EVAL, "2021-25", ROOM)[1]
        Tr = [{k: v for k, v in t.items() if k not in ("legs", "poi")} for t in Tr]
        S = rl.score(Tr, SESS)
        o = res.get(nm) or summary(both(U))
        rid = "lit_ob_" + ("base" if nm.startswith("base") else _slug(nm))
        ver = (f"{why_of.get(nm, '')} EVAL MODE ($800 up to a 25-pt stop + 60% room cap): H1 (pick) {_h(o['eval']['H1'])}; "
               f"H2 (check) {_h(o['eval']['H2'])}; 2021-25 reference {_h(o['eval']['2021-25'])}. TWO_WEEK MODE (live config C, "
               f"fresh eval each session, $ from back-to-back evals reset at 10 sessions): H1 {_h(o['two_week']['H1'])}; "
               f"H2 {_h(o['two_week']['H2'])}; 2021-25 {_h(o['two_week']['2021-25'])}.")
        rl.save(rid, "LIT order blocks: " + nm, "other",
                "Owner order 2026-10-18: order blocks are huge, trade all of LIT - does an order block (POI, entry, target, obstacle, "
                "OB-only setup) improve the live LIT trade in both 2026 halves?",
                params={**LIVE, **P}, sizing={"eval": {"rule": list(EVAL), "room_k": ROOM}, "two_week": TWC}, trades=Tr, scored=S,
                status=status_of.get(nm, "rejected" if not nm.startswith("base") else "info"), verdict=ver,
                notes="tools/lit_ob.py (detector engine/lit_ob.py; run loop = tools/lit_tightstop.trun + OB hooks; no OB option == run "
                      "lit_live trade for trade). Stored trades = eval-mode back-to-back path. Numbers per mode in "
                      "research/lit/ob_results.json. results=" + json.dumps(o, default=float),
                writeup="lit-order-blocks", tags=["lit", "lit_ob"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "grid":
        grid(sys.argv[2:] or None)
    else:
        globals()[cmd]()
