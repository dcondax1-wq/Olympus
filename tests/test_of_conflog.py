"""night-of-conflog 2026-11-27: the order-flow CONFLUENCE forward log (engine/of_conflog.py) + its cloud score
(research/orderflow/of_confluence.forward). Fake days only (synthetic 5m summaries + fake ledgers in a temp folder); no data/
written in the repo, no network, nothing that can trade.
  a. parity: the bot-side reads (absorbed zone, hard flip) = the frozen research ones (of_battery.Day.zone / of_confluence.Flow)
  b. kick: rows for finished LIT + ATLAS trades, the day export, idempotent, refuses 09:25-16:10 ET, off switch, never raises
  c. bounded log; d. no account fields in a row; e. the data feed allows / packs NQ_conflog.json.gz
  f. the cloud score reads the rows (C-b computed, judge state 'logging'); g. safety (imports, the autopilot hook)
    python -X utf8 -m tests.test_of_conflog
"""
from __future__ import annotations

import ast
import datetime as dt
import gzip
import importlib.util
import io
import json
import re
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "engine.account_c",
          "engine.multi_account", "engine.fleet", "server", "engine.guards", "engine.datafeed", "engine.tickrec")
DAY = "2026-12-01"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def _ts(day, hh, mm):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ET).timestamp())


