"""Entry facts for every combo-store trade (DESIGN.md). Only bars before the entry bar. -> features.json (gitignored-size ok)."""
import bisect, csv, datetime as dt, json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging; logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import combo_account as C
from engine import lit
from tools import lit_final as lf


def main():
    LP = json.load(open(os.path.join(ROOT, "live_model.json")))["lit"]
    M, CAND = lf.market(LP["ref"], LP["extra_boxes"])
    t, o, h, l, c, mod = M.t, M.o, M.h, M.l, M.c, M.mod
    at = M.atr
    e240 = pd.Series(c).ewm(span=240, adjust=False).mean().values
    e600 = pd.Series(c).ewm(span=600, adjust=False).mean().values
    days = M.days
    starts = np.array([s for _, s, _ in days]); ends = np.array([e for _, _, e in days])
    dclose = np.array([c[e - 1] for _, s, e in days]); drange = np.array([h[s:e].max() - l[s:e].min() for _, s, e in days])
    datr = np.array([at[s:e].mean() for _, s, e in days])
    vd, vc = lit._vix("VIX")
    news = []
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"))):
        if r["impact"] == "high":
            hh, mm = map(int, r["time_et"].split(":")); news.append((r["date"], hh * 60 + mm))
    nby = {}
    for d, m in news:
        nby.setdefault(d, []).append(m)
    cz = {}
    for z in CAND:
        cz.setdefault((z["day"], z["dir"]), []).append(z)
    T = C.trades(); S = C.sessions()
    out = []
    for i, dayT in enumerate(T):
        for tr in dayT:
            if tr["s"] not in ("Z", "A", "B"):
                continue
            k = int(np.searchsorted(t, tr["et"], side="right") - 1)
            j = int(np.searchsorted(starts, k, side="right") - 1)       # trading-day index
            kb = k - 1
            if j < 21 or kb <= starts[j]:
                kb = max(kb, starts[j])
            d = tr["d"]
            sma = dclose[j - 20:j].mean()
            vi = bisect.bisect_left(vd, tr["day"]) - 1
            em = int(mod[k])
            nm = [abs(x - em) for x in nby.get(tr["day"], [])]
            f = {"s": tr["s"], "day": tr["day"], "et": tr["et"], "d": d, "R": tr["pts"] / tr["risk"] if tr["risk"] else 0.0,
                 "pts": tr["pts"], "risk": tr["risk"], "src": tr["src"],
                 "stop_pts": tr["risk"], "stop_atr": tr["risk"] / max(at[kb], 1e-9),
                 "rr": (tr["tgt"] / tr["risk"]) if tr["tgt"] else None,
                 "atr_regime": at[kb] / max(datr[j - 20:j].mean(), 1e-9),
                 "vix": float(vc[vi]) if vi >= 0 else None,
                 "trend_d": 1 if (dclose[j - 1] - sma) * d > 0 else -1,
                 "trend_h": 1 if (e240[kb] - e600[kb]) * d > 0 else -1,
                 "range_adr": (h[starts[j]:k].max() - l[starts[j]:k].min()) / max(drange[j - 14:j].mean(), 1e-9) if k > starts[j] else 0.0,
                 "news_min": min(nm + [240]), "sess": 0 if em < 570 else (1 if em < 720 else 2),
                 "dow": dt.date.fromisoformat(tr["day"]).weekday()}
            if tr["s"] == "Z":
                zz = [z for z in cz.get((tr["day"], d), []) if z["entry_t"] <= tr["et"]]
                z = max(zz, key=lambda z: z["entry_t"]) if zz else None
                f.update(depth=z["depth_atr"] if z else None, disp=z["disp"] if z else None, idm=len(z["idm_a"]) if z else None)
            out.append(f)
    json.dump(out, open(os.path.join(HERE, "features.json"), "w"))
    import collections
    print(len(out), collections.Counter(x["s"] for x in out), "LIT unmatched", sum(1 for x in out if x["s"] == "Z" and x["depth"] is None))


if __name__ == "__main__":
    main()
