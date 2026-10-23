"""tools/import_tv.py on small synthetic TradingView exports (no real data is read or written).

    python -X utf8 -m tests.test_import_tv

Synthetic market: a random walk per Globex session (18:00 -> 17:00 ET, 1m bars, a busy 09:30 open), the 5m bars built from
it. Contracts: "Z26" prints the walk, "H27" the walk + 280 pts (the carry). A TradingView NQ1! export (B-ADJ off) prints
Z26 until TradingView's switch (Mon 2026-12-14 18:00 ET) and H27 after it. The files on disk are anchored on NQZ26 (as
data/ is today), with the Sep 2026 roll U26 -> Z26 (+294.75) recorded.
Checks: a clean merge (new bars, 15m / 1h rebuilt, backup, imported days); --check writes nothing; duplicates and
disagreeing overlaps; time zone (no offset, shifted stamps); holes; a known roll (applied, same switch bar); B-ADJ on
(refused); a NEW roll (refused without --roll; with --roll recorded and the history re-anchored on H27: the files then
equal the H27 truth); --gap; another price space (refused, nothing written); 1m vs 5m (verified, 5m holes filled, an
offset 1m export refused); micro / unnamed files.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import import_tv as it  # noqa: E402

ET = ZoneInfo("America/New_York")
COLS = ["time", "open", "high", "low", "close", "volume"]
RESULTS = []
G_DEC = 280.0           # Z26 -> H27 spread in the synthetic market
G_SEP = 294.75          # the recorded U26 -> Z26 roll
SW_DEC = it.tv_switch_t(2026, 12)
SW_SEP = it.tv_switch_t(2026, 9)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:600]}"), flush=True)


def at(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def walk(days, seed=7, start=25000.0):
    """1m bars of the base walk for the given trading days (each 18:00 ET of the previous calendar day -> 17:00 ET).
    No drift across the 17:00 halt (the 18:00 open = the 16:59 close), so a roll jump is exactly the contract spread."""
    rng = np.random.default_rng(seed)
    rows, px = [], start
    for day in days:
        d = dt.date.fromisoformat(day)
        prev = d - dt.timedelta(days=1)
        t0 = int(dt.datetime(prev.year, prev.month, prev.day, 18, 0, tzinfo=ET).timestamp())
        t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).timestamp())
        for t in range(t0, t1, 60):
            e = dt.datetime.fromtimestamp(t, ET)
            busy = 10.0 if (e.hour, e.minute) >= (9, 30) and (e.hour, e.minute) < (9, 35) else 1.0
            o = px
            c = round((o + rng.normal(0, 2.0)) * 4) / 4
            h = round((max(o, c) + abs(rng.normal(0, 1.0)) * busy) * 4) / 4
            lo = round((min(o, c) - abs(rng.normal(0, 1.0)) * busy) * 4) / 4
            rows.append((t, o, h, lo, c, int(rng.integers(5, 200))))
            px = c
    return pd.DataFrame(rows, columns=COLS)


def five(df1):
    g = df1.groupby(df1["time"] // 300 * 300)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    out.index.name = "time"
    return out.reset_index()


def coarse(df5, secs):
    g = df5.groupby(df5["time"] // secs * secs)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    out.index.name = "time"
    return out.reset_index()


def plus(df, pts, before=None, after=None):
    """df with pts added to the prices (only bars before / at-or-after a time when given)."""
    df = df.copy()
    m = np.ones(len(df), bool)
    if before is not None:
        m &= df["time"].values < before
    if after is not None:
        m &= df["time"].values >= after
    for c in ("open", "high", "low", "close"):
        df.loc[m, c] = df.loc[m, c] + pts
    return df


def tv_export(df, path, fmt="unix", extra_cols=True):
    """A TradingView 'Export chart data' file: time, open, high, low, close, (indicator columns), Volume."""
    out = pd.DataFrame({"time": df["time"].values})
    if fmt == "iso_naive":
        out["time"] = [dt.datetime.fromtimestamp(int(t), ET).strftime("%Y-%m-%dT%H:%M:%S") for t in df["time"]]
    elif fmt == "iso_offset":
        out["time"] = [dt.datetime.fromtimestamp(int(t), ET).isoformat() for t in df["time"]]
    for c in ("open", "high", "low", "close"):
        out[c] = df[c].values
    if extra_cols:
        out["Pools"] = 0
    out["Volume"] = df["volume"].values
    out.to_csv(path, index=False)


def run(folder, data, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = it.main([folder, "--data", data, *args])
    return rc, buf.getvalue()


def fresh_data(tmp, name, b1_disk, b5_disk, rolls=True):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    b1_disk.to_csv(os.path.join(d, "NQ_1m.csv"), index=False)
    b5_disk.to_csv(os.path.join(d, "NQ_5m.csv"), index=False)
    coarse(b5_disk, 900).to_csv(os.path.join(d, "NQ_15m.csv"), index=False)
    coarse(b5_disk, 3600).to_csv(os.path.join(d, "NQ_1h.csv"), index=False)
    doc = {"sym": "NQ", "anchor": "NQZ26", "method": "test", "weekday_open_drift_p50_p90": [4.0, 22.8],
           "rolls": [{"from": "NQU26", "to": "NQZ26", "switch_t": SW_SEP, "open_jump": G_SEP, "gap": G_SEP, "method": "open_jump"}]
           if rolls else []}
    json.dump(doc, open(os.path.join(d, "NQ_rolls.json"), "w"))
    return d


def folder(tmp, name, files):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    for fn, df, kw in files:
        tv_export(df, os.path.join(d, fn), **kw)
    return d


def rd(d, n):
    return pd.read_csv(os.path.join(d, n))


def same(a, b, cols=("open", "high", "low", "close")):
    m = a.merge(b, on="time", suffixes=("_a", "_b"))
    if len(m) != len(a) or len(m) != len(b):
        return False
    return all(np.allclose(m[c + "_a"], m[c + "_b"], atol=1e-6) for c in cols)


def main():
    tmp = tempfile.mkdtemp(prefix="le_import_tv_")
    try:
        # ---- the synthetic market: Dec 2026 sessions around TradingView's switch (Mon 12-14 18:00 ET)
        days = ["2026-12-07", "2026-12-08", "2026-12-09", "2026-12-10", "2026-12-11", "2026-12-14", "2026-12-15",
                "2026-12-16", "2026-12-17"]
        base1 = walk(days)
        base5 = five(base1)
        z1, z5 = base1, base5                                  # Z26 prices (the files' anchor: exchange prices)
        h1, h5 = plus(base1, G_DEC), plus(base5, G_DEC)        # H27 prices = the truth after a re-anchor on H27
        tv1 = pd.concat([z1[z1.time < SW_DEC], h1[h1.time >= SW_DEC]])     # TradingView NQ1!, B-ADJ off
        tv5 = pd.concat([z5[z5.time < SW_DEC], h5[h5.time >= SW_DEC]])
        cut = at(2026, 12, 10, 17)                             # the files on disk end Thu 12-10 17:00 (before the switch)
        print("calendar", flush=True)
        check("TradingView's switch rule reproduces every recorded NQ switch (21 rolls, 2021-2026) and says Mon 2026-12-14 "
              "18:00 ET for Dec 2026, Mon 2027-03-15 18:00 ET for Mar 2027",
              all(it.tv_switch_t(*it.parse_code(r["from"])) == r["switch_t"]
                  for r in json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"])
              and SW_DEC == at(2026, 12, 14, 18) and it.tv_switch_t(2027, 3) == at(2027, 3, 15, 18))
        check("file names: TradingView default and repo names -> symbol / bar size; micro flagged",
              it.name_info("CME_MINI_NQ1!, 1.csv") == ("NQ", False, 60) and it.name_info("CME_MINI_ES1!, 5 (2).csv") == ("ES", False, 300)
              and it.name_info("NQ1_1m_chunk_2025-03-03.csv") == ("NQ", False, 60) and it.name_info("ES1_5m_chunk_x.csv") == ("ES", False, 300)
              and it.name_info("MNQ1_5m_ETH.csv")[1] is True and it.name_info("export.csv")[0] is None,
              [it.name_info(x) for x in ("CME_MINI_NQ1!, 1.csv", "CME_MINI_ES1!, 5 (2).csv", "NQ1_1m_chunk_2025-03-03.csv")])

        # ---- 1. clean 5m merge before the switch
        print("1. clean merge", flush=True)
        d1 = fresh_data(tmp, "d1", z1[z1.time < cut], z5[z5.time < cut])
        f1 = folder(tmp, "f1", [("NQ1_5m_chunk_2026-12-11.csv", z5[(z5.time >= at(2026, 12, 9)) & (z5.time < at(2026, 12, 11, 17))], {})])
        rc, txt = run(f1, d1, "--check")
        check("--check: exit 0, says which files would change, writes nothing",
              rc == 0 and "would change" in txt and len(rd(d1, "NQ_5m.csv")) == len(z5[z5.time < cut])
              and not os.path.exists(os.path.join(d1, "_import_backup")), txt)
        rc, txt = run(f1, d1)
        m5 = rd(d1, "NQ_5m.csv")
        want5 = z5[z5.time < at(2026, 12, 11, 17)]
        check("merge: 5m file extended to Fri 12-11 17:00, every bar equal to the market; 15m / 1h rebuilt to match",
              rc == 0 and same(m5, want5) and same(rd(d1, "NQ_15m.csv"), coarse(want5, 900))
              and same(rd(d1, "NQ_1h.csv"), coarse(want5, 3600)), txt)
        bk = os.path.join(d1, "_import_backup")
        check("merge: backup of the old files written first; imported sessions recorded; summary in plain words",
              os.path.isdir(bk) and any(os.listdir(os.path.join(bk, x)) for x in os.listdir(bk))
              and "2026-12-11" in json.load(open(os.path.join(d1, "NQ_imported_days.json")))
              and "new bars" in txt and "no holes" in txt, txt)
        rc, txt2 = run(f1, d1)
        check("running the same import again changes nothing", rc == 0 and "Nothing to write" in txt2, txt2)

        # ---- 2. duplicates / overlapping files
        print("2. duplicates and overlaps", flush=True)
        a = z5[(z5.time >= at(2026, 12, 8)) & (z5.time < at(2026, 12, 10))]
        b = z5[(z5.time >= at(2026, 12, 9)) & (z5.time < at(2026, 12, 11))].copy()
        bad_t = int(b.time.iloc[-1])                               # file b ends on a "still forming" bar that differs
        b.loc[b.time == bad_t, "close"] += 3.0
        a2 = pd.concat([a, a.iloc[[5]]])                           # one exact duplicate row inside file a
        d2 = fresh_data(tmp, "d2", z1[z1.time < at(2026, 12, 8)], z5[z5.time < at(2026, 12, 8)])
        f2 = folder(tmp, "f2", [("NQ1_5m_a.csv", a2, {}), ("NQ1_5m_b.csv", b, {})])
        rc, txt = run(f2, d2)
        m5 = rd(d2, "NQ_5m.csv")
        check("overlapping files: counted, 0 disagree in the overlap; the duplicate row dropped; the merged bars are the market's",
              rc == 0 and "in more than one file" in txt and same(m5[m5.time < bad_t], z5[z5.time < bad_t]), txt)
        b2 = b.copy()
        mid = int(b2.time.iloc[40])
        b2.loc[b2.time == mid, "close"] += 2.0                      # disagrees inside the overlap with file a
        f2b = folder(tmp, "f2b", [("NQ1_5m_a.csv", a, {}), ("NQ1_5m_b.csv", b2, {})])
        rc, txt = run(f2b, fresh_data(tmp, "d2b", z1[z1.time < at(2026, 12, 8)], z5[z5.time < at(2026, 12, 8)]), "--check")
        check("a bar two files disagree on is counted ('1 disagree'); the copy farther from its file's end wins",
              rc == 0 and "1 disagree" in txt, txt)

        # ---- 3. time zone
        print("3. time zone", flush=True)
        f3 = folder(tmp, "f3", [("NQ1_5m_naive.csv", z5[(z5.time >= at(2026, 12, 9)) & (z5.time < cut)], {"fmt": "iso_naive"})])
        rc, txt = run(f3, d2, "--check")
        rc2, txt2 = run(f3, d2, "--check", "--tz", "America/New_York")
        f3b = folder(tmp, "f3b", [("NQ1_5m_offset.csv", z5[(z5.time >= at(2026, 12, 9)) & (z5.time < cut)], {"fmt": "iso_offset"})])
        rc3, txt3 = run(f3b, d2, "--check")
        check("ISO stamps without an offset: refused unless --tz; with --tz America/New_York or with an offset: fine",
              rc == 1 and "no time zone" in txt and rc2 == 0 and rc3 == 0, (txt, txt2[-300:], txt3[-300:]))
        sh = z5[(z5.time >= at(2026, 12, 9)) & (z5.time < cut)].copy()
        sh["time"] = sh["time"] + 3600                             # stamps shifted an hour (bars land in the CME halt)
        f3c = folder(tmp, "f3c", [("NQ1_5m_shift.csv", sh, {})])
        rc, txt = run(f3c, d2, "--check")
        check("stamps shifted by an hour: bars in the 17:00-17:59 ET halt -> ERROR, nothing written",
              rc == 1 and "17:00-17:59" in txt and "Nothing was written" in txt, txt)

        # ---- 4. holes
        print("4. holes", flush=True)
        hole = z5[(z5.time >= at(2026, 12, 9)) & (z5.time < at(2026, 12, 11, 17))]
        hole = hole[~hole.time.between(at(2026, 12, 10, 10), at(2026, 12, 10, 11))]
        rc, txt = run(folder(tmp, "f4", [("NQ1_5m_hole.csv", hole, {})]), d2, "--check")
        check("a session with an hour missing is listed ('2026-12-10 (13 bars missing)')",
              rc == 0 and "2026-12-10 (13 bars missing)" in txt, txt)

        # ---- 5. known roll inside the export (Sep 2026)
        print("5. a known roll (U26 -> Z26, recorded)", flush=True)
        sdays = ["2026-09-10", "2026-09-11", "2026-09-14", "2026-09-15", "2026-09-16"]
        sb5 = five(walk(sdays, seed=3))
        s_truth = plus(sb5, 0.0)                                   # Z26 prices = the files (anchored on Z26)
        s_tv = pd.concat([plus(sb5, -G_SEP)[sb5.time < SW_SEP], sb5[sb5.time >= SW_SEP]])   # U26 raw, then Z26 raw
        # the jump at the switch is the spread only (no drift across the halt in the synthetic walk)
        d5 = fresh_data(tmp, "d5", sb5.iloc[:0], s_truth[s_truth.time < at(2026, 9, 14, 12)])
        rc, txt = run(folder(tmp, "f5", [("NQ1_5m_sep.csv", s_tv, {})]), d5)
        check("known roll: same switch bar as the files, the export is back-adjusted (+294.75 before the switch) and "
              "matches the files exactly",
              rc == 0 and "same switch bar as the files" in txt and same(rd(d5, "NQ_5m.csv"), s_truth), txt)
        d5c = fresh_data(tmp, "d5c", sb5.iloc[:0], s_truth[s_truth.time >= at(2026, 9, 11)])
        rc, txt = run(folder(tmp, "f5c", [("NQ1_5m_old.csv", s_tv[s_tv.time < at(2026, 9, 11, 17)], {})]), d5c)
        check("an export that ends before a recorded roll (old contract only, like a 2025 export): every later roll's gap "
              "is added, it lands on the files' anchor",
              rc == 0 and same(rd(d5c, "NQ_5m.csv"), s_truth[(s_truth.time < at(2026, 9, 11, 17)) | (s_truth.time >= at(2026, 9, 11))]), txt)
        rc, txt = run(folder(tmp, "f5b", [("NQ1_5m_badj.csv", s_truth, {})]), d5, "--check")
        check("B-ADJ on (no jump at a recorded roll): ERROR 'turn B-ADJ off'", rc == 1 and "B-ADJ off" in txt, txt)

        # ---- 6. a NEW roll (Dec 2026: Z26 -> H27)
        print("6. a new roll (Z26 -> H27)", flush=True)
        d6 = fresh_data(tmp, "d6", z1[z1.time < cut], z5[z5.time < cut])
        before = {n: rd(d6, n) for n in ("NQ_1m.csv", "NQ_5m.csv", "NQ_15m.csv", "NQ_1h.csv")}
        f6 = folder(tmp, "f6", [("CME_MINI_NQ1!, 5.csv", tv5[tv5.time >= at(2026, 12, 9)], {}),
                                ("CME_MINI_NQ1!, 1.csv", tv1[tv1.time >= at(2026, 12, 9)], {})])
        rc, txt = run(f6, d6)
        check("new roll without --roll: refused, says the gap (+280.00) and how to run it; nothing written",
              rc == 1 and "NEW roll NQZ26 -> NQH27" in txt and "+280.00" in txt and "--roll" in txt
              and all(same(rd(d6, n), before[n]) for n in before), txt)
        rc, txt = run(f6, d6, "--roll")
        doc = json.load(open(os.path.join(d6, "NQ_rolls.json")))
        nr = doc["rolls"][-1]
        check("with --roll: the roll is recorded (anchor NQH27, switch Mon 12-14 18:00 ET, gap +280, open_jump method)",
              rc == 0 and doc["anchor"] == "NQH27" and nr["from"] == "NQZ26" and nr["switch_t"] == SW_DEC
              and nr["gap"] == G_DEC and nr["method"] == "open_jump" and len(doc["rolls"]) == 2, (txt, nr))
        check("with --roll: 1m / 5m / 15m / 1h all re-anchored on H27 (old bars +280) and extended: every bar equals H27",
              same(rd(d6, "NQ_5m.csv"), h5) and same(rd(d6, "NQ_1m.csv"), h1) and same(rd(d6, "NQ_15m.csv"), coarse(h5, 900))
              and same(rd(d6, "NQ_1h.csv"), coarse(h5, 3600)), txt)
        rc, txt = run(f6, d6, "--check")
        check("the same export again after the roll: the roll is now known ('same switch bar'), nothing changes",
              rc == 0 and "same switch bar as the files" in txt and "0 file(s) would change" in txt, txt)
        d6b = fresh_data(tmp, "d6b", z1[z1.time < cut], z5[z5.time < cut])
        rc, txt = run(folder(tmp, "f6b", [("NQ1_5m_x.csv", tv5[tv5.time >= at(2026, 12, 9)], {})]), d6b, "--roll", "--gap", "281.5")
        nr = json.load(open(os.path.join(d6b, "NQ_rolls.json")))["rolls"][-1]
        check("--gap 281.5 overrides the measured jump (method 'override', the files shift by 281.5)",
              rc == 0 and nr["gap"] == 281.5 and "override" in nr["method"]
              and abs(float(rd(d6b, "NQ_5m.csv").close.iloc[0]) - float(z5.close.iloc[0]) - 281.5) < 1e-9, txt)

        # ---- 7. another price space
        print("7. another price space", flush=True)
        d7 = fresh_data(tmp, "d7", z1[z1.time < cut], z5[z5.time < cut])
        off = plus(z5[(z5.time >= at(2026, 12, 8)) & (z5.time < at(2026, 12, 11, 17))], 50.0)
        rc, txt = run(folder(tmp, "f7", [("NQ1_5m_off.csv", off, {})]), d7)
        check("an export 50 pts off the files (wrong contract / mixed price space): ERROR, nothing written",
              rc == 1 and "different price space" in txt and same(rd(d7, "NQ_5m.csv"), z5[z5.time < cut]), txt)

        # ---- 8. 1m exports
        print("8. 1m exports", flush=True)
        d8 = fresh_data(tmp, "d8", z1[z1.time < at(2026, 12, 9)], z5[z5.time < cut].pipe(
            lambda x: x[~x.time.between(at(2026, 12, 9, 10), at(2026, 12, 9, 10, 25))]))
        f8 = folder(tmp, "f8", [("NQ1_1m_chunk_2026-12-10.csv", z1[(z1.time >= at(2026, 12, 8)) & (z1.time < cut)], {})])
        rc, txt = run(f8, d8)
        check("1m export: verified against the 5m file, merged, the 6 missing 5m bars rebuilt from complete 1m windows, "
              "cover reported",
              rc == 0 and "rebuilt to 5m it matches the 5m file" in txt and "6 5m bars" in txt and "1m cover" in txt
              and same(rd(d8, "NQ_1m.csv"), z1[z1.time < cut]) and same(rd(d8, "NQ_5m.csv"), z5[z5.time < cut]), txt)
        off1 = plus(z1[(z1.time >= at(2026, 12, 8)) & (z1.time < cut)], 12.0)
        d8b = fresh_data(tmp, "d8b", z1.iloc[:0], z5[z5.time < cut])
        rc, txt = run(folder(tmp, "f8b", [("NQ1_1m_off.csv", off1, {})]), d8b)
        check("1m export 12 pts off the 5m file: ERROR (not the 5m file's price space), nothing written",
              rc == 1 and "price space" in txt and len(rd(d8b, "NQ_1m.csv")) == 0, txt)

        # ---- 9. names
        print("9. names", flush=True)
        f9 = folder(tmp, "f9", [("MNQ1_5m_ETH.csv", z5.head(500), {}), ("NQ1_5m_ok.csv", z5[(z5.time >= at(2026, 12, 9)) & (z5.time < cut)], {})])
        rc, txt = run(f9, d2, "--check")
        f9b = folder(tmp, "f9b", [("export.csv", z5.head(500), {})])
        rc2, txt2 = run(f9b, d2, "--check")
        rc3, _ = run(f9b, d2, "--check", "--sym", "NQ")
        check("a micro export is skipped with a warning; a file without NQ/ES in its name needs --sym",
              rc == 0 and "micro" in txt and rc2 == 1 and "--sym" in txt2 and rc3 == 0, (txt, txt2))
        tv_nv = os.path.join(tmp, "f9c")
        os.makedirs(tv_nv)
        z5.head(100).drop(columns="volume").to_csv(os.path.join(tv_nv, "NQ1_5m_novol.csv"), index=False)
        rc, txt = run(tv_nv, d2, "--check")
        check("an export without a Volume column: ERROR 'add the Volume indicator'", rc == 1 and "Volume" in txt, txt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nimport_tv test: {'PASS' if n_ok == len(RESULTS) else 'FAIL'} ({n_ok}/{len(RESULTS)})")
    return n_ok == len(RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
