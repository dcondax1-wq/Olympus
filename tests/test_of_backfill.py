"""night-of-backfill 2026-11-27: the PC's order-flow year to the cloud by ntfy's own count (engine/ofpack, engine/ofbackfill,
engine/datafeed "bf", tools/of_backfill). In-process fake ntfy (topic + attachments + GET /v1/account with a live message and
attachment-room count) and a fake git remote (a local bare repo). Synthetic ticks only, no network, nothing in data/.
    python -X utf8 -m tests.test_of_backfill
"""
from __future__ import annotations

import ast
import datetime as dt
import gzip
import json
import os
import secrets
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "server")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def ts(y, mo, d, hh, mm=0):
    from zoneinfo import ZoneInfo
    return int(dt.datetime(y, mo, d, hh, mm, tzinfo=ZoneInfo("America/New_York")).timestamp())


class Hub:
    """ntfy.sh as this code uses it, in process: POST/PUT /<topic>, GET /<topic>/json?poll=1, GET /file/<id>, GET /v1/account.
    Every publish takes one message of today's count; attachments take room until they expire (3 h)."""

    def __init__(self, base="http://127.0.0.1:1", limit=250, used=0, reset_at=0, att_total=20 * 1024 * 1024):
        self.base, self.limit, self.used, self.reset_at, self.att_total = base, limit, used, reset_at, att_total
        self.msgs, self.files, self.now, self.tamper, self.account_ok = [], {}, 0, False, True

    def att_used(self):
        return sum(len(b) for b, exp in self.files.values() if exp > self.now)

    def http(self, method, url, body=None, headers=None, timeout=8.0, limit=4_000_000):
        u = urllib.parse.urlparse(url)
        if method == "GET" and u.path == "/v1/account":
            if not self.account_ok:
                return 500, b"{}"
            return 200, json.dumps({"limits": {"messages": self.limit, "attachment_file_size": 2097152, "attachment_total_size": self.att_total},
                                    "stats": {"messages": self.used, "messages_remaining": max(0, self.limit - self.used),
                                              "attachment_total_size_remaining": self.att_total - self.att_used(),
                                              "reset_at": self.reset_at}}).encode()
        if method == "GET" and u.path.startswith("/file/"):
            f = self.files.get(u.path[6:].split(".")[0])
            if not f or f[1] < self.now:
                return 404, b"{}"
            return 200, (f[0] + b"x") if self.tamper else f[0]
        if method == "GET" and u.path.endswith("/json"):
            return 200, "".join(json.dumps(m) + "\n" for m in self.msgs).encode()
        if method in ("POST", "PUT"):
            if self.used >= self.limit:
                return 429, b'{"http":429}'
            h = headers or {}
            mid = secrets.token_hex(6)
            m = {"id": mid, "time": int(self.now), "expires": int(self.now) + 43200, "event": "message"}
            if h.get("Filename"):
                if len(body) > 2 * 1024 * 1024 or len(body) > self.att_total - self.att_used():
                    return 413, b'{"http":413}'
                self.files[mid] = (body, int(self.now) + 10800)
                m["message"] = h.get("Message")
                m["attachment"] = {"url": f"{self.base}/file/{mid}.bin", "size": len(body), "expires": int(self.now) + 10800}
            else:
                m["message"] = body.decode()
            self.used += 1
            self.msgs.append(m)
            return 200, json.dumps(m).encode()
        return 404, b"{}"


def make_days(dp, days, n=20_000):
    from engine import ofsum
    for i, d in enumerate(days):
        ofsum.write_day(d, os.path.join(dp, "days"), x=ofsum.synth_day(d, n=n, seed=100 + i))


def raw_of(day_dir):
    out = {}
    for f in sorted(os.listdir(os.path.join(day_dir, "of"))):
        if f == "manifest.json":
            continue
        b = open(os.path.join(day_dir, "of", f), "rb").read()
        out[f] = gzip.decompress(b) if f.endswith(".gz") else b
    return out


