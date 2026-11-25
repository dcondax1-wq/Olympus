"""day-ofready 2026-11-24: engine/ofsum.py (per-day order-flow summaries) + research/orderflow/of_battery.py (the pre-registered
battery, research/orderflow/DESIGN.md). Synthetic ticks only, no data/ written, no network.
    python -X utf8 -m tests.test_ofready
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "server")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def imports(path):
    t = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mod = ("engine." if n.level and "engine" in path else "") + (n.module or "")
            out |= {mod} | {f"{mod}.{a.name}".strip(".") for a in n.names}
    return out


def main():
    from engine import ofsum
    check("ofsum selftest (sums, footprint, prints, histogram, sides)", ofsum.selftest())
    imp = imports(os.path.join(ROOT, "engine", "ofsum.py"))
    check("ofsum imports nothing that can trade", not any(i.startswith(b) for i in imp for b in BANNED), imp)
    users = subprocess.run(["git", "grep", "-l", "ofsum", "--", "engine/live.py", "engine/lit_live.py", "server.py", "engine/ninjatrader.py"],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("nothing in the bot imports ofsum", users == "", users)
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "research", "orderflow", "of_battery.py"), "--selftest"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    check("of_battery selftest (OF1/OF2 parity with of_study.prereg, 40-day gate, all 6 tests run)",
          r.returncode == 0 and "selftest: OK" in r.stdout, (r.stdout + r.stderr)[-400:])
    feed_checks()
    depth_checks()
    paging_checks()
    battery_kick_checks()
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def feed_checks():
    """W1-W4: the cloud accepts every order-flow name the PC can send (the Nov 20 fills.jsonl outage), an "of" answer never
    overwrites a day's real manifest, requests / grouping, the autopilot hook never raises."""
    import datetime as dt
    import json
    import tempfile
    from engine import datafeed as DF, ofsum, tickrec
    for x in DF.EXTRAS:
        check(f"cloud accepts EXTRAS name days/<day>/{x}", bool(DF.DAY_FILE.match(f"days/2026-11-02/{x}")))
    for x in ofsum.NAMES:
        check(f"every ofsum file is in EXTRAS ({x})", f"of/{x}" in DF.EXTRAS and f"of/{x}".split("/")[1] in DF.OF_FILES)
    check("cloud refuses an unknown of/ name", not DF.DAY_FILE.match("days/2026-11-02/of/NQ_ticks.parquet"))
    with tempfile.TemporaryDirectory() as td:
        dp = os.path.join(td, "dp")
        x = ofsum.synth_day("2026-11-02", n=60_000)
        for d in ("2026-10-30", "2026-11-02"):
            check(f"write_day {d}", ofsum.write_day(d, os.path.join(dp, "days"), x=x)["ok"])
        # (1) ride-along: a normal day zip with the of/ extras -> extract accepts and writes them
        day = "2026-11-02"
        fs = {f"of/{f}": open(os.path.join(dp, "days", day, "of", f), "rb").read() for f in DF.OF_FILES}
        fs["trades.jsonl.gz"] = DF.gz(b"") if hasattr(DF, "gz") else __import__("gzip").compress(b"")
        fs["manifest.json"] = json.dumps({"day": day, "partial": False, "files": {}}).encode()
        out = os.path.join(td, "pc_days")
        try:
            w = DF.extract(DF.zip_days({day: fs}), out)
            ok = w == [(day, False)] and os.path.exists(os.path.join(out, day, "of", "NQ_meta.json"))
        except ValueError as e:
            ok, w = False, e
        check("ride-along: a normal answer with of/ files is accepted by the cloud", ok, w)
        # (2) "of" answer: build_of -> extract keeps the day's existing manifest.json
        blob, meta = DF.build_of("2026-10-01", 1795000000, dp_work=dp)
        check("build_of packs both days, what=of", meta["days"] == 2 and meta["what"] == "of" and meta["from"] == "2026-10-30", meta)
        open(os.path.join(out, day, "manifest.json"), "w").write('{"day": "2026-11-02", "keep": 1}')
        w = DF.extract(blob, out)
        man = json.load(open(os.path.join(out, day, "manifest.json")))
        check("of answer extracted; the day's real manifest.json untouched", len(w) == 2 and man.get("keep") == 1, (w, man))
        R = ofsum.read(os.path.join(out, "2026-10-30"))
        check("of days readable by the battery (ofsum.read)", R is not None and int(R["bars"].vol.sum()) == int(x["size"].sum()))
        blob2, meta2 = DF.build_of("2026-10-01", 1795000000, dp_work=dp, until="2026-10-31")
        check("build_of honours until", meta2["days"] == 1 and meta2["to"] == "2026-10-30", meta2)
        b3, m3 = DF.build_of("2026-10-01", 1795000000, dp_work=dp, max_zip=30_000)
        check("build_of size cap -> 'more'", m3["days"] == 1 and m3["more"], m3)
        bad = DF.zip_days({day: {"of/manifest.json": fs["manifest.json"], "trades.jsonl.gz": fs["trades.jsonl.gz"]}})
        try:
            DF.extract(bad, os.path.join(td, "x")); refused = False
        except ValueError:
            refused = True
        check("an of-manifest day with non-of files is refused", refused)
        # (3) requests
        now = int(dt.datetime(2026, 11, 28, 12, tzinfo=dt.timezone.utc).timestamp())          # a Saturday: outside the session
        mk = lambda j: {"time": now, "message": json.dumps(j)}
        r = DF.parse_request(mk({"v": 1, "kind": "le-data-req", "id": "abc123", "since": "2025-12-01", "what": "of", "until": "2026-09-01"}), now)
        check("of request: 400 days back, until kept", r and r["what"] == "of" and r["since"] == "2025-12-01" and r["until"] == "2026-09-01", r)
        r = DF.parse_request(mk({"v": 1, "kind": "le-data-req", "id": "abc124", "since": "2025-12-01"}), now)
        check("normal request still clamps to 60 days", r and r["what"] == "all" and r["since"] > "2026-09-25", r)
        sent = []
        DF.post_request("abc125", "2026-01-01", now, http_fn=lambda *a, **k: (sent.append(a[2]) or (200, b"{}")), what="of", until="2026-02-01")
        j = json.loads(sent[0])
        check("post_request what=of", j.get("what") == "of" and j.get("until") == "2026-02-01" and j.get("want") == ["of"], j)
        # (4) grouping in maybe_answer: an of ask and a bars ask are answered apart
        msgs = [mk({"v": 1, "kind": "le-data-req", "id": "aaa111", "since": "2026-11-01"}),
                mk({"v": 1, "kind": "le-data-req", "id": "bbb222", "since": "2026-01-05", "what": "of"})]
        body = "\n".join(json.dumps(m) for m in msgs).encode()
        wk = os.path.join(td, "feed")
        res = DF.maybe_answer(now, env={"LE_DATAFEED_TOPIC": "t-test", "LE_DATAFEED_BASE": "http://127.0.0.1:9"}, say=lambda *_: None,
                              work=wk, spawn_fn=lambda w: 4242, http_fn=lambda *a, **k: (200, body))
        req = (res or {}).get("req") or {}
        check("maybe_answer: the newest ask (of) alone, the bars ask left for the next tick",
              req.get("id") == "bbb222" and req.get("what") == "of" and req.get("also") == [] and req.get("since") == "2026-01-05", res)
        # (5) cloud: covering() never takes an of answer for bars
        from tools import data_pull as DPL
        ans = [{"days": 3, "from": "2026-11-01", "to": "2026-11-27", "what": "of"}]
        check("data_pull.covering skips of answers", DPL.covering(ans, "2026-11-02", "2026-11-26") is None)
        check("data_pull.of_days sees the pulled days", DPL.of_days(out) == ["2026-10-30", "2026-11-02"], DPL.of_days(out))
        # (6) W1: build_summaries never raises, builds, then skips
        keep = (tickrec.nq_days, ofsum.write_day)
        try:
            tickrec.nq_days = lambda: ["2026-10-30"]
            r1 = tickrec.build_summaries(out_root=os.path.join(td, "w1"))
            check("build_summaries: no tick file -> counted as failed, no raise", r1.get("failed") == 1, r1)
            ofsum.write_day = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            r2 = tickrec.build_summaries(out_root=os.path.join(td, "w1"))
            check("build_summaries: a crash inside -> error dict, never raises", "error" in r2, r2)
        finally:
            tickrec.nq_days, ofsum.write_day = keep


