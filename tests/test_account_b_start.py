"""ATLAS without a start day (code review 2026-11-20, day-speed helper): engine/account_b.AccountB.start raised TypeError on an
eval block with no "eval_start" (the start log formatted the view's room None), engine/live.LiveBot._sync_account_b caught it,
set acct_b None and ATLAS silently did not start. Now the failure is loud and safe:

  a. the repro: an eval block without eval_start builds (no exception), the account has a plain problem ("did not start: its
     account block has no eval start day ... run python -X utf8 -m engine.second --account-b ... --start ..."), no adapter,
     never routes, never sizes a trade; info() / eval_view still work for the dashboards;
  b. one log line + one push a day ("ATLAS <Name> did not start"), the same instance never pushes twice;
  c. the private alert ("problems", soft = no sound in quiet hours) goes only from the real NinjaTrader bot, never from a
     harness or a paper bot;
  d. a funded block without funded_start: the same plain problem with the --to-funded line;
  e. the start present = exactly as before: an eval block and a funded block (today's live ATLAS shape, with and without
     eval_start) start "ready" with a paper adapter, no problem, no push;
  f. LiveBot._sync_account_b with such a block: acct_b is the stopped account (not None, no exception), its tick does
     nothing; a build that still raises leaves acct_b None with an error note, never an exception (LIT keeps trading);
     the owner's fixed block replaces a stopped account at once, even with a restored open trade (a working one still waits);
  g. ATLAS on the Rapid EOD (engine/rapid.RapidAtlas): its own engine.rapid line, never account B's --account-b
     (that would move ATLAS's 25K).

Paper / fake bots, temp files, made-up Sim names only: nothing armed, nothing routed, the real data/ and second_model.json
are never written (checked at the end).

    python -X utf8 -m tests.test_account_b_start          # ~5 s
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import live  # noqa: E402
from engine import rapid  # noqa: E402

RESULTS = []
KEYS = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]
NAME, FUND, RAPID = "SimATLASNOSTART", "SimATLASFUNDTEST", "SimRAPIDNOSTART"


def check(name, ok, info=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not ok else ""), flush=True)
    return bool(ok)


def ts(day, hh=9, mm=0):
    import datetime as dt
    from zoneinfo import ZoneInfo
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(hh, mm), ZoneInfo("America/New_York")).timestamp())


NOW = ts("2026-11-20", 9, 31)


class FakeBot:
    def __init__(self, now=NOW, adapter="paper", state_path=None):
        self._now = now
        self.cfg = {"adapter": adapter, "sym": "NQ"}
        self.state_path = state_path
        self.health = {}
        self.accts = None
        self.kill = False
        self.state = {}
        self.ledger = []
        self.logs = []
        self.pushed = []

    def clock(self):
        return self._now

    def _log(self, kind, text, **kw):
        self.logs.append((kind, text))

    def _note_error(self, text):
        self.health["last_error"] = text
        self.logs.append(("error", text))

    def _snote(self, key, kind, text):
        self.logs.append((kind, text))

    def _push_send(self, p):
        self.pushed.append(p)


def eval_block(name=NAME, **kw):
    return {"account": name, "plan": "builder25k", "strategies": list(KEYS), "sizing": "need", **kw}


def funded_block(name=FUND, **kw):
    return {**eval_block(name), "eval_start": "2026-10-26", "stage": "funded", "funded_start": "2026-11-18",
            "funded_balance": 25000.0, "payouts": {}, "eval_account": "SimATLASEVALTEST", **kw}


def no_route(B):
    """Any route on this account = a failed check (the account must never trade)."""
    hits = []
    B.route = lambda action: hits.append(action) or {"ok": False, "error": "test: never routed"}
    return hits


def nostart_pushes(fb):
    return [p for p in fb.pushed if "did not start" in str(p.get("title"))]


# ------------------------------------------------------------------------------------------------ a + b. the repro
def repro_checks(tmp):
    print("a. an eval block without eval_start", flush=True)
    blk = eval_block()
    spec = AB.normalize(blk)
    check("a. normalize itself is unchanged (no problem in the spec, eval_start empty)",
          spec["problem"] is None and spec["eval_start"] == "", spec.get("problem"))
    fb = FakeBot()
    err = None
    try:
        B = AB.build(fb, blk, state_path=os.path.join(tmp, "a_state.json"))
    except Exception as e:                     # before the fix: TypeError: unsupported format string passed to NoneType.__format__
        B, err = None, e
    check("a. build does not raise (was TypeError)", err is None and B is not None, repr(err))
    if B is None:
        return
    p = str(B.problem or "")
    check("a. a plain problem: no eval start day + the line to run (engine.second --account-b with the Name, --plan, --start)",
          "no eval start day" in p and "eval_start" in p and f'--account-b "{NAME}"' in p and "--plan builder25k" in p
          and "--start <first eval day" in p, p)
    check("a. no adapter is created and the account is disabled with that problem",
          B.adapter is None and B.disabled_reason() == B.problem, (B.adapter, B.disabled_reason()))
    hits = no_route(B)
    B.tick(None, None, "NQ", NOW)               # returns at once (problem): never reads bars, never routes
    B.tick(None, None, "NQ", NOW + 300)
    check("a. its poll never routes, never writes a ledger row", hits == [] and B.ledger == [] and B.open_t is None, (hits, B.ledger))
    q = AB.qty(B.spec, {"risk_pts": 10.0, "tgt_pts": 20.0}, B.eval_state(NOW))
    check("a. sizing fails closed: 0 micros (eval state unknown)", q["qty"] == 0 and "eval_start missing" in " ".join(q["reasons"]), q)
    try:
        info, ev = B.info(NOW), B.eval_view(NOW)
        ok = info["enabled"] is False and info["disabled"] == B.problem and ev["status"] == "no eval_start"
    except Exception as e:
        ok, info = False, repr(e)
    check("a. info() / eval_view still work for the dashboards (disabled, status 'no eval_start')", ok, info)
    check("a. no state file written for the stopped account", not os.path.exists(os.path.join(tmp, "a_state.json")))

    print("b. one log line + one push", flush=True)
    lines = [t for k, t in fb.logs if "did not start" in t]
    check("b. one log line 'ATLAS <Name> did not start: ...' (the bot's error note, also its health last_error)",
          len(lines) == 1 and lines[0].startswith(f"ATLAS {NAME} did not start: its account block has no eval start day")
          and fb.health.get("last_error") == lines[0], fb.logs)
    ps = nostart_pushes(fb)
    body = ps[0]["body"] if ps else ""
    check("b. one push: title 'ATLAS <Name> did not start', the plain body with the line to run, key per day",
          len(ps) == 1 and ps[0]["title"] == f"ATLAS {NAME} did not start" and body.startswith("Its account block has no eval start day")
          and "--account-b" in body and "LIT and the other accounts are not affected" in body
          and ps[0]["key"] == f"acctb:nostart:2026-11-20:{NAME}", ps)
    B._push_no_start(B.problem)
    check("b. the same account never pushes it twice the same day", len(nostart_pushes(fb)) == 1, nostart_pushes(fb))


# ------------------------------------------------------------------------------------------------ c. the private alert
def alarm_checks(tmp):
    print("c. the private alert only from the real NinjaTrader bot", flush=True)
    from engine import notify
    sent, keep_ip, keep_ps = [], notify.instant_problem, AB.PROBLEM_SENDER
    try:
        notify.instant_problem = lambda p, **kw: sent.append(p) or "sent"
        AB.PROBLEM_SENDER = None
        spec = AB.normalize(eval_block())
        fb = FakeBot()                                                    # a harness (its own state path)
        AB.AccountB(fb, spec, state_path=os.path.join(tmp, "c1.json")).start()
        fb2 = FakeBot(state_path=live.STATE_PATH)                         # the real bot's path, but on paper
        AB.AccountB(fb2, AB.normalize(eval_block()), state_path=os.path.join(tmp, "c2.json")).start()
        time.sleep(0.3)
        check("c. a harness or a paper bot: no private alert (the log + the app notice only)", sent == [] and len(nostart_pushes(fb)) == 1, sent)
        fb3 = FakeBot(adapter="ninjatrader", state_path=live.STATE_PATH)  # the real NinjaTrader bot (AccountB gets a temp state file)
        AB.AccountB(fb3, AB.normalize(eval_block()), state_path=os.path.join(tmp, "c3.json")).start()
        t0 = time.time()
        while not sent and time.time() - t0 < 5:
            time.sleep(0.05)
        p = sent[0] if sent else {}
        check("c. the real NinjaTrader bot: one 'problems' alert, soft (no sound in quiet hours), bot atlas, the same key",
              len(sent) == 1 and p.get("soft") is True and p.get("bot") == "atlas" and p.get("code") == "atlas_no_start"
              and p.get("key") == f"acctb:nostart:2026-11-20:{NAME}" and p.get("title") == f"ATLAS {NAME} did not start", sent)
        got = []
        AB.PROBLEM_SENDER = lambda p: got.append(p) or "sent"
        AB.AccountB(FakeBot(), AB.normalize(eval_block()), state_path=os.path.join(tmp, "c4.json")).start()
        check("c. PROBLEM_SENDER (tests) gets the same payload", len(got) == 1 and got[0]["key"] == p.get("key"), got)

        def boom(p):
            raise RuntimeError("ntfy down")
        AB.PROBLEM_SENDER = boom
        err = None
        try:
            B = AB.AccountB(FakeBot(), AB.normalize(eval_block()), state_path=os.path.join(tmp, "c5.json")).start()
        except Exception as e:
            B, err = None, e
        check("c. a failing alert never breaks the start (the account is still stopped with its problem)",
              err is None and B is not None and "no eval start day" in str(B.problem), repr(err))
    finally:
        notify.instant_problem, AB.PROBLEM_SENDER = keep_ip, keep_ps


# ------------------------------------------------------------------------------------------------ d. funded without a start
def funded_checks(tmp):
    print("d. a funded block without funded_start", flush=True)
    fb = FakeBot()
    B = AB.build(fb, funded_block(funded_start=""), state_path=os.path.join(tmp, "d.json"))
    p = str(B.problem or "")
    check("d. the plain problem with the --to-funded line (the funded Name, --start)",
          "no funded start day" in p and "funded_start" in p and f'--to-funded --account "{FUND}"' in p and "--start <first funded day" in p, p)
    hits = no_route(B)
    B.tick(None, None, "NQ", NOW)
    ps = nostart_pushes(fb)
    check("d. no adapter, never routed, one push", B.adapter is None and hits == [] and len(ps) == 1
          and ps[0]["title"] == f"ATLAS {FUND} did not start", (B.adapter, hits, ps))


# ------------------------------------------------------------------------------------------------ e. start present = as before
def present_checks(tmp):
    print("e. the start present: exactly as before", flush=True)
    for tag, blk, want in (("eval", eval_block(eval_start="2026-11-16"), "eval from 2026-11-16"),
                           ("funded", funded_block(), "FUNDED sizing (the plan's funded rule) from 2026-11-18"),
                           ("funded without eval_start", {k: v for k, v in funded_block().items() if k != "eval_start"},
                            "FUNDED sizing (the plan's funded rule) from 2026-11-18")):
        fb = FakeBot()
        B = AB.build(fb, blk, state_path=os.path.join(tmp, f"e_{tag.replace(' ', '_')}.json"))
        ready = [t for k, t in fb.logs if k == "system" and t.endswith(": ready")]
        check(f"e. {tag}: no problem, a paper adapter, one '... ready' start line ({want}), no 'did not start' anywhere",
              B.problem is None and B.no_start() is None and isinstance(B.adapter, live.PaperAdapter) and len(ready) == 1
              and want in ready[0] and not nostart_pushes(fb) and not any("did not start" in t for _, t in fb.logs)
              and "last_error" not in fb.health, (B.problem, fb.logs, fb.pushed))
    fb = FakeBot()
    B = AB.build(fb, eval_block(eval_start="2026-11-16"), state_path=os.path.join(tmp, "e_line.json"))
    line = next((t for k, t in fb.logs if k == "system"), "")
    check("e. the eval start line keeps its words and $ (balance $25,000, room $1,000)",
          line == f"[ATLAS {NAME}] PAPER {NAME} MFFU Builder 25K, strategies {', '.join(B.spec['keys'])}, size need, "
                  "eval from 2026-11-16 (balance $25,000, room $1,000): ready", line)


# ------------------------------------------------------------------------------------------------ f. the LiveBot path
def livebot_checks(tmp):
    print("f. LiveBot._sync_account_b never raises, LIT untouched", flush=True)
    fb = FakeBot(state_path=os.path.join(tmp, "f", "live_state.json"))
    fb.cfg["account_b"] = eval_block()
    fb.acct_b, fb._acct_b_sig = None, None
    fb._account_b_block = types.MethodType(live.LiveBot._account_b_block, fb)
    fb._sync_account_b = types.MethodType(live.LiveBot._sync_account_b, fb)
    err = None
    try:
        live.LiveBot._sync_account_b(fb)
    except Exception as e:
        err = e
    ab = fb.acct_b
    check("f. the bot keeps the stopped ATLAS (not None), with the plain problem, no exception",
          err is None and isinstance(ab, AB.AccountB) and "no eval start day" in str(ab.problem) and ab.adapter is None, (err, fb.logs))
    try:
        live.LiveBot._account_b_tick(fb, None, None, "NQ", NOW)
        ok = True
    except Exception as e:
        ok = repr(e)
    check("f. the bot's account B poll runs without an error and routes nothing",
          ok is True and ab.ledger == [] and not any(k == "error" and "account B failed" in t for k, t in fb.logs), (ok, fb.logs))
    keep = AB.build
    try:
        def boom(bot, blk, **kw):
            raise TypeError("unsupported format string passed to NoneType.__format__")
        AB.build = boom
        fb2 = FakeBot(state_path=os.path.join(tmp, "f2", "live_state.json"))
        fb2.cfg["account_b"] = eval_block(eval_start="2026-11-16")
        fb2.acct_b, fb2._acct_b_sig = None, None
        fb2._account_b_block = types.MethodType(live.LiveBot._account_b_block, fb2)
        err = None
        try:
            live.LiveBot._sync_account_b(fb2)
        except Exception as e:
            err = e
        check("f. a build that still raises: acct_b None + one error note, never an exception (the LIT bot keeps polling)",
              err is None and fb2.acct_b is None and any("account B NOT started: TypeError" in t for _, t in fb2.logs), (err, fb2.logs))
    finally:
        AB.build = keep
    check("f. the bot's harness state folder holds no ATLAS state file (the stopped account writes nothing)",
          not os.path.exists(os.path.join(tmp, "f", "live_state_acctb.json")))


def fixed_block_checks(tmp):
    """f2. a stopped ATLAS that restored an open trade from its state file: the owner's fixed block is applied at once (a
    stopped account never manages a trade, so waiting for it to go flat would wait until the next bot start); the new account
    restores the same trade and manages it. A working account with an open trade still waits (as before)."""
    import json
    print("f2. the fixed block is applied at once", flush=True)
    d = os.path.join(tmp, "f3")
    os.makedirs(d, exist_ok=True)
    sp = os.path.join(d, "live_state_acctb.json")
    et_ = NOW - 3600
    blob = {"v": 1, "account": NAME, "plan": "builder25k", "eval_start": "", "saved_at": et_, "ledger": [], "closes": [],
            "prov": {str(et_): {"key": "ema_lon_vix", "short": "EMA", "dir": 1, "qty": 1, "entry": 20000.0, "stop": 19990.0,
                                "target": 20020.0}}, "open_t": et_, "seen": [], "lock": None, "notified": [], "held": {}}
    with open(sp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh)
    raw0 = open(sp, "rb").read()
    fb = FakeBot(state_path=os.path.join(d, "live_state.json"))
    fb.cfg["account_b"] = eval_block()
    fb.acct_b, fb._acct_b_sig = None, None
    fb._account_b_block = types.MethodType(live.LiveBot._account_b_block, fb)
    live.LiveBot._sync_account_b(fb)
    old = fb.acct_b
    check("f2. the stopped ATLAS restored the open trade (LIT's never-opposite check still sees it) and wrote nothing",
          isinstance(old, AB.AccountB) and old.start_missing and old.open_t == et_ and old.position() is not None
          and open(sp, "rb").read() == raw0, (getattr(old, "open_t", None), fb.logs))
    fb.cfg["account_b"] = eval_block(eval_start="2026-11-16")          # the owner ran the line
    live.LiveBot._sync_account_b(fb)
    new = fb.acct_b
    check("f2. the fixed block replaces it at once (no 'applied once its open trade is closed' wait), same trade restored, ready",
          new is not old and new.problem is None and not new.start_missing and new.open_t == et_
          and isinstance(new.adapter, live.PaperAdapter) and not any("applied once its open trade" in t for _, t in fb.logs), fb.logs)
    fb.cfg["account_b"] = eval_block(eval_start="2026-11-17")          # a working account with an open trade: waits, as before
    live.LiveBot._sync_account_b(fb)
    check("f2. a working ATLAS with an open trade still waits for it to close (unchanged)",
          fb.acct_b is new and any("applied once its open trade is closed" in t for _, t in fb.logs), fb.logs)


# ------------------------------------------------------------------------------------------------ g. Rapid ATLAS
def rapid_checks(tmp):
    print("g. ATLAS on the Rapid EOD: its own line", flush=True)
    fb = FakeBot()
    R = rapid.build_atlas(fb, {"account": RAPID, "plan": "mffu_rapid_eod_25k", "armed": False},
                          state_path=os.path.join(tmp, "g.json"))
    p = str(getattr(R, "problem", "") or "")
    check("g. Rapid ATLAS without eval_start: stopped, the engine.rapid --account line, never --account-b",
          isinstance(R, rapid.RapidAtlas) and R.adapter is None and "no eval start day" in p
          and f'python -X utf8 -m engine.rapid --account "{RAPID}" --start' in p and "--account-b" not in p, p)
    ps = nostart_pushes(fb)
    check("g. one push, the Rapid's own key (rapid: + acctr)", len(ps) == 1 and ps[0]["key"] == f"rapid:acctr:nostart:2026-11-20:{RAPID}"
          and ps[0]["title"] == f"ATLAS Rapid {RAPID} did not start", ps)
    fb2 = FakeBot()
    R2 = rapid.build_atlas(fb2, {"account": RAPID, "plan": "mffu_rapid_eod_25k", "armed": False, "eval_start": "2026-11-16"},
                           state_path=os.path.join(tmp, "g2.json"))
    check("g. Rapid ATLAS with its start: as before (no problem, paper adapter, no push)",
          R2.problem is None and isinstance(R2.adapter, live.PaperAdapter) and not nostart_pushes(fb2), (R2.problem, fb2.logs))


def _digest(paths) -> dict:
    out = {}
    for p in paths:
        try:
            out[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def main() -> bool:
    watch = [os.path.join(ROOT, "second_model.json"), os.path.join(ROOT, "data", "account_b.json"),
             os.path.join(ROOT, "data", "live_state_acctb.json"), os.path.join(ROOT, "data", "live_state_acctr.json"),
             os.path.join(ROOT, "data", "push_sent.json"), os.path.join(ROOT, "data", "rapid.json")]
    before = _digest(watch)
    tmp = tempfile.mkdtemp(prefix="abstart_")
    try:
        repro_checks(tmp)
        alarm_checks(tmp)
        funded_checks(tmp)
        present_checks(tmp)
        livebot_checks(tmp)
        fixed_block_checks(tmp)
        rapid_checks(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("the real data/ files and second_model.json are never written", _digest(watch) == before)
    n, ok = len(RESULTS), sum(RESULTS)
    print(f"\n{ok}/{n} passed", flush=True)
    return ok == n


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