def fake_day(root, day=DAY, seed=7):
    """A synthetic RTH-ish day of 5m bars 08:00-16:00 ET with footprints; random flow, some bars planted absorbed / flipped."""
    rng = np.random.default_rng(seed)
    t0 = _ts(day, 8, 0)
    bars, fp, px = [], [], 21000.0
    for i in range(96):
        o = px
        lo, hi = o - rng.integers(4, 40) * 0.25, o + rng.integers(4, 40) * 0.25
        c = round(rng.uniform(lo, hi) * 4) / 4
        kmax = int(round((hi - lo) / 0.25))
        cells, buy, sell = [], 0, 0
        plant = i % 7
        for k in range(kmax + 1):
            a, b = int(rng.integers(0, 30)), int(rng.integers(0, 30))
            if plant == 1 and k <= 8:          # sellers hit the low and were absorbed -> absorbed for a LONG
                b += 60
            if plant == 2 and k >= kmax - 8:   # buyers lifted the high and were absorbed -> absorbed for a SHORT
                a += 60
            if plant == 3:                     # a hard selling bar
                b += 40
            cells.append((i, k, b, a, 0)); buy += a; sell += b
        fp += cells
        vol = buy + sell
        bars.append((t0 + 300 * i, o, hi, lo, c, vol, buy, sell, 0, max(25, vol // 2)))
        px = c
    d = os.path.join(root, "logs", "datapipe", "days", day, "of")
    os.makedirs(d, exist_ok=True)
    with gzip.open(os.path.join(d, "NQ_bars5m.csv.gz"), "wt") as fh:
        fh.write("t,o,h,l,c,vol,buy,sell,unk,n\n")
        for b in bars:
            fh.write(",".join(str(x) for x in b) + "\n")
    with gzip.open(os.path.join(d, "NQ_fp5m.csv.gz"), "wt") as fh:
        fh.write("bar,k,b,a,u\n")
        for f in fp:
            fh.write(",".join(str(x) for x in f) + "\n")
    with open(os.path.join(d, "NQ_meta.json"), "w") as fh:
        json.dump({"v": 1, "day": day, "rows": 500000}, fh)
    return bars


def fake_ledgers(root, bars, day=DAY):
    """One LIT long (live_state.json) + one ATLAS short (live_state_acctb.json), both closed, + an open LIT trade (no exit)."""
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    e1 = _ts(day, 10, 0); px1 = bars[24][1]
    lit = [{"t": e1 + 20, "sym": "NQ", "side": "buy", "qty": 3, "entry": px1, "stop": px1 - 20, "target": px1 + 60, "entry_t": e1,
            "result": {"ok": True, "adapter": "ninjatrader", "fill_px": px1 + 0.5}, "account": "SECRET-ACCT"},
           {"t": e1 + 3000, "sym": "NQ", "side": "exit", "qty": 3, "reason": "TARGET", "pnl": 357.9, "entry_t": e1, "result": {"ok": True}},
           {"t": _ts(day, 13, 0), "sym": "NQ", "side": "sell", "qty": 1, "entry": 21000, "stop": 21020, "entry_t": _ts(day, 13, 0),
            "result": {"ok": True}}]
    e2 = _ts(day, 9, 45); px2 = bars[21][1]
    atl = [{"t": e2 + 5, "sym": "NQ", "side": "sell", "qty": 5, "entry": px2, "stop": px2 + 25, "target": px2 - 80, "entry_t": e2,
            "result": {"ok": True, "adapter": "paper"}},
           {"t": e2 + 1200, "sym": "NQ", "side": "exit", "qty": 5, "reason": "STOP", "pnl": -259.5, "entry_t": e2, "result": {"ok": True}}]
    json.dump({"ledger": lit, "nt_account": "SECRET-ACCT"}, open(os.path.join(root, "data", "live_state.json"), "w"))
    json.dump({"ledger": atl}, open(os.path.join(root, "data", "live_state_acctb.json"), "w"))


def _research():
    sp = importlib.util.spec_from_file_location("t_ofc", os.path.join(ROOT, "research", "orderflow", "of_confluence.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


def main():
    from engine import of_conflog as CL, oflive
    import pandas as pd
    OC = _research()
    with tempfile.TemporaryDirectory() as root:
        bars = fake_day(root)
        fake_ledgers(root, bars)
        # ---- a. parity with the frozen research reads
        d_of = os.path.join(root, "logs", "datapipe", "days", DAY, "of")
        R = {"bars": pd.read_csv(os.path.join(d_of, "NQ_bars5m.csv.gz")), "fp": pd.read_csv(os.path.join(d_of, "NQ_fp5m.csv.gz")),
             "meta": {}}
        D = {DAY: OC.OB.Day(DAY, R)}
        F = OC.Flow(D)
        S = CL._prep(oflive._summary(DAY, root))
        mism, n_abs = [], 0
        for j, b in enumerate(S["bars"]):
            for d in (1, -1):
                a1, a2 = CL.zone_absorbed(S, j, d), F.absorbed(DAY, int(b["t"]), d)
                n_abs += bool(a1)
                if a1 != a2:
                    mism.append((j, d, a1, a2))
        check("a. absorbed zone = of_battery.Day.zone / OF1 on every bar, both sides", not mism and n_abs > 5, (mism[:5], n_abs))
        fb = F.bars(DAY)
        mism, n_h = [], 0
        for j, r in enumerate(fb.itertuples()):
            for d in (1, -1):
                for entry in (21000.0, float(r.close) + d * 2):
                    h1 = CL.flip_info(S, j, d, entry)[3]; h2 = F.hard_flip(DAY, r, d, entry * d)
                    n_h += h1
                    if h1 != h2:
                        mism.append((j, d, entry, h1, h2))
        check("a. hard flip = of_confluence.Flow.hard_flip on every bar", not mism and n_h > 3, (mism[:5], n_h))
        check("a. frozen constants = the research's", (CL.ABS_SHARE, CL.FLIP_SHARE, CL.WIN_BARS) == (OC.ABS_SHARE, OC.FLIP_SHARE,
              OC.WIN_BARS) and (CL.ZONE_TICKS, CL.ABS_SHARE) == (OC.OB.ZONE, OC.OB.ABS_SHARE))
        # ---- b. kick
        night = _ts("2026-12-01", 20, 0) + 86400 * 0
        busy = _ts("2026-12-02", 11, 0)
        log = os.path.join(root, "data", "of_confluence_log.jsonl")
        r0 = CL.kick(root, now=busy, log=log)
        check("b. refuses 09:25-16:10 ET on a weekday", r0.get("ran") is False and not os.path.exists(log), r0)
        os.environ["LE_OFCONFLOG"] = "0"
        r_off = CL.kick(root, now=night, log=log)
        os.environ.pop("LE_OFCONFLOG")
        check("b. LE_OFCONFLOG=0 = off", r_off.get("why") == "off", r_off)
        r1 = CL.kick(root, now=_ts("2026-12-02", 1, 0), log=log)
        rows = [x for x in oflive._jl(log) if not x.get("day_done")]
        check("b. one row per FINISHED trade (LIT + ATLAS; the open one skipped)", r1.get("days") == [DAY] and
              sorted(x["bot"] for x in rows) == ["atlas", "lit"], (r1, rows[:1]))
        L = next(x for x in rows if x["bot"] == "lit"); A = next(x for x in rows if x["bot"] == "atlas")
        need = ("sweep_read", "sweep_vz", "sweep_dz", "abs1_t", "flip1_t", "flip1_share", "hard1_t", "sig_delta", "nonadv1_t", "bars",
                "pnl", "qty", "stop", "target", "tf")
        check("b. every LEAD_WIRES field is on the row", all(k in L for k in need), [k for k in need if k not in L])
        check("b. slip_ticks from the real fill (LIT +0.5 pt = +2 ticks); none without a fill price",
              L.get("slip_ticks") == 2.0 and "slip_ticks" not in A, (L.get("slip_ticks"), A.get("slip_ticks")))
        check("b. sweep read = the journal's (oflive.said_at)", L["sweep_read"] == oflive.said_at(S, L["t"], 1, L["stop"])["read"])
        check("b. the replay series is bounded and starts at the fill's bar", 0 < len(L["bars"]) <= CL.MAX_BARS and
              L["bars"][0][0] + 300 > L["tf"], L["bars"][:2])
        exp = os.path.join(d_of, CL.EXPORT_NAME)
        doc = json.load(gzip.open(exp, "rt"))
        check("b. the day's export for the data feed (paper research, 2 rows, < 150 KB)",
              doc.get("paper_research") and len(doc["rows"]) == 2 and os.path.getsize(exp) < 150_000)
        r2 = CL.kick(root, now=_ts("2026-12-02", 1, 30), log=log)
        check("b. idempotent: a second night adds nothing", r2.get("days") == [] and len(oflive._jl(log)) == 3, r2)
        r3 = CL.kick(os.path.join(root, "nope"), now=_ts("2026-12-02", 1, 0), log=os.path.join(root, "x", "y.jsonl"))
        check("b. a missing folder: no error, nothing written", r3.get("ran") and r3.get("rows") == 0, r3)
        orig = CL.fields
        CL.fields = lambda S, tr: 1 / 0
        try:
            r4 = CL.day_rows(DAY, root)
        finally:
            CL.fields = orig
        check("b. a broken read becomes an 'error' row, never an exception", r4 and all(x.get("error") for x in r4), r4)
        # ---- c. bounded
        big = os.path.join(root, "data", "big.jsonl")
        with open(big, "w") as fh:
            for i in range(5000):
                fh.write(json.dumps({"day": "x", "i": i, "pad": "z" * 900}) + "\n")
        CL._bound(big)
        kept = oflive._jl(big)
        check("c. the log is bounded (oldest rows dropped)", len(kept) == CL.KEEP_ROWS and kept[-1]["i"] == 4999, len(kept))
        # ---- d. privacy
        blob = json.dumps(rows) + json.dumps(doc)
        check("d. no account name / id in the rows or the export", "SECRET" not in blob and '"account"' not in blob
              and "nt_account" not in blob)
        # ---- e. data feed
        from engine import datafeed as DF
        check("e. DAY_FILE allows days/<day>/of/NQ_conflog.json.gz", bool(DF.DAY_FILE.match(f"days/{DAY}/of/NQ_conflog.json.gz")))
        check("e. the daily day bundle carries it (EXTRAS)", "of/NQ_conflog.json.gz" in DF.EXTRAS)
        src = open(os.path.join(ROOT, "engine", "datafeed.py"), encoding="utf-8").read()
        check("e. the nightly 'of' pages carry it", bool(re.search(r'OF_FILES \+ \([^)]*"NQ_conflog\.json\.gz"', src)))   # day-ofready2: NQ_lane rides the same tuple
        # ---- f. cloud score on the shipped rows (C-b needs no bars; the others need 1m bars of the day: absent here)
        pc = os.path.join(root, "pc_days", DAY, "of")
        os.makedirs(pc)
        with open(exp, "rb") as a, open(os.path.join(pc, CL.EXPORT_NAME), "wb") as b:
            b.write(a.read())
        FR = OC.forward_rows(os.path.join(root, "pc_days"))
        check("f. the cloud reads the shipped rows (forward days only)", len(FR) == 2, len(FR))
        gl = OC._gains(next(x for x in FR if x["bot"] == "lit"), None, None)
        q = L["qty"]; want = L["pnl"] * (min(40, int(q * 1.5)) - q) / q if L["sweep_read"] == "absorbed" else 0.0
        check("f. C-b gain = the extra micros x the real trade's $", abs(gl.get("b", 99) - want) < 1e-6, (gl, want))
        old_src = OC.forward_rows
        OC.forward_rows = lambda src=None: FR
        try:
            out = OC.forward(say=lambda *_: None, write=False)
        finally:
            OC.forward_rows = old_src
        st = out["ideas"]["lit:b"]
        check("f. judge state says 'logging (n of 30)' until 30 LIT trades", st["state"].startswith("logging (1 of 30)"), st)
        # ---- g. safety
        tree = ast.parse(open(os.path.join(ROOT, "engine", "of_conflog.py"), encoding="utf-8").read())
        imps = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imps |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imps.add(("engine." if n.level else "") + (n.module or ""))
        bad = [m for m in imps if any(m == b or m.startswith(b + ".") for b in BANNED) or m.split(".")[0] in ("numpy", "pandas")]
        check("g. of_conflog imports nothing that can trade (stdlib + engine.oflive only)", not bad and imps <= {
              "__future__", "datetime", "gzip", "json", "os", "statistics", "time", "engine.", "engine.oflive"} | {"engine"}, imps)
        tr = open(os.path.join(ROOT, "engine", "tickrec.py"), encoding="utf-8").read()
        check("g. hooked into the tick autopilot next to the journal (outside trading hours), in a try", "of_conflog.kick(" in tr
              and tr.index("oflive.journal_kick(") < tr.index("of_conflog.kick("))
        gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
        check("g. data/of_confluence_log.jsonl is gitignored", "data/of_confluence_log.jsonl" in gi)
        for m in ("engine.live", "engine.lit_live", "server", "engine.account_b"):
            p = os.path.join(ROOT, *m.split(".")) + ".py"
            if os.path.exists(p):
                check(f"g. {m} does not import of_conflog", "of_conflog" not in open(p, encoding="utf-8").read())
    ok = all(RES)
    print(f"of_conflog: {sum(RES)}/{len(RES)} {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