def depth_checks():
    """day-ofmax: LE_TickRec depth CSV -> data/depth -> per-5m depth summary -> datafeed -> cloud."""
    import json
    import tempfile
    import numpy as np
    import pandas as pd
    from engine import datafeed as DF, ofsum, tickrec as T
    with tempfile.TemporaryDirectory() as td:
        nd = os.path.join(td, "NinjaTrader 8"); dd = os.path.join(nd, "le_ticks", "depth"); os.makedirs(dd)
        keep = (T.DEPTH_DIR, T.CFG_PATH)
        T.DEPTH_DIR, T.CFG_PATH = os.path.join(td, "depth"), os.path.join(td, "data", "tickrec.json")
        try:
            t0 = int(pd.Timestamp("2026-11-02 10:00", tz="America/New_York").timestamp() * 1000)
            hdr = ",".join(T.depth_cols())
            def row(t, bp, b1, a1):
                bd = list(range(10)); bs = [b1] + [10] * 9; ad = list(range(1, 11)); as_ = [a1] + [10] * 9
                return ",".join(str(v) for v in [t, bp] + bd + bs + ad + as_)
            lines = [row(t0, 21000, 100, 30), row(t0 + 300, 21000, 30, 30),      # bid level 1 pulled (100 -> 30) at the same price
                     row(t0 + 600, 21000, 30, 90), row(t0 + 900, 21000.25, 30, 90), "1795,bad"]     # ask stacked; then bp moves
            open(os.path.join(dd, "NQ_2026-11-02.csv"), "w").write(hdr + "\n" + "\n".join(lines) + "\n")
            r = T.ingest_depth(nd)
            dp = T.read_depth("2026-11-02")
            check("depth ingested (torn line dropped)", r.get("ok") and dp is not None and len(dp) == 4, (r, None if dp is None else len(dp)))
            sm = ofsum.depth_summary(dp)
            check("depth summary: 1 bar, 1 bid pull, 1 ask stack, bp move not counted",
                  len(sm) == 1 and int(sm.pull_b[0]) == 1 and int(sm.stack_a[0]) == 1 and int(sm.pull_a[0]) == 0 and int(sm.bmax[0]) == 100, sm.to_dict("records"))
            check("depth ingest idempotent", T.ingest_depth(nd).get("files") == 0)
            out = os.path.join(td, "dp", "days")
            x = ofsum.synth_day("2026-11-02", n=40_000)
            ofsum.write_day("2026-11-02", out, x=x)
            check("write_day adds NQ_depth5m.csv.gz when depth exists", os.path.exists(os.path.join(out, "2026-11-02", "of", ofsum.DEPTH_NAME)))
            check("cloud accepts of/NQ_depth5m.csv.gz", bool(DF.DAY_FILE.match("days/2026-11-02/of/NQ_depth5m.csv.gz")) and "of/NQ_depth5m.csv.gz" in DF.EXTRAS)
            blob, meta = DF.build_of("2026-11-01", 1795000000, dp_work=os.path.join(td, "dp"))
            pc = os.path.join(td, "pc_days")
            DF.extract(blob, pc)
            R = ofsum.read(os.path.join(pc, "2026-11-02"))
            check("of answer carries the depth summary to the cloud", R is not None and R["depth"] is not None and len(R["depth"]) == 1)
            ofsum.write_day("2026-11-03", out, x=ofsum.synth_day("2026-11-03", n=40_000))
            check("a day without depth: no depth file, still fine", not os.path.exists(os.path.join(out, "2026-11-03", "of", ofsum.DEPTH_NAME)))
        finally:
            T.DEPTH_DIR, T.CFG_PATH = keep


