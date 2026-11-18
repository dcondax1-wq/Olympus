"""Data pipe + ZEUS daily review (2026-11-18, engine/datapipe.py, engine/zeus_review.py, tools/data_pull.py). Offline: the
"backup repo" is a local bare repo, git is real but never touches the network; failing git is stubbed. Temp folders only.

  python -X utf8 -m tests.test_datapipe        # ~10 s
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import datapipe as DP, zeus_review as ZR  # noqa: E402
from tools import data_pull as PULL  # noqa: E402

ET = ZoneInfo("America/New_York")
RES = []
DAY, PREV = "2026-11-18", "2026-11-17"
ACCT_A, ACCT_B = "MFFUEVB50K000001234", "MFFUEVB25K000009999"


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:400]}"))


def ts(day, hh, mm=0):
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ET).timestamp())


def git(*a, cwd=None):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def wjson(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def feed_rows(day, base=21000.0):
    rows = []
    t0 = ts(PREV if day == DAY else "2026-11-16", 18, 5)                # an evening bar belongs to the next CME day
    rows.append((t0, base, base + 1, base - 1, base + 0.5, 10))
    for i in range(60):
        t = ts(day, 9, 30) + 60 * i
        p = base + i * 0.25
        rows.append((t, p, p + 1.0, p - 0.75, p + 0.25, 100 + i))
    return rows


def make_pc(tmp, contract="MNQ 12-26"):
    root = os.path.join(tmp, "pc")
    nt = os.path.join(tmp, "nt")
    fd = os.path.join(nt, "le_feed")
    os.makedirs(fd, exist_ok=True)
    rows = feed_rows(PREV, 20990.0) + feed_rows(DAY, 21000.0)
    with open(os.path.join(fd, "MNQ_1m.csv"), "w") as fh:
        fh.write("".join(f"{t},{o},{h},{l},{c},{v}\n" for t, o, h, l, c, v in rows))
    b5 = {}
    for t, o, h, l, c, v in rows:
        k = t // 300 * 300
        x = b5.get(k)
        b5[k] = [k, o, h, l, c, v] if x is None else [k, x[1], max(x[2], h), min(x[3], l), c, x[5] + v]
    with open(os.path.join(fd, "MNQ_5m.csv"), "w") as fh:
        fh.write("".join(",".join(str(x) for x in r) + "\n" for r in sorted(b5.values())))
    with open(os.path.join(fd, "MNQ_instrument.txt"), "w") as fh:
        fh.write(contract + "\n")
    with open(os.path.join(fd, "accounts.csv"), "w") as fh:
        fh.write(f"{ACCT_A},Connected\nSim101,Connected\n")
    e1 = ts(DAY, 9, 45)
    wjson(os.path.join(root, "data", "live_state.json"), {"adapter": "ninjatrader", "nt_account": ACCT_A, "balance": 49192.78, "ledger": [
        {"t": e1 + 5, "side": "buy", "qty": 3, "entry_t": e1, "entry": 21003.0, "stop": 20990.0, "target": 21030.0,
         "result": {"ok": True, "adapter": "ninjatrader", "account": ACCT_A, "path": "C:\\Users\\owner\\Documents\\NinjaTrader 8\\incoming\\x.txt",
                    "lines": [f"PLACE;{ACCT_A};MNQ 12-26;BUY;3"]}},
        {"t": e1 + 900, "side": "exit", "qty": 3, "entry_t": e1, "reason": "TARGET", "pnl": 156.3, "exit_t": e1 + 900,
         "result": {"ok": True, "adapter": "ninjatrader"}},
        {"t": e1 + 1000, "side": "sell", "qty": 2, "entry_t": e1 + 990, "result": {"ok": False, "adapter": "ninjatrader",
                                                                                     "error": f"order refused for account {ACCT_A}: Limit 0"}}]})
    wjson(os.path.join(root, "data", "live_state_acctb.json"), {"adapter": "paper", "ledger": [
        {"t": ts(DAY, 10, 0), "side": "sell", "qty": 1, "entry_t": ts(DAY, 10, 0), "result": {"ok": True, "adapter": "paper"}},
        {"t": ts(DAY, 11, 0), "side": "exit", "qty": 1, "entry_t": ts(DAY, 10, 0), "reason": "STOP", "pnl": -80.0, "result": {"ok": True}}]})
    wjson(os.path.join(root, "data", "live_state_accounts.json"), {"accounts": {"b25k_2": {"nt_account": ACCT_B, "ledger": [
        {"t": e1 + 6, "side": "buy", "qty": 1, "entry_t": e1, "result": {"ok": True, "adapter": "ninjatrader", "account": ACCT_B}},
        {"t": e1 + 1001, "side": "sell", "qty": 1, "entry_t": e1 + 990, "result": {"ok": False, "adapter": "ninjatrader",
                                                                                   "error": f"{ACCT_B} Limit 0"}}]}}})
    os.makedirs(os.path.join(root, "data", "brain"), exist_ok=True)
    with open(os.path.join(root, "data", "brain", f"{DAY}.jsonl"), "w") as fh:
        fh.write(json.dumps({"key": "k1", "t": ts(DAY, 9, 0), "kind": "fact", "text": f"no sweep yet ({ACCT_A})"}) + "\n")
    ex = os.path.join(root, "logs", "exec_audit")
    wjson(os.path.join(ex, "notes.json"), {"blocked": {str(ts(DAY, 12, 0)): {"reason": "feed stale", "t": ts(DAY, 12, 1)}}, "uptime": []})
    wjson(os.path.join(ex, "nightly", f"{DAY}.json"), {"day": DAY, "verdict": "same", "text": "live = backtest", "rows": [
        {"status": "matched", "day": DAY, "side": "LONG", "entry_t": e1, "entry_slip_ticks": 1.0, "exit_slip_ticks": 0.0,
         "slip_usd": -1.5, "exec_usd": -1.5, "bt_pnl": 157.8, "live_pnl": 156.3}]})
    return root, nt


def branch_files(remote, ref="data"):
    c, o, _ = git("--git-dir", remote, "ls-tree", "-r", "--name-only", ref)
    return o.splitlines() if c == 0 else []


def blob(remote, path, ref="data"):
    r = subprocess.run(["git", "--git-dir", remote, "show", f"{ref}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


# ================================================================================================ checks
def privacy_checks():
    names = {ACCT_A}
    o = DP.scrub({"account": ACCT_A, "balance": 49000, "result": {"path": "C:\\Users\\me\\x", "error": f"refused {ACCT_A} and MFFUFOO55554444"},
                  "text": "see C:\\Users\\me\\file.txt", "entry": 21000.25, "nt_account": "Sim101"}, names)
    s = json.dumps(o)
    check("a. privacy: account -> last 4, balance + path dropped, Sim101 kept",
          o["account"] == "...1234" and "balance" not in o and "path" not in o["result"] and o["nt_account"] == "Sim101", o)
    check("a. privacy: names in error text masked (known + look-alike), prices untouched",
          ACCT_A not in s and "MFFUFOO55554444" not in s and "...4444" in s and o["entry"] == 21000.25 and "<path>" in o["text"], s)


def pack_checks(tmp, root, nt):
    frames = DP.bar_frames(nt, os.path.join(tmp, "arc"))
    files = DP.pack_day(DAY, frames, DP.ledger_rows(root), DP.known_names(root, nt), root, now=ts(DAY, 17, 30), build_twin=False,
                        contracts=DP.chart_contracts(nt))
    from engine import pcbars
    b1 = pcbars.decode(files["bars/MNQ_1m.csv.gz"])
    days = {DP.trading_day(int(t)) for t in b1["time"]}
    check("b. pack: the day's 1m bars only (incl. the 18:05 ET bar of the evening before)", days == {DAY} and len(b1) == 61, (days, len(b1)))
    check("b. pack: 5m bars too", "bars/MNQ_5m.csv.gz" in files and len(pcbars.decode(files["bars/MNQ_5m.csv.gz"])) >= 12)
    tr = DP.jsonl_rows(files["trades.jsonl.gz"])
    bots = {(r["bot"], r["acct"], r["mode"]) for r in tr}
    check("b. pack: every ledger (Zlarior main, extra account b25k_2, ATLAS paper) tagged bot / acct / mode",
          {("zlarior", "zlarior", "live"), ("zlarior", "b25k_2", "live"), ("atlas", "atlas", "paper")} <= bots, bots)
    allb = b"".join(gzip.decompress(v) if v[:2] == b"\x1f\x8b" else v for v in files.values())
    check("b. pack: no full account name / balance / Windows path anywhere in the day",
          ACCT_A.encode() not in allb and ACCT_B.encode() not in allb and b"49192" not in allb and b"Users" not in allb)
    man = json.loads(files["manifest.json"])
    check("b. pack: manifest (counts, chart, sha, not partial after 17:00 ET)",
          man["counts"]["entries"] == 5 and man["chart"].get("MNQ") == "MNQ 12-26" and not man["partial"]
          and all(len(v["sha256"]) == 64 for v in man["files"].values()), man)
    dc = DP.jsonl_rows(files["decisions.jsonl.gz"])
    check("b. pack: decisions = brain log + held-back entries", {r["src"] for r in dc} == {"brain", "held_back"}, dc)


def push_checks(tmp, root, nt):
    remote = os.path.join(tmp, "remote.git")
    git("init", "-q", "--bare", remote)
    git("--git-dir", remote, "symbolic-ref", "HEAD", "refs/heads/pc")
    work = os.path.join(tmp, "work")
    emitted, pushed = [], []
    kw = dict(root=root, work=work, folder=nt, url=remote, build_twin=False, archive_root=os.path.join(tmp, "arc"),
              edge={"light": "GREEN", "line": "Edge health: GREEN"},
              emit=lambda *a: emitted.append(a) or {"ok": 1}, notify=lambda text, title: pushed.append(text) or (True, "ok"))
    g = DP.Git(os.path.join(root, DP.SCRATCH_REL), cwd=root, exe="git")
    r0 = DP.run(now=ts(DAY, 16, 45), g=g, days=[DAY], **kw)          # on demand before the close: the day is "partial"
    part0 = json.loads(blob(remote, f"days/{DAY}/manifest.json") or b"{}").get("partial")
    _c, tip0, _ = git("--git-dir", remote, "rev-parse", "data")
    r = DP.run(now=ts(DAY, 17, 10), g=g, **kw)                       # the nightly run: completes today + backfills the day before
    fs = branch_files(remote)
    check("c. run: on demand before the close = partial; the nightly run packs both days and pushes to branch data",
          part0 is True and r["pushed"] and r["pushed"].get("ok") and sorted(r["days"]) == [PREV, DAY] and
          f"days/{DAY}/manifest.json" in fs and f"days/{PREV}/bars/MNQ_1m.csv.gz" in fs and "README.md" in fs, (r0, r, fs[:6]))
    check("c. run: the review is in the day folder", f"days/{DAY}/review.json" in fs and
          json.loads(blob(remote, f"days/{DAY}/review.json"))["day"] == DAY)
    c, refs, _ = git("--git-dir", remote, "for-each-ref", "--format=%(refname)")
    check("c. run: only refs/heads/data exists on the backup (pc / main never written)", refs.splitlines() == ["refs/heads/data"], refs)
    allb = b"".join(gzip.decompress(x) if x[:2] == b"\x1f\x8b" else x for x in [blob(remote, p) or b"" for p in fs])
    check("c. run: no full account name on the branch", ACCT_A.encode() not in allb and ACCT_B.encode() not in allb)
    check("c. review: one board event, one push (2 orders refused = action), not repeated by the nightly run",
          len(emitted) == 1 and emitted[0][0] == "daily_review" and len(pushed) == 1 and "refused" in pushed[0], (emitted, pushed))
    # d. the partial day was completed (replaced); another run has nothing new
    _c, tip1, _ = git("--git-dir", remote, "rev-parse", "data")
    part = json.loads(blob(remote, f"days/{DAY}/manifest.json"))["partial"]
    r3 = DP.run(now=ts(DAY, 17, 45), g=g, **kw)
    _c, tip2, _ = git("--git-dir", remote, "rev-parse", "data")
    check("d. after the close: the partial day completed, then nothing new (no commit)",
          tip0 != tip1 and part is False and r3["days"] == [] and tip1 == tip2 and len(emitted) == 1, (r3, tip0, tip1, tip2, part))
    hist = git("--git-dir", remote, "rev-list", "--count", "data")[1]
    # e. append-only: an old day's file with other bytes is kept; a recent one is replaced
    old = "2026-10-01"
    res = DP.push_files({f"days/{old}/manifest.json": b"{}"}, remote, g=g, replace_ok=DP.replace_ok_for(DAY))
    res2 = DP.push_files({f"days/{old}/manifest.json": b'{"x":1}'}, remote, g=g, replace_ok=DP.replace_ok_for(DAY))
    res3 = DP.push_files({f"days/{DAY}/decisions.jsonl.gz": DP.gz(b"")}, remote, g=g, replace_ok=DP.replace_ok_for(DAY))
    check("e. append-only: a day older than REPLACE_DAYS keeps its file, a recent day may be completed",
          res["ok"] and res2.get("unchanged") and res2.get("kept") == 1 and blob(remote, f"days/{old}/manifest.json") == b"{}"
          and res3["ok"] and res3.get("replaced") == 1, (res, res2, res3))
    c, ff, _ = git("--git-dir", remote, "merge-base", "--is-ancestor", tip1, "data")
    check("e. append-only: history only grows (old tip is an ancestor, never forced)", c == 0 and
          int(git("--git-dir", remote, "rev-list", "--count", "data")[1]) > int(hist))
    # f. branch guard
    rb = DP.push_files({"x": b"1"}, remote, g=g, branch="pc")
    check("f. the pipe refuses any branch but data", not rb["ok"] and "refused" in rb["error"] and
          git("--git-dir", remote, "rev-parse", "-q", "--verify", "refs/heads/pc")[0] != 0, rb)

    # g. someone moved the branch between our read and our push: rebuilt on the new tip once
    class Racy(DP.Git):
        raced = False

        def run(self, args, **k):
            if "push" in args and not Racy.raced:
                Racy.raced = True
                other = os.path.join(tmp, "other")
                git("clone", "-q", "-b", "data", remote, other)
                with open(os.path.join(other, "other.txt"), "w") as fh:
                    fh.write("x")
                git("-C", other, "add", "other.txt")
                git("-C", other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "other")
                git("-C", other, "push", "-q", "origin", "data")
            return super().run(args, **k)
    rr = DP.push_files({f"days/{DAY}/extra.json": b"{}"}, remote, g=Racy(g.git_dir, cwd=root, exe="git"))
    fs2 = branch_files(remote)
    check("g. a moved branch: rebuilt on its new tip, both files kept", rr.get("ok") and rr.get("attempts") == 2 and
          "other.txt" in fs2 and f"days/{DAY}/extra.json" in fs2, rr)
    # h. backup not reachable / git missing: soft errors, counted
    bad = DP.run(now=ts(DAY, 17, 40), g=g, days=[DAY], **{**kw, "url": os.path.join(tmp, "nope.git")})
    st = DP._read_json(os.path.join(work, "state.json"), {})
    check("h. backup not reachable: no exception, the local copy is still written, fails counted",
          not (bad["pushed"] or {}).get("ok") and st.get("fails") == 1 and os.path.exists(os.path.join(work, "days", DAY, "manifest.json")), bad)
    nog = DP.push_files({"days/x/y": b"1"}, remote, g=DP.Git(g.git_dir, cwd=root, exe=os.path.join(tmp, "no-such-git")))
    check("h. no git at all: a clean error, never raises", nog["ok"] is False and nog.get("error"), nog)
    return remote


def review_checks():
    def day(d, entries=0, bt=0, bars=True, rejected=0):
        tr = [{"side": "buy", "bot": "zlarior", "acct": "zlarior", "mode": "live", "t": 1, "result": {"ok": True}}] * entries
        tr += [{"side": "buy", "bot": "zlarior", "acct": "zlarior", "mode": "live", "t": 2, "result": {"ok": False, "error": "Limit 0"}}] * rejected
        rows = [{"status": "missed", "pc_on": False, "missed_usd": 100}] * bt
        return {"day": d, "trades": tr, "twin": {"nightly": {"rows": rows, "verdict": "pc off" if bt else "no trades"}},
                "manifest": {"files": {"bars/MNQ_1m.csv.gz": {"rows": 900 if bars else 0}}}}
    ds = [f"2026-11-{x:02d}" for x in (9, 10, 11, 12, 13, 16, 17, 18)]
    quiet = [day(d, bt=0) for d in ds[:2]] + [day(d, bt=0) for d in ds[2:]]
    R = ZR.review(quiet, {"light": "GREEN"})
    check("i. review: 8 quiet sessions with no setups = info only, nothing needs you",
          not R["action"] and any(i["key"] == "no_trades" for i in R["items"]) and "nothing needs you" in R["text"], R["items"])
    R = ZR.review([day(ds[0], entries=1)] + [day(d, bt=1) for d in ds[1:]], {"light": "GREEN"})
    check("i. review: 7 sessions without an entry while the backtest traded = action", R["action"] and
          any(i["key"] == "no_trades" and i["level"] == "act" for i in R["items"]), R["items"])
    R = ZR.review([day(ds[0], entries=1)] + [day(ds[1], entries=1, bars=False)], {"light": "RED"}, prev={"light": "GREEN"})
    keys = {i["key"] for i in R["items"] if i["level"] == "act"}
    check("i. review: no bars for the session + the light turning RED = action", {"bars", "edge_red"} <= keys, keys)
    closed = [{"side": "exit", "bot": "zlarior", "acct": "zlarior", "mode": "live", "pnl": -50.0 if i % 3 else 40.0, "t": i,
               "entry_t": i} for i in range(20)]
    R = ZR.review([{"day": ds[-1], "trades": closed, "twin": {}, "manifest": {"files": {"bars/MNQ_1m.csv.gz": {"rows": 1}}}}], {})
    check("i. review: Zlarior last 20 PF < 1 -> a research proposal (never a setting), with the proof rule",
          R["stats"]["zlarior"]["n"] == 20 and R["stats"]["zlarior"]["pf"] < 1 and
          any(p["bot"] == "zlarior" and "Strategy changes" in p["rule"] for p in R["proposals"]), R["proposals"])
    R = ZR.review([day(ds[-1], entries=1)], {}, pipe={"fails": 2})
    check("i. review: the data push failing twice = action with the sign-in fix", any(i["key"] == "pipe" and "--signin" in i["fix"]
                                                                                   for i in R["items"]), R["items"])


def pull_checks(tmp, remote):
    cloud = os.path.join(tmp, "cloud")
    git("init", "-q", cloud)
    git("-C", cloud, "fetch", "-q", remote, "data")
    dd = os.path.join(tmp, "cloud_data")
    os.makedirs(dd, exist_ok=True)
    with open(os.path.join(dd, "NQ_1m.csv"), "w") as fh:     # the TradingView export ends the day before
        fh.write("time,open,high,low,close,volume\n" + "".join(f"{ts('2026-11-16', 10, 0) + 60 * i},20980,20981,20979,20980.5,5\n" for i in range(30)))
    with open(os.path.join(dd, "NQ_5m.csv"), "w") as fh:
        fh.write("time,open,high,low,close,volume\n" + "".join(f"{ts('2026-11-16', 10, 0) + 300 * i},20980,20981,20979,20980.5,5\n" for i in range(6)))
    wjson(os.path.join(dd, "NQ_rolls.json"), {"sym": "NQ", "anchor": "NQZ26", "rolls": []})
    out = os.path.join(tmp, "pc_days")
    q = os.path.join(tmp, "zeus_queue.jsonl")
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = PULL.main(["--repo", cloud, "--ref", "FETCH_HEAD", "--out", out, "--data", dd, "--queue", q, "--review"])
    txt = buf.getvalue()
    import pandas as pd
    n1 = pd.read_csv(os.path.join(dd, "NQ_1m.csv"))
    check("j. data_pull: day folders copied", rc == 0 and os.path.exists(os.path.join(out, DAY, "trades.jsonl.gz")), txt)
    check("j. data_pull: PC bars appended after the export (both days), old export rows untouched",
          int(n1["time"].max()) == ts(DAY, 10, 29) and len(n1) == 30 + 61 * 2 and
          float(n1[n1["time"] == ts("2026-11-16", 10, 0)]["close"].iloc[0]) == 20980.5, (len(n1), txt))
    check("j. data_pull: the review is rebuilt from the same files", "ZEUS Nov 18" in txt, txt)
    with contextlib.redirect_stdout(io.StringIO()):
        PULL.main(["--repo", cloud, "--ref", "FETCH_HEAD", "--out", out, "--data", dd, "--queue", q])
    n2 = pd.read_csv(os.path.join(dd, "NQ_1m.csv"))
    check("j. data_pull: a second pull adds nothing", len(n2) == len(n1))
    # a chart on the next contract with the roll not recorded: refused, never mixed
    wjson(os.path.join(dd, "NQ_rolls.json"), {"sym": "NQ", "anchor": "NQH27", "rolls": []})
    F, notes = PULL.gather(out, "NQ", data_dir=dd)
    check("j. data_pull: a chart on another contract than the roll anchor is refused with the fix",
          len(F["1m"]) == 0 and notes and "record the roll" in notes[0], notes)


def schedule_checks(tmp):
    w = os.path.join(tmp, "sched")
    calls = []
    sp = lambda work: calls.append(work) or os.getpid()   # noqa: E731  (a live pid: "still running")
    env = {"LE_DATAPIPE": "1"}
    r1 = DP.maybe_run(now=ts(DAY, 10, 0), say=lambda *a: None, env=env, work=w, spawn_fn=sp, root=os.path.join(tmp, "pc"))
    r2 = DP.maybe_run(now=ts(DAY, 17, 10), say=lambda *a: None, env=env, work=w, spawn_fn=sp, root=os.path.join(tmp, "pc"))
    r3 = DP.maybe_run(now=ts(DAY, 17, 20), say=lambda *a: None, env=env, work=w, spawn_fn=sp, root=os.path.join(tmp, "pc"))
    check("k. schedule: never in session hours; after 17:05 ET one child; not again while it runs",
          r1 is None and r2 == os.getpid() and r3 is None and len(calls) == 1, (r1, r2, r3, calls))
    off = DP.maybe_run(now=ts(DAY, 16, 45), env={"LE_DATAPIPE": "0"}, work=w, spawn_fn=sp)
    check("k. schedule: LE_DATAPIPE=0 = off", off is None and len(calls) == 1)
    st = DP._read_json(os.path.join(w, "state.json"), {})
    st["done_day"] = DAY
    DP._write_json(os.path.join(w, "state.json"), st)
    os.remove(os.path.join(w, "running.json"))
    r4 = DP.maybe_run(now=ts(DAY, 18, 0), say=lambda *a: None, env=env, work=w, spawn_fn=sp, root=os.path.join(tmp, "pc"))
    sat = DP.last_session(ts("2026-11-21", 12, 0))
    check("k. schedule: done for the day = nothing; Saturday's newest session is Friday", r4 is None and sat == "2026-11-20", (r4, sat))
    col = DP._jl_read(os.path.join(w, DP.ARCHIVE))
    check("k. every hook call archives the ledger rows (state files keep today only)", len(col) >= 6, len(col))
    src = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read() + open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read()
    check("k. wired into the PC's report task and the ops task", src.count("datapipe") >= 2 and "maybe_run" in src)
    from engine import board_events as BE
    check("k. board kind daily_review exists (quiet, not LOUD)", "daily_review" in BE.KINDS and "daily_review" not in BE.LOUD)


def main():
    tmp = tempfile.mkdtemp(prefix="le_dp_")
    try:
        root, nt = make_pc(tmp)
        privacy_checks()
        pack_checks(tmp, root, nt)
        remote = push_checks(tmp, root, nt)
        review_checks()
        pull_checks(tmp, remote)
        schedule_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\ndata pipe + ZEUS review: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