def pack_checks(td):
    from engine import ofpack
    dp = os.path.join(td, "dpk")
    days = ["2026-10-05", "2026-10-06", "2026-10-07"]
    make_days(dp, days, n=200_000)
    files = {}
    for d in days:
        for f in os.listdir(os.path.join(dp, "days", d, "of")):
            files[f"days/{d}/of/{f}"] = open(os.path.join(dp, "days", d, "of", f), "rb").read()
    blob = ofpack.pack(files)
    back = ofpack.contents(blob)
    same = all(back[p] == (gzip.decompress(b) if p.endswith(".gz") else b) for p, b in files.items()) and set(back) == set(files)
    check("a. ofpack: lossless (every file's content back byte for byte)", same)
    gz = sum(len(b) for b in files.values())
    check("a. ofpack: page <= 0.65 of the gzip bytes (more days per ntfy message)", len(blob) <= 0.65 * gz, (len(blob), gz))
    bad = bytearray(blob)
    bad[len(bad) // 2] ^= 0x55
    try:
        ofpack.unpack(bytes(bad))
        hit = False
    except ValueError:
        hit = True
    check("a. ofpack: a damaged page is refused (ValueError, nothing returned)", hit)
    try:
        ofpack.pack({"days/../x": b"1"})
        hit = False
    except ValueError:
        hit = True
    check("a. ofpack: a '..' path is refused", hit)
    check("a. ofpack selftest (odd CSVs travel as text, '-0.0' / quotes kept)", ofpack.selftest())


def bitmap_checks():
    from engine import ofbackfill as BF
    have = ["2026-11-26", "2026-11-25", "2026-10-01", "2026-01-02", "2025-11-10"]
    hb = BF.have_bitmap(have)
    back = BF.have_days(hb)
    check("b. 'have' bitmap round trip (400+ days in <= 80 characters)", back == set(have) and len(hb["hb"]) <= 80, (sorted(back), hb))
    check("b. a bad bitmap = nothing held (the PC sends all, never skips a day)", BF.have_days({"hb0": "2026-11-26", "hb": "%%%"}) == set())


def budget_checks():
    from engine import ofbackfill as BF
    # Monday 19:05 ET = 00:05 UTC Tuesday: ntfy's day just reset; the session (01:50-16:10 ET) still ahead in this UTC day
    mon = ts(2026, 11, 30, 19, 5)
    reset = ts(2026, 12, 1, 19, 0)
    q = {"remaining": 248, "used": 2, "limit": 250, "reset_at": reset, "att_left": 20_900_000, "att_file": 2_097_152}
    b = BF.budget(mon, q, {}, 1_850_000)
    m = b["math"]
    check("c. weekday evening: projection = the PC's ~210-230 posts still ahead; a few pages only", 200 <= m["projected"] <= 235 and 1 <= b["pages"] <= 12, b)
    check("c. weekday: pages never eat the alert + answer reserve", m["remaining"] - b["pages"] >= m["projected"] + BF.ALERT_RESERVE + BF.ANSWER_RESERVE, m)
    sat = ts(2026, 11, 28, 2, 0)                   # Saturday 02:00 ET: market closed, ntfy day began Fri 19:00 ET
    q2 = {**q, "remaining": 230, "used": 20, "reset_at": ts(2026, 11, 28, 19, 0)}
    b2 = BF.budget(sat, q2, {}, 1_850_000)
    check("c. weekend: the message count is wide, the 20 MiB attachment room binds (<= 10 pages)", b2["pages"] == min(BF.MAX_PAGES, (q2["att_left"] - BF.STORE_KEEP) // 1_850_000) and b2["math"]["msg_free"] > 50, b2)
    check("c. ntfy did not say its count -> 0 pages", BF.budget(mon, None, {}, 1_850_000)["pages"] == 0)
    low = BF.budget(mon, {**q, "remaining": 230}, {}, 1_850_000)
    check("c. remaining close to the projection -> 0 pages (trade alerts keep their room)", low["pages"] == 0 and "reserve" in low["why"], low)
    full = BF.budget(sat, {**q2, "att_left": 3_000_000}, {}, 1_850_000)
    check("c. attachment room used -> 0 pages", full["pages"] == 0 and "attachment" in full["why"], full)
    utc = dt.datetime.fromtimestamp(sat, dt.timezone.utc).strftime("%Y-%m-%d")
    capd = BF.budget(sat, q2, {"bf_sent": [{"utc": utc}] * BF.DAY_MAX}, 1_850_000)
    check("c. at most DAY_MAX pages a UTC day (a stranger's asks cannot burn more)", capd["pages"] == 0, capd)
    # learning: 4 samples of 15 min, 1 post each outside the session -> learned 4/h x 1.25 = 5 (>= MIN_RATE)
    st, hub = {}, Hub(used=10, reset_at=ts(2026, 11, 29, 19, 0))
    t = ts(2026, 11, 28, 20, 0)
    for k in range(6):
        hub.now = t + k * 900
        BF.sample(st, hub.now, hub.base, hub.http)
        hub.used += 1
    r = BF.rates(st)
    check("d. learned rate from ntfy's own count (closed market: 4/h x 1.25 safety)", abs(r["closed"] - 5.0) < 0.01 and st["bf_rates"]["closed"]["n"] == 5, (r, st.get("bf_rates")))
    st2 = {"bf_own": 0}
    hub2 = Hub(used=10, reset_at=ts(2026, 11, 29, 19, 0))
    for k in range(6):
        hub2.now = t + k * 900
        BF.sample(st2, hub2.now, hub2.base, hub2.http)
        hub2.used += 3
        st2["bf_own"] += 3                     # the PC's own backfill pages are not counted as its normal rate
    check("d. the backfill's own pages are taken out of the learned rate", st2["bf_rates"]["closed"]["r"] == 0 and BF.rates(st2)["closed"] == BF.MIN_RATE, st2.get("bf_rates"))


def flow_checks(td):
    from engine import datafeed as DF, ofbackfill as BF
    import pandas as pd
    import importlib
    OB = importlib.import_module("tools.of_backfill")
    DPL = importlib.import_module("tools.data_pull")
    dp = os.path.join(td, "dp")
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-08-03", periods=40)]
    make_days(dp, days)
    one = sum(os.path.getsize(os.path.join(dp, "days", days[0], "of", f)) for f in DF.OF_FILES)
    max_zip = int(one * 3.2)                          # a small page in the test (real: 1.85 MB), so many pages are needed
    hub = Hub(used=30, reset_at=ts(2026, 11, 28, 19, 0))
    hub.now = ts(2026, 11, 27, 20, 0)                 # Friday 20:00 ET: outside the session
    env = {"LE_DATAFEED_BASE": hub.base, "LE_DATAFEED_TOPIC": "bftest"}
    out = os.path.join(td, "cloud")
    os.makedirs(out)
    # the cloud already holds 6 of the days (copied as a real earlier pull would have left them)
    import shutil
    for d in days[-6:]:
        shutil.copytree(os.path.join(dp, "days", d, "of"), os.path.join(out, d, "of"))
    keep = (DF.http, DF.feed_cfg, DF.parse_answer)
    keep_env = dict(os.environ)
    try:
        DF.http = hub.http
        os.environ.update(env)
        real_parse = DF.parse_answer
        DF.parse_answer = lambda m, now=None, base=None, vk="pinned": real_parse(m, now, base, vk=None)
        clock = [hub.now]
        r0 = OB.ask_and_collect(out, wait_min=0, pages=12, now_fn=lambda: clock[0])
        asks = [json.loads(m["message"]) for m in hub.msgs if "le-data-req" in m["message"]]
        check("e. cloud: ONE 'bf' ask with what it holds (6 days in the bitmap)", len(asks) == 1 and asks[0]["what"] == "bf"
              and len(BF.have_days(asks[0])) == 6, asks)
        # the PC's 5-minute hook sees it and runs the child (here: inline)
        w = os.path.join(td, "feed")
        ran = []

        def spawn_sync(work):
            req = json.load(open(os.path.join(work, "pending.json")))
            ran.append(DF.answer(req, hub.now, work=work, env=env, http_fn=hub.http, dp_work=dp, max_zip=max_zip,
                                 sleep=lambda s: setattr(hub, "now", hub.now + s)))
            return 4242
        orig_build = BF.answer_bf

        def no_build(*a, **k):
            k["build"] = lambda: {"made": 0}
            return orig_build(*a, **k)
        BF.answer_bf = no_build
        try:
            res = DF.maybe_answer(hub.now, env=env, say=lambda *_: None, work=w, spawn_fn=spawn_sync, http_fn=hub.http)
        finally:
            BF.answer_bf = orig_build
        a = ran[0] if ran else {}
        check("e. PC: the hook started the answer for the bf ask", bool(res) and res["req"]["what"] == "bf" and a.get("ok"), (res, a))
        pages = [json.loads(m["message"]) for m in hub.msgs if '"what":"bf"' in (m.get("message") or "") and "le-data-req" not in m["message"]]
        sent_days = []
        for p in pages:
            sent_days += [d for d in days if p.get("from") <= d <= p.get("to")]
        missing = days[:-6]
        check("e. PC: pages carry ONLY the 34 days the cloud lacks, newest first, no day twice",
              sorted(sent_days) == sorted(missing) and len(set(sent_days)) == len(sent_days)
              and all(pages[k]["from"] > pages[k + 1]["to"] for k in range(len(pages) - 1)), [(p["page"], p["from"], p["to"]) for p in pages])
        check("e. PC: every page <= the page size, packed (enc ofp1), with its sha256 + the PC's holdings",
              all(p["bytes"] <= max_zip and p["enc"] == "ofp1" and len(p["sha256"]) == 64 and p["pc"].get("of_days") == 40 for p in pages), pages[:1])
        check("e. PC: answered under ntfy's limits (no 429 / 413)", all(p.get("bytes") for p in pages) and hub.used <= hub.limit)
        st = json.load(open(os.path.join(w, "state.json")))
        check("e. PC: bf pages kept apart from the bars answers' daily cap (state 'sent' untouched)",
              len(st.get("bf_sent") or []) == len(pages) and not [s for s in (st.get("sent") or []) if s.get("page")], st.get("sent"))
        r1 = OB.ask_and_collect(out, wait_min=0.01, pages=12, sleep=lambda s: None, now_fn=lambda: clock[0])
        got = OB.of_days(out)
        check("e. cloud: the pages collected into data/pc_days: every one of the 40 days now", len(got) == 40 and r1["pages"] == len(pages), (len(got), r1))
        same = all(raw_of(os.path.join(out, d)) == raw_of(os.path.join(dp, "days", d)) for d in missing)
        check("e. cloud: every day's content = the PC's, byte for byte", same)
        n_asks = len([m for m in hub.msgs if "le-data-req" in m["message"]])
        check("e. cloud: a re-run within 3 h reuses the ask (no second ask)", n_asks == 1, n_asks)
        # tampered download: nothing written
        out2 = os.path.join(td, "cloud2")
        os.makedirs(out2)
        hub.tamper = True
        x = [real_parse(m, hub.now, hub.base, vk=None) for m in hub.msgs]
        x = [y for y in x if y and y.get("what") == "bf" and y.get("days")][0]
        try:
            OB.extract_bf(DPL.fetch_bundle(x), out2)
            hit = False
        except ValueError:
            hit = True
        check("e. cloud: a download that differs from the PC's sha256 is refused", hit and not OB.of_days(out2))
        hub.tamper = False
    finally:
        DF.http, DF.feed_cfg, DF.parse_answer = keep
        os.environ.clear()
        os.environ.update(keep_env)
    return dp, days, out, max_zip


def reserve_checks(td, dp, days, max_zip):
    """The quota stops the pages: with ntfy's count near the projection only what fits goes, then 'more_tomorrow'."""
    from engine import datafeed as DF, ofbackfill as BF
    hub = Hub(reset_at=ts(2026, 12, 1, 19, 0))
    hub.now = ts(2026, 11, 30, 19, 10)               # Monday evening: tomorrow's session is still in this UTC day
    need = BF.projected(hub.now, hub.reset_at, BF.rates({}))
    hub.used = int(hub.limit - (need + BF.ALERT_RESERVE + BF.ANSWER_RESERVE + 2.5))   # room for exactly 2 pages
    env = {"LE_DATAFEED_BASE": hub.base, "LE_DATAFEED_TOPIC": "bftest2"}
    w = os.path.join(td, "feed2")
    r = BF.answer_bf({"id": "bfres01", "since": "2026-01-01", "pages": 12}, hub.now, w, env, hub.http, dp, max_zip, [],
                     sleep=lambda s: setattr(hub, "now", hub.now + s), build=lambda: {})
    msgs = [json.loads(m["message"]) for m in hub.msgs]
    check("f. weekday: ntfy's count allows 2 pages -> exactly 2 go, the last says more_tomorrow", r["pages"] == 2 and msgs[-1].get("more_tomorrow")
          and msgs[-1].get("more"), (r, [(m.get("page"), m.get("more"), m.get("more_tomorrow")) for m in msgs]))
    left = hub.limit - hub.used
    check("f. after them ntfy still has the projected posts + the alert reserve", left >= need + BF.ALERT_RESERVE, (left, need))
    hub3 = Hub(reset_at=ts(2026, 12, 1, 19, 0), used=240)
    hub3.now = hub.now
    r3 = BF.answer_bf({"id": "bfres02", "since": "2026-01-01"}, hub3.now, os.path.join(td, "feed3"), env, hub3.http, dp, max_zip, [],
                      sleep=lambda s: None, build=lambda: {})
    check("f. no room at all -> no page and NO message (not even the 'held' line)", r3["pages"] == 0 and hub3.used == 240, (r3, hub3.used))
    hub4 = Hub(reset_at=ts(2026, 11, 28, 19, 0))
    hub4.now = ts(2026, 11, 27, 20, 0)
    hub4.account_ok = False
    r4 = BF.answer_bf({"id": "bfres03", "since": "2026-01-01"}, hub4.now, os.path.join(td, "feed4"), env, hub4.http, dp, max_zip, [],
                      sleep=lambda s: None, build=lambda: {})
    check("f. ntfy's count unknown -> no page", r4["pages"] == 0 and hub4.used == 0, r4)
    hub5 = Hub(reset_at=ts(2026, 12, 1, 19, 0))
    hub5.now = ts(2026, 12, 1, 3, 0)                 # Tuesday 03:00 ET: the session
    r5 = BF.answer_bf({"id": "bfres04", "since": "2026-01-01"}, hub5.now, os.path.join(td, "feed5"), env, hub5.http, dp, max_zip, [],
                      sleep=lambda s: None, build=lambda: {})
    check("f. never in the weekday session (01:50-16:00 ET)", r5["pages"] == 0 and "session" in str(r5.get("why")), r5)
    check("f. the hook itself stays silent in the session", DF.maybe_answer(hub5.now, env=env, say=lambda *_: None, work=os.path.join(td, "feed5"),
                                                                            spawn_fn=lambda w_: 1, http_fn=hub5.http) is None)


def store_checks(td, out):
    import importlib
    OB = importlib.import_module("tools.of_backfill")
    remote = os.path.join(td, "remote.git")
    subprocess.run(["git", "init", "-q", "--bare", remote], check=True)
    repo = os.path.join(td, "repo")
    subprocess.run(["git", "init", "-q", repo], check=True)
    store = os.path.join(td, "store")
    wrote = OB.save(out, store)
    check("g. store: one file a month (lossless pack)", wrote == sorted({d[:7] for d in OB.of_days(out)}), wrote)
    check("g. store: a second save with nothing new writes nothing", OB.save(out, store) == [])
    ok, why = OB.push(store, remote=remote, repo=repo, sleep=lambda s: None)
    check("g. store: pushed to branch of-store of the (fake) remote", ok and subprocess.run(["git", "--git-dir", remote, "rev-parse", "refs/heads/of-store"],
                                                                                       capture_output=True).returncode == 0, why)
    ok2, why2 = OB.push(store, remote=remote, repo=repo, sleep=lambda s: None)
    check("g. store: an unchanged store pushes nothing", ok2 and why2 == "unchanged", why2)
    repo2 = os.path.join(td, "repo2")
    subprocess.run(["git", "init", "-q", repo2], check=True)
    fresh = os.path.join(td, "fresh_days")
    n = OB.restore(fresh, os.path.join(td, "store2"), remote=remote, repo=repo2)
    same = n == len(OB.of_days(out)) and all(raw_of(os.path.join(fresh, d)) == raw_of(os.path.join(out, d)) for d in OB.of_days(out))
    check("g. a NEW cloud session restores every day from the branch, byte for byte", same, (n, len(OB.of_days(out))))
    check("g. restore again: nothing to write", OB.restore(fresh, os.path.join(td, "store2"), remote=remote, repo=repo2) == 0)


def hostile_checks(td):
    import importlib
    from engine import ofpack
    OB = importlib.import_module("tools.of_backfill")
    blob = ofpack.pack({"days/2026-10-01/trades.jsonl.gz": gzip.compress(b"{}\n"), "days/2026-10-01/manifest.json": b'{"day":"2026-10-01"}'})
    try:
        OB.extract_bf(blob, os.path.join(td, "hx"))
        hit = False
    except ValueError:
        hit = True
    check("h. a page with a non-order-flow file (trades) is refused", hit and not os.path.exists(os.path.join(td, "hx", "2026-10-01")))
    blob2 = ofpack.pack({"days/2026-10-01/of/NQ_meta.json": b"{}", "days/2026-10-01/of/manifest.json": b'{"day":"2026-10-02"}'})
    try:
        OB.extract_bf(blob2, os.path.join(td, "hx"))
        hit = False
    except ValueError:
        hit = True
    check("h. a day whose manifest names another day is refused", hit)


def safety_checks():
    for f in ("engine/ofpack.py", "engine/ofbackfill.py", "tools/of_backfill.py"):
        t = ast.parse(open(os.path.join(ROOT, f), encoding="utf-8").read())
        imp = set()
        for n in ast.walk(t):
            if isinstance(n, ast.Import):
                imp |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imp |= {("engine." if n.level else "") + (n.module or "")}
        check(f"i. {f} imports nothing that can trade", not any(i.startswith(b) for i in imp for b in BANNED), imp)
    users = subprocess.run(["git", "grep", "-l", "ofbackfill\\|ofpack", "--", "engine/live.py", "engine/lit_live.py", "server.py",
                            "engine/ninjatrader.py", "engine/account_b.py"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("i. no live-loop file imports the backfill", users == "", users)


def real_checks(td):
    """5 REAL tick-summary days from branch of-days (market data only; skipped when this clone does not have it)."""
    from engine import ofpack
    r = subprocess.run(["git", "archive", "origin/of-days", "research/orderflow/real_days"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        print("[SKIP] j. real days: branch of-days not fetched here")
        return
    import io
    import tarfile
    files = {}
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        for m in tf.getmembers():
            parts = m.name.split("/")
            if m.isfile() and len(parts) >= 5 and parts[-1] != "manifest.json" and parts[3] < "2026-10-04":
                files[f"days/{parts[3]}/of/{parts[-1]}"] = tf.extractfile(m).read()
    blob = ofpack.pack(files)
    back = ofpack.contents(blob)
    gz = sum(len(b) for b in files.values())
    check("j. REAL days (of-days): lossless and <= 0.5 of gzip", files and all(back[p] == (gzip.decompress(b) if p.endswith(".gz") else b)
                                                                     for p, b in files.items()) and len(blob) <= 0.5 * gz, (len(blob), gz))


def main():
    with tempfile.TemporaryDirectory() as td:
        real_checks(td)
        pack_checks(td)
        bitmap_checks()
        budget_checks()
        dp, days, out, max_zip = flow_checks(td)
        reserve_checks(td, dp, days, max_zip)
        store_checks(td, out)
        hostile_checks(td)
        safety_checks()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
