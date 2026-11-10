#!/usr/bin/env python3
"""MONEY ENGINE: runs every money scanner in tools/money/ and builds the hub's index (2026-11-10). PAPER ONLY.

  python tools/money_engine.py                  run the scanners that exist, write <out>/<id>.json + <out>/index.json
  python tools/money_engine.py --fixture        scanners get --fixture; a missing scanner is filled from tools/money/fixtures/
  python tools/money_engine.py --selftest       offline self-test in a temp folder (fake scanners: ok, slow, crash, bad json, missing)
  options: --out DIR (default money_out/)  --timeout SEC (default 60)  --only id,id  --quiet

Scanners: tools/money/<id>.py (chrysos, mercury, sibyl, oikos, arbiter), each `--out <dir>` writes <dir>/<id>.json. One that is missing,
slow, crashing or writing bad JSON never stops the others: the hub falls back to the last good file (status stale) and then to the
bundled sample (status sample). The engine never trades, never reads keys, never touches engine/ or live_model*.json.
Contract of a scanner file: {"v":1,"id","asof","mode":"paper","status":"ok|stale|sample","headline":{"text","usd_month"},"items":[...],"notes":[...]}.
All money here is an ESTIMATE with a low / base / high range, never a promise.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCANNERS = os.path.join(HERE, "money")
FIXTURES = os.path.join(SCANNERS, "fixtures")
DEFAULT_OUT = os.path.join(ROOT, "money_out")
IDS = ("chrysos", "mercury", "sibyl", "oikos", "arbiter")
NAMES = {"chrysos": "Chrysos", "mercury": "Mercury", "sibyl": "Sibyl", "oikos": "Oikos", "arbiter": "Arbiter"}
ROLES = {"chrysos": "Prop-firm savings and payouts", "mercury": "Small resale gaps", "sibyl": "Prediction-market edges (paper)",
         "oikos": "Household savings", "arbiter": "The referee: what to do first"}
STALE_HOURS = 6            # a file older than this is shown as stale, whatever it says
LOCK_MAX_MIN = 20          # a lock older than this is abandoned
# the honest range around a base estimate: (low, high) as multiples of the base, by how much we trust it
RANGE = {"ok": (0.3, 1.5), "stale": (0.0, 1.2), "sample": (0.0, 2.0), "none": (0.0, 0.0)}
RISKS = ("low", "med", "high")


# ------------------------------------------------------------------------------------------------ small helpers
def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def num(v):
    """A finite number or None (bool, nan, inf and text are not numbers)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v and abs(v) != float("inf") else None


