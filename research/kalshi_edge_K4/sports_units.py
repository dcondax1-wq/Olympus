"""K4 sports: turn harvested markets into trade units (market x horizon x side), taker at the ask, fee in.
Horizons (hours relative to the scheduled start; the last hourly candle closing at or before that time):
  pre24 (-24), pre6 (-6), pre1 (-1), start (0, last quote before tip-off), in1 (+1), in2 (+2), in3 (+3).
A side costs the YES ask (buy YES) or 1 - YES bid (buy NO). Spread over 6c skipped; prices outside 2-98c skipped.
"""
import gzip
import json
import os

from lib import pnl_per_dollar

HERE = os.path.dirname(os.path.abspath(__file__))
HOR = {"pre24": -24, "pre6": -6, "pre1": -1, "start": 0, "in1": 1, "in2": 2, "in3": 3}
SPORT = {"KXNBAGAME": "NBA", "KXNFLGAME": "NFL", "KXNHLGAME": "NHL", "KXMLBGAME": "MLB", "KXNCAAFGAME": "NCAAF",
         "KXNCAAMBGAME": "NCAAB", "KXWNBAGAME": "WNBA", "KXATPMATCH": "Tennis", "KXWTAMATCH": "Tennis", "KXUFCFIGHT": "UFC"}


def sport(s):
    return SPORT.get(s, "Soccer")


def load():
    rows = []
    for fn in ("sports_live_KXMLBGAME.json.gz", "sports_hist.json.gz", "sports_live.json.gz"):
        p = os.path.join(HERE, "data", fn)
        if os.path.exists(p):
            x = json.load(gzip.open(p))
            if fn == "sports_live.json.gz":  # its MLB rows used the wrong start offset (48 h; MLB is 72 h); tennis has no start
                x = [r for r in x if r["s"] not in ("KXMLBGAME", "KXATPMATCH", "KXWTAMATCH")]
            rows += x
    seen, out = set(), []
    for r in rows:
        if r["t"] not in seen:
            seen.add(r["t"])
            out.append(r)
    return out


def units(rows, one_per_event=True, max_spread=0.06):
    used = set()
    out = []
    for r in rows:
        if one_per_event and sport(r["s"]) != "Soccer":
            if r["e"] in used:
                continue
            used.add(r["e"])
        c = sorted(x for x in r.get("c") or [] if x[1] is not None and x[2] is not None)
        if not c:
            continue
        for h, off in HOR.items():
            t = r["start"] + off * 3600
            if t >= r["close"]:
                continue  # game already over
            q = [x for x in c if x[0] <= t + 1 and x[0] > t - 3600 * 1.01]
            if not q:
                continue
            _, bid, ask, _, _ = q[-1]
            if ask - bid > max_spread or ask <= bid:
                continue
            for side, p, won in (("yes", ask, r["res"] == "yes"), ("no", 1 - bid, r["res"] == "no")):
                if not 0.02 <= p <= 0.98:
                    continue
                out.append({"sport": sport(r["s"]), "series": r["s"], "h": h, "side": side, "p": round(p, 4), "won": won,
                            "r": pnl_per_dollar(p, won), "cl": r["e"], "ts": r["start"], "t": r["t"]})
    return out


def band(p):
    for lo, hi, name in ((0, .1, "02-10"), (.1, .25, "10-25"), (.25, .4, "25-40"), (.4, .6, "40-60"), (.6, .75, "60-75"),
                         (.75, .9, "75-90"), (.9, .95, "90-95"), (.95, 1.01, "95-98")):
        if lo <= p < hi:
            return name
