"""ATLAS: LIT's armed-setup windows (tools/atlas_lit_armed.py) == what the live LIT loop shows as armed setups.

engine/account_b.AccountB.lit_opposite blocks a B entry while LIT's state has a setup armed the other way
(state["setups"]["long" / "short"]: limit working, or tapped and waiting for its 1m CISD). The research windows come from a
walker that copies engine/lit.simulate_x's setup loop; on 67 of 1,959 setups the walker says "confirmed" while the
backtest has no trade (the 1m CISD confirmed, then the trade was dropped: target < 1.5R from the real fill, or risk out of
range); the window then ends at that CISD close, the moment the live loop drops the setup. This test polls the live loop
(engine/lit_live.run on cut data, the PC's early mode, as tests/test_lit_live.py) on sampled 2026 setups:
  inside   a poll in the middle of the window shows the setup armed on its side (or LIT already entering)
  after    a poll 65 s after the window's end no longer shows it armed (dropped, or filled: LIT entering / in the trade)
Samples: every "confirmed but no trade" setup of 2026 on 1m bars + a seeded sample of unfilled and filled ones.

    python -X utf8 -m tests.test_atlas_armed [--n 40]
"""
from __future__ import annotations

import os
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.disable(logging.CRITICAL)
from engine import lit_live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402
from tools import atlas_lit_armed as ARM  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 40
    P = {**AC.LIVE, "t_check": AC.T15, "be_off": AC.BE_OFF}
    W = [w for w in ARM.windows() if w["day"] >= "2026-01-02" and w["tf"] == 1 and w["end"] - w["t0"] >= 180]
    diff = [w for w in W if w.get("confirmed") and not w["filled"]]
    rng = random.Random(7)
    unf = [w for w in W if not w["filled"] and not w.get("confirmed")]
    fil = [w for w in W if w["filled"]]
    S = rng.sample(unf, min(n, len(unf))) + rng.sample(fil, min(n // 2, len(fil))) + diff
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= int(min(w["t0"] for w in S)) - 70 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    T5 = df5["time"].values

    def poll(now):
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        jf = int(np.searchsorted(b1.t, now - now % 60))
        forming = (int(b1.t[jf]), float(b1.o[jf])) if jf < len(b1.t) and int(b1.t[jf]) == now - now % 60 else None
        return lit_live.run(cut5, P, one_min=cut1, now=now, forming=forming, early=True)["state"]

    bad_in, bad_out = [], []
    for w in S:
        side = "long" if w["dir"] == 1 else "short"
        mid = (w["t0"] + w["end"]) // 2
        mid = mid - mid % 60 + 5
        st = poll(mid)
        ok_in = bool((st.get("setups") or {}).get(side)) or int((st.get("enter_now") or {}).get("dir") or 0) == w["dir"] \
            or int((st.get("position") or {}).get("dir") or 0) == w["dir"]
        if not ok_in:
            bad_in.append((w["day"], side, w["t0"], w["end"], w["filled"]))
        stb = poll(w["end"] - 55)                    # the last minute of the window: still armed (or entering / in)
        if not (bool((stb.get("setups") or {}).get(side)) or int((stb.get("enter_now") or {}).get("dir") or 0) == w["dir"]
                or int((stb.get("position") or {}).get("dir") or 0) == w["dir"]):
            bad_in.append((w["day"], side, w["t0"], w["end"], w["filled"], "last minute"))
        st2 = poll(w["end"] + 65)
        su = (st2.get("setups") or {}).get(side)
        if su and int(su.get("arm_t") or 0) == w["t0"]:
            bad_out.append((w["day"], side, w["t0"], w["end"], w["filled"]))
    print(f"armed windows vs the live LIT loop: {len(S)} setups ({sum(1 for w in S if not w['filled'])} unfilled); "
          f"inside the window shown armed: {len(S) - len(bad_in)}/{len(S)}; gone after the end: {len(S) - len(bad_out)}/{len(S)}")
    if bad_in:
        print("  not armed inside:", bad_in[:8])
    if bad_out:
        print("  still armed after:", bad_out[:8])
    ok = len(bad_in) <= max(1, len(S) // 20) and len(bad_out) <= max(1, len(S) // 20)
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
