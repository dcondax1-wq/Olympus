"""day-nqops 2026-11-21: the PC-off leak and the MFFU 7-day clocks.

  a. clock7     engine/clock7.py: per account last fill, MFFU's last day (base + 7), sessions left, red / amber / ok, keep-alive switch;
                the pc_post fixture: Zlarior 50K last fill Mon 11-16 -> MFFU last day Mon 11-23 (the lead's "hard day")
  b. preflight  engine/preflight.py: "Ready" with all green, the exact first fix otherwise (NinjaTrader, an unarmed account, a red clock),
                the Sunday 17:30 ET window in engine/ops_checks.due and its tick (one push, key ops:sun:<day>), the weekday pre-session
                notice carries the clock line, never raises
  c. cloud      tools/pc_silent_check.preopen_step: Sunday 17:00-18:00 ET and weekdays 01:00-01:30 ET, ONE "PC is off: market opens in N
                min" when the PC's last post is stale, none when fresh, none twice (state or read back), none on Saturday; run() wired
  d. post       tools/pc_report: the ext block "k7" (no "t": ext_hash stays still), every post <= 3,900 bytes
  e. page       tools/web_public/nq/clock7.js = engine/clock7.py on the same post (node); the NQ page's 7-day clock card + window.NQ_K7
                (Chromium, the pc_post fixture)

    python -X utf8 -m tests.test_nqops [--static]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
ET = ZoneInfo("America/New_York")
PC = json.load(open(os.path.join(AK.ROOT, "tests", "fixtures", "truth", "pc_post.json"), encoding="utf-8"))


def ts(y, mo, d, h, mi=0) -> int:
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


SAT = ts(2026, 11, 21, 15, 0)
SUN = ts(2026, 11, 22, 17, 30)


def test_clock7():
    from engine import clock7 as C
    k = C.from_post(PC, SAT)
    rows = {r["id"]: r for r in (k or {}).get("a") or []}
    z = rows.get("mffu50k_eval") or {}
    check("a. Zlarior 50K: last fill Mon 11-16 -> MFFU last day Mon 11-23, 2 calendar days and 1 session (Monday) left = RED",
          z.get("lf") == "2026-11-16" and z.get("hard") == "2026-11-23" and z.get("left") == 2 and z.get("ses") == 1 and z.get("lvl") == "bad", z)
    b = rows.get("b25k_2") or {}
    check("a. 25K #2 with no fill yet counts from the day before its start (11-18 -> base 11-17): last day Tue 11-24",
          b.get("lf") is None and b.get("base") == "start" and b.get("hard") == "2026-11-24", b)
    a = rows.get("atlas") or {}
    check("a. ATLAS funded: last fill Fri 11-20 -> Fri 11-27, ok", a.get("hard") == "2026-11-27" and a.get("lvl") == "ok", a)
    check("a. soonest deadline first", [r["id"] for r in k["a"]][0] == "mffu50k_eval", [r["id"] for r in k["a"]])
    ka = {"t": SAT, "on": {"lit": True}, "last": {"atlas": "2026-11-21"}, "lane": {"lit": "lit", "atlas": "atlas"}}
    k2 = C.build(PC["mf"], ka, SAT)
    r2 = {r["id"]: r for r in k2["a"]}
    check("a. the heartbeat's keep-alive block: a newer kept fill moves the clock (ATLAS 11-21 -> 11-28), the switches read ON / OFF",
          r2["atlas"]["lf"] == "2026-11-21" and r2["atlas"]["hard"] == "2026-11-28" and r2["mffu50k_eval"]["on"] is True and r2["atlas"]["on"] is False, r2)
    check("a. plain line", C.line(z).startswith("Zlarior 50K: last fill Mon 11-16, MFFU last day Mon 11-23 (2 days)"), C.line(z))
    check("a. never raises / None on junk", C.build(None) is None and C.build({"a": [3, {"id": "x"}]}) is None and C.from_post("x") is None)


def _checks(**bad):
    base = [{"key": k, "name": n, "level": "ok", "text": "ok", "fix": ""} for k, n in
            (("server", "Dashboard server"), ("bot", "Bot"), ("heartbeat", "Heartbeat"), ("nt_folder", "NinjaTrader folder"),
             ("nt_conn", "NinjaTrader connection"), ("feed_1m", "Bar feed 1m"))]
    for c in base:
        if c["key"] in bad:
            c.update(level="bad", text=bad[c["key"]], fix="Open NinjaTrader 8 and connect your account.")
    return base


HB = {"t": SAT, "health": {"account": {"label": "LIVE", "armed": True, "enabled": True}},
      "second": {"route": {"account_b": {"enabled": True, "armed": True, "label": "LIVE"}}}}


def test_preflight():
    from engine import preflight as PF, ops_checks as OC
    ext_ok = {"mf": {"a": [{"id": "atlas", "nm": "ATLAS 25K funded", "lt": "2026-11-20", "sd": "2026-11-17"}]}}
    p = PF.build(_checks(), HB, SUN, ext_ok)
    check("b. all green + both accounts LIVE armed + clock fine: 'Ready for Sunday's open (18:00 ET)'",
          p["ready"] and p["title"] == "Ready for Sunday's open (18:00 ET)" and "ATLAS 25K: LIVE, armed" in p["body"] and "7-day clock OK" in p["body"], p)
    p = PF.build(_checks(nt_conn="DISCONNECTED: Tradovate"), HB, SUN, ext_ok)
    check("b. NinjaTrader disconnected: the title names it, the body says the fix", not p["ready"] and p["title"] == "Fix before 18:00 ET: NinjaTrader connection"
          and "Open NinjaTrader 8" in p["body"], p)
    hb2 = copy.deepcopy(HB)
    hb2["second"]["route"]["account_b"]["armed"] = False
    p = PF.build(_checks(), hb2, SUN, ext_ok)
    check("b. ATLAS not armed = a fix (Arm; the owner types the phrase himself)", not p["ready"] and "ATLAS 25K: LIVE, NOT armed" in p["body"]
          and "type your phrase yourself" in p["body"], p)
    p = PF.build(_checks(), HB, SUN, {"mf": PC["mf"]})
    check("b. Zlarior's 7-day clock red on Sunday (MFFU last day Mon 11-23) = the first fix, with what to do",
          not p["ready"] and p["fixes"] and p["fixes"][0].startswith("Zlarior 50K: last fill Mon 11-16, MFFU last day Mon 11-23") and "by hand" in p["fixes"][0], p["fixes"])
    p = PF.build(_checks(), {}, ts(2026, 11, 23, 1, 45), ext_ok)
    check("b. a weekday: 'today's session' wording", p["title"].startswith("Ready for today's session"), p)
    check("b. never raises on junk", isinstance(PF.build(None, "x", SUN, 3), dict))
    du = [OC.due(t).get("preflight") for t in (ts(2026, 11, 22, 17, 29), ts(2026, 11, 22, 17, 30), ts(2026, 11, 22, 18, 15),
                                                ts(2026, 11, 22, 18, 16), ts(2026, 11, 21, 17, 30), ts(2026, 11, 23, 17, 30))]
    check("b. ops_checks.due: preflight only Sunday 17:30-18:15 ET", du == [False, True, True, False, False, False], du)
    st, sent = {"sent": {}}, []
    tmpd = os.path.join(AK.ROOT, "tests", "fixtures", "_nqops_ops")
    os.makedirs(tmpd, exist_ok=True)
    sp = os.path.join(tmpd, "ops_state.json")
    ctx = {"now": SUN, "folder": tmpd, "ping": None, "hb": HB, "net": {"up": True, "n": 3, "drift_s": 0.2}, "state": st, "light": True}
    real_rc, real_ext = OC.run_checks, PF.last_ext
    OC.run_checks = lambda c: _checks()
    PF.last_ext = lambda path=None: ext_ok
    try:
        OC.tick(now=SUN, ctx=ctx, state=st, sender=lambda p: sent.append(p) or {"sent": True}, state_path=sp, do_backup=False)
        OC.tick(now=SUN + 300, ctx=ctx, state=st, sender=lambda p: sent.append(p) or {"sent": True}, state_path=sp, do_backup=False)
    except Exception as e:  # noqa: BLE001
        sent.append({"err": repr(e)})
    finally:
        OC.run_checks, PF.last_ext = real_rc, real_ext
        shutil.rmtree(tmpd, ignore_errors=True)
    pre = [p for p in sent if str(p.get("key", "")).startswith("ops:sun:")]
    check("b. ops_checks.tick on Sunday 17:30: ONE preflight push (key ops:sun:2026-11-22), not repeated 5 min later",
          len(pre) == 1 and pre[0]["key"] == "ops:sun:2026-11-22" and pre[0]["title"].startswith("Ready for Sunday"), [(p.get("key"), p.get("title"), p.get("err")) for p in sent])
    cl = PF.clock_line({}, ts(2026, 11, 23, 1, 45), {"mf": PC["mf"]})
    check("b. the weekday pre-session line: the red / amber accounts", cl.startswith(" 7-day clock: Zlarior 50K") and "TODAY" in cl, cl)


def test_cloud():
    sys.path.insert(0, os.path.join(AK.ROOT, "tools"))
    import pc_silent_check as P
    s = {"pc_silent_after_min": 20, "alerts": {}}
    fri = ts(2026, 11, 20, 21, 0)
    clock = [{"nm": "Zlarior 50K", "lf": "2026-11-16", "hard": "2026-11-23", "left": 1, "on": False, "lvl": "bad"}]
    st, m = P.preopen_step({}, fri, SUN, s, clock=clock)
    check("c. Sunday 17:30 ET, PC silent since Fri 21:00: ONE 'PC is off: market opens in 30 min' with the red clock",
          len(m) == 1 and m[0]["title"] == "PC is off: market opens in 30 min" and "Fri Nov 20 21:00 ET" in m[0]["body"] and "Mon 11-23" in m[0]["body"], m)
    _st2, m2 = P.preopen_step(st, fri, SUN + 600, s)
    _st3, m3 = P.preopen_step({}, fri, SUN + 600, s, sent=[SUN])
    check("c. not twice the same day (state, or the push read back from the topic)", not m2 and not m3, (m2, m3))
    check("c. none when the PC reported 5 min ago", not P.preopen_step({}, SUN - 300, SUN, s)[1])
    check("c. none on Saturday 17:30 or Sunday 18:05 (the PC-silent check owns market hours)",
          not P.preopen_step({}, fri, ts(2026, 11, 21, 17, 30), s)[1] and not P.preopen_step({}, fri, ts(2026, 11, 22, 18, 5), s)[1])
    _s, mw = P.preopen_step({}, fri, ts(2026, 11, 23, 1, 10), s)
    check("c. Monday 01:10 ET: 'the bot's day starts in 50 min'; 01:30 is the PC-silent window's",
          len(mw) == 1 and mw[0]["title"] == "PC is off: the bot's day starts in 50 min" and not P.preopen_step({}, fri, ts(2026, 11, 23, 1, 30), s)[1], mw)
    check("c. network trouble: nothing", not P.preopen_step({}, fri, SUN, s, fetched=False)[1])
    ext = {"v": 1, "kind": "le-live-ext", "x": {"mf": PC["mf"]}}
    msgs = [{"event": "message", "time": fri, "message": json.dumps(ext)}]
    fc = P.feed_clock(msgs, SUN)
    check("c. the clock from the newest ext post on the status topic", fc and fc[0]["id"] == "mffu50k_eval" and fc[0]["lvl"] == "bad", fc[:1])
    core = {"kind": "le-live", "t": fri, "reporter": {"t": fri}}
    feed_txt = "\n".join(json.dumps(x) for x in [{"event": "message", "time": fri, "message": json.dumps(core)}, msgs[0]])
    out = []
    tmp = os.path.join(AK.ROOT, "tests", "fixtures", "_nqops_out")
    try:
        r = P.run(tmp, now=SUN, env={}, get=lambda url, **k: (200, feed_txt), post=lambda *a, **k: (200, ""), hb={"present": False}, dry=True,
                  say=out.append, feed={"ntfy": "https://ntfy.example", "topic": "status"}, s=s)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. run(): the pre-open push goes with the PC-silent check's (dry run prints it)",
          any(x["key"] == "pc_preopen:2026-11-22" for x in r["msgs"]) and any("PC is off" in str(x) for x in out), (r["msgs"], out[-2:]))


def test_post():
    from tools import pc_report as R
    from tests.test_live_publish import hb_payload
    from engine import live_publish as lp
    t = SAT
    hb = hb_payload(t)
    hb["keepalive"] = {"t": t, "on": {"lit": True}, "last": {}, "lane": {"lit": "lit"}}
    snap = {"t": t, "hb": hb, "hb_t": t - 60, "server": True, "nt": True, "market_open": False, "entry_hours": False, "mode": "LIVE",
            "live": lp.build(hb, t)}
    full = R.full(snap)
    k7 = full.get("k7") or {}
    check("d. pc_report.full: the 'k7' block (rows, no 't')", isinstance(k7.get("a"), list) and "t" not in k7, k7)
    core, exts = R.posts(snap)
    xs = [k for e in exts for k in (e.get("x") or {})]
    check("d. it rides an ext post; every post <= 3,900 bytes; at most 2 ext posts",
          ("k7" in xs or not k7.get("a")) and all(R._size(x) <= R.MAX_STATUS_BYTES for x in [core, *exts]) and len(exts) <= R.EXT_PARTS,
          (xs, [R._size(x) for x in [core, *exts]]))


JS = r"""
(async () => {
  const W = process.argv[2], NOW = +process.argv[3];
  const K = await import(require('url').pathToFileURL(require('path').join(W, 'nq', 'clock7.js')).href);
  const PC = require(require('path').join(W, '..', '..', 'tests', 'fixtures', 'truth', 'pc_post.json'));
  const r = K.rows(PC, NOW), j = K.jarvis(r);
  const P2 = { k7: { a: r.map((x) => ({ id: x.id, nm: x.nm, lf: x.lf, base: x.base, hard: x.hard, on: true })) } };
  console.log(JSON.stringify({ day: K.tradingDay(NOW), r, j, k: K.rows(P2, NOW + 86400), w: K.words(r[0]), none: K.rows(null, NOW) }));
})().catch((e) => console.log(JSON.stringify({ err: String(e && e.stack || e) })));
"""


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("e. node skipped", True)
        return
    from engine import clock7 as C
    tmp = os.path.join(AK.ROOT, "tests", "fixtures", "_nqops.cjs")
    try:
        open(tmp, "w", encoding="utf-8").write(JS)
        r = subprocess.run([exe, tmp, AK.WEB, str(SAT)], capture_output=True, text=True, timeout=60)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"err": r.stderr[-600:]}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if "err" in o:
        check("e. the node harness ran", False, o["err"])
        return
    py = [(x["id"], x["hard"], x["left"], x["ses"], x["lvl"]) for x in C.from_post(PC, SAT)["a"]]
    js = [(x["id"], x["hard"], x["left"], x["ses"], x["lvl"]) for x in o["r"]]
    check("e. clock7.js = engine/clock7.py on the same post (ids, last day, days, sessions, level)", py == js and o["day"] == C.trading_day(SAT), (py, js))
    check("e. the PC's k7 block re-counted for a later day (Sunday: Zlarior 1 day, still red)", o["k"][0]["left"] == 1 and o["k"][0]["lvl"] == "bad" and o["k"][0]["on"] is True, o["k"][:1])
    check("e. words + the Jarvis field", o["w"]["hard"] == "MFFU last day Mon 11/23 (in 2 days, 1 session left)" and o["j"][0]["mffu_last_day"] == "2026-11-23"
          and o["j"][0]["sessions_left"] == 1 and o["none"] == [], (o["w"], o["j"][:1]))


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("e. page skipped: no Playwright", True)
        return
    from tests import test_nq_chart as NC, test_nq_page as NP
    now = PC["reporter"]["t"] + 600
    real = NP.time.time
    NP.time.time = lambda: float(now)
    try:
        home = NP.home_json(3 * 3600)
    finally:
        NP.time.time = real
    core = json.dumps({"event": "message", "time": PC["reporter"]["t"], "message": json.dumps(PC)}) + "\n"
    srv, origin = AK.serve({"/status_feed.json": NC.FEED, "/home.json": home})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{NC.TOPIC}/json": core})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(now, dt.timezone.utc))
            p.goto(f"{origin}/nq/")
            try:
                p.wait_for_function("document.querySelectorAll('#k7List li').length >= 3", timeout=45000)
            except Exception:
                pass
            o = p.evaluate("() => ({ rows: [...document.querySelectorAll('#k7List li')].map((li) => [li.className, li.textContent]), pill: document.querySelector('#k7Pill').textContent, j: window.NQ_K7 || null })")
            rows = o["rows"]
            check("e. the NQ page's 7-day clock card: Zlarior 50K first with 'MFFU last day Mon 11/23', the 25K #2 and ATLAS below; the pill names it",
                  len(rows) >= 3 and "Zlarior 50K" in rows[0][1] and "MFFU last day Mon 11/23" in rows[0][1] and o["pill"].startswith("Zlarior"), o)
            check("e. window.NQ_K7 for Jarvis: rows with mffu_last_day / days_left / keepalive", o["j"] and o["j"]["rows"][0]["mffu_last_day"] == "2026-11-23"
                  and "keepalive" in o["j"]["rows"][0], o["j"])
            check("e. no console error, no sideways scroll, taps >= 44 px", not errs and AK.no_sideways(p) and not AK.taps(p), (errs[:3], AK.taps(p)[:3]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_clock7()
    test_preflight()
    test_cloud()
    test_post()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
