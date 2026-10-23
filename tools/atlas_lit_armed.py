"""LIT's armed-setup windows (2026-10-22, ATLAS): when did the live LIT have a setup ARMED (limit working for 30 min at the
CISD level, or tapped and waiting for its 1m CISD) in each direction?

engine/account_b.py blocks an account B entry while LIT holds, enters or has an armed setup in the OTHER direction
(AccountB.lit_opposite). The research no-hedge rule (tools/second_mix.no_hedge) only knew LIT's filled trades; this
module adds the armed setups, so ATLAS is scored under the real account-B rules.

How: the live LIT replay (tools/lit_final.run on live_model.json "lit", exactly run lit_live) with engine/lit.simulate_x
wrapped: every setup the engine walks (it only walks setups that passed every filter, while LIT is flat and has its trade
of the day left, i.e. what the live loop shows as "setups") gets its window [t0, end):
  t0  = the open of the first bar the limit can fill (the 5m CISD close: the live state shows the setup from then on)
  end = the time the live loop knows the setup is gone: the close of the bar that broke the stop / hit the cancel level /
        confirmed the 1m CISD (= LIT's fill, the trade unit takes over), or the open of the bar where the 30-min limit
        expired / the 1m-CISD wait ran out / the day ended.
A walker that copies simulate_x's loop (no research-only options: no mkt / cisd_nth / entry_delay, which live LIT does
not use) gives the end; it is checked against simulate_x's own result (fill / no fill) on every setup.

    python -X utf8 tools/atlas_lit_armed.py      # -> research/runs/_cache/atlas_lit_armed.pkl + a summary
Paper research only.
"""
from __future__ import annotations

import collections
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache", "atlas_lit_armed.pkl")


def _walk_end(M, B, cand, entry_px, tgt, stop, P):
    """(end time, filled) of simulate_x's setup walk (copied loop; live LIT options only)."""
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    if k0 >= B.n:
        return t0, False
    flat = P["flat_mod"]
    ev = bool(P.get("all_hours"))
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    tapped = None
    k = k0
    sec = B.secs
    while k < B.n:
        if B.day[k] != s_day or lit._late(B.mod[k], flat, ev):
            return int(B.t[k]), False
        if tapped is None and B.t[k] >= t0 + wait_s:
            return int(B.t[k]), False
        if lo_d[k] <= stop:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                return int(B.t[k]), True
            return int(B.t[k]) + sec, False
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                return int(B.t[k]), True
        if tapped is None and hi_d[k] >= tgt_cancel:
            return int(B.t[k]) + sec, False
        if tapped is not None:
            if k - tapped > cis:
                return int(B.t[k]), False
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                return int(B.t[k]) + sec, True
        k += 1
    return int(B.t[B.n - 1]) + sec, False


def build():
    from tools import lit_final as F
    from tools import lit_adopt_combo as AC
    W = []
    orig = lit.simulate_x
    st = collections.Counter()

    def wrap(M, B, cand, entry_px, tgt, stop, P, live=False):
        t = orig(M, B, cand, entry_px, tgt, stop, P, live=live)
        end, filled = _walk_end(M, B, cand, entry_px, tgt, stop, P)
        st["same" if bool(filled) == (t is not None) else "diff"] += 1
        W.append({"day": cand["day"], "dir": int(cand["dir"]), "t0": int(M.t[cand["entry_i"]]), "end": int(end),
                  "filled": t is not None, "confirmed": bool(filled), "entry_t": int(t["entry_t"]) if t is not None else None, "tf": B.secs // 60})
        return t

    lit.simulate_x = wrap
    try:
        T = F.run(AC.LIVE | {"t_check": AC.T15, "be_off": AC.BE_OFF})
    finally:
        lit.simulate_x = orig
    print(f"LIT trades {len(T)}; setups walked {len(W)} ({sum(w['filled'] for w in W)} filled); walker vs simulate_x {dict(st)}",
          flush=True)
    out = {"windows": W, "check": dict(st), "n_trades": len(T)}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    pickle.dump(out, open(CACHE, "wb"))
    return out


_C = {}


def windows():
    if "w" not in _C:
        _C["w"] = pickle.load(open(CACHE, "rb")) if os.path.exists(CACHE) else build()
    return _C["w"]["windows"]


def by_day():
    """day -> list of (dir, t0, end) of setups that were armed (unfilled ones, and filled ones up to their fill)."""
    by = collections.defaultdict(list)
    for w in windows():
        if w["end"] > w["t0"]:
            by[w["day"]].append((w["dir"], w["t0"], w["end"]))
    return by


if __name__ == "__main__":
    o = build()
    W = o["windows"]
    dur = [(w["end"] - w["t0"]) / 60 for w in W if not w["filled"]]
    print(f"unfilled setups {len(dur)}, median armed {np.median(dur):.0f} min, 2026: "
          f"{sum(1 for w in W if w['day'] >= '2026-01-01' and not w['filled'])}")