def paging_checks():
    """day-ofmax: one "of" ask a night -> up to OF_PAGES pages, newest days first, inside the daily cap; the cloud collects them."""
    import argparse
    import datetime as dt
    import json
    import tempfile
    from engine import datafeed as DF, ofsum
    from tools import data_pull as DPL
    with tempfile.TemporaryDirectory() as td:
        dp = os.path.join(td, "dp")
        days = [d.strftime("%Y-%m-%d") for d in __import__("pandas").bdate_range("2026-10-01", periods=12)]
        for i, d in enumerate(days):
            ofsum.write_day(d, os.path.join(dp, "days"), x=ofsum.synth_day(d, n=20_000, seed=i))
        one = sum(os.path.getsize(os.path.join(dp, "days", days[0], "of", f)) for f in DF.OF_FILES)
        sent = []
        fake_send = lambda blob, meta, env=None, http_fn=None: (sent.append((blob, dict(meta))) or (True, "ok", {"id": "m%d" % len(sent)}))
        keep = DF.send
        DF.send = fake_send
        try:
            now = int(dt.datetime(2026, 11, 28, 15, tzinfo=dt.timezone.utc).timestamp())
            w = os.path.join(td, "feed")
            out = DF.answer({"id": "of1abc", "since": "2026-09-01", "what": "of"}, now, work=w, dp_work=dp,
                            max_zip=int(one * 2.6), sleep=lambda *_: None)
            pg = [m for _, m in sent]
            check("one ask -> 4 pages (the nightly cap), each <= 2-3 days", out.get("pages") == 4 and len(pg) == 4 and all(1 <= m["days"] <= 3 for m in pg), [(m["page"], m["days"]) for m in pg])
            check("pages newest first, no gap between pages",
                  pg[0]["to"] == days[-1] and all(dt.date.fromisoformat(pg[k]["from"]) > dt.date.fromisoformat(pg[k + 1]["to"]) for k in range(3)), [(m["from"], m["to"]) for m in pg])
            check("last page says more_tomorrow", pg[-1].get("more") and pg[-1].get("more_tomorrow"), pg[-1])
            st = json.load(open(os.path.join(w, "state.json")))
            check("every page counted in today's sent (daily cap)", sum(1 for x in st["sent"] if x.get("page")) == 4)
            sent.clear()
            DF.answer({"id": "of2abc", "since": "2026-09-01", "what": "of"}, now, work=w, dp_work=dp, max_zip=int(one * 2.6), sleep=lambda *_: None)
            check("a second ask the same day gets only what the cap leaves (8 - 2 reserve - 4 used = 2)", len(sent) == 2, len(sent))
            mk = lambda j: {"time": now, "message": json.dumps(j)}
            body = json.dumps(mk({"v": 1, "kind": "le-data-req", "id": "of3abc", "since": "2026-09-01", "what": "of"})).encode()
            r = DF.maybe_answer(now, env={"LE_DATAFEED_TOPIC": "t", "LE_DATAFEED_BASE": "http://127.0.0.1:9"}, say=lambda *_: None,
                                work=w, spawn_fn=lambda w_: 1, http_fn=lambda *a, **k: (200, body))
            check("PC: no second 'of' ask answered the same night", r is None, r)
        finally:
            DF.send = keep
        # cloud: collect the pages of tonight's ask by id, extract them, remember the ask (no new ask on a re-run)
        pages = [{"what": "of", "req": "rid001", "page": k + 1, "days": m["days"], "from": m["from"], "to": m["to"],
                  "more": m["more"], "more_tomorrow": m.get("more_tomorrow"), "_blob": b} for k, (b, m) in enumerate([(b, m) for b, m in []])]
        blobs = []
        for k in range(2):
            b, m = DF.build_of("2026-09-01", now, dp, int(one * 2.6), None if k == 0 else (dt.date.fromisoformat(blobs[-1][1]["from"]) - dt.timedelta(days=1)).isoformat())
            m.update(req="rid001", page=k + 1)
            if k == 1:
                m["more"] = False
            blobs.append((b, m))
        posted = []
        keep2 = (DF.post_request, DF.poll, DF.parse_answer, DPL.fetch_bundle)
        try:
            DF.post_request = lambda rid, since, now=None, env=None, http_fn=None, what="all", until=None: (posted.append((rid, since, what, until)) or (True, "ok"))
            DF.poll = lambda base, topic, since, http_fn=None: (True, [{"i": i} for i in range(len(blobs))])
            DF.parse_answer = lambda m, now=None, base=None, vk="pinned": blobs[m["i"]][1]
            DPL.fetch_bundle = lambda x: next(b for b, m in blobs if m["page"] == x["page"])
            outd = os.path.join(td, "pc_days")
            ns = argparse.Namespace(out=outd, since=None, wait=0.01)
            orig_tok = DPL.secrets.token_hex
            DPL.secrets.token_hex = lambda n: "rid001"
            rc = DPL.latest_of(ns, sleep=lambda *_: None)
            DPL.secrets.token_hex = orig_tok
            got = DPL.of_days(outd)
            check("cloud: one ask, both pages collected and extracted", rc == 0 and len(posted) == 1 and posted[0][2] == "of" and len(got) == sum(m["days"] for _, m in blobs), (rc, posted, got))
            rc2 = DPL.latest_of(ns, sleep=lambda *_: None)
            check("cloud: a re-run the same night sends no new ask", len(posted) == 1, posted)
        finally:
            DF.post_request, DF.poll, DF.parse_answer, DPL.fetch_bundle = keep2


