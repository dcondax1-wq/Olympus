"""The phone app's live.json from the PC (engine/live_publish.py + tools/web_public/live.js). Offline: temporary bare git
repos only, fake bots, no network (the phone check answers the GitHub API from Playwright).

  python -X utf8 -m tests.test_live_publish            (add --no-browser to skip the Playwright phone check)

Checks: the payload (Home essentials, same shapes as data.json, < 64 KB), no secret / confirm phrase / local path in it,
the rate limit and the failure backoff, the replace-commit (one commit on the branch, the project's .git untouched,
scratch objects pruned), a failed push / a broken bot never raises, enabled() and the target URL, the server wiring, the
phone files (poll, merge, SW network-only, cache bump), and in a real browser that Home updates from a changed live.json
within one poll.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from engine import live_publish as lp
from engine.tradovate import LIVE_PHRASE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES: list = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not cond else ""))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def hb_payload(now, n_trades=3, position=True):
    trades = [{"day": "2026-10-20", "entry_t": int(now) - 86400 + i, "exit_t": int(now) - 86000 + i, "side": "LONG", "qty": 4,
               "entry": 25000.0, "exit_px": 25040.0, "pnl": 640.0 - i, "r": 1.6, "exit": "TARGET", "note": "x" * 200}
              for i in range(n_trades)]
    pos = {"entry_t": int(now) - 600, "side": "SHORT", "dir": -1, "qty": 6, "entry": 25100.25, "stop": 25130.0, "stop0": 25130.0,
           "target": 24980.0, "be": False, "risk_pts": 29.75, "target_label": "VIX band low", "unrealized": 120.0,
           "unrealized_r": 0.3} if position else None
    return {"t": int(now), "running": True, "adapter": "ninjatrader", "position": bool(position), "model_state": "IN TRADE",
            "host": "SURFACE", "model": "lit", "push_pk": "BPUBLICKEY", "every_s": 300,
            "acct": {"v": 1, "t": int(now), "account": {"name": "FAKEEVAL1", "label": "LIVE ACCOUNT", "adapter": "ninjatrader"},
                     "running": True, "kill": False, "model": "lit",
                     "eval": {"start": "2026-10-19", "days": {"2026-10-19": 300.0, "2026-10-20": 450.0}},
                     "position": pos, "orders": [{"t": int(now) - 600, "side": "sell", "text": "SELL 6 MNQ"}], "trades": trades,
                     "day_pnl": 0.0},
            "health": {"v": 1, "t": int(now), "running": True, "kill": False, "model": "lit",
                       "account": {"name": "FAKEEVAL1", "adapter": "ninjatrader", "is_live": True, "label": "LIVE", "enabled": True,
                                   "disabled": None, "armed": True, "live_lock": True},
                       "feed": {"source": "ninjatrader", "used": "ninjatrader", "no_yahoo": True, "age_1m_s": 12, "age_5m_s": 40,
                                "last_1m_t": int(now) - 72, "last_5m_t": int(now) - 340, "stale": False, "market_open": True,
                                "entries_blocked": False, "block": None},
                       "poll": {"last_t": int(now) - 3, "age_s": 3, "errors": 0},
                       "lit": {"stage": "trade", "text": "in trade", "price": 25070.5,
                               "last_setup": {"t": int(now) - 900, "side": "SHORT", "level": "PDH"}},
                       "nt": {"connected": True, "last_error": f"bad file C:\\Users\\owner\\Documents\\NinjaTrader 8\\incoming\\x.txt"},
                       "auto": {"version": "abc1234", "update": {"on": True}, "resume": {"on": True, "account": "FAKEEVAL1"}}},
            "ops": {"red": 0, "yellow": 1, "fix": f"type {LIVE_PHRASE} to arm"},
            "remote": {"on": True, "text": "remote: last cmd status done at 09:12 ET", "token": "ghp_SECRET"},
            "exec": {"n": 1}}


def account_c_block(now):
    """An engine/account_c.AccountC.hb_block-shaped block: BLITZ on its own 25K eval (SIM), two booked days this week."""
    import datetime as _dt
    from engine import live_board
    d0 = _dt.date.fromisoformat(live_board.trading_day(now))
    mon = d0 - _dt.timedelta(days=d0.weekday())
    return {"account": "FAKEEVALC", "kind": "SIM", "real": False, "plan_label": "MFFU Builder 25K", "stage": "eval",
            "eval": {"start": "2026-11-02", "balance": 25310.0, "floor": 24310.0, "room": 1000.0, "to_target": 1190.0, "target": 26500.0,
                     "profit": 310.0, "today": 0.0, "status": "open", "session": 2, "dll": 600.0, "max_micros": 20},
            "rules": {"start": 25000.0, "target": 1500.0, "mll": 1000.0, "lock": 25100.0, "dll": 600.0, "max_micros": 20},
            "day_pnl": 125.5, "entries_today": 1, "state": {"text": "waiting for the 11:30 check"},
            "days": {str(mon - _dt.timedelta(days=3)): 999.0, str(mon): 184.5, str(d0): 125.5}, "closed": [], "routed": [], "t": int(now)}


def hidden_checks(now, lm):
    """Hidden bots (owner 2026-11-15, dashboard_view.json, default ["blitz"]): live.json carries no BLITZ card, no account C,
    no BLITZ trade, and says "hidden_bots" so the pages know; the heartbeat payload itself is not changed."""
    import copy
    from engine import hidden_bots
    hb = hb_payload(now)
    hb["account_c"] = account_c_block(now)
    hb["blitz"] = {"label": "BLITZ (paper shadow)", "eval": {"room": 900}}
    before = copy.deepcopy(hb)
    hidden_bots.FORCE = ("blitz",)
    try:
        p = lp.build(hb, now, lm=lm, hb_last={"at": int(now) - 30, "ok": True}, every_s=60)
    finally:
        hidden_bots.FORCE = None
    blob = json.dumps({k: v for k, v in p.items() if k != "hidden_bots"}).lower()
    check("hidden: BLITZ hidden by default (the committed dashboard_view.json)", hidden_bots.hidden() == ("blitz",), hidden_bots.hidden())
    check("hidden: live.json has no blitz / account_c anywhere and says hidden_bots",
          "blitz" not in blob and "account_c" not in blob and p.get("hidden_bots") == ["blitz"]
          and "lit" in (p.get("board") or {}) and "atlas" in (p.get("board") or {}), [k for k in p if "blitz" in k.lower()])
    check("hidden: read-only (the heartbeat payload keeps BLITZ: the engine and ledgers are untouched)", hb == before)


def blitz_checks(now, lm, p_off):
    """BLITZ (account C) on the phone feed: an "off" card while account C is off, the board's card shape while on,
    read-only, None (never an exception) when it cannot be built. Run with BLITZ shown (dashboard_view.json "hidden_bots": [])."""
    import copy
    from engine import live_board
    bz = p_off.get("blitz") or {}
    check("blitz: account C off -> an 'off' card in live.json, board.blitz left out (its 'absent = off' contract)",
          bz.get("off") is True and bz.get("status") == "off" and bz.get("plan") == "MFFU Builder 25K" and bz.get("room") is None
          and "blitz" not in (p_off.get("board") or {}) and "lit" in p_off["board"] and "atlas" in p_off["board"], bz)
    hb = hb_payload(now)
    hb["account_c"] = account_c_block(now)
    before = copy.deepcopy(hb)
    p = lp.build(hb, now, lm=lm, hb_last={"at": int(now) - 30, "ok": True}, every_s=60)
    bz, card, lit = p.get("blitz") or {}, (p.get("board") or {}).get("blitz") or {}, (p.get("board") or {}).get("lit") or {}
    core = ("id", "name", "plan", "badge", "status", "today_pnl", "week_pnl", "room", "to_target", "floor", "balance", "mll", "session")
    check("blitz: account C on -> the card from its heartbeat block (plan, badge, status, today, room, to target, floor)",
          bz.get("off") is False and bz["plan"] == "MFFU Builder 25K" and bz["badge"] == "SIM" and bz["status"] == "open"
          and bz["today_pnl"] == 125.5 and bz["room"] == 1000.0 and bz["to_target"] == 1190.0 and bz["floor"] == 24310.0, bz)
    wk_want = round(sum(v for d, v in hb["account_c"]["days"].items() if v != 999.0), 2)    # a Monday run: one day (dict key clash)
    check("blitz: this week's P&L from account C's booked days (last week's day left out)", bz.get("week_pnl") == wk_want, bz.get("week_pnl"))
    check("blitz: same keys as the board's lit card", all(k in bz for k in core) and all(k in lit for k in core if k != "badge"),
          [k for k in core if k not in bz])
    check("blitz: board.blitz is there while account C is on and agrees", card.get("room") == 1000.0 and card.get("id") == "blitz", card)
    check("blitz: read-only (the heartbeat payload is not changed)", hb == before)
    check("blitz: blitz_block never raises on junk (None or an off card)",
          all((lambda r: r is None or isinstance(r, dict))(lp.blitz_block(x, now)) for x in (None, {}, {"account_c": "x"}, {"account_c": {"days": 5}}, "junk", 7)))
    check("blitz: account C reporting an error -> an off card that says so",
          (lp.blitz_block({"account_c": {"error": "KeyError: x"}}, now) or {}).get("status") == "error")
    real = live_board.blitz_now
    try:
        live_board.blitz_now = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        r = lp.blitz_block(hb, now)
        p2 = lp.build(hb, now, lm=lm)
        check("blitz: a failure gives None, never an exception, and live.json still builds",
              r is None and p2.get("blitz") is None and isinstance(p2.get("board"), dict) and "lit" in p2["board"], (r, p2.get("blitz")))
    except Exception as e:
        check("blitz: a failure gives None, never an exception, and live.json still builds", False, e)
    finally:
        live_board.blitz_now = real


def pc_health_checks(now, lm, p_none):
    """Jarvis's System view (2026-11-02): live.json "pc_health" = the heartbeat's pc_health block, cut small, secret-free."""
    check("pc_health: no block in the heartbeat -> no key in live.json (as before)", "pc_health" not in p_none)
    hb = hb_payload(now)
    hb["pc_health"] = {"t": int(now) - 40, "level": "amber", "skipped": [], "lines": [
        {"key": "cpu", "level": "green", "text": "CPU 23%"},
        {"key": "ram", "level": "amber", "text": "RAM 89% in use (3.2 of 3.6 GB): close other apps (browser tabs)"},
        {"key": "disk", "level": "green", "text": "41.0 GB free"},
        {"key": "nt", "level": "green", "text": "NinjaTrader running, 900 MB"},
        {"key": "onedrive", "level": "amber", "text": "1 OneDrive conflict copy: C:\\Users\\owner\\OneDrive\\bot\\x (1).json " + "y" * 200},
        {"key": "token", "level": "green", "text": f"type {LIVE_PHRASE} now"}]}
    p = lp.build(hb, now, lm=lm)
    ph = p.get("pc_health") or {}
    ln = {x["key"]: x for x in ph.get("lines") or []}
    check("pc_health: CPU / RAM numbers, the overall level (amber -> warn), the check-in age",
          ph.get("cpu") == 23 and ph.get("ram") == 89 and ph.get("level") == "warn" and ph.get("age_s") == 40 and ph.get("t") == int(now) - 40, ph)
    check("pc_health: one line per check with its label and level (green -> ok)",
          ln.get("cpu", {}).get("label") == "CPU" and ln.get("cpu", {}).get("level") == "ok" and ln.get("ram", {}).get("level") == "warn"
          and ln.get("nt", {}).get("label") == "NinjaTrader", ln)
    blob = json.dumps(ph)
    check("pc_health: secret-free (no confirm phrase, local paths redacted) and short texts",
          LIVE_PHRASE not in blob and "C:\\\\Users" not in blob and all(len(x["text"]) <= 140 for x in ln.values()), blob[:300])
    check("pc_health: the heartbeat payload is not changed (read-only)", hb["pc_health"]["lines"][0] == {"key": "cpu", "level": "green", "text": "CPU 23%"})
    check("pc_health: pc_health_summary never raises on junk",
          all(lp.pc_health_summary(x) is None for x in (None, {}, "x", 5, {"lines": "x"})) and isinstance(lp.pc_health_summary({"lines": [None, 3, {"key": "cpu"}], "t": "junk"}), dict))
    big = lp.build({**hb_payload(now, n_trades=60), "pc_health": hb["pc_health"]}, now, lm=lm)
    check("pc_health: still under 64 KB with 60 trades", len(json.dumps(big, separators=(",", ":"))) < lp.MAX_BYTES)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tmp = tempfile.mkdtemp(prefix="le_livepub_")
    now = time.time()
    lm = {"lit_sizing": {"eval_start": "2026-10-19"}}
    try:
        # ------------------------------------------------------------------ payload
        p = lp.build(hb_payload(now), now, lm=lm, hb_last={"at": int(now) - 30, "ok": True}, every_s=60)
        blob = json.dumps(p)
        acc = (p.get("accounts") or [{}])[0]
        check("payload: kind / t / every_s / host / model_state", p["kind"] == "le-live" and p["t"] == int(now) and p["every_s"] == 60
              and p["host"] == "SURFACE" and p["model_state"] == "IN TRADE", {k: p.get(k) for k in ("kind", "t", "every_s")})
        check("payload: verdict from engine/accounts.verdict (heartbeat fresh, live account)",
              (p.get("pc_verdict") or {}).get("code") in ("TRADING", "FEED", "DISABLED", "SIM", "PAPER") and p["pc_verdict"]["hb_age_s"] == 0,
              p.get("pc_verdict"))
        check("payload: the PC account like data.json accounts (eval $ to go / room / session, position, today's P&L)",
              acc.get("source") == "pc" and acc["eval"]["to_target"] == 2250.0 and acc["eval"]["room"] == 2000.0
              and acc["eval"]["session"] and acc["position"]["side"] == "SHORT" and acc["position"]["stop"] == 25130.0
              and "today" in acc["pnl"] and acc["conn"]["connected"] and not any(a.get("source") == "cloud" for a in p["accounts"]), acc.get("eval"))
        check("payload: price, last signal, last heartbeat push, feed ages, check-in time",
              p["price"] == 25070.5 and p["last_signal"]["level"] == "PDH" and p["heartbeat"] == {"t": int(now) - 30, "ok": True}
              and p["pc"]["health"]["feed"]["age_1m_s"] == 12 and p["pc"]["t"] == int(now) and p["pc"]["present"] and not p["pc"]["silent"])
        check("payload: the raw acct / exec / push key blocks stay out of pc", all(k not in p["pc"] for k in ("acct", "exec", "push_pk")))
        gl = p["pc"].get("glance") or {}
        check("payload: pc.glance for the Brain page (engine/brain_glance.py): Zlarior + ATLAS, the open trade's $ risk / $ target, small",
              [b.get("id") for b in gl.get("bots") or []] == ["lit", "atlas"] and gl["bots"][0].get("pos", {}).get("risk_usd") == 357
              and gl["bots"][0]["pos"].get("tgt_usd") == 1443 and len(json.dumps(gl)) < 2500, gl)
        # ------------------------------------------------------------------ secrets
        check("secrets: no confirm phrase anywhere", LIVE_PHRASE not in blob)
        check("secrets: no token / password-like key, no token value", "ghp_SECRET" not in blob and '"token"' not in blob)
        check("secrets: local paths redacted", "C:\\\\Users" not in blob and "<path>" in blob)
        check("secrets: scrub() drops credential keys at any depth and keeps eval words like 'passed'",
              lp.scrub({"a": {"password": 1, "api_key": 2, "passed": 3, "list": [{"webhook": "u", "ok": 1}]}})
              == {"a": {"passed": 3, "list": [{"ok": 1}]}})
        hidden_checks(now, lm)
        from engine import hidden_bots as _hbz
        _hbz.FORCE = ()                       # BLITZ shown: its own contract (the switch set to [])
        try:
            blitz_checks(now, lm, lp.build(hb_payload(now), now, lm=lm, hb_last={"at": int(now) - 30, "ok": True}, every_s=60))
        finally:
            _hbz.FORCE = None
        pc_health_checks(now, lm, p)
        big =lp.build(hb_payload(now, n_trades=60), now, lm=lm)
        sz = len(json.dumps(big, separators=(",", ":")))
        check("size: under 64 KB with 60 trades of long notes (trimmed to the last 25)", sz < lp.MAX_BYTES and len(big["accounts"][0]["trades"]) <= 25, sz)
        # the Bot Brain's phone cut (engine/brain.compact, < 16 KB) rides in pc.brain: with 60 trades it still fits
        hbb = hb_payload(now, n_trades=60)
        hbb["brain"] = {"v": 1, "kind": "le-brain", "compact": True, "stage": {"key": "limit", "waiting": "x" * 200},
                        "levels": [{"label": f"L{i}", "price": 30000 + i} for i in range(20)], "setups": [{"id": str(i), "checks": [["depth", True, "y" * 120]] * 8} for i in range(8)],
                        "log": [{"hm": "04:00", "kind": "sweep", "text": "z" * 150} for _ in range(30)]}
        bb = lp.build(hbb, now, lm=lm)
        szb = len(json.dumps(bb, separators=(",", ":")))
        check("size: under 64 KB with the Bot Brain in pc.brain", szb < lp.MAX_BYTES and (bb["pc"].get("brain") or {}).get("stage"), szb)
        bad = lp.build({"t": "x", "running": True, "health": "not a dict"}, now, lm=lm)
        check("payload: junk heartbeat input -> still a valid live.json (never raises)", bad["kind"] == "le-live" and isinstance(bad["pc"], dict))

        # ------------------------------------------------------------------ rate limit + backoff (fake clock, fake push)
        clock = [1000.0]
        pushes = []
        bot = SimpleNamespace(running=True, cfg={}, state={})
        hb = SimpleNamespace(payload=lambda: hb_payload(clock[0]), last={"at": 1, "ok": True})
        pub = lp.Publisher(bot, hb, log=lambda t: None, clock=lambda: clock[0], url="file:///x",
                           push_fn=lambda pl, url, **kw: pushes.append(pl["t"]) or {"ok": True, "bytes": 10})
        r1 = pub.publish()
        clock[0] += 10
        r2 = pub.publish()
        clock[0] += 40
        r3 = pub.publish()
        check("rate limit: a second push within 45 s is skipped, the next one goes", r1["ok"] and r2.get("skipped") == "rate limit"
              and r3["ok"] and len(pushes) == 2, (r1, r2, r3))
        r4 = pub.publish(force=True)
        check("rate limit: force (the owner's --once) pushes at once", r4["ok"] and len(pushes) == 3)
        check("cadence: 60 s while the bot runs, 300 s when stopped", pub.next_wait() == 60 and
              lp.Publisher(SimpleNamespace(running=False), None, url="x").next_wait() == 300)
        logs = []
        fail = lp.Publisher(bot, hb, log=logs.append, clock=lambda: clock[0], url="file:///x",
                            push_fn=lambda pl, url, **kw: {"ok": False, "error": "remote: Permission denied"})
        waits = []
        for _ in range(8):
            clock[0] += 3600
            fail.publish()
            waits.append(fail.next_wait())
        check("backoff: 2, 4, 8 ... min after failures, capped at 30 min; logged at most once an hour",
              waits[:3] == [120, 240, 480] and max(waits) == lp.MAX_BACKOFF_S and len(logs) <= 8 and "Permission denied" in logs[0], waits)
        hf = lp.hb_field() or {}
        check("heartbeat field: the last push result (ok False + the reason) for the phone's health card",
              hf.get("ok") is False and "Permission denied" in (hf.get("error") or "") and hf.get("fails", 0) >= 1, hf)
        boom = lp.Publisher(bot, SimpleNamespace(payload=lambda: 1 / 0), log=lambda t: None, clock=lambda: clock[0], url="file:///x",
                            push_fn=lambda pl, url, **kw: (_ for _ in ()).throw(RuntimeError("git exploded")))
        try:
            rb = boom.publish(force=True)
            check("failure-safe: a broken heartbeat payload + a raising push never raise", not rb["ok"] and "git exploded" in rb["error"])
        except Exception as e:
            check("failure-safe: a broken heartbeat payload + a raising push never raise", False, e)

        # ------------------------------------------------------------------ replace-commit on a temporary bare repo
        bare, proj = os.path.join(tmp, "nq-dashboard.git"), os.path.join(tmp, "proj")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        subprocess.run(["git", "init", "-q", proj], check=True)
        before = subprocess.run(["git", "-C", proj, "count-objects"], capture_output=True, text=True).stdout
        scratch = os.path.join(tmp, "live_pub.git")
        a = lp.push({"t": 1, "kind": "le-live", "n": "first"}, bare, git_dir=scratch, cwd=proj)
        b = lp.push({"t": 2, "kind": "le-live", "n": "second"}, bare, git_dir=scratch, cwd=proj, prune=True)
        cnt = subprocess.run(["git", "--git-dir", bare, "rev-list", "--count", "live"], capture_output=True, text=True).stdout.strip()
        body = subprocess.run(["git", "--git-dir", bare, "show", "live:live.json"], capture_output=True, text=True).stdout
        ls = subprocess.run(["git", "--git-dir", bare, "ls-tree", "--name-only", "live"], capture_output=True, text=True).stdout.split()
        check("git: two pushes -> ONE commit on branch live holding only live.json = the second payload",
              a["ok"] and b["ok"] and cnt == "1" and json.loads(body)["n"] == "second" and ls == ["live.json"], (a, b, cnt, ls))
        after = subprocess.run(["git", "-C", proj, "count-objects"], capture_output=True, text=True).stdout
        loose = subprocess.run(["git", "--git-dir", scratch, "count-objects"], capture_output=True, text=True).stdout
        check("git: the project's .git is untouched (scratch git dir only), the scratch dir is pruned",
              before == after and int(loose.split()[0]) <= 3, (before, after, loose))
        heads = subprocess.run(["git", "--git-dir", bare, "for-each-ref", "--format=%(refname)"], capture_output=True, text=True).stdout.split()
        check("git: only refs/heads/live is written (never main: no Pages build)", heads == ["refs/heads/live"], heads)
        r = lp.push({"t": 3}, os.path.join(tmp, "missing.git"), git_dir=scratch, cwd=proj)
        check("git: a failed push returns ok False with the reason (never raises)", not r["ok"] and r["error"], r)
        check("git: no target -> ok False", not lp.push({"t": 3}, "", git_dir=scratch)["ok"])

        # ------------------------------------------------------------------ switches + target URL
        check("enabled: on with LE_HEARTBEAT=1, off by default, LE_LIVE_PUBLISH=0/1 override",
              lp.enabled({"LE_HEARTBEAT": "1"}) and not lp.enabled({}) and not lp.enabled({"LE_HEARTBEAT": "1", "LE_LIVE_PUBLISH": "0"})
              and lp.enabled({"LE_LIVE_PUBLISH": "1"}))
        for origin, want in (("https://github.com/demetrades2000-coder/nq-liquidity-engine.git", "https://github.com/demetrades2000-coder/nq-dashboard.git"),
                             ("git@github.com:demetrades2000-coder/nq-liquidity-engine.git", "git@github.com:demetrades2000-coder/nq-dashboard.git"),
                             ("https://github.com/demetrades2000-coder/nq-liquidity-engine", "https://github.com/demetrades2000-coder/nq-dashboard.git")):
            subprocess.run(["git", "-C", proj, "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", proj, "remote", "add", "origin", origin], check=True)
            got = lp.target_url(proj, env={})
            check(f"target: {origin.split('github.com')[0]}... origin -> the Pages repo nq-dashboard, same owner + protocol", got == want, got)
        check("target: LE_LIVE_REPO overrides", lp.target_url(proj, env={"LE_LIVE_REPO": "file:///x"}) == "file:///x")
        pu = lp.phone_urls("https://github.com/demetrades2000-coder/nq-dashboard.git")
        check("phone URLs: the API contents path on ref=live and the raw fallback",
              pu["api"] == "https://api.github.com/repos/demetrades2000-coder/nq-dashboard/contents/live.json?ref=live"
              and pu["raw"].endswith("/nq-dashboard/live/live.json"))
        check("status(): the target URL is shown without a token",
              "tok" not in lp.Publisher(bot, None, url="https://u:tok@github.com/o/nq-dashboard.git").status()["target"])

        # ------------------------------------------------------------------ wiring + phone files
        srv = read("server.py")
        check("server.py: Publisher made with the heartbeat, started next to it, in the status API",
              "_lp.Publisher(BOT, HEARTBEAT" in srv and "LIVEPUB.start()" in srv and '"live_publish": LIVEPUB.status()' in srv)
        check(".gitignore: the scratch git dir is ignored", "data/live_pub.git/" in read(".gitignore"))
        lj, idx, sw, more = read("tools/web_public/live.js"), read("tools/web_public/index.html") + read("tools/web_public/main.js"), read("tools/web_public/sw.js"), read("tools/web_public/more.js")   # main.js: the page's own script (QA Round 7)
        check("phone: live.js polls the API (raw fallback), 30-60 s, on focus, merges into D / HOMEJ, redraws Home",
              "contents/live.json?ref=live" in lj and "raw.githubusercontent.com" in lj and "visibilitychange" in lj
              and "LIVE.every = rem > 30 ? 30 : 60" in lj and "LIVE.apply(D)" in lj and "render(true)" in lj)
        check("phone: index.html loads live.js and applies it after every data.json / home.json load",
              'src="live.js?v=' in idx and "window.LIVE.apply(D)" in idx and "window.LIVE.apply(j)" in idx)
        check("phone: SW cache bumped to v15+, live.json network-only",
              int(__import__("re").search(r"le-public-v(\d+)", sw).group(1)) >= 15 and "url.pathname.endsWith('live.json') || url.pathname.endsWith('status_feed.json')) return;" in sw)
        check("phone: stale banner off while live.json is fresh; 'Live · N ago' in the update line", "!liveOn" in more and "Live</b>" in more)
        check("phone: build copies live.js (every file of tools/web_public)", "for name in os.listdir(WEB)" in read("tools/build_web_dashboard.py"))

        # ------------------------------------------------------------------ the real phone page (Playwright)
        if "--no-browser" not in argv:
            phone_check(tmp, now)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"live publish: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


def phone_check(tmp, now):
    node = shutil.which("node")
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not node or not os.path.isdir(os.path.join(groot, "playwright")):
        print("[SKIP] phone Playwright check: node + playwright not installed")
        return
    site = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules"))
    T = int(now)
    old = T - 25 * 3600                                  # the cloud's last heartbeat: 25 h old (tonight's bug)
    acct = {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "SIM",
            "conn": {"present": True, "t": old, "age_s": 90000, "connected": False, "has_detail": True, "running": True, "host": "SURFACE"},
            "eval": {"balance": 50100, "profit": 100, "to_target": 2900, "floor": 48000, "room": 2100, "mll": 2000, "dll": 1000,
                     "dll_used": 0, "session": 3, "sessions": 10}, "pnl": {"today": 0}, "position": None, "orders": [], "trades": [], "days": [], "stats": {"n": 0}}
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T - 1020)),
            "live": {"last_run": T - 1020, "runs": 1, "pc": {"present": True, "t": old, "age_s": 90000, "running": True, "every_s": 300, "host": "SURFACE"},
                     "pc_verdict": {"code": "SILENT", "label": "CLOUD VERDICT OLD", "level": "bad", "reason": "old"}},
            "accounts": [acct], "results": {"periods": {}}, "trades": [], "strategy": {}}
    for n in ("data.json", "home.json"):
        with open(os.path.join(site, n), "w", encoding="utf-8") as f:
            json.dump(data, f)
    env = {**os.environ, "NODE_PATH": os.path.join(subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())}
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers" if os.path.isdir("/opt/pw-browsers") else "")
    if not env["PLAYWRIGHT_BROWSERS_PATH"]:
        env.pop("PLAYWRIGHT_BROWSERS_PATH")
    r = subprocess.run([node, os.path.join(ROOT, "tests", "phone_live_check.js"), site, "8799"], capture_output=True, text=True,
                       timeout=180, env=env)
    try:
        out = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        check("phone (Playwright): the check ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-300:])
        return
    for name, ok, info in out.get("steps") or []:
        check(f"phone (Playwright): {name}", ok, info)
    if out.get("error"):
        check("phone (Playwright): no harness error", False, out["error"])


if __name__ == "__main__":
    sys.exit(main())