def clean_text(v, n=240):
    s = " ".join(str(v if v is not None else "").split())
    return s[:n]


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ the contract
def normalize(sid: str, raw, now: dt.datetime | None = None):
    """A scanner file -> a clean stream dict, or None when it is not usable. Never raises."""
    if not isinstance(raw, dict) or raw.get("id") not in (sid, None):
        return None
    now = now or now_utc()
    head = raw.get("headline") if isinstance(raw.get("headline"), dict) else {}
    text = clean_text(head.get("text"))
    if not text:
        return None
    items = []
    for it in raw.get("items") if isinstance(raw.get("items"), list) else []:
        if not isinstance(it, dict) or not clean_text(it.get("title")):
            continue
        sc = num(it.get("score"))
        items.append({"title": clean_text(it.get("title"), 90), "detail": clean_text(it.get("detail"), 260), "usd": num(it.get("usd")),
                      "score": int(max(0, min(100, sc))) if sc is not None else 0, "risk": it.get("risk") if it.get("risk") in RISKS else "med"})
    status = raw.get("status") if raw.get("status") in ("ok", "stale", "sample") else "stale"
    asof = parse_iso(raw.get("asof"))
    age_min = max(0, int((now - asof).total_seconds() // 60)) if asof else None
    if status == "ok" and (age_min is None or age_min > STALE_HOURS * 60):
        status = "stale"
    notes = [clean_text(n, 200) for n in raw.get("notes", []) if clean_text(n)] if isinstance(raw.get("notes"), list) else []
    return {"v": 1, "id": sid, "asof": iso(asof) if asof else None, "mode": "paper", "status": status, "age_min": age_min,
            "headline": {"text": text, "usd_month": num(head.get("usd_month"))}, "items": items[:8], "notes": notes[:6]}


def estimate(status: str, base):
    """(low, base, high) in $ a month for one stream; base None -> all None."""
    b = num(base)
    if b is None:
        return None, None, None
    lo, hi = RANGE.get(status, RANGE["stale"])
    return round(b * lo, 2), round(b, 2), round(b * hi, 2)


def build_index(streams: list[dict], now: dt.datetime | None = None) -> dict:
    """streams: [{stream fields + source + error}] -> the index the hub reads."""
    now = now or now_utc()
    rows, lo, base, hi = [], 0.0, 0.0, 0.0
    real = 0.0
    for s in streams:
        e = estimate(s["status"], s["headline"]["usd_month"]) if s.get("headline") else (None, None, None)
        rows.append({"id": s["id"], "name": NAMES.get(s["id"], s["id"].title()), "role": ROLES.get(s["id"], ""), "status": s["status"], "source": s.get("source", "scanner"),
                     "asof": s.get("asof"), "age_min": s.get("age_min"), "headline": s["headline"]["text"] if s.get("headline") else "",
                     "usd_month": {"low": e[0], "base": e[1], "high": e[2]}, "items": (s.get("items") or [])[:3], "notes": (s.get("notes") or [])[:3],
                     "error": s.get("error")})
        if e[1] is not None:
            lo, base, hi = lo + e[0], base + e[1], hi + e[2]
            if s["status"] == "ok":
                real += e[1]
    sample = sum(1 for r in rows if r["status"] == "sample")
    return {"v": 1, "asof": iso(now), "mode": "paper", "label": "ESTIMATE",
            "total": {"low": round(lo, 2), "base": round(base, 2), "high": round(hi, 2), "real_base": round(real, 2), "unit": "usd_per_month"},
            "counts": {"streams": len(rows), "ok": sum(1 for r in rows if r["status"] == "ok"), "stale": sum(1 for r in rows if r["status"] == "stale"), "sample": sample},
            "note": "An ESTIMATE, not income. Low / base / high is a range of what could happen; sample streams are examples, not real finds. Paper only.",
            "streams": rows}


# ------------------------------------------------------------------------------------------------ the lock
class Lock:
    """One run at a time: <out>/.money_engine.lock created exclusively; a lock older than LOCK_MAX_MIN is abandoned."""

    def __init__(self, out: str):
        self.path = os.path.join(out, ".money_engine.lock")
        self.held = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {iso(now_utc())}\n".encode())
                os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > LOCK_MAX_MIN * 60:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                return self
        return self

    def __exit__(self, *a):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass


# ------------------------------------------------------------------------------------------------ one scanner
def run_scanner(sid: str, out: str, fixture: bool, timeout: float, scanners: str, fixtures: str, now: dt.datetime | None = None) -> dict:
    """Run tools/money/<sid>.py (if it exists). Falls back: the file it wrote -> the last good file in out -> the bundled sample."""
    now = now or now_utc()
    script = os.path.join(scanners, sid + ".py")
    target = os.path.join(out, sid + ".json")
    err, source, stream = None, "scanner", None
    if os.path.isfile(script):
        work = tempfile.mkdtemp(prefix=f"money-{sid}-")
        cmd = [sys.executable, script, "--out", work] + (["--fixture"] if fixture else [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT, stdin=subprocess.DEVNULL)
            if r.returncode:
                err = f"exit {r.returncode}: {clean_text(r.stderr[-200:], 160)}"
            stream = normalize(sid, read_json(os.path.join(work, sid + ".json")), now)
            if stream is None and not err:
                err = "no usable file written"
        except subprocess.TimeoutExpired:
            err = f"timed out after {int(timeout)} s"
        except OSError as e:
            err = f"could not start: {e}"
        finally:
            try:
                for f in os.listdir(work):
                    os.remove(os.path.join(work, f))
                os.rmdir(work)
            except OSError:
                pass
    else:
        err = "scanner not written yet"
    if stream is None:
        old = normalize(sid, read_json(target), now)
        if old is not None and old["status"] != "sample":
            stream, source = dict(old, status="stale"), "previous"
        else:
            stream, source = normalize(sid, read_json(os.path.join(fixtures, sid + ".json")), now), "fixture"
    if stream is None:   # even the sample is gone: a stub so the hub still has a card
        stream, source = {"v": 1, "id": sid, "asof": None, "mode": "paper", "status": "sample", "age_min": None,
                          "headline": {"text": "No data yet for this stream.", "usd_month": None}, "items": [], "notes": []}, "none"
    stream["source"], stream["error"] = source, err
    if err is None:
        stream["error"] = None
    write_json(target, {k: v for k, v in stream.items() if k not in ("age_min", "source", "error")})
    return stream


# ------------------------------------------------------------------------------------------------ the run
def run(out: str = DEFAULT_OUT, fixture: bool = False, timeout: float = 60, only=None, scanners: str = SCANNERS, fixtures: str = FIXTURES,
        ids=IDS, quiet: bool = False, now: dt.datetime | None = None) -> dict | None:
    """Run everything, write <out>/<id>.json and <out>/index.json; returns the index (None when another run holds the lock)."""
    now = now or now_utc()
    with Lock(out) as lk:
        if not lk.held:
            if not quiet:
                print("money_engine: another run is in progress (lock file); skipped")
            return None
        streams = []
        for sid in ids:
            if only and sid not in only:
                continue
            t0 = time.time()
            s = run_scanner(sid, out, fixture, timeout, scanners, fixtures, now)
            streams.append(s)
            if not quiet:
                print(f"  {sid:<8} {s['status']:<7} {s['source']:<9} {time.time() - t0:5.1f}s  {s['headline']['text'][:60]}" + (f"  [{s['error']}]" if s["error"] else ""))
        idx = build_index(streams, now)
        write_json(os.path.join(out, "index.json"), idx)
        if not quiet:
            t = idx["total"]
            print(f"money_engine: ESTIMATE ${t['low']:.0f} to ${t['high']:.0f} a month (base ${t['base']:.0f}), {idx['counts']['sample']} sample, written to {out}")
        return idx


# ------------------------------------------------------------------------------------------------ self-test
def selftest() -> int:
    bad, total = [], []

    def chk(name, ok):
        total.append(1)
        print(("[PASS] " if ok else "[FAIL] ") + name)
        if not ok:
            bad.append(name)

    tmp = tempfile.mkdtemp(prefix="money-selftest-")
    sc = os.path.join(tmp, "scanners")
    os.makedirs(sc)
    good = ('import argparse, json, os, datetime as d\np = argparse.ArgumentParser(); p.add_argument("--out"); p.add_argument("--fixture", action="store_true"); a = p.parse_args()\n'
            'json.dump({"v": 1, "id": "%s", "asof": d.datetime.now(d.timezone.utc).strftime("%%Y-%%m-%%dT%%H:%%M:%%SZ"), "mode": "paper", "status": "ok", '
            '"headline": {"text": "Live test line", "usd_month": 100}, "items": [{"title": "T", "detail": "D", "usd": 5, "score": 150, "risk": "weird"}], "notes": ["n"]}, open(os.path.join(a.out, "%s.json"), "w"))\n')
    files = {"chrysos": good % ("chrysos", "chrysos"), "mercury": "import time\ntime.sleep(30)\n", "sibyl": "import sys\nsys.exit(3)\n",
             "oikos": 'import argparse, os\np = argparse.ArgumentParser(); p.add_argument("--out"); p.add_argument("--fixture", action="store_true"); a = p.parse_args()\nopen(os.path.join(a.out, "oikos.json"), "w").write("{nope")\n'}
    for k, v in files.items():
        with open(os.path.join(sc, k + ".py"), "w") as fh:
            fh.write(v)                                   # arbiter has no script on purpose
    out = os.path.join(tmp, "out")
    t0 = time.time()
    idx = run(out, False, 3, scanners=sc, quiet=True)
    chk("a slow scanner is stopped by its timeout and the run still ends fast", idx is not None and time.time() - t0 < 25)
    by = {s["id"]: s for s in idx["streams"]} if idx else {}
    chk("the good scanner is ok, score clamped to 100, a bad risk becomes med", by.get("chrysos", {}).get("status") == "ok" and by["chrysos"]["items"][0]["score"] == 100 and by["chrysos"]["items"][0]["risk"] == "med")
    chk("slow, crashing, bad-json and missing scanners fall back to the bundled sample (never an error, never blank)",
        all(by[k]["status"] == "sample" and by[k]["source"] == "fixture" for k in ("mercury", "sibyl", "oikos", "arbiter")))
    chk("each failure says why in plain words", "timed out" in (by["mercury"]["error"] or "") and "exit 3" in (by["sibyl"]["error"] or "") and "no usable" in (by["oikos"]["error"] or "") and "not written" in (by["arbiter"]["error"] or ""))
    chk("one file per id plus index.json written", all(os.path.isfile(os.path.join(out, f"{i}.json")) for i in IDS) and os.path.isfile(os.path.join(out, "index.json")))
    t = idx["total"]
    chk("the total is an ESTIMATE with low <= base <= high", idx["label"] == "ESTIMATE" and t["low"] <= t["base"] <= t["high"] and t["real_base"] == 100.0 and t["base"] > 100)
    chk("the lock file is gone after the run", not os.path.exists(os.path.join(out, ".money_engine.lock")))
    open(os.path.join(out, ".money_engine.lock"), "w").write("x")
    chk("a fresh lock makes a second run skip (returns None)", run(out, False, 3, scanners=sc, quiet=True) is None)
    os.utime(os.path.join(out, ".money_engine.lock"), (0, 0))
    chk("an old lock is abandoned and the run goes ahead", run(out, True, 3, scanners=sc, quiet=True, only=["chrysos"]) is not None)
    # previous good file is kept (stale) when a scanner later fails
    os.remove(os.path.join(sc, "chrysos.py"))
    idx2 = run(out, False, 3, scanners=sc, quiet=True, only=["chrysos"])
    chk("a scanner that vanishes keeps its last good numbers, marked stale", idx2["streams"][0]["status"] == "stale" and idx2["streams"][0]["source"] == "previous" and idx2["streams"][0]["usd_month"]["base"] == 100)
    old = normalize("sibyl", dict(read_json(os.path.join(FIXTURES, "sibyl.json")), status="ok", asof="2020-01-01T00:00:00Z"))
    chk("an old file claiming ok is shown as stale", old["status"] == "stale")
    chk("normalize refuses junk", normalize("x", None) is None and normalize("sibyl", {"id": "other"}) is None and normalize("sibyl", {"id": "sibyl", "headline": {}}) is None)
    fixt = [normalize(i, read_json(os.path.join(FIXTURES, i + ".json"))) for i in IDS]
    chk("all five bundled fixtures follow the contract (paper, sample, headline, 1-8 items, 'not real' note)",
        all(f and f["status"] == "sample" and f["items"] and any("not real" in n for n in f["notes"]) for f in fixt))
    full = run(os.path.join(tmp, "fx"), True, 3, scanners=os.path.join(tmp, "none"), quiet=True)
    chk("--fixture with no scanners at all still gives five sample cards and a total", full["counts"]["sample"] == 5 and full["total"]["base"] == 255.0 and len(full["streams"]) == 5)
    print(f"\n{len(total) - len(bad)}/{len(total)} passed")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the money scanners and build the Mint hub index (paper only).")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--fixture", action="store_true", help="pass --fixture to the scanners; fill missing ones from tools/money/fixtures/")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("--only", default="", help="comma list of ids")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    run(a.out, a.fixture, a.timeout, [x for x in a.only.split(",") if x] or None, quiet=a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
