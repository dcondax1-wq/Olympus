"""Trade alerts on EVERY account route (owner 2026-11-20: "notifications to my phone exactly when a trade is taken and closed,
results of it"). Fake fills go through each route's real notice code (no NinjaTrader, no network, temp files only):

  a. LIT primary (Zlarior 50K): the bot's own NinjaTrader adapter (_push_fill / _push_exit) + LiveBot's own exit notice
  b. an extra account (engine/multi_account, Zlarior 25K #2): its adapter (push_as) + the router's notify_entry / notify_outcome
  c. account B (ATLAS funded 25K): its adapter (push_as, new) + AccountB._push_entry / _push_outcome (before: neither sent on
     NinjaTrader, so ATLAS's entries / stop / target exits reached the phone only with the 15-minute report)
  d. the Rapid EOD 25K: LIT's lane (an extra account, id "rapid") + ATLAS's lane (engine/rapid.RapidAtlas, key ":acctr"),
     both on the same bar = two alerts each, named after the Rapid
  e. the 50K combo (engine/combo50k, when on): "ATLAS on Zlarior 50K: ..."
  f. the words + $: 'Zlarior 50K: LONG 4 MNQ @ 21,034.25' / 'stop 21,012.00 (-$178), target 21,090.50 (+$450)';
     'Zlarior 50K: closed LONG +$312 (target)' / 'today +$312, balance $49,505, $3,495 to pass'
  g. the settings (trade_closed off = no exit push) and the ntfy budget (the report's extra posts + chart keep room for them)

Each route: exactly ONE entry and ONE exit message (dedupe by the fill's key), the right name, the right $.
    python -X utf8 -m tests.test_trade_alerts        (~2 s)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import mffu_view as MV  # noqa: E402
from engine import notify as N  # noqa: E402
from engine import push as P  # noqa: E402

RES = []
T0 = 1795050000 - 10 * 3600 + 600          # Wed 2026-11-18 10:10 ET


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  ({info})"))


class Box:
    """engine/push + engine/notify + names / live view pointed at temp files; every notice runs _pc_send synchronously (no
    phone: the ntfy path, the owner's fallback) and the ntfy posts are recorded."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="tradealerts_")
        self.saved = (P.CONFIG_PATH, P.SENT_PATH, P.PC_KEY_PATH, N.INSTANT_PATH, N.settings, P._PC["notifier"], P.pc_notify,
                      MV.NAMES_FILE, N.LIVE_SNAP)
        P.CONFIG_PATH = os.path.join(self.dir, "push.json")
        P.SENT_PATH = os.path.join(self.dir, "push_sent.json")
        P.PC_KEY_PATH = os.path.join(self.dir, "push_pc_key.json")
        N.INSTANT_PATH = os.path.join(self.dir, "instant.json")
        N.LIVE_SNAP = os.path.join(self.dir, "live.json")
        MV.NAMES_FILE = os.path.join(self.dir, "names.json")
        self.cfg = {"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"}
        self.set_settings({"quiet_hours": {"off": True}})
        P._PC["notifier"] = None
        self.posts = []
        self.payloads = []
        poster = lambda base, topic, msg: self.posts.append(msg) or True   # noqa: E731

        def run(payload):
            self.payloads.append(dict(payload))
            return P._pc_send(dict(payload), ntfy=lambda p: N.instant_entry(p, cfg=self.cfg, poster=poster),
                              ntfy_exit=lambda p: N.instant_exit(p, cfg=self.cfg, poster=poster))
        P.pc_notify = run
        with open(MV.NAMES_FILE, "w", encoding="utf-8") as fh:
            json.dump({"l4": {"6016": "Zlarior 50K", "2222": "Zlarior 25K #2", "6018": "ATLAS 25K funded", "5555": "Rapid EOD 25K"},
                       "id": {"atlas": "ATLAS 25K funded", "rapid": "Rapid EOD 25K"}}, fh)

    def set_settings(self, raw):
        N.settings = lambda path=None: N.merge(raw)

    def live(self, t, accounts=(), atlas=None):
        with open(N.LIVE_SNAP, "w", encoding="utf-8") as fh:
            json.dump({"t": t, "accounts": list(accounts), "board": {"atlas": atlas} if atlas else {}}, fh)

    def take(self):
        out, self.posts = self.posts, []
        return out

    def close(self):
        (P.CONFIG_PATH, P.SENT_PATH, P.PC_KEY_PATH, N.INSTANT_PATH, N.settings, P._PC["notifier"], P.pc_notify,
         MV.NAMES_FILE, N.LIVE_SNAP) = self.saved
        shutil.rmtree(self.dir, ignore_errors=True)


def nt_adapter(account="MFFUEVBLDR000006016", push_as=None, real=True):
    """A NinjaTrader adapter without NinjaTrader: only what its phone notices use."""
    from engine import ninjatrader as NT
    ad = object.__new__(NT.NinjaTraderAdapter)
    ad._alert_fn, ad.readonly, ad.sim, ad.account = None, False, False, account
    ad.state_path = NT.STATE_PATH if real else os.path.join(tempfile.gettempdir(), "nt_state_sub.json")
    ad.push_as = push_as
    ad.clock = lambda: T0 + 1800
    return ad


def leg(t=T0, d=1, q=4, fill=21034.25, stop=21012.0, target=21090.5, who=None):
    lg = {"instrument": "MNQ 12-26", "dir": d, "filled": q, "entry_t": t, "fill_px": fill, "stop0": stop, "stop": stop, "target": target,
          "bracket_qty": q}
    if who:
        lg["who"] = who
    return lg


def split(posts):
    ent = [m for m in posts if m["tags"].startswith("chart_with")]
    ex = [m for m in posts if not m["tags"].startswith("chart_with")]
    return ent, ex


# ------------------------------------------------------------------------------------------------ a. LIT primary
def part_a(b: Box):
    b.live(T0 - 600, [{"id": "mffu50k_eval", "name": "MFFU 50K", "plan": "MFFU Builder 50K", "kind": "eval", "source": "pc",
                       "broker_account": "MFFUEVBLDR000006016", "eval": {"balance": 49193.0, "today": 0.0, "to_target": 3807.0}}])
    ad = nt_adapter()
    ad._push_fill(leg())
    ad._push_fill(leg())                               # NinjaTrader reports the same fill twice (two legs, a retry)
    ad._push_exit(leg(), "TARGET", {"avg": 21073.25, "filled": 4})
    from engine import push as PP
    PP.pc_notify(PP.outcome_payload("MFFU 50K", "LONG", "TARGET", 305.6, T0, T0 + 1790, src="pc", R=1.4, qty=4))   # LiveBot's own copy
    ent, ex = split(b.take())
    check("a. LIT primary: ONE entry: 'Zlarior 50K: LONG 4 MNQ @ 21,034.25' / 'stop 21,012.00 (-$178), target 21,090.50 (+$450)'",
          len(ent) == 1 and ent[0]["title"] == "Zlarior 50K: LONG 4 MNQ @ 21,034.25"
          and ent[0]["body"].startswith("stop 21,012.00 (-$178), target 21,090.50 (+$450)"), ent)
    check("a. LIT primary: ONE exit (the bracket fill first; LiveBot's copy of the same trade dropped): "
          "'Zlarior 50K: closed LONG +$312 (target)' / 'today +$312, balance $49,505, $3,495 to pass'",
          len(ex) == 1 and ex[0]["title"] == "Zlarior 50K: closed LONG +$312 (target)"
          and ex[0]["body"].startswith("today +$312, balance $49,505, $3,495 to pass"), ex)
    check("a. the entry rings (high), the exit is a normal push; no account id anywhere",
          ent and ex and ent[0]["priority"] == "high" and ex[0]["priority"] == "default"
          and not any("000006016" in m["title"] + m["body"] for m in ent + ex))


# ------------------------------------------------------------------------------------------------ b. an extra account
def router():
    from engine import live as L
    from engine import multi_account as MA
    r = object.__new__(MA.AccountRouter)
    r.bot = type("Bot", (), {"state_path": L.STATE_PATH})()
    r.clock = lambda: T0 + 1800
    return r


class Acc:
    def __init__(self, id_, name):
        self.id, self.name, self.adapter = id_, name, None


def part_b(b: Box):
    b.live(T0 - 600, [{"id": "b25k_2", "name": "Zlarior Builder 25K #2", "plan": "MFFU Builder 25K", "kind": "eval", "source": "pc",
                       "broker_account": "MFFUEVBLDR000002222", "eval": {"balance": 25120.0, "today": 40.0, "to_target": 1380.0}}])
    r = router()
    acc = Acc("b25k_2", "MFFUEVBLDR000002222")
    acc.adapter = nt_adapter(acc.name, real=False)
    r._wire_push(acc)
    check("b. the router gives the account's NinjaTrader adapter its own name + key (push_as)",
          acc.adapter.push_as == {"account": acc.name, "suffix": ":b25k_2", "url": "#/accounts"}, acc.adapter.push_as)
    acc.adapter._push_fill(leg(q=2))                                    # NinjaTrader's fill
    r.notify_entry(acc, {"dir": 1, "entry_t": T0, "entry": 21034.0, "stop": 21012.0, "target": 21090.5}, 2, "NQ",
                   {"legs": [{"filled": 2, "fill_px": 21034.25}]})        # the router's own copy (same key)
    acc.adapter._push_exit(leg(q=2), "STOP", {"avg": 21012.0, "filled": 2})
    r.notify_outcome(acc, {"dir": 1, "entry_t": T0, "exit_t": T0 + 1790, "exit_reason": "STOP"}, 2, -92.9)
    ent, ex = split(b.take())
    check("b. extra account: ONE entry 'Zlarior 25K #2: LONG 2 MNQ @ 21,034.25' (stop -$89)",
          len(ent) == 1 and ent[0]["title"] == "Zlarior 25K #2: LONG 2 MNQ @ 21,034.25" and "(-$89)" in ent[0]["body"], ent)
    check("b. extra account: ONE exit 'Zlarior 25K #2: closed LONG -$89 (stop)', today -$49, balance $25,031, $1,469 to pass",
          len(ex) == 1 and ex[0]["title"] == "Zlarior 25K #2: closed LONG -$89 (stop)"
          and ex[0]["body"].startswith("today -$49, balance $25,031, $1,469 to pass"), ex)
    # the same bar on the 50K too: its own alert (one per trade AND account)
    nt_adapter()._push_fill(leg(t=T0 + 60))
    acc.adapter._push_fill(leg(t=T0 + 60, q=2))
    check("b. the 50K and the 25K #2 entering on the same bar: two alerts, one each", len(b.take()) == 2)


# ------------------------------------------------------------------------------------------------ c. account B (ATLAS)
def atlas(cls=None, label="ATLAS 25K", account="MFFUSFBLDR000006018"):
    from engine import account_b as AB
    from engine import live as L
    cls = cls or AB.AccountB
    a = object.__new__(cls)
    a.label, a.name = label, account
    a.bot = type("Bot", (), {"state_path": L.STATE_PATH, "_push_send": staticmethod(lambda p: P.pc_notify(p))})()
    a.clock = lambda: T0 + 1800
    a.adapter = nt_adapter(account, real=False)
    a.adapter.reports_fills = True
    a._wire_push()
    return a


def part_c(b: Box):
    b.live(T0 - 600, [], atlas={"balance": 26050.0, "profit": 1050.0, "today_pnl": 0.0, "status": "funded", "broker": "MFFUSFBLDR000006018",
                                "funded": {"max_request": 0}})
    a = atlas()
    check("c. ATLAS: account B now gives its adapter its own name + key (before: neither sent a NinjaTrader fill)",
          a.adapter.push_as == {"account": "ATLAS 25K", "suffix": ":acctb", "url": "#nq"}, a.adapter.push_as)
    t = T0 + 120
    a.adapter._push_fill(leg(t=t, d=-1, q=3, fill=21050.0, stop=21070.0, target=21010.0))
    a._push_entry({"side": "sell", "entry_t": t, "entry": 21050.0, "stop": 21070.0, "target": 21010.0, "strategy": "EMA"}, 3)
    a.adapter._push_exit(leg(t=t, d=-1, q=3, fill=21050.0, stop=21070.0, target=21010.0), "TARGET", {"avg": 21010.0, "filled": 3})
    a._push_outcome({"dir": -1, "short": "EMA"}, "TARGET", 236.2, t + 1500, 3, t)
    ent, ex = split(b.take())
    check("c. ATLAS: ONE entry 'ATLAS 25K funded: SHORT 3 MNQ @ 21,050.00' (stop -$120, target +$240)",
          len(ent) == 1 and ent[0]["title"] == "ATLAS 25K funded: SHORT 3 MNQ @ 21,050.00"
          and ent[0]["body"].startswith("stop 21,070.00 (-$120), target 21,010.00 (+$240)"), ent)
    check("c. ATLAS: ONE exit 'ATLAS 25K funded: closed SHORT +$240 (target)' with today / balance",
          len(ex) == 1 and ex[0]["title"] == "ATLAS 25K funded: closed SHORT +$240 (target)"
          and ex[0]["body"].startswith("today +$240, balance $26,290"), ex)
    a2 = atlas()
    a2.adapter = object()                                             # a paper adapter: account B sends its own (no push_as)
    a2._push_entry({"side": "buy", "entry_t": t + 900, "entry": 21000.0, "stop": 20990.0, "target": 21030.0, "strategy": "MACD"}, 2)
    a2._push_outcome({"dir": 1, "short": "MACD"}, "TIME", 40.0, t + 1700, 2, t + 900)
    ent, ex = split(b.take())
    check("c. ATLAS without a NinjaTrader adapter: its own entry + exit, one each", len(ent) == 1 and len(ex) == 1, (ent, ex))


# ------------------------------------------------------------------------------------------------ d. the Rapid EOD
def part_d(b: Box):
    from engine import rapid as RP
    b.live(T0 - 600, [{"id": "rapid", "name": "MFFURPDEOD000005555", "plan": "MFFU Rapid EOD 25K", "kind": "eval", "source": "pc",
                       "broker_account": "MFFURPDEOD000005555", "eval": {"balance": 25300.0, "today": 0.0, "to_target": 1200.0}}])
    r = router()
    lane = Acc("rapid", "MFFURPDEOD000005555")
    lane.adapter = nt_adapter(lane.name, real=False)
    r._wire_push(lane)
    ar = atlas(RP.RapidAtlas, label="ATLAS Rapid MFFURPDEOD000005555", account="MFFURPDEOD000005555")
    t = T0 + 300
    lane.adapter._push_fill(leg(t=t, q=2))
    ar.adapter._push_fill(leg(t=t, q=1))
    ent, _ = split(b.take())
    titles = sorted(m["title"] for m in ent)
    check("d. Rapid EOD: LIT's lane and ATLAS's lane on the same bar = two entries, named after the Rapid",
          titles == ["Rapid EOD 25K (ATLAS): LONG 1 MNQ @ 21,034.25", "Rapid EOD 25K: LONG 2 MNQ @ 21,034.25"], titles)
    lane.adapter._push_exit(leg(t=t, q=2), "TARGET", {"avg": 21090.5, "filled": 2})
    r.notify_outcome(lane, {"dir": 1, "entry_t": t, "exit_t": t + 900, "exit_reason": "TARGET"}, 2, 221.1)
    ar.adapter._push_exit(leg(t=t, q=1), "TARGET", {"avg": 21090.5, "filled": 1})
    _, ex = split(b.take())
    tt = sorted(m["title"] for m in ex)
    check("d. Rapid EOD: one exit per lane, the second one's 'today' counts the first ($225 + $112 = +$338)",
          tt == ["Rapid EOD 25K (ATLAS): closed LONG +$112 (target)", "Rapid EOD 25K: closed LONG +$225 (target)"]
          and any(m["body"].startswith("today +$338, balance $25,638, $862 to pass") for m in ex), ex)


# ------------------------------------------------------------------------------------------------ e. the 50K combo
def part_e(b: Box):
    ad = nt_adapter()
    t = T0 + 2400
    ad._push_fill(leg(t=t, who="ATLAS on Zlarior 50K"))
    ad._push_exit(leg(t=t, who="ATLAS on Zlarior 50K"), "STOP", {"avg": 21012.0, "filled": 4})
    ent, ex = split(b.take())
    check("e. the combo: 'ATLAS on Zlarior 50K: LONG 4 MNQ @ 21,034.25' and 'ATLAS on Zlarior 50K: closed LONG -$178 (stop)'",
          len(ent) == 1 and ent[0]["title"] == "ATLAS on Zlarior 50K: LONG 4 MNQ @ 21,034.25"
          and len(ex) == 1 and ex[0]["title"] == "ATLAS on Zlarior 50K: closed LONG -$178 (stop)", (ent, ex))


# ------------------------------------------------------------------------------------------------ f/g. settings, paper, budget
def part_g(b: Box):
    b.set_settings({"quiet_hours": {"off": True}, "alerts": {"trade_closed": False}})
    ad = nt_adapter()
    t = T0 + 3600
    ad._push_fill(leg(t=t))
    ad._push_exit(leg(t=t), "TARGET", {"avg": 21090.5, "filled": 4})
    ent, ex = split(b.take())
    check("g. trade_closed off in notify_settings.json: the entry still comes, no exit push", len(ent) == 1 and not ex, (ent, ex))
    b.set_settings({"quiet_hours": {"off": True}, "alerts": {"trade_opened": False}})
    ad._push_fill(leg(t=t + 60))
    check("g. trade_opened off: no entry push", not b.take())
    b.set_settings({"quiet_hours": {"off": True}})
    sim = nt_adapter("Sim101")
    sim.sim = True
    sim._push_fill(leg(t=t + 120))
    p = P.entry_payload("Paper", "LONG", 1, t + 180, src="pc", entry=1, stop=0, target=2)
    P.pc_notify(p)
    P.pc_notify(dict(p, account="MFFU 25K", key=f"fill:{t + 181}:acctc", strategy="BLITZ"))
    sub_sim = nt_adapter("Sim102", push_as={"account": "ATLAS 25K", "suffix": ":acctb"}, real=False)
    sub_sim.sim = True
    sub_sim._push_fill(leg(t=t + 150))
    check("g. never for Sim / Paper / BLITZ (a sub-account's Sim adapter too, whatever its route calls it)", not b.take())
    import time
    now = time.time()
    n0 = N.ntfy_today()
    check("g. each instant ntfy alert counts in this PC's UTC day (the report's budget reads it)", n0 == 1, n0)
    from tools import pc_report as R
    work = os.path.join(b.dir, "pc_report")
    os.makedirs(work, exist_ok=True)
    day = R._utc_day(now)
    R.write_json(os.path.join(work, R.BARS_STATE), {"days": {day: {"all": R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE - n0}}})
    st = {"days": {day: {"all": R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE - n0, "inst": n0}}}
    due, why = R.bars_due(st, {"t": now}, now, True)
    check("g. ntfy budget: the chart stops TRADE_ALERT_RESERVE posts before the cap, counting the instant alerts",
          not due and "the status and the pushes first" in why, (due, why))
    check("g. ntfy budget: day_used = the report's posts + the instant trade alerts", R.day_used(work, now) == R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE, R.day_used(work, now))
    src = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("g. the extra status posts hold back near the cap (the last room of the day stays for the trade alerts)",
          "day_used(work, snap[\"t\"]) + len(exts) > NTFY_DAY_CAP - TRADE_ALERT_RESERVE" in src)


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_g):
        b = Box()
        try:
            f(b)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
        finally:
            b.close()
    n, ok = len(RES), sum(RES)
    print(f"\ntrade alerts: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
