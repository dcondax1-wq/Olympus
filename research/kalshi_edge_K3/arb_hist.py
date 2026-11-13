#!/usr/bin/env python3
"""K3 angle 1 (history): internal arbitrage on SETTLED events, from team C's hourly bid/ask closes
(research/kalshi_edge_C/data/snap_*.jsonl.gz, read only; same-timestamp candle closes across the event's markets).

For every event and every hour-before-close offset where ALL the event's markets have a quote:
  range events (strikes tile the line: weather highs/lows, S&P/Nasdaq daily ranges, gas, FX ranges ...):
     buy-all-YES: 100 - sum(yes ask) - fees;  buy-all-NO: sum(yes bid) - 100 - fees   (exactly one bucket pays)
  threshold ladders ("above X", T-strikes): buy YES easy + NO hard when ask(easy) + 100 - bid(hard) < 100
Fees: 0.07 p (1-p), rounded up per order, priced for N_REF contracts per leg. Also the realised payoff check
(the set really paid $1, so the 'arb' is not an artefact of a missing bucket).
Writes data/arb_hist.json.
"""
import glob, gzip, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

N_REF = 100
CDATA = os.path.join(os.path.dirname(kk.HERE), "kalshi_edge_C", "data")


def fpc(p):
    return kk.fee_c(p, N_REF) / N_REF


def tiles(ms):
    lo = [m for m in ms if m["st"] in ("less", "less_or_equal")]
    hi = [m for m in ms if m["st"] in ("greater", "greater_or_equal")]
    mid = sorted([m for m in ms if m["st"] == "between"], key=lambda m: m["fs"])
    if len(lo) != 1 or len(hi) != 1 or len(mid) + 2 != len(ms) or not mid:
        return False
    prev = lo[0]["cs"]
    for m in mid + [hi[0]]:
        f = m["fs"]
        if f is None or prev is None or not (abs(f - prev) < 1e-6 or abs(f - prev - 1) < 1e-6 or abs(f - prev - 0.01) < 1e-6 or abs(f - prev - 0.001) < 1e-7):
            return False
        prev = m.get("cs")
    return True


def main():
    res = {}
    events_out = []
    for fn in sorted(glob.glob(os.path.join(CDATA, "snap_*.jsonl.gz"))):
        ser = os.path.basename(fn)[5:-9]
        rows = [json.loads(l) for l in gzip.open(fn, "rt")]
        ev = defaultdict(list)
        for r in rows:
            ev[r["e"]].append(r)
        st = {"events": len(ev), "range_events": 0, "range_obs": 0, "yes_arb": 0, "no_arb": 0, "yes_gross_pos": 0, "no_gross_pos": 0,
              "sum_ask_med": None, "sum_bid_med": None, "ladder_pairs": 0, "ladder_arb": 0, "ladder_gross_pos": 0, "paid_ok": 0}
        sa, sb = [], []
        for e, ms in ev.items():
            if tiles(ms):
                st["range_events"] += 1
                if sum(1 for m in ms if m["res"] == "yes") == 1:
                    st["paid_ok"] += 1
                offs = set.intersection(*[set(m["q"]) for m in ms])
                for o in offs:
                    qs = [m["q"][o] for m in ms]
                    asks = [q[1] for q in qs]
                    bids = [q[0] for q in qs]
                    if any(a <= 0 or a > 100 for a in asks):
                        continue
                    st["range_obs"] += 1
                    s_a, s_b = sum(asks), sum(bids)
                    sa.append(s_a); sb.append(s_b)
                    g_yes = 100 - s_a
                    n_yes = g_yes - sum(fpc(a) for a in asks if a < 100)
                    g_no = s_b - 100
                    n_no = g_no - sum(fpc(100 - b) for b in bids)
                    if all(a < 100 for a in asks) and g_yes > 0:
                        st["yes_gross_pos"] += 1
                        if n_yes > 0:
                            st["yes_arb"] += 1
                            events_out.append({"s": ser, "e": e, "off_h": o, "k": "yes", "gross_c": g_yes, "net_c": round(n_yes, 2), "vol": [q[2] for q in qs]})
                    if g_no > 0:
                        st["no_gross_pos"] += 1
                        if n_no > 0:
                            st["no_arb"] += 1
                            events_out.append({"s": ser, "e": e, "off_h": o, "k": "no", "gross_c": g_no, "net_c": round(n_no, 2), "vol": [q[2] for q in qs]})
            # threshold ladders
            th = sorted([m for m in ms if m["st"] in ("greater", "greater_or_equal") and m["fs"] is not None and "-T" in m["t"]], key=lambda m: m["fs"])
            if len(th) >= 2 and len({m["fs"] for m in th}) == len(th):
                offs = set.intersection(*[set(m["q"]) for m in th])
                for o in offs:
                    for i in range(len(th)):
                        for j in range(i + 1, len(th)):
                            a = th[i]["q"][o][1]; b = th[j]["q"][o][0]
                            if a <= 0 or a >= 100:
                                continue
                            st["ladder_pairs"] += 1
                            g = b - a
                            if g > 0:
                                st["ladder_gross_pos"] += 1
                                if g - fpc(a) - fpc(100 - b) > 0:
                                    st["ladder_arb"] += 1
                                    events_out.append({"s": ser, "e": e, "off_h": o, "k": "ladder", "gross_c": g,
                                                       "net_c": round(g - fpc(a) - fpc(100 - b), 2), "pair": [th[i]["t"], th[j]["t"]],
                                                       "vol": [th[i]["q"][o][2], th[j]["q"][o][2]]})
        if sa:
            sa.sort(); sb.sort()
            st["sum_ask_med"] = sa[len(sa) // 2]; st["sum_bid_med"] = sb[len(sb) // 2]
            st["sum_ask_p05"] = sa[len(sa) // 20]; st["sum_bid_p95"] = sb[len(sb) * 19 // 20]
        res[ser] = st
    tot = defaultdict(int)
    for s in res.values():
        for k in ("range_events", "range_obs", "yes_arb", "no_arb", "yes_gross_pos", "no_gross_pos", "ladder_pairs", "ladder_arb", "ladder_gross_pos"):
            tot[k] += s[k]
    out = {"note": "hourly candle closes, team C data; fees for 100-contract orders", "total": tot, "by_series": res, "hits": events_out}
    json.dump(out, open(os.path.join(kk.DATA, "arb_hist.json"), "w"), indent=1)
    print(json.dumps(tot))
    for s, v in res.items():
        if v["range_events"] or v["ladder_pairs"]:
            print(s, {k: v[k] for k in ("range_events", "paid_ok", "range_obs", "sum_ask_med", "sum_bid_med", "yes_gross_pos", "yes_arb", "no_gross_pos", "no_arb", "ladder_pairs", "ladder_gross_pos", "ladder_arb")})
    for h in sorted(events_out, key=lambda h: -h["net_c"])[:20]:
        print(h)


if __name__ == "__main__":
    main()
