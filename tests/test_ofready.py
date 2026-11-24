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


if __name__ == "__main__":
    sys.exit(main())
