"""K7 universe: which Kalshi series are studied, grouped into families, with everything earlier teams covered left out.

Covered before (not redone): crypto (A, B, K4), commodities (another helper), S&P / Nasdaq hourly and daily (A, C, K1), daily high and low
temperatures (C, K1, K3), CPI / payrolls / U3 / GDP / claims / AAA gas and diesel (C, K3, K5), sports GAME / MATCH winners (K4),
K5's public-number series (YouTube, Truth Social, TSA, App Store, Spotify daily, Netflix show rank) and multivariate combos.
    python research/kalshi_edge_K7/universe.py        # prints the pick
"""
import gzip
import json
import os
import re

SERIES_FILE = os.path.join(os.environ.get("KK7_CACHE", "/home/user/kalshi_cache/knew2"), "series_compact.json.gz")

EXCLUDE_CATS = {"Crypto", "Commodities", "Exotics"}
EXCLUDE_RE = re.compile(r"^(KXMVE|KXHIGH|KXLOWT|KXINXU$|KXNASDAQ100U$|KXINX$|KXNASDAQ100$|KXINX15M|KXCPI|KXECONSTATCPI|KXPAYROLL|KXU3$|"
                        r"KXGDP$|KXJOBLESS|KXAAAGAS|KXDIESEL|KXTSAW|KXYTVIEWS|KXTRUTHSOCIAL|KXAPPRANK|KXSPOTIFYD|KXNETFLIXRANKSHOW$|"
                        r".*15M$|.*(GAME|MATCH)$|KXUFCFIGHT|KXBOXING|KXUSDJPY$|KXEURUSD$|KXDJI$)")
FUTURES_CUSTOM = {"KXMENWORLDCUP", "KXMARMAD", "KXMLB", "KXPGATOUR", "KXNASCARRACE", "KXDPWORLDTOUR", "KXWCADVANCE", "KXNEXTTEAMNBA"}
# families (first match wins); sports split into season-long futures and in-game props
FAMILIES = [
    ("mentions", lambda s: s["cat"] == "Mentions"),
    ("politics", lambda s: s["cat"] in ("Politics", "Elections")),
    ("entertainment", lambda s: s["cat"] in ("Entertainment", "Culture", "Social")),
    ("sci_tech_companies", lambda s: s["cat"] in ("Science and Technology", "Companies", "Health", "World", "Transportation", "Business",
                                                  "Education")),
    ("econ_fin_other", lambda s: s["cat"] in ("Economics", "Financials")),
    ("climate_other", lambda s: s["cat"] == "Climate and Weather"),
    ("sports_futures", lambda s: s["cat"] == "Sports" and (s["freq"] == "annual" or s["t"] in FUTURES_CUSTOM)),
    ("sports_props", lambda s: s["cat"] == "Sports"),      # game-level: spreads, totals, player props, set / map winners
]
TOP_PER_FAMILY = {"mentions": 12, "politics": 16, "entertainment": 15, "sci_tech_companies": 12, "econ_fin_other": 12,
                  "climate_other": 8, "sports_futures": 12, "sports_props": 8}


def family_of(s):
    for name, f in FAMILIES:
        if f(s):
            return name
    return None


def load_series():
    with gzip.open(SERIES_FILE, "rt") as fh:
        return json.load(fh)


def pick():
    out = {}
    for s in load_series():
        if s["cat"] in EXCLUDE_CATS or EXCLUDE_RE.match(s["t"]):
            continue
        fam = family_of(s)
        if fam:
            out.setdefault(fam, []).append(s)
    for fam in out:
        out[fam] = sorted(out[fam], key=lambda s: -s["vol"])[:TOP_PER_FAMILY[fam]]
    return out


if __name__ == "__main__":
    P = pick()
    for fam, L in P.items():
        print("==", fam, len(L))
        for s in L:
            print("  %-26s %-9s %13.0f fee x%s  %s" % (s["t"], s["freq"], s["vol"], s["fm"], s["title"][:55]))
