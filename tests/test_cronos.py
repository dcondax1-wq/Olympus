"""CRONOS (tools/cronos, .github/workflows/cronos.yml, docs/CRONOS.md): the nightly refresh of the OLYMPUS research apps.

    python -X utf8 -m tests.test_cronos            # everything (~40 s: two full site builds, one real ODEON export)
    python -X utf8 -m tests.test_cronos --quick    # no site build, no ODEON export

  a. the registry: tasks, groups, runners, the apps' folders and cards, timeouts and max ages, the CLI
  b. the orchestrator: a good run moves its files in, a failure / bad card / timeout keeps the last good files and is
     recorded, saver mode skips the heavy tasks, ODEON and the weekly tasks skip when nothing new came in, the run summary
  c. freshness: weekday hours, fresh / stale / failed / no data -> the card fields (amber, never fake-fresh), idempotent,
     every stamped card passes the Jarvis contract
  d. the site: branch data pulled when newer, all-or-nothing per app, skipped cleanly when absent, git fetch of a branch
     (a local bare repo), and the real build (tools/build_web_dashboard.py) with and without the branch data
  e. the workflows: valid YAML, the expected crons and timeouts, GitHub's own actions only, no new secrets, never main;
     the minutes budget stays well under the 2,000 free minutes
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.cronos import fresh, registry, run, site  # noqa: E402
from tools.cronos import __main__ as cli  # noqa: E402

RESULTS = []
WEB = os.path.join(ROOT, "tools", "web_public")
QUICK = "--quick" in sys.argv


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"   -> {str(detail)[:300]}"))


def ts(y, mo, d, h=0, mi=0):
    import datetime as dt
    return dt.datetime(y, mo, d, h, mi, tzinfo=fresh.ET).timestamp()


def card(t, level="ok", label="all good", lines=("line one", "line two", "line three")):
    return {"v": 1, "name": "X", "status": {"level": level, "label": label},
            "kpis": [{"label": "A", "value": "1"}], "lines": list(lines), "t": int(t), "open": "#top", "theme": "#000000"}


def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def rjson(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------------------------------------ a
def test_registry():
    names = [t.name for t in registry.TASKS]
    check("a. registry: unique names, the eight research apps", len(names) == len(set(names))
          and set(names) == {"datacity", "kalshicity", "fates", "odeon", "pantheon", "hermes", "tree", "prometheus"}, names)
    check("a. groups: nightly = fates + odeon + pantheon, weekly = tree + prometheus, all = both",
          registry.GROUPS["nightly"] == ("fates", "odeon", "pantheon") and registry.GROUPS["weekly"] == ("tree", "prometheus")
          and registry.GROUPS["all"] == ("fates", "odeon", "pantheon", "tree", "prometheus"), registry.GROUPS)
    pt = registry.get("pantheon")
    check("a. pantheon: nightly, run by CRONOS, light (not skipped in saver mode), publishes pantheon.json + states.json + card",
          pt.cadence == "nightly" and pt.runner == "cronos" and not pt.heavy and pt.max_age_h == 36
          and pt.files == ("pantheon.json", "states.json", "jarvis.json") and pt.timeout_s <= 10 * 60, pt)
    check("a. every task CRONOS runs has a runner", all(n in run.RUNNERS for n in registry.GROUPS["all"]))
    for t in registry.TASKS:
        check(f"a. {t.name}: its page folder and jarvis.json exist", os.path.exists(os.path.join(WEB, t.app, "index.html"))
              and os.path.exists(os.path.join(WEB, t.app, "jarvis.json")))
        if t.runner == "cronos":
            check(f"a. {t.name}: publishes jarvis.json last, timeout 1-30 min",
                  t.files and t.files[-1] == "jarvis.json" and 60 <= t.timeout_s <= 30 * 60, t)
        check(f"a. {t.name}: max age {t.max_age_h:g} weekday hours fits its cadence",
              t.max_age_h == (36 if t.cadence in ("nightly", "publish", "frequent") else 156), t.max_age_h)
    dc = registry.get("datacity")
    check("a. datacity runs in its own workflow and its branch files map into datacity/",
          dc.runner == "workflow" and os.path.exists(os.path.join(ROOT, dc.workflow)) and dc.branch == "datacity"
          and registry.site_files(dc) == [("city.json", "datacity/city.json"), ("jarvis.json", "datacity/jarvis.json")])
    check("a. fates' files come from the cronos branch as fates/...",
          registry.site_files(registry.get("fates")) == [("fates/fates.json", "fates/fates.json"), ("fates/jarvis.json", "fates/jarvis.json")])
    check("a. hermes is stamped by itself (runs in the build), the others by CRONOS", "hermes" not in registry.STAMPED
          and set(registry.STAMPED) == {"datacity", "kalshicity", "fates", "odeon", "pantheon", "tree", "prometheus"})
    kc = registry.get("kalshicity")
    check("a. kalshicity: every 6 hours in its own workflow, the three site files come from the kalshicity branch into kalshicity/ (ledger.json stays on the branch), not run by CRONOS",
          kc.runner == "workflow" and kc.cadence == "frequent" and kc.every == "every 6 hours" and kc.branch == "kalshicity" and kc.max_age_h == 36 and os.path.exists(os.path.join(ROOT, kc.workflow))
          and registry.site_files(kc) == [("edges.json", "kalshicity/edges.json"), ("learning_log.json", "kalshicity/learning_log.json"), ("hypotheses.json", "kalshicity/hypotheses.json"), ("jarvis.json", "kalshicity/jarvis.json")]
          and "kalshicity" not in registry.GROUPS["all"] and "kalshicity" in site.BRANCHES, kc)
    try:
        registry.get("nope")
        check("a. an unknown task is refused", False)
    except KeyError:
        check("a. an unknown task is refused", True)
    check("a. CLI --list exits 0", cli.main(["--list"]) == 0)
    try:
        cli.main(["--task", "nope"])
        check("a. CLI refuses an unknown task", False)
    except KeyError:
        check("a. CLI refuses an unknown task", True)
    check("a. weekly inputs exist (their fingerprint means something)",
          all(os.path.exists(os.path.join(ROOT, p)) for n in registry.GROUPS["weekly"] for p in registry.get(n).inputs))


# ------------------------------------------------------------------------------------------------------------ b
def _writer(t, payload="new"):
    def fn(task, tmp, ctx):
        ctx["log"].append(f"writing {task.app}")
        wjson(os.path.join(tmp, task.files[0]), {"payload": payload})
        wjson(os.path.join(tmp, "jarvis.json"), card(t))
        return {"ran": True, "note": "rebuilt"}
    return fn


def test_orchestrator(tmp):
    out = os.path.join(tmp, "pub")
    now = time.time()
    st = run.run(["fates"], out, now=now, runners={"fates": _writer(now)}, echo=lambda *a: None)
    e = st["tasks"]["fates"]
    check("b. a good run: ok, rebuilt, files moved into <out>/fates/, status written",
          e["ok"] and e["ran"] and e["last_ok_t"] == int(now) and e["data_t"] == int(now)
          and rjson(os.path.join(out, "fates", "fates.json")) == {"payload": "new"}
          and os.path.exists(run.status_path(out)) and not os.path.exists(os.path.join(out, ".cronos_tmp")), e)

    def boom(task, tmp_, ctx):
        wjson(os.path.join(tmp_, "fates.json"), {"payload": "half"})
        raise RuntimeError("disk on fire")
    st = run.run(["fates"], out, now=now + 100, runners={"fates": boom}, echo=lambda *a: None)
    e = st["tasks"]["fates"]
    check("b. a failure is recorded (ok false, error, last_ok kept) and the last good files stay",
          e["ok"] is False and "disk on fire" in e["error"] and e["last_ok_t"] == int(now) and e["last_run_t"] == int(now + 100)
          and rjson(os.path.join(out, "fates", "fates.json")) == {"payload": "new"}, e)

    def badcard(task, tmp_, ctx):
        wjson(os.path.join(tmp_, "fates.json"), {"payload": "bad"})
        c = card(now)
        c["status"]["level"] = "great"
        wjson(os.path.join(tmp_, "jarvis.json"), c)
        return {"ran": True}
    st = run.run(["fates"], out, now=now + 200, runners={"fates": badcard}, echo=lambda *a: None)
    check("b. a card that breaks the Jarvis contract fails the task, the old files stay",
          st["tasks"]["fates"]["ok"] is False and "contract" in st["tasks"]["fates"]["error"]
          and rjson(os.path.join(out, "fates", "fates.json")) == {"payload": "new"}, st["tasks"]["fates"])

    log = []
    try:
        run.sub([sys.executable, "-c", "import time; print('working', flush=True); time.sleep(10)"], 1, log)
        check("b. a task over its timeout is killed", False)
    except run.TaskError as ex:
        check("b. a task over its timeout is killed (TaskError, its output kept in the log)", "timed out" in str(ex), (ex, log))
    try:
        run.sub([sys.executable, "-c", "import sys; print('bad input'); sys.exit(3)"], 30, log)
        check("b. a non-zero exit is a failure", False)
    except run.TaskError as ex:
        check("b. a non-zero exit is a failure with its last line", "exit 3" in str(ex) and "bad input" in str(ex), ex)

    called = []
    st = run.run(["fates", "odeon"], out, now=now + 300, saver=True,
                 runners={"fates": lambda *a: called.append(1), "odeon": _writer(now + 300)}, echo=lambda *a: None)
    check("b. saver mode skips the heavy task (fates), runs the light one (odeon)",
          not called and st["tasks"]["fates"]["note"].startswith("skipped") and st["tasks"]["odeon"]["ok"], st["tasks"])
    md = run.summary_md(st, ["fates", "odeon"])
    check("b. the run summary: a table row per task and the log tails", "| Task | Result |" in md and "| odeon | rebuilt |" in md
          and "| fates | " in md and "writing odeon" in md, md[:400])
    st = run.run(["datacity", "hermes"], out, now=now, runners={}, echo=lambda *a: None)
    check("b. datacity / hermes are not run by CRONOS (own workflow / the build)",
          "datacity" not in st["tasks"] and "hermes" not in st["tasks"])

    # ODEON: skips when the heartbeat branch has no newer bar; re-exports (the real exporter) when it does
    bars = "time,open,high,low,close,volume\n" + "".join(f"{1793660000 + 60 * i},25000,25001,24999,25000.5,10\n" for i in range(30))
    gz = gzip.compress(bars.encode())
    newest = 1793660000 + 60 * 29
    s = rjson(run.status_path(out))
    s["tasks"]["odeon"]["inputs"] = {"bars_t": newest}
    wjson(run.status_path(out), s)
    st = run.run(["odeon"], out, now=now + 400, ctx_extra={"bars_gz": gz, "data_json": ""}, echo=lambda *a: None)
    e = st["tasks"]["odeon"]
    check("b. odeon: no new PC bars -> ok, nothing rebuilt, last_ok moves (checked)",
          e["ok"] and not e["ran"] and "no new PC bars" in e["note"] and e["last_ok_t"] == int(now + 400), e)
    if not QUICK:
        gz2 = gzip.compress((bars + f"{newest + 60},25000,25002,24998,25001,5\n").encode())
        st = run.run(["odeon"], out, now=now + 500, ctx_extra={"bars_gz": gz2, "data_json": ""}, echo=print)
        e = st["tasks"]["odeon"]
        tr = rjson(os.path.join(out, "odeon", "trades.json"))
        check("b. odeon: a newer PC bar -> the real exporter rebuilds the reels and the card",
              e["ok"] and e["ran"] and e["inputs"]["bars_t"] == newest + 60 and tr.get("n", 0) > 0
              and not fresh.valid_card(rjson(os.path.join(out, "odeon", "jarvis.json"))), e)

    # weekly: unchanged inputs -> skipped without running
    t = registry.get("tree")
    wjson(os.path.join(out, "tree", "tree.json"), {"x": 1})
    wjson(os.path.join(out, "tree", "jarvis.json"), card(now))
    s = rjson(run.status_path(out))
    s["tasks"]["tree"] = {"ok": True, "inputs": {"fp": run.fingerprint(t.inputs)}}
    wjson(run.status_path(out), s)
    st = run.run(["tree"], out, now=now + 600, echo=lambda *a: None)
    check("b. tree: inputs unchanged -> checked, not rerun", st["tasks"]["tree"]["ok"] and not st["tasks"]["tree"]["ran"]
          and "unchanged" in st["tasks"]["tree"]["note"], st["tasks"]["tree"])
    check("b. the fingerprint is stable and changes with the inputs",
          run.fingerprint(t.inputs) == run.fingerprint(t.inputs) != run.fingerprint(t.inputs[:1]))


# ------------------------------------------------------------------------------------------------------------ c
def test_fresh():
    fri, mon = ts(2026, 10, 30, 23, 0), ts(2026, 11, 2, 1, 30)
    check("c. weekday hours: Fri 23:00 -> Mon 01:30 ET is 2.5 h (the weekend does not age a nightly job)",
          abs(fresh.business_hours(fri, mon) - 2.5) < 1e-6, fresh.business_hours(fri, mon))
    check("c. weekday hours: Tue -> Wed is 24 h, Sat -> Sun is 0",
          abs(fresh.business_hours(ts(2026, 11, 3, 9), ts(2026, 11, 4, 9)) - 24) < 1e-6
          and fresh.business_hours(ts(2026, 10, 31, 1), ts(2026, 11, 1, 23)) == 0)
    N, W = registry.get("fates"), registry.get("tree")
    now = ts(2026, 11, 4, 9, 0)                                   # Wednesday 09:00 ET
    v = fresh.verdict(N, int(ts(2026, 11, 3, 23, 7)), {"ok": True, "last_ok_t": int(ts(2026, 11, 3, 23, 7))}, now)
    c = fresh.stamp(card(ts(2026, 11, 3, 23, 7)), N, v, now)
    check("c. fresh: t = the publish, the engine's level and label kept, 'Updated nightly · last run' line",
          v["state"] == "fresh" and c["t"] == int(now) and c["status"] == {"level": "ok", "label": "all good"}
          and c["lines"][-1].startswith("Updated nightly · last run Tue Nov 3, 23:07 ET") and len(c["lines"]) == 3
          and c["kpis"] == card(0)["kpis"] and c["cronos"]["data_t"] == int(ts(2026, 11, 3, 23, 7)), c)
    old = int(ts(2026, 11, 2, 9, 0))                               # Monday 09:00: 48 weekday hours before
    v = fresh.verdict(N, old, None, now)
    c = fresh.stamp(card(old), N, v, now)
    check("c. stale (> 36 h): amber 'Not updated since Mon Nov 2', last status kept as such, t = the publish (not grey)",
          v["state"] == "stale" and c["status"] == {"level": "warn", "label": "Not updated since Mon Nov 2"}
          and c["lines"][0].startswith("Updates nightly; last good data Mon Nov 2") and c["lines"][1] == "Last status: all good"
          and c["t"] == int(now), c)
    v = fresh.verdict(N, int(ts(2026, 11, 3, 8)), {"ok": False, "last_ok_t": int(ts(2026, 11, 3, 8)),
                                                   "last_run_t": int(ts(2026, 11, 3, 23, 7)), "error": "timed out after 15 min"}, now)
    c = fresh.stamp(card(ts(2026, 11, 3, 8)), N, v, now)
    check("c. failed (the last run failed after the last good one): amber even though the data is young, the error shown",
          v["state"] == "failed" and c["status"]["level"] == "warn" and c["status"]["label"] == "Not updated since Tue Nov 3"
          and "failed Tue Nov 3, 23:07 ET: timed out after 15 min" in c["lines"][0], c)
    v = fresh.verdict(N, int(ts(2026, 11, 3, 23, 30)), {"ok": False, "last_run_t": int(ts(2026, 11, 3, 23, 7)), "error": "x"}, now)
    check("c. a failure older than the data (a manual rerun since) is not a failure", v["state"] == "fresh", v)
    v = fresh.verdict(N, None, None, now)
    c = fresh.stamp({"v": 1, "name": "X", "status": {"level": "off", "label": "Demo"}, "t": 0}, N, v, now)
    check("c. no data: amber 'No data yet'", v["state"] == "nodata" and c["status"] == {"level": "warn", "label": "No data yet"}, c)
    v = fresh.verdict(W, int(ts(2026, 11, 1, 14, 17)), None, ts(2026, 11, 8, 14, 0))
    check("c. weekly: a week-old Sunday run is fresh on the next Sunday", v["state"] == "fresh", v)
    v = fresh.verdict(W, int(ts(2026, 11, 1, 14, 17)), None, ts(2026, 11, 10, 13, 0))
    check("c. weekly: a missed Sunday makes it stale by Tuesday afternoon (156 weekday hours)", v["state"] == "stale", v)
    a = fresh.stamp(card(old), N, fresh.verdict(N, old, None, now), now)
    b = fresh.stamp(a, N, fresh.verdict(N, fresh.data_time(a), None, now + 60), now + 60)
    check("c. stamping a stamped card again gives the same card (only t moves)", {**a, "t": 0} == {**b, "t": 0}
          and fresh.data_time(b) == old, (a, b))
    long = card(now, label="L" * 48, lines=["W" * 120] * 3)
    ok = all(not fresh.valid_card(fresh.stamp(long, N, fresh.verdict(N, *args), now))
             for args in ((int(now), None, now), (old, None, now), (old, {"ok": False, "last_run_t": int(now), "error": "E" * 300}, now)))
    check("c. every stamped card (long texts too) passes the Jarvis contract", ok)
    for app in registry.STAMPED:
        real = rjson(os.path.join(WEB, app, "jarvis.json"))
        t = registry.get(app)
        c = fresh.stamp(real, t, fresh.verdict(t, fresh.data_time(real), None, time.time()), time.time())
        check(f"c. {app}: the real card stamps into a valid card", not fresh.valid_card(c), fresh.valid_card(c))


# ------------------------------------------------------------------------------------------------------------ d
def _site(tmp, name):
    out = os.path.join(tmp, name)
    for t in registry.TASKS:
        if t.runner != "build":
            os.makedirs(os.path.join(out, t.app), exist_ok=True)
            shutil.copy(os.path.join(WEB, t.app, "jarvis.json"), os.path.join(out, t.app, "jarvis.json"))
    return out


def _branches(tmp, now, fates_t, status=None):
    d = os.path.join(tmp, "branches")
    shutil.rmtree(d, ignore_errors=True)
    wjson(os.path.join(d, "cronos", "fates", "fates.json"), {"from": "branch"})
    wjson(os.path.join(d, "cronos", "fates", "jarvis.json"), card(fates_t, label="from the branch"))
    wjson(os.path.join(d, "cronos", "odeon", "trades.json"), {"from": "branch"})          # no odeon jarvis.json: all or nothing
    wjson(os.path.join(d, "cronos", "cronos", "status.json"),
          status or {"v": 1, "tasks": {"fates": {"ok": True, "last_ok_t": int(fates_t), "last_run_t": int(fates_t)}}})
    wjson(os.path.join(d, "datacity", "city.json"), {"city": "branch"})
    wjson(os.path.join(d, "datacity", "jarvis.json"), card(now - 3600, label="city from the branch"))
    return d


def test_optional(tmp):
    """kalshicity's optional files (whatif.json, forward.json): copied when the branch has them, skipped without a word when it does not,
    never part of the all-or-nothing rule of the four required files; the committed seed copies keep serving without a branch."""
    now = time.time()
    kc = registry.get("kalshicity")
    check("o. registry: kalshicity lists whatif.json, forward.json and scan.json as OPTIONAL files (forward_card.json is not published), the four required ones unchanged",
          registry.optional_site_files(kc) == [("whatif.json", "kalshicity/whatif.json"), ("forward.json", "kalshicity/forward.json"), ("scan.json", "kalshicity/scan.json")]
          and [d for _, d in registry.site_files(kc)] == ["kalshicity/edges.json", "kalshicity/learning_log.json", "kalshicity/hypotheses.json", "kalshicity/jarvis.json"]
          and all(registry.optional_site_files(t) == [] for t in registry.TASKS if t.name != "kalshicity"))

    def branch(name, required=True, optional=("whatif.json", "forward.json", "scan.json"), card_t=None, skip=()):
        d = os.path.join(tmp, name)
        shutil.rmtree(d, ignore_errors=True)
        if required:
            for f in ("edges.json", "learning_log.json", "hypotheses.json"):
                if f not in skip:
                    wjson(os.path.join(d, "kalshicity", f), {"f": f, "from": "branch"})
            if "jarvis.json" not in skip:
                wjson(os.path.join(d, "kalshicity", "jarvis.json"), card(card_t or now - 600, label="kalshicity from the branch"))
        for f in optional:
            wjson(os.path.join(d, "kalshicity", f), {"f": f, "from": "branch", "kind": "x"})
        os.makedirs(os.path.join(d, "kalshicity"), exist_ok=True)
        return {"kalshicity": site.dir_reader(os.path.join(d, "kalshicity"))}

    def served(out, f):
        return os.path.exists(os.path.join(out, "kalshicity", f))

    # a required file missing: the whole app is skipped as before, optional files included
    out = _site(tmp, "opt_a")
    notes, _ = site.pull(out, branch("br_a", skip=("hypotheses.json",)), log=lambda *a: None)
    check("o. a REQUIRED file missing on the branch: the whole app is skipped (nothing pulled, the optional files too), 'not on the branch'",
          "not on the branch" in notes["kalshicity"] and not served(out, "edges.json") and not served(out, "whatif.json") and not served(out, "forward.json"), notes)
    # optional files missing: the required four are published exactly as before
    out = _site(tmp, "opt_b")
    notes, _ = site.pull(out, branch("br_b", optional=()), log=lambda *a: None)
    check("o. optional files missing on the branch: the required four are still published, no complaint in the note",
          all(served(out, f) for f in ("edges.json", "learning_log.json", "hypotheses.json")) and rjson(os.path.join(out, "kalshicity", "jarvis.json"))["status"]["label"] == "kalshicity from the branch"
          and not served(out, "forward.json") and notes["kalshicity"].startswith("pulled from kalshicity") and "+" not in notes["kalshicity"], notes)
    # optional files present: published with the app
    out = _site(tmp, "opt_c")
    notes, _ = site.pull(out, branch("br_c"), log=lambda *a: None)
    check("o. optional files present: whatif.json and forward.json are published beside the four required ones, named in the note",
          rjson(os.path.join(out, "kalshicity", "whatif.json"))["from"] == "branch" and rjson(os.path.join(out, "kalshicity", "forward.json"))["f"] == "forward.json"
          and served(out, "edges.json") and served(out, "scan.json") and "+whatif.json, forward.json, scan.json" in notes["kalshicity"], notes)
    # only one optional file there
    out = _site(tmp, "opt_d")
    site.pull(out, branch("br_d", optional=("forward.json",)), log=lambda *a: None)
    check("o. only forward.json on the branch: it is published, whatif.json is not invented", served(out, "forward.json") and not served(out, "whatif.json"))
    # a broken optional file is skipped, the rest is published
    out = _site(tmp, "opt_e")
    rd = branch("br_e", optional=())
    with open(os.path.join(tmp, "br_e", "kalshicity", "forward.json"), "w") as fh:
        fh.write("<html>not json")
    notes, _ = site.pull(out, rd, log=lambda *a: None)
    check("o. an optional file that is not valid JSON is skipped silently, the required four are published", not served(out, "forward.json") and served(out, "edges.json"), notes)
    # the page's copy of the required card is as new, but a new optional file still moves; an identical one is not rewritten
    out = _site(tmp, "opt_f")
    site.pull(out, branch("br_f1", card_t=now - 600), log=lambda *a: None)
    wjson(os.path.join(out, "kalshicity", "forward.json"), {"f": "forward.json", "from": "older"})
    notes, _ = site.pull(out, branch("br_f2", card_t=now - 600), log=lambda *a: None)
    check("o. required card as new: the required files stay, a changed optional file still moves ('page copy is as new (+forward.json)'), an identical one is left alone",
          notes["kalshicity"] == "page copy is as new (+forward.json)" and rjson(os.path.join(out, "kalshicity", "forward.json"))["from"] == "branch", notes)
    notes, _ = site.pull(out, branch("br_f3", card_t=now - 600), log=lambda *a: None)
    check("o. nothing changed at all: 'page copy is as new', no rewrite", notes["kalshicity"] == "page copy is as new", notes)
    # no branch: the committed seed copies keep serving
    out = _site(tmp, "opt_g")
    wjson(os.path.join(out, "kalshicity", "whatif.json"), {"seed": True})
    notes, _ = site.pull(out, {}, log=lambda *a: None)
    check("o. no kalshicity branch: nothing is touched and the committed seed copy (whatif.json) keeps serving", notes["kalshicity"] == "no branch"
          and rjson(os.path.join(out, "kalshicity", "whatif.json")) == {"seed": True} and not served(out, "forward.json"))
    seed = os.path.join(WEB, "kalshicity", "whatif.json")
    check("o. the repo carries the seed whatif.json (valid JSON, kind kalshi-whatif) and NO forward*.json seed (a seed would freeze a wrong start date)",
          rjson(seed)["kind"] == "kalshi-whatif" and not any(os.path.exists(os.path.join(WEB, "kalshicity", f)) for f in ("forward.json", "forward_state.json", "forward_card.json")))


def test_site(tmp):
    now = time.time()
    out = _site(tmp, "site_a")
    d = _branches(tmp, now, now - 600)
    res = site.apply(out, now=now, readers={b: site.dir_reader(os.path.join(d, b)) for b in site.BRANCHES}, log=lambda *a: None)
    fj = rjson(os.path.join(out, "fates", "jarvis.json"))
    check("d. newer branch data is pulled (fates.json + its card) and stamped fresh",
          rjson(os.path.join(out, "fates", "fates.json")) == {"from": "branch"} and fj["status"]["label"] == "from the branch"
          and fj["cronos"]["state"] == "fresh" and fj["t"] == int(now), (res, fj))
    check("d. the datacity branch's city.json + card are pulled into datacity/",
          rjson(os.path.join(out, "datacity", "city.json")) == {"city": "branch"}
          and rjson(os.path.join(out, "datacity", "jarvis.json"))["status"]["label"] == "city from the branch")
    check("d. an app missing a file on the branch is not pulled at all (all or nothing)",
          not os.path.exists(os.path.join(out, "odeon", "trades.json")) and "not on the branch" in res["odeon"], res["odeon"])
    check("d. the branch's status.json is published at cronos/status.json",
          rjson(os.path.join(out, "cronos", "status.json"))["tasks"]["fates"]["ok"] is True)
    out = _site(tmp, "site_b")
    d = _branches(tmp, now, 1000)
    site.apply(out, now=now, readers={b: site.dir_reader(os.path.join(d, b)) for b in site.BRANCHES}, log=lambda *a: None)
    check("d. older branch data never overwrites the page's newer copy",
          not os.path.exists(os.path.join(out, "fates", "fates.json"))
          and rjson(os.path.join(out, "fates", "jarvis.json"))["status"]["label"] != "from the branch")
    out = _site(tmp, "site_c")
    d = _branches(tmp, now, now - 600, status={"v": 1, "tasks": {"fates": {"ok": False, "last_ok_t": int(now - 90000),
                                                                            "last_run_t": int(now - 300), "error": "exit 1: boom"}}})
    site.apply(out, now=now, readers={b: site.dir_reader(os.path.join(d, b)) for b in site.BRANCHES}, log=lambda *a: None)
    fj = rjson(os.path.join(out, "fates", "jarvis.json"))
    check("d. a failed nightly run turns the published card amber with its error", fj["status"]["level"] == "warn"
          and "boom" in " ".join(fj["lines"]), fj)
    out = _site(tmp, "site_d")
    before = rjson(os.path.join(out, "fates", "jarvis.json"))
    site.apply(out, now=now, readers={}, log=lambda *a: None)
    after = rjson(os.path.join(out, "fates", "jarvis.json"))
    check("d. no branch at all: nothing pulled, the page's cards still stamped (fresh or amber), nothing raised",
          not os.path.exists(os.path.join(out, "fates", "fates.json")) and not os.path.exists(os.path.join(out, "cronos"))
          and after["cronos"]["data_t"] == before["t"] and after["t"] == int(now))
    check("d. readers stay off outside Actions unless asked (CRONOS_FETCH / CRONOS_DIR unset)",
          site.default_readers() == {} if not (os.environ.get("CRONOS_DIR") or site.want_fetch()) else True)

    # git: a bare origin with a `cronos` branch, fetched and read by the same path the build uses in Actions
    git = shutil.which("git")
    if git:
        bare, work, clone = (os.path.join(tmp, x) for x in ("origin.git", "w", "clone"))
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        q = dict(capture_output=True, env=env, timeout=60)
        subprocess.run([git, "init", "-q", "--bare", bare], **q)
        subprocess.run([git, "init", "-q", "-b", "cronos", work], **q)
        wjson(os.path.join(work, "fates", "jarvis.json"), card(now))
        subprocess.run([git, "-C", work, "add", "-A"], **q)
        subprocess.run([git, "-C", work, "commit", "-q", "-m", "c"], **q)
        subprocess.run([git, "-C", work, "push", "-q", bare, "cronos"], **q)
        subprocess.run([git, "init", "-q", clone], **q)
        subprocess.run([git, "-C", clone, "remote", "add", "origin", bare], **q)
        rd = site.git_reader("cronos", fetch=True, root=clone)
        check("d. git: the branch is fetched (depth 1) and its files read; a missing file is None",
              rd is not None and json.loads(rd("fates/jarvis.json"))["t"] == int(now) and rd("nope.json") is None)
        check("d. git: a branch that does not exist gives no reader", site.git_reader("datacity", fetch=True, root=clone) is None)

    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    i, j, k = b.find("from tools.cronos import site as _cronos"), b.find('for app in ("jarvis", "kalshi"'), b.find("from tools.hermes import build")
    check("d. the build calls CRONOS after copying the apps and before HERMES, inside try/except",
          j < i < k and "_cronos.apply(out)" in b and 'print("  cronos unavailable:"' in b)
    if QUICK:
        return
    snap = os.path.join(ROOT, "tools", "web_hub_snapshot.json")
    keep = open(snap, "rb").read() if os.path.exists(snap) else None
    saved = {k_: os.environ.get(k_) for k_ in ("CRONOS_DIR", "CRONOS_FETCH")}
    try:
        from tools import build_web_dashboard as bwd
        d = _branches(tmp, time.time(), time.time() - 60)
        os.environ["CRONOS_DIR"] = d
        out = os.path.join(tmp, "build_with")
        bwd.build(os.path.join(tmp, "no_state.json"), None, out)
        fj = rjson(os.path.join(out, "fates", "jarvis.json"))
        check("d. the real build includes the branch data when present (fates.json + a fresh stamped card)",
              rjson(os.path.join(out, "fates", "fates.json")) == {"from": "branch"} and fj["cronos"]["state"] == "fresh"
              and rjson(os.path.join(out, "datacity", "city.json")) == {"city": "branch"}, fj)
        os.environ["CRONOS_DIR"] = os.path.join(tmp, "no_such_dir")
        os.environ["CRONOS_FETCH"] = "0"
        out = os.path.join(tmp, "build_without")
        bwd.build(os.path.join(tmp, "no_state.json"), None, out)
        page = rjson(os.path.join(WEB, "fates", "jarvis.json"))
        fj = rjson(os.path.join(out, "fates", "jarvis.json"))
        check("d. the real build without branch data: the page copies published, every research card stamped and valid",
              open(os.path.join(out, "fates", "fates.json"), "rb").read() == open(os.path.join(WEB, "fates", "fates.json"), "rb").read()
              and fj["cronos"]["data_t"] == page["t"]
              and all(not fresh.valid_card(rjson(os.path.join(out, a, "jarvis.json"))) and "cronos" in rjson(os.path.join(out, a, "jarvis.json"))
                      for a in registry.STAMPED if os.path.isdir(os.path.join(out, a))), fj)      # kalshicity joins once the build's app list names it (the lead wires that)
    finally:
        for k_, v_ in saved.items():
            if v_ is None:
                os.environ.pop(k_, None)
            else:
                os.environ[k_] = v_
        if keep is not None:
            with open(snap, "wb") as fh:
                fh.write(keep)


# ------------------------------------------------------------------------------------------------------------ e
def _wf(name):
    import yaml
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as fh:
        text = fh.read()
    doc = yaml.safe_load(text)
    return doc, text


def _cron_ok(expr):
    f = expr.split()
    return len(f) == 5 and all(x.replace("*", "").replace(",", "").replace("-", "").replace("/", "").isdigit() or x == "*" for x in f)


def test_workflows():
    try:
        import yaml  # noqa: F401
    except ImportError:
        check("e. PyYAML available", False)
        return
    doc, text = _wf("cronos.yml")
    on = doc.get("on", doc.get(True))
    crons = [c["cron"] for c in on["schedule"]]
    check("e. cronos.yml: valid YAML, nightly 04:07 UTC Tue-Sat + Sunday 19:17 UTC, manual run",
          crons == ["7 4 * * 2-6", "17 19 * * 0"] and all(_cron_ok(c) for c in crons) and "workflow_dispatch" in on, crons)
    job = doc["jobs"]["cronos"]
    steps = job["steps"]
    run_step = next(s for s in steps if s.get("name") == "Run CRONOS")
    check("e. cronos.yml: job timeout 75 min, the run step 70 min and continue-on-error, publish if: always()",
          job["timeout-minutes"] == 75 and run_step["timeout-minutes"] == 70 and run_step["continue-on-error"] is True
          and any(s.get("if") == "always()" and "cronos" in s.get("run", "") for s in steps))
    check("e. cronos.yml: ubuntu-latest (free runner), GitHub's own actions only, one concurrency group",
          job["runs-on"] == "ubuntu-latest" and all(s["uses"].split("@")[0] in ("actions/checkout", "actions/setup-python")
                                                    for s in steps if "uses" in s) and doc["concurrency"]["group"] == "cronos")
    check("e. cronos.yml: no secrets (GITHUB_TOKEN only), contents: write, pushes only the cronos branch (never main)",
          "secrets." not in text and doc["permissions"] == {"contents": "write"} and '.git" cronos' in text
          and "git push" in text and " main" not in "".join(ln for ln in text.splitlines() if "git push" in ln))
    check("e. cronos.yml: the weekly cron selects the weekly group, the rest nightly",
          "github.event.schedule == '17 19 * * 0' && 'weekly' || 'nightly'" in run_step["env"]["GROUP"])
    check("e. cronos.yml: the nightly run starts after datacity's (03:37 UTC) and the weekly before the Sunday publish (21:47 UTC)",
          (4 * 60 + 7) > (3 * 60 + 37) and (19 * 60 + 17 + 75) < (21 * 60 + 47))
    d, dt_ = _wf("datacity.yml")
    don = d.get("on", d.get(True))
    check("e. datacity.yml: still valid, nightly Tue-Sat, timeout 20, publishes the datacity branch",
          [c["cron"] for c in don["schedule"]] == ["37 3 * * 2-6"] and d["jobs"]["city"]["timeout-minutes"] == 20
          and "datacity" in dt_ and "secrets." not in dt_)
    k, kt = _wf("kalshicity.yml")
    kon = k.get("on", k.get(True))
    kjob = k["jobs"]["learn"]
    check("e. kalshicity.yml: valid, every 6 hours (minute 17) + manual run, timeout 5 min, one concurrency group, minimal permissions, GitHub's own checkout only",
          [c["cron"] for c in kon["schedule"]] == ["17 */6 * * *"] and "workflow_dispatch" in kon and kjob["timeout-minutes"] == 5 and k["concurrency"]["group"] == "kalshicity"
          and k["permissions"] == {"contents": "write"} and kjob["runs-on"] == "ubuntu-latest" and all(s["uses"].split("@")[0] == "actions/checkout" for s in kjob["steps"] if "uses" in s), kon)
    check("e. kalshicity.yml: no secrets (GITHUB_TOKEN only), no pip, pushes only the kalshicity branch (never main), commits only when something changed, a failed feed read does not publish",
          "secrets." not in kt and "pip " not in kt and kt.count("git push") == 1 and '.git" kalshicity' in kt and "nothing new: no commit" in kt
          and next(s for s in kjob["steps"] if s.get("id") == "learn")["continue-on-error"] is True and "steps.learn.outcome == 'success'" in kt
          and "kalshi_edges.py --out state" in kt and "kalshi.com" not in kt)
    m, _ = _wf("cloud-monitor.yml")
    check("e. cloud-monitor.yml still parses and sparse-checks out /tools/ (tools/cronos reaches the site build)",
          "/tools/" in next(s for s in m["jobs"]["monitor"]["steps"] if s.get("uses", "").startswith("actions/checkout"))["with"]["sparse-checkout"])

    # the minutes budget (docs/CRONOS.md): 2-core runner, each job rounded up, ~22 weeknights and ~4.35 Sundays a month
    setup = 1.5
    nightly = setup + sum(registry.get(n).est_min for n in registry.GROUPS["nightly"])
    weekly_full = setup + sum(registry.get(n).est_min for n in registry.GROUPS["weekly"])
    month = 22 * nightly + 4.35 * weekly_full
    datacity = 22 * registry.get("datacity").est_min
    kalshi = 120 * registry.get("kalshicity").est_min                      # kalshicity.yml: 4 runs a day = 120 a month, ~1 billed minute each
    print(f"   budget: nightly {nightly:.1f} min x 22 + weekly {weekly_full:.1f} min x 4.35 = {month:.0f} min/month "
          f"(+ datacity {datacity:.0f}, kalshicity {kalshi:.0f}) of 2,000")
    check("e. CRONOS stays well under the free minutes: < 300 a month even when every weekly task reruns",
          month < 300 and month + datacity < 400 and month + datacity + kalshi < 480, month)
    doc_md = os.path.join(ROOT, "docs", "CRONOS.md")
    check("e. docs/CRONOS.md exists with the schedule and the minutes budget", os.path.exists(doc_md)
          and "minutes" in open(doc_md, encoding="utf-8").read().lower())


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="cronos_test_")
    try:
        test_registry()
        test_orchestrator(tmp)
        test_fresh()
        test_site(tmp)
        test_optional(tmp)
        test_workflows()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} passed in {time.time() - t0:.0f}s")
    for n in bad:
        print("FAILED:", n)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
