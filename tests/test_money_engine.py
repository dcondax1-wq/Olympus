"""MONEY ENGINE (tools/money_engine.py, 2026-11-10): runs the five money scanners, builds money/index.json. Paper only, stdlib, offline.

  a. the five contract fixtures in tools/money/fixtures/ follow the data contract; the sample is labelled "not real"
  b. the engine's own --selftest (fake scanners: ok, slow, crashing, bad json, missing; lock file; stale fallback) passes
  c. a run with no scanners present works from the fixtures; the index has a low <= base <= high ESTIMATE and never an error
  d. the schedule helpers: tools/bat/RUN_MONEY.bat (CRLF, every goto target exists) and .github/workflows/money-engine.yml (schedule + dispatch only, read-only token, no secrets)
  e. paper only: the engine and the workflow never import engine/, never read keys, never place orders
    python -X utf8 -m tests.test_money_engine
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from tests import agora_kit as AK  # noqa: E402
import money_engine as M  # noqa: E402
import money_publish as P  # noqa: E402

check = AK.check
ROOT = AK.ROOT
FX = os.path.join(ROOT, "tools", "money", "fixtures")


def test_fixtures():
    for sid in M.IDS:
        raw = json.load(open(os.path.join(FX, sid + ".json"), encoding="utf-8"))
        ok = (raw["v"] == 1 and raw["id"] == sid and raw["mode"] == "paper" and raw["status"] == "sample" and M.parse_iso(raw["asof"]) is not None
              and isinstance(raw["headline"]["text"], str) and raw["headline"]["text"] and (raw["headline"]["usd_month"] is None or M.num(raw["headline"]["usd_month"]) is not None)
              and 1 <= len(raw["items"]) <= 8 and all({"title", "detail", "usd", "score", "risk"} <= set(i) <= {"title", "detail", "usd", "score", "risk", "expires"} and 0 <= i["score"] <= 100 and i["risk"] in M.RISKS for i in raw["items"])
              and any("not real" in n.lower() for n in raw["notes"]))
        check(f"a. fixture {sid}: v1, paper, sample, headline + $/month, 1-8 items with title/detail/usd/score/risk, a 'not real' note", ok, raw)
        n = M.normalize(sid, raw)
        check(f"a. fixture {sid} survives normalize() unchanged in meaning (same headline, same item count)", n and n["headline"]["text"] == raw["headline"]["text"] and len(n["items"]) == len(raw["items"]))


def test_selftest():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_engine.py"), "--selftest"], capture_output=True, text=True, timeout=120)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    check("b. money_engine.py --selftest passes (timeout, crash, bad json, missing scanner, lock, stale fallback)", r.returncode == 0 and "FAIL" not in r.stdout, (r.stdout[-500:], r.stderr[-300:]))
    check("b. the self-test counts its checks", re.match(r"\d+/\d+ passed", last) is not None, last)


def test_run():
    out = tempfile.mkdtemp(prefix="money-test-")
    empty = tempfile.mkdtemp(prefix="money-none-")
    idx = M.run(out, True, 5, scanners=empty, quiet=True)
    check("c. a run with no scanners at all still gives five streams in the fixed order", idx and [s["id"] for s in idx["streams"]] == list(M.IDS))
    t = idx["total"]
    check("c. the total is labelled ESTIMATE, low <= base <= high, paper mode, and states it is not income", idx["label"] == "ESTIMATE" and idx["mode"] == "paper" and t["low"] <= t["base"] <= t["high"] and "not income" in idx["note"].lower(), idx["note"])
    check("c. every stream: status sample, source fixture, a headline, a low / base / high, up to 3 items, an 'age' key", all(s["status"] == "sample" and s["source"] == "fixture" and s["headline"] and set(s["usd_month"]) == {"low", "base", "high"} and len(s["items"]) <= 3 and "age_min" in s for s in idx["streams"]))
    check("c. sample money is never counted as real: real_base is 0 when every stream is a sample", t["real_base"] == 0 and idx["counts"]["sample"] == 5)
    files = sorted(f for f in os.listdir(out) if f.endswith(".json"))
    check("c. the output folder holds <id>.json for each id plus index.json, and no lock file is left", files == sorted([i + ".json" for i in M.IDS] + ["index.json"]) and not os.path.exists(os.path.join(out, ".money_engine.lock")), files)
    one = M.run(out, True, 5, only=["sibyl"], scanners=empty, quiet=True)
    check("c. --only runs just the named streams", [s["id"] for s in one["streams"]] == ["sibyl"])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_engine.py"), "--fixture", "--quiet", "--out", out], capture_output=True, text=True, timeout=120)
    check("c. the command line works (--fixture --quiet) and exits 0", r.returncode == 0, r.stderr[-300:])
    ex = M.estimate("ok", 100), M.estimate("stale", 100), M.estimate("sample", 100), M.estimate("ok", None)
    check("c. the honest range: ok 30%-150%, stale 0-120%, sample 0-200%, no number -> none", ex == ((30.0, 100.0, 150.0), (0.0, 100.0, 120.0), (0.0, 100.0, 200.0), (None, None, None)), ex)
    own = {"low": -42.0, "base": 100.0, "high": 150.0}
    nr = M.normalize("chrysos", {"id": "chrysos", "status": "ok", "asof": M.iso(M.now_utc()), "headline": {"text": "x", "usd_month": 100}, "usd_month": own})
    check("c. a scanner's OWN range passes through (a negative low is a loss and is kept) and wins over the multipliers; one that gives only a number keeps 30% / 100% / 150%",
          nr["usd_range"] == own and M.estimate("ok", 100, own) == (-42.0, 100.0, 150.0) and M.estimate("sample", 100, own) == (-42.0, 100.0, 150.0) and M.estimate("ok", 100, None) == (30.0, 100.0, 150.0)
          and M.normalize("mercury", {"id": "mercury", "status": "ok", "asof": M.iso(M.now_utc()), "headline": {"text": "x", "usd_month": 100}})["usd_range"] is None, nr)
    junk = [{"low": 5, "base": 1, "high": 9}, {"low": "a", "base": 1, "high": 9}, {"low": 1, "base": 2}, [1, 2, 3], "x", None, {"low": float("nan"), "base": 1, "high": 2}]
    check("c. a broken own range is ignored (low > base, text, a missing key, nan, a list): the fixed multipliers apply instead", all(M.own_range({"usd_month": j}) is None for j in junk), junk)
    two = M.build_index([dict(M.normalize("chrysos", {"id": "chrysos", "status": "ok", "asof": M.iso(M.now_utc()), "headline": {"text": "x", "usd_month": 100}, "usd_month": own}), source="scanner", error=None),
                         dict(M.normalize("mercury", {"id": "mercury", "status": "ok", "asof": M.iso(M.now_utc()), "headline": {"text": "y", "usd_month": 100}}), source="scanner", error=None)])
    check("c. the combined total adds each stream's own range: (-42 + 30) / (100 + 100) / (150 + 150) = -12 / 200 / 300; the stream rows carry their own low / base / high",
          two["total"]["low"] == -12.0 and two["total"]["base"] == 200.0 and two["total"]["high"] == 300.0 and two["streams"][0]["usd_month"] == own and two["streams"][1]["usd_month"] == {"low": 30.0, "base": 100.0, "high": 150.0}, two["total"])
    bad = M.normalize("mercury", {"id": "mercury", "status": "ok", "asof": "garbage", "headline": {"text": "x", "usd_month": float("nan")}, "items": [None, {"title": ""}, {"title": "t", "score": "x", "risk": 5}]})
    check("c. junk input is cleaned, never raises: bad date -> stale, nan -> no number, bad items dropped / defaulted", bad and bad["status"] == "stale" and bad["headline"]["usd_month"] is None and len(bad["items"]) == 1 and bad["items"][0]["risk"] == "med" and bad["items"][0]["score"] == 0, bad)


def test_schedule():
    bat = open(os.path.join(ROOT, "tools/bat/RUN_MONEY.bat"), "rb").read()
    txt = bat.decode("ascii")
    check("d. tools/bat/RUN_MONEY.bat is ASCII with CRLF line endings only", b"\r\n" in bat and bat.count(b"\n") == bat.count(b"\r\n"))
    labels = {m.lower() for m in re.findall(r"^:(\w+)", txt, re.M)}
    gotos = {m.lower() for m in re.findall(r"goto :(\w+)", txt, re.I)}
    check("d. every goto target in tools/bat/RUN_MONEY.bat exists", gotos <= labels, gotos - labels)
    check("d. tools/bat/RUN_MONEY.bat runs the engine, shows the Task Scheduler line (every 30 minutes) and has an 'auto' mode without pause", "tools\\money_engine.py" in txt and "/MO 30" in txt and 'auto' in txt and "schtasks /Create" in txt)
    wf = open(os.path.join(ROOT, ".github", "workflows", "money-engine.yml"), encoding="utf-8").read()
    on = wf.split("jobs:")[0]
    check("d. the workflow runs only on schedule and by hand (no push / pull_request trigger)", "schedule:" in on and "workflow_dispatch:" in on and not re.search(r"^\s*(push|pull_request)\s*:", on, re.M), on)
    check("d. the workflow has a read-only token (contents: read), no secrets, no write permission, uploads the JSON as an artifact",
          "contents: read" in wf and "secrets." not in wf and "write" not in re.sub(r"#[^\n]*", "", wf) and "upload-artifact" in wf)
    check("d. the workflow self-tests, then runs the engine from the repo, with a job timeout", "money_engine.py --selftest" in wf and "money_engine.py --out" in wf and "timeout-minutes" in wf)
    ig = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("d. the generated money_out/ folder and the runner log are gitignored", "money_out/" in ig and "money_out_log.txt" in ig)


def test_publish():
    tmp = tempfile.mkdtemp(prefix="money-pubtest-")
    site, src = os.path.join(tmp, "site"), os.path.join(tmp, "src")
    got = P.publish(os.path.join(tmp, "missing"), site, True)
    idx = json.load(open(os.path.join(site, "money", "index.json"), encoding="utf-8"))
    check("f. no engine output yet: publish writes a SAMPLE index (five sample streams, ESTIMATE) and the five files, so the pages are never blank", len(got) == 6 and idx["counts"]["sample"] == 5 and idx["label"] == "ESTIMATE", got)
    os.makedirs(src)
    M.run(src, True, 5, scanners=os.path.join(tmp, "none"), quiet=True)
    for n, body in (("mercury_state.json", "{}"), ("notes.json", "{}"), (".money_engine.lock", "x"), ("sibyl.json", "{broken")):
        open(os.path.join(src, n), "w").write(body)
    got = P.publish(src, site, True)
    left = sorted(os.listdir(os.path.join(site, "money")))
    check("f. only <id>.json and index.json are published: no state file, no lock, no unknown file, no broken JSON, no .tmp left", "sibyl.json" not in got and left == sorted(f for f in left if f[:-5] in P.KEEP and f.endswith(".json")) and not any(x.endswith(".tmp") for x in left), (got, left))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_publish.py"), "--site", os.path.join(tmp, "s2"), "--src", src, "--quiet"], capture_output=True, text=True, timeout=60)
    check("f. the command line (--site, --src) works and writes <site>/money/index.json", r.returncode == 0 and os.path.isfile(os.path.join(tmp, "s2", "money", "index.json")), r.stderr[-200:])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money_publish.py"), "--selftest"], capture_output=True, text=True, timeout=60)
    check("f. money_publish.py --selftest passes", r.returncode == 0, r.stdout[-300:])


STOA_HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fs = require('fs'), idx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const live = JSON.parse(JSON.stringify(idx)); live.streams.forEach((s) => { s.status = 'ok'; });
  const cards = C.buildCards({ home: { accounts: [] }, money: live }, Date.parse('2026-11-12T12:00:00Z'));
  const d = cards.find((c) => c.slot === 'deals'), f = cards.find((c) => c.slot === 'feeds');
  console.log(JSON.stringify({ deals: [d.tone, d.title, d.needs], n: cards.length, feeds: f.tone, dollarMinus: JSON.stringify(cards).includes('$-') }));
});
"""


