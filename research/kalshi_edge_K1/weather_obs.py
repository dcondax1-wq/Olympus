#!/usr/bin/env python3
"""Free, keyless weather truth for the Kalshi daily-high markets (Iowa Environmental Mesonet archives):
  1. every ASOS report (routine + specials) for the station Kalshi settles on: time, temperature, raw METAR
     (the METAR remarks carry the exact tenths-of-a-degree temperature 'T' group and the 6-hour max '1' group);
  2. the NWS Daily Climate Report (CLI) high: the number Kalshi settles on.
Writes cache/wobs.json.gz (gitignored, ~MBs): {city: {"tz_std": h, "obs": [[utc_ts, temp_F_tenths_or_whole, max6h_F_or_null], ...],
                                   "cli": {"YYYY-MM-DD": high_F}}}

    python research/kalshi_edge_K1/weather_obs.py [--since 2024-01-01]
"""
import argparse, csv, gzip, io, json, os, re, sys, time, calendar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk

# Kalshi city code (series suffix) -> (station, standard-time UTC offset). Stations as in team C's mos_fetch.py (checked
# there against each market's rules_primary).
CITIES = {"NY": ("KNYC", -5), "CHI": ("KMDW", -6), "MIA": ("KMIA", -5), "AUS": ("KAUS", -6), "LAX": ("KLAX", -8),
          "DEN": ("KDEN", -7), "PHIL": ("KPHL", -5), "TSFO": ("KSFO", -8), "TPHX": ("KPHX", -7), "TATL": ("KATL", -5),
          "TSEA": ("KSEA", -8), "TBOS": ("KBOS", -5), "TDAL": ("KDFW", -6), "TDC": ("KDCA", -5), "TLV": ("KLAS", -8),
          "THOU": ("KHOU", -6), "TMIN": ("KMSP", -6), "TOKC": ("KOKC", -6), "TNOLA": ("KMSY", -6), "TSATX": ("KSAT", -6)}
IEM = "https://mesonet.agron.iastate.edu"


def c2f(c):
    return c * 9 / 5 + 32


def parse(metar, tmpf):
    """exact temperature from the T group (tenths C) when present, else IEM's tmpf; 6-hour max from the 1snTTT group."""
    t = tmpf
    m = re.search(r"\sT([01])(\d{3})([01])(\d{3})", metar or "")
    if m:
        t = c2f((-1 if m.group(1) == "1" else 1) * int(m.group(2)) / 10)
    mx = None
    m6 = re.search(r"\s1([01])(\d{3})(?=\s|$)", (metar or "").split(" RMK ")[-1] if " RMK " in (metar or "") else "")
    if m6:
        mx = c2f((-1 if m6.group(1) == "1" else 1) * int(m6.group(2)) / 10)
    return t, mx


def fetch_obs(st, since, until):
    y1, m1, d1 = since.split("-")
    y2, m2, d2 = until.split("-")
    u = (f"{IEM}/cgi-bin/request/asos.py?station={st[1:]}&data=tmpf&data=metar&year1={y1}&month1={int(m1)}&day1={int(d1)}"
         f"&year2={y2}&month2={int(m2)}&day2={int(d2)}&tz=Etc/UTC&format=onlycomma&latlon=no&missing=empty&report_type=3&report_type=4")
    txt = kk.get(u, raw=True, gap=3.0)
    out = []
    for r in csv.DictReader(io.StringIO(txt or "")):
        try:
            tm = float(r["tmpf"]) if r.get("tmpf") else None
        except ValueError:
            tm = None
        t, mx = parse(r.get("metar"), tm)
        if t is None and mx is None:
            continue
        ts = calendar.timegm(time.strptime(r["valid"], "%Y-%m-%d %H:%M"))
        out.append([ts, None if t is None else round(t, 2), None if mx is None else round(mx, 2)])
    return out


def fetch_cli(st, years):
    out = {}
    for y in years:
        d = kk.get(f"{IEM}/json/cli.py", {"station": st, "year": y}, gap=3.0)
        for r in (d or {}).get("results", []):
            if isinstance(r.get("high"), (int, float)):
                out[r["valid"]] = r["high"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-01-01")
    ap.add_argument("--until", default=time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400)))
    a = ap.parse_args()
    res = {}
    for city, (st, tz) in CITIES.items():
        obs = []
        y0 = int(a.since[:4])
        for y in range(y0, int(a.until[:4]) + 1):   # one call per year keeps each response small
            lo = a.since if y == y0 else f"{y}-01-01"
            hi = f"{y + 1}-01-01" if y < int(a.until[:4]) else a.until
            obs += fetch_obs(st, lo, hi)
        cli = fetch_cli(st, range(y0, int(a.until[:4]) + 1))
        res[city] = {"st": st, "tz_std": tz, "obs": obs, "cli": cli}
        print(city, st, "obs", len(obs), "cli", len(cli), kk.STATS, flush=True)
    with gzip.open(os.path.join(kk.CACHE, "wobs.json.gz"), "wt") as fh:
        json.dump(res, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
