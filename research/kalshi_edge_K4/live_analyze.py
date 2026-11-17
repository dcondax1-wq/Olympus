#!/usr/bin/env python3
"""K4 live check analysis. (1) Stamp test: fetch the Polymarket prices-history for the windows we recorded live and find
the shift s that best matches history p(stamp) to OUR live midpoint at stamp + s (s < 0 = the print shows an older price,
s > 0 = the stamp is earlier than the moment the price was seen). (2) Real-time lead / lag: correlation of the last 30 s
move on one venue with the next 30 s move on the other (changes, so the two venues' different strikes cancel).
    python research/kalshi_edge_K4/live_analyze.py data/live_<ts>.json
"""
import bisect
import json
import statistics
import sys

from net import CLOB, get


def at(ts, vals, t, tol=4):
    i = bisect.bisect_right(ts, t) - 1
    if i >= 0 and t - ts[i] <= tol:
        return vals[i]
    return None


def corr(a, b):
    if len(a) < 10:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((y - mb) ** 2 for y in b) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None


def main():
    rec = json.load(open(sys.argv[1]))
    out = {}
    for coin in sorted({r["coin"] for r in rec}):
        R = [r for r in rec if r["coin"] == coin and r["pm"] is not None and r["kb"] is not None]
        # (1) stamp test, window by window
        err = {s: [] for s in range(-90, 91, 10)}
        for tok in sorted({r["tok"] for r in R}):
            W = sorted((r["t"], r["pm"]) for r in R if r["tok"] == tok)
            if len(W) < 20:
                continue
            ts, pv = [w[0] for w in W], [w[1] for w in W]
            h = get(CLOB + "/prices-history", {"market": tok, "startTs": int(ts[0]) - 60, "endTs": int(ts[-1]) + 60,
                                               "fidelity": 1}, cache=False)
            for x in (h or {}).get("history", []):
                for s in err:
                    v = at(ts, pv, x["t"] + s)
                    if v is not None:
                        err[s].append(abs(x["p"] - v))
        stamp = {s: (round(statistics.mean(v), 4), len(v)) for s, v in err.items() if v}
        # (2) lead / lag on 30 s changes, same window only
        lead_pk, lead_kp, n = [], [], 0
        for tk in sorted({r["tk"] for r in R}):
            W = sorted((r["t"], r["pm"], (r["kb"] + r["ka"]) / 2) for r in R if r["tk"] == tk)
            ts = [w[0] for w in W]
            P = [w[1] for w in W]
            K = [w[2] for w in W]
            for i, t in enumerate(ts):
                p0, k0 = at(ts, P, t - 30, 5), at(ts, K, t - 30, 5)
                p2, k2 = at(ts, P, t + 30, 5), at(ts, K, t + 30, 5)
                if None in (p0, k0, p2, k2):
                    continue
                lead_pk.append((P[i] - p0, k2 - K[i]))
                lead_kp.append((K[i] - k0, p2 - P[i]))
                n += 1
        out[coin] = {"stamp_shift_mean_abs_gap": stamp,
                     "best_shift_s": min(stamp, key=lambda s: stamp[s][0]) if stamp else None,
                     "corr_poly_past30_vs_kalshi_next30": corr(*zip(*lead_pk)) if lead_pk else None,
                     "corr_kalshi_past30_vs_poly_next30": corr(*zip(*lead_kp)) if lead_kp else None,
                     "n_pairs": n, "snapshots": len(R)}
    print(json.dumps(out, indent=1))
    with open(sys.argv[1].replace(".json", "_analysis.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
