#!/usr/bin/env python3
"""REAL archived forecasts, free, no key: NWS MOS guidance (GFS MOS, NAM MOS, National Blend "NBS") as archived by the
Iowa Environmental Mesonet with the model RUN TIME on every row. So "what was forecast the evening before" is honest:
we only ever use a run whose nominal time is >= 6 hours before the decision (GFS MOS is public ~4.5 h after run time, NBS ~1.5 h).

Writes data/mos.json.gz: {station: {"YYYY-MM-DD" (local day D): {"x": {model: {"12p": F, "18p": F, "00": F, "06": F}}, "n": {...}}}}
  x = forecast daily MAX for day D (row valid 00Z D+1), n = forecast MIN for day D (row valid 12Z D).
  run keys: "12p"/"18p" = 12Z / 18Z run of D-1, "00"/"06" = 00Z / 06Z run of D.

    python research/kalshi_edge_C/mos_fetch.py
"""
import csv, gzip, io, json, os, sys, time, urllib.request, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kc

# Kalshi city -> the station its rules name (NWS Climatological Report station). Checked against rules_primary printed by harvest_c.py.
STATIONS = {"NY": "KNYC", "NYC": "KNYC", "CHI": "KMDW", "MIA": "KMIA", "AUS": "KAUS", "LAX": "KLAX", "DEN": "KDEN", "PHIL": "KPHL",
            "SFO": "KSFO", "PHX": "KPHX", "ATL": "KATL", "SEA": "KSEA", "BOS": "KBOS", "DAL": "KDFW", "DC": "KDCA", "LV": "KLAS",
            "HOU": "KHOU", "MIN": "KMSP", "OKC": "KOKC", "NOLA": "KMSY", "SATX": "KSAT"}
MODELS = ["GFS", "NBS", "NAM"]


def fetch(station, model, sts, ets):
    u = f"https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py?station={station}&model={model}&sts={sts}T00:00Z&ets={ets}T00:00Z&format=csv"
    fn = os.path.join(kc.CACHE, f"mos_{station}_{model}_{sts}_{ets}.csv")
    if os.path.exists(fn) and os.path.getsize(fn) > 1000:
        return open(fn).read()
    for k in range(5):
        try:
            time.sleep(4.0)
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-client"}), timeout=180).read().decode()
            open(fn, "w").write(r)
            return r
        except Exception as e:
            print("retry", station, model, repr(e)[:80], flush=True)
            time.sleep(5 * (k + 1))
    return ""


def main():
    sts, ets = "2025-10-25", time.strftime("%Y-%m-%d", time.gmtime())
    out = {}
    for st in sorted(set(STATIONS.values())):
        days = {}
        for model in MODELS:
            txt = fetch(st, model, sts, ets)
            n = 0
            for r in csv.DictReader(io.StringIO(txt)):
                v = r.get("n_x") or r.get("txn")
                if not v:
                    continue
                try:
                    v = float(v)
                except ValueError:
                    continue
                run = dt.datetime.strptime(r["runtime"][:16], "%Y-%m-%d %H:%M")
                ft = dt.datetime.strptime(r["ftime"][:16], "%Y-%m-%d %H:%M")
                if ft.hour == 0:      # max of the local day that ends around this time
                    kind, day = "x", (ft - dt.timedelta(days=1)).date()
                elif ft.hour == 12:   # min of the morning of this day
                    kind, day = "n", ft.date()
                else:
                    continue
                d0 = dt.datetime.combine(day, dt.time(0))
                lead = (d0 - run).total_seconds() / 3600   # hours from run to 00Z of day D
                key = {12: "12p", 6: "18p", 0: "00", -6: "06"}.get(int(lead))
                if key is None:
                    continue
                days.setdefault(str(day), {}).setdefault(kind, {}).setdefault(model, {})[key] = v
                n += 1
            print(st, model, n, flush=True)
        out[st] = days
    with gzip.open(os.path.join(kc.DATA, "mos.json.gz"), "wt") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("wrote mos.json.gz", os.path.getsize(os.path.join(kc.DATA, "mos.json.gz")))


if __name__ == "__main__":
    main()
