"""AI watch (engine/ai_watch.py, engine/rulelog.py, engine/ai_api.py, ops_checks readiness + restore): anomalies (bad tick,
spike, jump, feed frozen mid-trade, slow route), the anomaly pause and the both-accounts loss cap (OFF by default, then on),
drift (LIT health band, account B bootstrap, execution), the rule-change log (diff, git history, runtime change + push),
the pre-session / weekly lines, backup restore (dry run, refused while running, applied with a pre-restore copy), and the
static wiring (guards, LiveBot, alerts_plus kinds + critical freeze, heartbeat, live.json, cloud monitor, phone, PC).
Paper only: fake bots, temp dirs, no network, nothing is armed or routed.

  python -X utf8 -m tests.test_ai_features
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import zipfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd

from engine import ai_watch as AW, rulelog as RL

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(y, mo, d, h=0, mi=0):
    return int(dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def bars(t0, n=61, rng=8.0, last=None, gap=0.0):
    rows, px = [], 25000.0
    for i in range(n):
        o = px
        c = o + (1 if i % 2 else -1)
        rows.append({"time": t0 + 60 * i, "open": o, "high": max(o, c) + rng / 2, "low": min(o, c) - rng / 2, "close": c, "volume": 100})
        px = c
    if gap:
        rows[-1]["open"] += gap
        rows[-1]["high"] += gap
        rows[-1]["low"] += gap
        rows[-1]["close"] += gap
    if last:
        rows[-1].update(last)
    return pd.DataFrame(rows)


class FakeB:
    def __init__(self, closes=(), prov=None, day_pnl=0.0, open_t=None, spec=None, ledger=()):
        self.closes, self.prov, self._dp, self.open_t = list(closes), dict(prov or {}), day_pnl, open_t
        self.spec = spec or {"plan": "builder25k", "sizing": "need", "keys": ["ema_lon_vix"]}
        self.label, self.name, self.ledger, self.problem = "Account B ATLAS", "Sim102", list(ledger), None

    def day_pnl(self, day):
        return self._dp

    def eval_view(self, now=None):
        return {"room": 1234.0, "status": "open"}


def fake_bot(tmp, ledger=(), pnl=0.0, position=None, health=None, acct_b=None, guards=None):
    b = SimpleNamespace(state_path=os.path.join(tmp, "live_state.json"), ledger=list(ledger), state={"position": position},
                        health=health or {}, acct_b=acct_b, cfg={"sym": "NQ", "guards": guards or {}}, _open_routed=None, errors=[])
    b.day_pnl_routed = lambda: pnl
    b._note_error = lambda t: b.errors.append(t)
    return b


# ------------------------------------------------------------------------------------------------ 1. anomalies
def test_anomalies():
    t0 = ts(2026, 10, 21, 9, 0)
    check("normal bars: no anomaly", AW.bar_anomaly(bars(t0)) is None)
    a = AW.bar_anomaly(bars(t0, last={"high": 25200.0}))
    check("spike: a 1m range far above 8x the median and 60 pts -> price spike", a and a["what"] == "price spike", a)
    a = AW.bar_anomaly(bars(t0, last={"high": 24000.0, "low": 24100.0}))
    check("bad tick: high below low -> malformed bar", a and a["what"] == "bad tick", a)
    a = AW.bar_anomaly(bars(t0, last={"close": 0.0, "low": 0.0}))
    check("bad tick: a zero price", a and a["what"] == "bad tick", a)
    a = AW.bar_anomaly(bars(t0, gap=80.0))
    check("jump: an open 80 pts from the previous close -> price jump", a and a["what"] == "price jump", a)
    check("30 pts at the open with a quiet median is NOT a spike (min 60 pts)", AW.bar_anomaly(bars(t0, last={"high": 25030.0})) is None)
    tmp = tempfile.mkdtemp()
    try:
        now = t0 + 3600
        h = {"market_open": True, "last_1m_bar_t": now - 600}
        check("freeze: no position -> nothing", AW.freeze_check(fake_bot(tmp, health=h), now) is None)
        fz = AW.freeze_check(fake_bot(tmp, health=h, position={"dir": 1}), now)
        check("freeze: LIT in a trade + newest 1m bar 9 min old -> frozen", fz and "LIT" in fz["text"], fz)
        fz = AW.freeze_check(fake_bot(tmp, health=h, acct_b=FakeB(open_t=now - 900)), now)
        check("freeze: account B in a trade counts too", fz and "Account B" in fz["text"], fz)
        check("freeze: market closed -> nothing", AW.freeze_check(fake_bot(tmp, health={**h, "market_open": False}, position={"dir": 1}), now) is None)
        check("freeze: fresh bar -> nothing", AW.freeze_check(fake_bot(tmp, health={**h, "last_1m_bar_t": now - 90}, position={"dir": 1}), now) is None)
        cc = AW.crit_conditions(fake_bot(tmp, health=h, position={"dir": 1}), now)
        check("freeze is critical (alerts_plus kind 'freeze', repeats until Got it)", cc and cc[0]["kind"] == "freeze", cc)
        led = [{"side": "buy", "entry_t": now - 200, "t": now - 197, "result": {"ok": True}},
               {"side": "sell", "entry_t": now - 100, "t": now - 40, "result": {"ok": True}},
               {"side": "buy", "entry_t": now - 50, "t": now - 5, "result": {"ok": False}}]
        L = AW.latency_check(AW.latency_rows(fake_bot(tmp, ledger=led)), now)
        check("latency: only the entry routed 60 s after its signal is flagged (3 s fine, refused ignored)",
              len(L) == 1 and L[0]["lat_s"] == 60, L)
        bb = FakeB(ledger=[{"side": "buy", "entry_t": now - 300, "t": now - 250, "strategy": "EMA", "result": {}}])
        L = AW.latency_check(AW.latency_rows(fake_bot(tmp, acct_b=bb)), now)
        check("latency: account B's ledger too", len(L) == 1 and L[0]["text"].startswith("EMA"), L)
        # the tick: one push per anomaly, the pause marker only for a fresh one
        sent = []
        bot = fake_bot(tmp, ledger=led, health=h, position={"dir": 1})
        bot._nt_last = {("NQ", "1m"): bars(now - 61 * 60, last={"high": 25300.0})}
        out = AW.tick(bot, now, send=sent.append)
        kinds = sorted(p["kind"] for p in sent)
        check("tick: spike + slow route pushed as kind anomaly", kinds.count("anomaly") == 2, kinds)
        AW.tick(bot, now + 5, send=sent.append)
        check("tick: the same anomalies are not pushed twice", sum(p["kind"] == "anomaly" for p in sent) == 2, [p["key"] for p in sent])
        check("tick: anomaly log kept, freeze state stored", len(bot._ai["anomalies"]) >= 3 and bot._ai["freeze"], bot._ai.get("anomalies"))
        check("tick: state written next to the bot's state (data/ai_watch.json)", os.path.isfile(os.path.join(tmp, "ai_watch.json")))
        check("tick: alert text says nothing was blocked (pause off)", all("Alert only" in p["body"] for p in sent if p["kind"] == "anomaly"), sent)
        hb = AW.hb_block(bot)
        check("heartbeat block: anomalies, drift, loss, switches (both off), rule log", hb and {"anomalies", "drift", "loss", "switches", "rule_log"} <= set(hb)
              and hb["switches"]["anomaly_pause"] is False and hb["switches"]["combined_loss"] is False, hb)
        check("heartbeat block is small (< 6 KB)", len(json.dumps(hb, default=str)) < 6000, len(json.dumps(hb, default=str)))
        check("tick never raised (no error noted)", not bot.errors, bot.errors)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ guards: OFF by default
def test_blocks():
    from engine import guards as G
    check("guards DEFAULTS: anomaly_pause and combined_loss OFF", G.DEFAULTS["anomaly_pause"] is False and G.DEFAULTS["combined_loss"] is False)
    tmp = tempfile.mkdtemp()
    try:
        now = ts(2026, 10, 21, 10, 0)
        bot = fake_bot(tmp, pnl=-1400.0, acct_b=FakeB(day_pnl=-300.0), health={"market_open": True, "last_1m_bar_t": now - 900},
                       position={"dir": 1})
        bot._ai = {"pause_from": {"t": now - 60, "what": "price spike"}, "days": {}}
        c = G.config(bot)
        check("defaults: no block even at -$1,700 together + a fresh spike", G._owner_blocks(bot, c, now) == [], G._owner_blocks(bot, c, now))
        x = AW.combined(bot, now)
        check("combined: LIT -$1,400 + B -$300 = -$1,700 today", x["total"] == -1700.0 and x["lit"] == -1400.0 and x["b"] == -300.0, x)
        c2 = {**c, "combined_loss": True}
        p = G._owner_blocks(bot, c2, now)
        check("combined_loss on: blocked at the $1,500 daily cap", any("combined daily cap" in s for s in p), p)
        bot2 = fake_bot(tmp, pnl=-200.0, acct_b=FakeB(day_pnl=0.0))
        mon = AW.trading_day(now - 2 * 86400)
        bot2._ai = {"days": {mon: {"total": -2900.0}, "2026-10-12": {"total": -5000.0}}}
        p = AW.combined_problem(bot2, c2, now)
        check("combined_loss on: this week's earlier days count (-$2,900 + -$200), last week's do not", p and "weekly cap" in p, p)
        c3 = {**c, "anomaly_pause": True}
        p = G._owner_blocks(bot, c3, now)
        check("anomaly_pause on: blocked 1 min after a spike", any("anomaly pause" in s for s in p), p)
        bot._ai["pause_from"]["t"] = now - 20 * 60
        bot.health["last_1m_bar_t"] = now - 60
        check("anomaly_pause on: free again after 15 min (fresh feed)", AW.anomaly_problem(bot, c3, now) is None, AW.anomaly_problem(bot, c3, now))
        bot.health["last_1m_bar_t"] = now - 900
        check("anomaly_pause on: blocked while the feed is frozen in a trade", "anomaly pause" in (AW.anomaly_problem(bot, c3, now) or ""))
        bot._guards_cfg = None
        bot.cfg["guards"] = {"combined_loss": True}
        check("switch: start cfg / live_model.json guards {\"combined_loss\": true} reaches the guard", G.config(bot)["combined_loss"] is True)
        # tick pushes at the cap even with the block off
        sent = []
        b3 = fake_bot(tmp, pnl=-1600.0)
        AW.tick(b3, now, send=sent.append, df1=bars(now - 3700))
        lc = [p for p in sent if p["kind"] == "loss_cap"]
        check("loss_cap push at -$1,600 today (alert only while the block is off)", len(lc) == 1 and "Alert only" in lc[0]["body"], sent)
        AW.tick(b3, now + 30, send=sent.append, df1=bars(now - 3700))
        check("loss_cap push once a day", sum(p["kind"] == "loss_cap" for p in sent) == 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 2. drift
def test_drift():
    p = AW.boot_pct([1.0, -1.0] * 50, -8.0, 10)
    check("bootstrap: -8R in 10 trades of a +/-1R coin is below p5", p is not None and p < 5, p)
    p = AW.boot_pct([1.0, -1.0] * 50, 0.0, 10)
    check("bootstrap: 0R is near the median", p is not None and 35 < p < 65, p)
    check("levels: bad < 5 <= warn < 10 <= good", (AW.level(3), AW.level(7), AW.level(50), AW.level(None)) == ("bad", "warn", "good", None))
    pool = AW.b_pool({"plan": "builder25k", "sizing": "need"})
    check("account B pool: run acctb_25k_need, 2026 trades in R", len(pool) > 100, len(pool))
    t0 = ts(2026, 10, 1, 4, 0)
    closes = [["2026-10-0%d" % (i + 1), t0 + i * 86400 + 600, -110.0, t0 + i * 86400] for i in range(6)]
    prov = {t0 + i * 86400: {"qty": 5, "risk_pts": 10.0} for i in range(6)}
    ab = FakeB(closes=closes, prov=prov)
    R = AW.b_live_r(ab)
    check("account B live R = pnl / (stop pts x micros x $2 + $1.90 a micro): -$110 on 5 x 10 pts = -1.0R",
          len(R) == 6 and abs(R[0] + 1.0) < 0.01, R)
    d = AW.drift_b(ab)
    check("account B: 6 straight -1R stops is below p5 (investigate)", d and d["level"] == "bad" and d["run"] == "acctb_25k_need", d)
    d = AW.drift_b(FakeB(closes=closes[:2], prov=prov))
    check("account B: 2 trades = too early (no verdict)", d and d["level"] is None and "too early" in d["text"], d)
    dl = AW.drift_lit(journal_rows=[], now=ts(2026, 10, 22, 17, 0))
    check("LIT drift: the H2 band loads, no live trade yet = no verdict", dl and dl.get("level") is None and not dl.get("error"), dl)
    jr = [{"source": "pc", "day": f"2026-10-{19 + i:02d}", "entry_t": ts(2026, 10, 19 + i, 3), "exit": "STOP", "r": -1.0, "pnl": -500}
          for i in range(4)] + [{"source": "pc", "day": "2026-10-26", "entry_t": ts(2026, 10, 26, 3), "exit": "STOP", "r": -1.0, "pnl": -500},
                                 {"source": "pc", "day": "2026-10-27", "entry_t": ts(2026, 10, 27, 3), "exit": "STOP", "r": -1.0, "pnl": -500}]
    dl = AW.drift_lit(journal_rows=jr, now=ts(2026, 10, 27, 17, 0))
    check("LIT drift: 6 straight stops in 7 sessions -> a verdict below the middle", dl and dl.get("level") in ("bad", "warn") and dl.get("trades") == 6, dl)
    de = AW.drift_exec({"trades": 8, "latency_s_med": 45, "entry_slip_ticks_med": 1.0})
    check("execution drift: median latency 45 s flagged", de and de["level"] == "warn" and "latency" in de["text"], de)
    check("execution in line: 3 s, 0.5 ticks", AW.drift_exec({"trades": 8, "latency_s_med": 3, "entry_slip_ticks_med": 0.5})["level"] == "good")
    s = {}
    now = ts(2026, 10, 27, 17, 0)
    n1 = AW.drift_notices([{"strategy": "LIT", "level": "bad", "trades": 6, "text": "x"}, {"strategy": "B", "level": "warn", "trades": 6, "text": "y"},
                           {"strategy": "C", "level": "good", "trades": 9, "text": "z"}], s, now)
    n2 = AW.drift_notices([{"strategy": "LIT", "level": "bad", "trades": 6, "text": "x"}, {"strategy": "B", "level": "warn", "trades": 7, "text": "y"}], s, now)
    check("drift pushes: bad once per trade count, warn once a week, good never", len(n1) == 2 and n2 == [] and all(p["kind"] == "drift" for p in n1), n1 + n2)
    check("drift push says nothing was changed", "Nothing was changed" in n1[0]["body"], n1[0]["body"])


# ------------------------------------------------------------------------------------------------ 4. rule-change log
def test_rules():
    a = {"lit": {"t_check": {"at": 15, "x": 0.3}, "be_off": 1.25, "note": "x"}, "guards": {}}
    b = {"lit": {"t_check": {"at": 20, "x": 0.3}, "scale_in": {"pb": 0.25}, "note": "y"}, "guards": {"news": True}}
    d = RL.diff(a, b)
    check("diff: changed, added, removed; text keys left out",
          d == ["guards.news: added true", "lit.be_off: removed (was 1.25)", "lit.scale_in.pb: added 0.25", "lit.t_check.at: 15 -> 20"], d)
    H = RL.history(20)
    check("git history: commits that changed a trading file, with who / when / why", H and all({"sha", "who", "when", "why", "files"} <= set(h) for h in H), H[:1])
    tmp = tempfile.mkdtemp()
    try:
        bot = fake_bot(tmp)
        s = {"_rule_log_path": os.path.join(tmp, "rule_changes.jsonl")}
        now = ts(2026, 10, 22, 20, 0)
        check("runtime: first snapshot = baseline, no push", AW.rules_step(bot, s, now, snap=a) == [])
        p = AW.rules_step(bot, s, now + 60, snap=b)
        check("runtime: a change -> one push kind rules_change with the changes", len(p) == 1 and p[0]["kind"] == "rules_change"
              and "lit.scale_in.pb: added 0.25" in p[0]["body"] and "(+1 more)" in p[0]["body"], p)
        rows = RL.runtime_rows(s["_rule_log_path"])
        check("runtime: appended to the rule-change log file", len(rows) == 1 and "lit.t_check.at: 15 -> 20" in rows[0]["changes"], rows)
        check("runtime: same rules again -> nothing", AW.rules_step(bot, s, now + 120, snap=b) == [])
        snap = AW.rules_snapshot(bot)
        check("snapshot: live_model lit / lit_sizing (no eval_start) / guards + second_model", {"lit", "lit_sizing", "second"} <= set(snap)
              and "eval_start" not in (snap.get("lit_sizing") or {}), list(snap))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ 5. readiness, weekly, restore
def test_ops():
    from engine import ops_checks as OC
    now = ts(2026, 10, 22, 1, 45)
    ev = [{"t": ts(2026, 10, 22, 8, 30), "event": "CPI m/m", "time_et": "08:30"}, {"t": ts(2026, 10, 23, 8, 30), "event": "NFP", "time_et": "08:30"}]
    hb = {"ai": {"acct_b": {"label": "Account B ATLAS", "room": 1100, "status": "open"}, "switches": {"anomaly_pause": False, "combined_loss": True},
                 "drift": [{"strategy": "LIT", "level": "good", "pct": 41.0}, {"strategy": "Account B ATLAS", "level": "bad", "pct": 3.0}],
                 "anomalies": [{"what": "price spike"}], "rule_changes": [{"t": now}]}}
    ln = AW.readiness_line(hb, now, events=ev)
    check("readiness: today's news, account B room, blocks on", "08:30 CPI m/m" in ln and "NFP" not in ln and "room $1,100" in ln
          and "Blocks on: combined_loss" in ln, ln)
    check("readiness: no news -> says so", "No Tier-1 news today" in AW.readiness_line({}, now, events=[]))
    wl = AW.weekly_line(hb)
    check("weekly self-review: drift verdicts + anomalies + rule changes", "LIT in range (p41)" in wl and "INVESTIGATE (p3)" in wl
          and "1 anomaly" in wl and "1 rule change" in wl, wl)
    rows = AW.ops_checks({"ai": {"acct_b": {"label": "B", "problem": "account Sim102 not found in NinjaTrader"}}}, now)
    check("health screen: account B problem is a FIX row (pre-session push key acct_b)", rows and rows[0]["level"] == "bad" and rows[0]["key"] == "acct_b", rows)
    check("pre-session keys include acct_b", '"acct_b")' in read("engine/ops_checks.py"))
    tmp = tempfile.mkdtemp()
    try:
        root, dest = os.path.join(tmp, "root"), os.path.join(tmp, "backups")
        os.makedirs(os.path.join(root, "data"))
        with open(os.path.join(root, "data", "live_state.json"), "w") as fh:
            fh.write('{"now": 1}')
        os.makedirs(dest)
        z = os.path.join(dest, "le-backup-20261021-2300.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("data/live_state.json", '{"old": 1}')
            zf.writestr("data/ai_watch.json", '{"t": 1}')
            zf.writestr("data/push_pc_key.json", "SECRET")
            zf.writestr("../evil.json", "x")
        r = OC.restore("latest", root=root, dest=dest)
        check("restore: dry run lists the state files, skips anything else (keys, paths outside data/)",
              r["ok"] and not r["applied"] and sorted(r["files"]) == ["data/ai_watch.json", "data/live_state.json"]
              and "data/push_pc_key.json" in r["skipped"], r)
        r = OC.restore("latest", root=root, dest=dest, yes=True, ping={"bot_running": True}, hb={})
        check("restore: refused while the bot runs", not r["ok"] and "running" in r["error"], r)
        r = OC.restore("latest", root=root, dest=dest, yes=True, ping=None, hb={"position": True})
        check("restore: refused with an open position", not r["ok"] and "position" in r["error"], r)
        r = OC.restore("latest", root=root, dest=dest, yes=True, ping=None, hb={})
        got = json.load(open(os.path.join(root, "data", "live_state.json")))
        pre = os.path.join(dest, r.get("pre_restore") or "-")
        check("restore: applied, the replaced file zipped first", r["ok"] and r["applied"] and got == {"old": 1} and os.path.isfile(pre)
              and json.loads(zipfile.ZipFile(pre).read("data/live_state.json")) == {"now": 1}, r)
        check("backup sources include the new state files", "ai_watch.json" in read("engine/ops_checks.py") and "live_state_acctb.json" in read("engine/ops_checks.py"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ wiring
def test_static():
    from engine import alerts_plus as ap
    for k in ("freeze", "anomaly", "drift", "loss_cap", "rules_change"):
        check(f"alerts_plus kind {k} (on / silent / off in the app)", k in ap.KINDS and f"['{k}'," in read("tools/web_public/alerts.js"))
    check("freeze is the only new critical kind", ap.KINDS["freeze"][2] is True and not any(ap.KINDS[k][2] for k in ("anomaly", "drift", "loss_cap", "rules_change")))
    check("alerts_plus.pc_conditions carries the freeze crit", "ai_watch.crit_conditions" in read("engine/alerts_plus.py"))
    lv = read("engine/live.py")
    check("LiveBot._alerts_tick runs ai_watch.tick (real bot only, after routing)", "ai_watch.tick(self, now)" in lv)
    g = read("engine/guards.py")
    check("guards._owner_blocks (LIT and account B) call the ai_watch blocks only when switched on",
          'if c.get("anomaly_pause") or c.get("combined_loss"):' in g and "G._owner_blocks(self.bot" in read("engine/account_b.py"))
    check("heartbeat carries 'ai'", '"ai": _ai(self.bot)' in read("engine/heartbeat.py"))
    # the tuples grew a "launch" key after "ai" (launch checklist, 2026-10-25): match the "ai" entry, not the tuple's end
    check("live.json carries 'ai' (trimmed first when too big)", '"second", "ai"' in read("engine/live_publish.py") and 'for k in ("ai", "second"' in read("engine/live_publish.py"))
    check("cloud monitor passes live.pc.ai through",                # BLITZ's block sits between second and ai since 2026-10-28
          '"brain", "second", "ai"' in read("tools/cloud_monitor.py") or '"brain", "second", "blitz", "ai"' in read("tools/cloud_monitor.py"))
    check("phone: index.html loads ai.js, System > AI watch page", 'src="ai.js?v=' in read("tools/web_public/index.html") and "VIEWS.aiwatch" in read("tools/web_public/ai.js"))
    check("PC: /api/next/ai mounted, System page AI-watch card", "ai_api import router" in read("engine/next_api.py") and "/api/next/ai" in read("web_next/js/next/hubpages.js"))
    from engine import ai_api
    v = ai_api.view(None)
    check("PC API view: rule log + switches (both blocks listed with their exact switch)", v["rule_log"].get("commits") is not None
          and [s["key"] for s in v["switches"]][:2] == ["anomaly_pause", "combined_loss"] and "guards" in v["switches"][0]["on"], v["switches"])
    check(".gitignore: data/ai_watch.json", "data/ai_watch.json" in read(".gitignore"))
    code = read("engine/ai_watch.py").split('"""', 2)[2]
    check("ai_watch never imports the NinjaTrader adapter / never routes or flattens",
          "import ninjatrader" not in code and "ninjatrader import" not in code and "adapter." not in code and "._route(" not in code
          and "flatten(" not in code and "kill_switch" not in code)


def main():
    for f in (test_anomalies, test_blocks, test_drift, test_rules, test_ops, test_static):
        try:
            f()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n = len(RES)
    print(f"ai features: {sum(RES)}/{n} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
