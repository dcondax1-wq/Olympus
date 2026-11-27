"""big-ofpipe 2026-11-26: the Order Flow pillar's PAPER state shipped PC -> cloud, and the OF input field for the live setup score.
  a. engine/oflive.paper_tiny: today's paper state as a <= 300-byte status block (paper-labelled), None for another day / non-paper
  b. tools/pc_report: "ofp" rides an EXT post (no new post); only a new / closed paper trade or a new day is news (ntfy quota)
  c. engine/of_paper.export_day -> logs/datapipe/days/<day>/of/NQ_paper.json.gz -> engine/datafeed.build_of packs it (checksum in
     the day's of/manifest.json; the answer meta is signed as before) -> extract() accepts it -> tools/build_of_room "shipped" source
  d. engine/oflive.setup_of (live) / setup_of_hist (summary): OF1 at a LIT setup's sweep extreme
  e. the ops task starts the paper bot BELOW_NORMAL; nothing in the order path imports any of it
Synthetic only, temp folders, no network.    python -X utf8 -m tests.test_ofpipe
"""
from __future__ import annotations

import datetime as dt
import gzip
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main():
    from engine import of_paper as P, oflive as OL, datafeed as DF, ofsum
    from tools import pc_report as PR
    sp = importlib.util.spec_from_file_location("t_sim3", os.path.join(ROOT, "research", "orderflow", "of_sim.py"))
    Sim = importlib.util.module_from_spec(sp); sp.loader.exec_module(Sim)
    sp = importlib.util.spec_from_file_location("t_room3", os.path.join(ROOT, "tools", "build_of_room.py"))
    RB = importlib.util.module_from_spec(sp); sp.loader.exec_module(RB)
    W = Sim.world(6, "planted", seed=51, lvl=True)
    d0, d1 = W["days"][-2], W["days"][-1]
    S = P.replay_summary(W["R"][d1], d1, W["R"][d0], d0, lit=[{"t": W["lit"][-1]["tn"], "d": W["lit"][-1]["dir"], "stop": 0, "pnl": 120.0}])
    now = time.time()
    today = dt.datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d")
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "root"); os.makedirs(os.path.join(root, "data"))
        T = json.loads(json.dumps(S, default=float))
        T["day"] = today
        for r in T["rows"]:
            r["day"] = today
        json.dump(T, open(os.path.join(root, "data", "of_paper.json"), "w"))
        t1 = OL.paper_tiny(root, now)
        raw = json.dumps(t1, separators=(",", ":"))
        check("a. paper_tiny: today's paper state as a status block <= 300 bytes, paper-labelled", t1 and t1["p"] == 1 and t1["d"] == today
              and len(raw) <= 300 and all(x[2] in ("a", "n", "u") for x in t1["lv"]), (len(raw), raw))
        check("a. paper_tiny: no $ of a real trade (Zlarior = take / skip + won / lost)", all(len(x) == 3 and x[2] in ("won", "lost", None) for x in t1["lb"]), t1["lb"])
        T2 = dict(T, day="2020-01-01")
        json.dump(T2, open(os.path.join(root, "data", "of_paper.json"), "w"))
        check("a. another day's state -> None (never yesterday's trades as today's)", OL.paper_tiny(root, now) is None)
        json.dump(dict(T, paper=False), open(os.path.join(root, "data", "of_paper.json"), "w"))
        check("a. a state not labelled paper -> None", OL.paper_tiny(root, now) is None)
        # b. pc_report ext
        out = {"v": 1, "kind": "le-live", "t": int(now), "src": "pc_report", "ofp": t1}
        core, exts = PR.split(out)
        check("b. 'ofp' rides an ext post, not the core", "ofp" not in core and any("ofp" in (e.get("x") or {}) for e in exts), (list(core), [list(e.get("x") or {}) for e in exts]))
        h0 = PR.ext_hash(exts)
        t2 = dict(t1, R=(t1.get("R") or 0) + 1.5, ln="changed", t=int(now) + 300, lv=[[x[0], x[1], "a"] for x in t1["lv"]])
        h1 = PR.ext_hash(PR.split({**out, "ofp": t2})[1])
        t3 = dict(t1, n=(t1.get("n") or 0) + 1)
        h2 = PR.ext_hash(PR.split({**out, "ofp": t3})[1])
        check("b. ntfy quota: R / line / level reads / run time are NOT news; a new paper trade IS", h0 == h1 and h0 != h2, (h0, h1, h2))
        check("b. 'ofp' is in EXT_ORDER (placed before the long Brain blocks)", "ofp" in PR.EXT_ORDER)
        # c. export -> build_of -> extract -> room
        S["day"] = d1
        p = P.export_day(S, root)
        dp_work = os.path.join(root, "logs", "datapipe")
        od = os.path.join(dp_work, "days", d1, "of")
        files = ofsum.summarize(Sim.simulate_day(d1, 80_000, __import__("numpy").random.default_rng(1))[0], d1)
        for nm, b in files.items():
            open(os.path.join(od, nm), "wb").write(b)
        shipped = json.load(gzip.open(p, "rt"))
        check("c. export_day: gz paper state next to the summary, paper-labelled, no $ of real trades", p and p.endswith("of/NQ_paper.json.gz")
              and shipped["paper"] and shipped["never_routed"] and all("pnl" not in r for r in shipped["lit"]), shipped.get("lit"))
        blob, meta = DF.build_of(d1, dp_work=dp_work)
        z = zipfile.ZipFile(io.BytesIO(blob))
        names = z.namelist()
        man = json.loads(z.read(f"days/{d1}/of/manifest.json"))
        check("c. build_of packs NQ_paper.json.gz with its sha256 in the day's of/manifest.json", f"days/{d1}/of/NQ_paper.json.gz" in names
              and "of/NQ_paper.json.gz" in man["files"] and meta["what"] == "of", names)
        check("c. the cloud's file filter accepts it", DF.DAY_FILE.match(f"days/{d1}/of/NQ_paper.json.gz") is not None)
        cloud = os.path.join(td, "cloud")
        os.makedirs(os.path.join(cloud, "data", "pc_days"))
        got = DF.extract(blob, os.path.join(cloud, "data", "pc_days"))
        check("c. extract() writes the shipped paper state", got and os.path.exists(os.path.join(cloud, "data", "pc_days", d1, "of", "NQ_paper.json.gz")), got)
        r = RB.build(cloud)
        check("c. build_of_room: source = the PC paper bot's shipped state (before any replay)", str(r["source"]).startswith("PC paper bot") and r["day"] == d1
              and r.get("rows") is not None, r.get("source"))
        src = open(os.path.join(ROOT, "engine", "datafeed.py"), encoding="utf-8").read()
        check("c. the 'of' answer is still signed (send() -> _sign_msg)", "msg = _sign_msg(msg)" in src)
        # d. setup_of on a live tick file: sellers hit into a long's sweep level 21,000 and it held
        nd = os.path.join(td, "nt"); os.makedirs(os.path.join(nd, "le_ticks"))
        t_ms = int(now * 1000)
        with open(os.path.join(nd, "le_ticks", f"NQ_{OL._et_day(now)}.csv"), "w") as fh:
            fh.write("t_ms,price,size,bid,ask\n")
            for k in range(60):
                fh.write(f"{t_ms - 600_000 + k * 5000},21000.00,5,21000.00,21000.25\n")   # sells at the bid (into the level)
            for k in range(10):
                fh.write(f"{t_ms - 300_000 + k * 5000},21000.25,3,21000.00,21000.25\n")
        f = OL.setup_of({"side": "LONG", "plan": {"stop": 20999.75}}, now=now, nd=nd)
        check("d. setup_of: OF1 at a LIT long's sweep extreme = absorbed (+ volume, delta, 15-min delta)", f["of1"] == "absorbed" and f["of_vz"] > 0
              and f["of_dz"] < 0 and f["of_level"] == 21000.0, f)
        g = OL.setup_of({"side": "SHORT", "plan": {"stop": 21000.25}}, now=now, nd=nd)
        check("d. setup_of: the same tape for a SHORT at 21,000 = not absorbed", g["of1"] == "not absorbed", g)
        check("d. setup_of: stale file (> 15 min) or no stop -> of1 None (score: 'no OF read', never a no)",
              OL.setup_of({"side": "LONG", "plan": {"stop": 20999.75}}, now=now + 3600, nd=nd)["of1"] is None
              and OL.setup_of({"side": "LONG", "plan": {}}, now=now, nd=nd)["of1"] is None)
        os.makedirs(os.path.join(root, "logs", "datapipe", "days", d1, "of"), exist_ok=True)
        lt = W["lit"][-1]
        h = OL.setup_of_hist(d1, lt["tn"], lt["dir"], 0.0, root=root)
        check("d. setup_of_hist: the same field for a past setup from the day's summary", h["of1"] in ("absorbed", "not absorbed", "not tested", None) and "of_vz" in h, h)
    # e. safety
    ops = open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read()
    check("e. the ops task starts the paper bot BELOW_NORMAL (Windows flag 0x4000) and detached", "0x00004000" in ops and "0x00000008" in ops)
    users = subprocess.run(["git", "grep", "-l", "-e", "of_paper", "-e", "paper_tiny", "-e", "setup_of", "--", "engine/live.py", "engine/lit_live.py", "server.py",
                            "engine/ninjatrader.py", "engine/bg_worker.py", "engine/account_b.py", "engine/account_c.py", "engine/guards.py"],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("e. nothing in the order path uses any of it", users == "", users)
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