def battery_kick_checks():
    """day-ofmax: the PC runs the battery once per look (40 / 60 / 120 / 250 summary days), never near 02:00 ET."""
    import datetime as dt
    import json
    import tempfile
    from zoneinfo import ZoneInfo
    from engine import tickrec as T
    ET = ZoneInfo("America/New_York")
    with tempfile.TemporaryDirectory() as td:
        keep = (T.BATTERY_DIR, T.BATTERY_NOTE)
        T.BATTERY_DIR, T.BATTERY_NOTE = os.path.join(td, "logs"), os.path.join(td, "note.json")
        try:
            root = os.path.join(td, "days")
            for i in range(41):
                os.makedirs(os.path.join(root, "2026-%02d-%02d" % (9 + i // 28, 1 + i % 28), "of"))
                open(os.path.join(root, "2026-%02d-%02d" % (9 + i // 28, 1 + i % 28), "of", "NQ_meta.json"), "w").write("{}")
            calls = []
            ev = dt.datetime(2026, 11, 25, 20, 0, tzinfo=ET)
            r = T.battery_kick(ev, root, runner=lambda cmd, to: calls.append((cmd, to)) or True)
            check("41 summary days: look 1 runs, output under logs/, phone line path", r["look"] == 1 and r["ran"] and "--out-dir" in calls[0][0]
                  and T.BATTERY_DIR in calls[0][0] and T.BATTERY_NOTE in calls[0][0], r)
            os.makedirs(T.BATTERY_DIR, exist_ok=True)
            json.dump([{"look": 1}], open(os.path.join(T.BATTERY_DIR, "battery_looks.json"), "w"))
            r = T.battery_kick(ev, root, runner=lambda cmd, to: calls.append(1) or True)
            check("look 1 done: not run again", not r["ran"] and len(calls) == 1, r)
            json.dump([], open(os.path.join(T.BATTERY_DIR, "battery_looks.json"), "w"))
            r = T.battery_kick(dt.datetime(2026, 11, 26, 1, 35, tzinfo=ET), root, runner=lambda cmd, to: calls.append(1) or True)
            check("01:35 ET: too close to 02:00, waits", not r["ran"] and len(calls) == 1, r)
            check("never raises on a broken folder", isinstance(T.battery_kick(ev, os.path.join(td, "nope")), dict))
        finally:
            T.BATTERY_DIR, T.BATTERY_NOTE = keep
    import importlib.util
    sp = importlib.util.spec_from_file_location("ofb", os.path.join(ROOT, "research", "orderflow", "of_battery.py"))
    B = importlib.util.module_from_spec(sp); sp.loader.exec_module(B)
    line = B.phone_line({"look": 1, "tick_days": 41, "first": "2026-09-14", "last": "2026-11-20",
                         "verdicts": {"OF1 LIT": "REJECTED", "OF5 abs": "TOO FEW"}})
    check("battery phone line: plain, says LIT stays", "OF1 REJECTED" in line and "LIT stays" in line and len(line) < 300, line)
    check("battery looks 40 / 60 / 120 / 250", B.LOOK_AT == (40, 60, 120, 250) and T.BATTERY_LOOKS == B.LOOK_AT)


if __name__ == "__main__":
    sys.exit(main())