MINT_HARNESS = r"""
import(process.argv[2]).then((C) => {
  const idx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8')), now = Date.parse(idx.asof);
  const streams = C.IDS.map((id) => C.normStream(id, idx.streams.find((s) => s.id === id), now)), c = C.combine(streams), bar = C.rangeBar(c.low, c.base, c.high);
  console.log(JSON.stringify({ low: c.low, base: c.base, high: c.high, text: c.text, worst: C.worstText(c.low), bar, dollarMinus: (c.text + C.worstText(c.low) + C.rangeText(c.low, c.high)).includes('$-') }));
});
"""
CITY_HARNESS = r"""
import(process.argv[2]).then((C) => {
  const idx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const streams = C.IDS.map((id) => C.normStream(id, idx.streams.find((s) => s.id === id))), c = C.combine(streams), card = C.jarvisCard(streams, Date.parse(idx.asof));
  console.log(JSON.stringify({ low: c.low, text: c.text, range: card.kpis.find((k) => k.label === 'Range').value, dollarMinus: (c.text + C.rangeText(c.low, c.high)).includes('$-') }));
});
"""


def test_real_scanners():
    out = tempfile.mkdtemp(prefix="money-real-")
    idx = M.run(out, True, 120, quiet=True)
    by = {s["id"]: s for s in idx["streams"]}
    check("g. the five REAL scanners run through the engine with --fixture: every stream comes from its scanner (not the stand-in), status sample, no error", all(by[i]["source"] == "scanner" and by[i]["status"] == "sample" and not by[i]["error"] for i in M.IDS), {i: (by[i]["source"], by[i]["error"]) for i in M.IDS})
    raw = json.load(open(os.path.join(out, "mercury.json"), encoding="utf-8"))
    check("g. the scanner's own file is kept whole (Mercury still has its pick, prices and pages for its own page), not the hub's trimmed copy", all(k in raw for k in ("pick", "prices", "pages")) and "mercury_state.json" in os.listdir(out), sorted(raw))
    check("g. the scanner's memory file survives a second run (Mercury's polite one-fetch-per-page state)", M.run(out, True, 120, only=["mercury"], quiet=True) is not None and os.path.isfile(os.path.join(out, "mercury_state.json")))
    exp = [i.get("expires") for i in by["mercury"]["items"] if i.get("expires")]
    check("g. Mercury's dated deals carry `expires` (YYYY-MM-DD) into the index", exp and all(M.clean_expires(e) for e in exp), exp)
    check("g. the contract: expires accepts a date or a date-time and nothing else", M.clean_expires("2026-11-13") and M.clean_expires("2026-11-13T10:00:00Z") and not M.clean_expires("soon") and not M.clean_expires("2026-13-45") and not M.clean_expires(5) and not M.clean_expires("13/11/2026"))
    check("g. every real stream has a headline, 1+ items, and a hub role", all(by[i]["headline"] and by[i]["items"] and by[i]["role"] for i in M.IDS))
    o = AK.node("stoa", STOA_HARNESS, os.path.join(out, "index.json"))
    if o is not None:
        check("g. Stoa reads the real index: Mercury's 'ends 2026-11-13' deal becomes 'Deal ends in ...' on 2026-11-12 (warn), six cards", "_error" not in o and o["deals"][0] == "warn" and o["deals"][1].startswith("Deal ends in") and o["n"] == 6, o)
    ch = by["chrysos"]["usd_month"]
    t = idx["total"]
    check("g. the REAL Chrysos scanner's own range reaches the index: its Stress case is a LOSS (negative low), low < base < high, and the combined low is the sum of the five lows (so it can be below the others' lows)",
          ch["low"] < 0 < ch["base"] < ch["high"] and abs(t["low"] - sum((s["usd_month"]["low"] or 0) for s in idx["streams"])) < 0.02 and t["low"] < sum(max((s["usd_month"]["low"] or 0), 0) for s in idx["streams"]), (ch, t))
    sibyl = by["sibyl"]["usd_month"]
    check("g. a scanner that gives only a number keeps the fixed multipliers (a sample stream: 0 to 200% of its base)", sibyl["low"] in (0, 0.0, None) or sibyl["base"] is None or (sibyl["low"] == 0 and sibyl["high"] == round(sibyl["base"] * 2, 2)), sibyl)
    M.run(out, True, 120, quiet=True)          # the whole index again (the Mercury-only run above rewrote it)
    idx_path = os.path.join(out, "index.json")
    mo = AK.node("mint", MINT_HARNESS, idx_path)
    if mo is not None:
        check("g. Mint reads the REAL index: the combined low end is negative (the Stress loss), worded 'Worst case: you could lose about $...', the sentence says so, the range bar marks zero, nothing reads '$-'",
              "_error" not in mo and mo["low"] < 0 and mo["worst"].startswith("Worst case: you could lose about $") and "could lose about" in mo["text"] and mo["bar"]["neg"] and mo["bar"]["zero"] is not None and not mo["dollarMinus"], mo)
    co = AK.node("mintcity", CITY_HARNESS, idx_path)
    if co is not None:
        check("g. Mint City reads the REAL index: the same negative low end, 'you could lose about $...' in its sentence, the Jarvis range with a sign, nothing reads '$-'",
              "_error" not in co and co["low"] < 0 and "could lose about" in co["text"] and co["range"].startswith("-$") and not co["dollarMinus"], co)
    so = AK.node("stoa", STOA_HARNESS, idx_path)
    if so is not None:
        check("g. Stoa reads the REAL index with a negative Chrysos low end: six cards, no crash, no '$-' in any card", "_error" not in so and so["n"] == 6 and not so.get("dollarMinus", False), so)
    P.publish(out, os.path.join(out, "site"), True)
    pub = os.listdir(os.path.join(out, "site", "money"))
    check("g. publish copies the five whole scanner files, the index and Sibyl's ledger (or its honest 'not started' file), not the state file",
          sorted(pub) == sorted([i + ".json" for i in M.IDS] + ["index.json", "sibyl_forward.json"]), pub)


def test_paper_only():
    src = open(os.path.join(ROOT, "tools", "money_engine.py"), encoding="utf-8").read()
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    check("e. the engine never imports engine/ or the bot, never reads live_model*.json, keys or .env, never opens a network connection of its own",
          not re.search(r"^\s*(from|import)\s+engine\b|live_model|\.env|alerts\.json|urllib|requests|socket|http\.client|ninjatrader", code, re.M | re.I), re.findall(r"live_model|\.env|urllib|requests|socket", code))
    check("e. the engine says paper in its output (mode paper) and its docstring", '"mode": "paper"' in src and "PAPER ONLY" in src)


if __name__ == "__main__":
    test_fixtures()
    test_selftest()
    test_run()
    test_schedule()
    test_publish()
    test_real_scanners()
    test_paper_only()
    AK.finish()
