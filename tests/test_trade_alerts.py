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
        self.ntfy_ok = True                                                  # False: ntfy.sh refuses (a 429, the network)
        poster = lambda base, topic, msg: (self.posts.append(msg) or True) if self.ntfy_ok else False   # noqa: E731

        def run(payload):
            self.payloads.append(dict(payload))
            return P._pc_send(dict(payload), ntfy=lambda p: N.instant_entry(p, cfg=self.cfg, poster=poster),
                              ntfy_exit=lambda p: N.instant_exit(p, cfg=self.cfg, poster=poster))
        P.pc_notify = run
        with open(MV.NAMES_FILE, "w", encoding="utf-8") as fh:
            json.dump({"l4": {"9998": "Zlarior 50K", "2222": "Zlarior 25K #2", "9999": "ATLAS 25K funded", "5555": "Rapid EOD 25K"},
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


def nt_adapter(account="MFFUEVBLDR000009998", push_as=None, real=True):
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
                       "broker_account": "MFFUEVBLDR000009998", "eval": {"balance": 49193.0, "today": 0.0, "to_target": 3807.0}}])
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
          and not any("000009998" in m["title"] + m["body"] for m in ent + ex))


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
def atlas(cls=None, label="ATLAS 25K", account="MFFUSFBLDR000009999"):
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
    b.live(T0 - 600, [], atlas={"balance": 26050.0, "profit": 1050.0, "today_pnl": 0.0, "status": "funded", "broker": "MFFUSFBLDR000009999",
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


# ------------------------------------------------------------------------------------------------ h. the miss of 2026-11-20
ATLAS_ENTRY_T = 1795164300          # Fri 2026-11-20 03:45:00 ET: ATLAS SHORT 1 MNQ @ 26,380.75, stop 26,419.50, target 26,122.75 (LIVE)
ATLAS_EXIT_T = 1795176603           # 07:10:03 ET: the target filled (+$514.18 after costs; $516 from the fills)
ATLAS_ID = "MFFUSFBLDR000009999"    # the test id of atlas() above (this test's names.json maps it to "ATLAS 25K funded")


class _Clock:
    """engine/notify's clock at a chosen time (quiet hours are decided by the wall clock, not by the trade's time)."""

    def __init__(self, t):
        import time as _t
        self.t, self._t = float(t), _t

    def time(self):
        return self.t

    def __getattr__(self, k):
        return getattr(self._t, k)


def phone_accepts(app):
    """engine/push.app_send as when ONE Olympus phone is registered and its push service answers 201 ("accepted"): what the PC
    saw at 03:45 and 07:10 ET (the public status listed one phone all night and never dropped it)."""
    def fake(payload, cfg=None, sender=None, path=None):
        app.append(dict(payload))
        return {"sent": 1, "devices": 1, "gone": [], "errors": []}
    return fake


def replay_atlas(b: Box, app: list):
    """Today's ATLAS trade through its real route (account B's NinjaTrader adapter with push_as), the shipped notify_settings.json,
    one phone that accepts every push. -> (entry ntfy posts, exit ntfy posts, the notify module's clock)."""
    raw = json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8"))
    b.set_settings(raw)                                       # the PC's own settings file (quiet hours 23:00-07:00 ET)
    b.live(ATLAS_ENTRY_T - 300, [], atlas={"balance": 24887.20, "profit": -112.80, "today_pnl": 0.0, "status": "funded", "broker": ATLAS_ID,
                                           "funded": {"max_request": 0}})
    a = atlas(label=f"ATLAS {ATLAS_ID}", account=ATLAS_ID)  # engine/account_b.load_spec: label = "ATLAS <account>"
    lg = leg(t=ATLAS_ENTRY_T, d=-1, q=1, fill=26380.75, stop=26419.5, target=26122.75)
    N.time = _Clock(ATLAS_ENTRY_T + 3)                          # 03:45:03 ET: NinjaTrader reports the fill
    a.adapter.clock = lambda: ATLAS_ENTRY_T + 3
    a.adapter._push_fill(lg)
    ent = b.take()
    lg["stop"] = 26379.5                                      # moved to break-even at ~04:00
    N.time = _Clock(ATLAS_EXIT_T)                             # 07:10:03 ET: the target leg fills
    a.adapter.clock = lambda: ATLAS_EXIT_T
    a.adapter._push_exit(lg, "TARGET", {"avg": 26122.75, "filled": 1})
    a._push_outcome({"dir": -1, "short": "EMA"}, "TARGET", 514.18, ATLAS_EXIT_T, 1, ATLAS_ENTRY_T)   # account B's own copy (same key)
    return ent, b.take()


def part_h(b: Box):
    import time as real_time
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    try:
        ent, ex = replay_atlas(b, app)
        sw = [p for p in app if p.get("kind") == "fill"]
        check("h. 2026-11-20 03:45 ET, ATLAS LIVE short, ONE Olympus phone that accepts: the phone app gets the entry "
              "'ATLAS 25K funded: SHORT 1 MNQ @ 26,380.75' (as before)",
              len(sw) == 1 and sw[0]["title"] == "ATLAS 25K funded: SHORT 1 MNQ @ 26,380.75", sw)
        check("h. the most likely miss (unconfirmed: the PC's push logs were not read): the entry ALSO goes to the private ntfy topic "
              "(before, ntfy skipped it whenever a phone accepted: 'skipped: the phone app has it')",
              len(ent) == 1 and ent[0]["title"] == "ATLAS 25K funded: SHORT 1 MNQ @ 26,380.75"
              and ent[0]["body"].startswith("stop 26,419.50 (-$78), target 26,122.75 (+$516)"), ent)
        check("h. 03:45 ET is inside quiet hours: the entry SHOWS on both routes, without sound (ntfy low, Olympus silent): nights stay "
              "silent as before (lead 2026-11-20; ringing at night is the owner's yes / no)",
              ent and ent[0]["priority"] == "low" and sw and sw[0].get("silent") is True, (ent[:1], sw[:1]))
        check("h. the shipped notify_settings.json and the defaults do not ring trades at night; adding TRADE_RING to ring_in_quiet_hours "
              "makes the same 03:45 entry ring",
              not any(N.rings(k, N.merge(json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8")))) for k in N.TRADE_RING)
              and not any(N.rings(k, N.merge({})) for k in N.TRADE_RING)
              and N.entry_message(dict(sw[0], kind="fill") if sw else {}, now=ATLAS_ENTRY_T + 3,
                                  s=N.merge({"ring_in_quiet_hours": ["problems", *N.TRADE_RING]}))["priority"] == "high")
        so = [p for p in app if p.get("kind") == "outcome"]
        check("h. 07:10:03 ET the target fills: ONE result on the phone app 'ATLAS 25K funded: closed SHORT +$516 (target)' "
              "(account B's own copy of the same close dropped)",
              len(so) == 1 and so[0]["title"] == "ATLAS 25K funded: closed SHORT +$516 (target)", so)
        check("h. the same for the result (most likely miss, unconfirmed): it ALSO goes to ntfy, $ first, with today / balance: "
              "'today +$516, balance $25,403'",
              len(ex) == 1 and ex[0]["title"] == "ATLAS 25K funded: closed SHORT +$516 (target)"
              and ex[0]["body"].startswith("today +$516, balance $25,403") and ex[0]["priority"] == "default", ex)
        check("h. no account id in any alert (only the owner's name)",
              not any(ATLAS_ID in json.dumps(x) for x in ent + ex + [{k: p.get(k) for k in ("title", "body")} for p in app]))
        rep = [{"key": f"open:atlas:{ATLAS_ENTRY_T}", "priority": "high"}, {"key": f"close:atlas:{ATLAS_ENTRY_T}", "priority": "default"}]
        kept = [m["key"] for m in N.apply(rep, ATLAS_EXIT_T + 300, N.settings())]
        check("h. the 04:00 / 07:15 reports then skip their copies (ntfy already has both: one alert per route, no repeat)", kept == [], kept)
        lines = [json.loads(x) for x in open(os.path.join(b.dir, N.TRADE_LOG_NAME), encoding="utf-8")]
        mine = [r for r in lines if str(r.get("key", "")).startswith(("fill:1795164300", "out:1795164300"))]
        check("h. each route's answer is kept on disk (logs/notify/trade_alerts.jsonl): app sent 1, ntfy sent, for the entry and the "
              "result; no id, no topic", len(mine) == 2 and all(r["app"].get("sent") == 1 and r["ntfy"] == "sent" and "warn" not in r for r in mine)
              and not any(ATLAS_ID in json.dumps(r) or b.cfg["topic"] in json.dumps(r) for r in lines), lines)
    finally:
        P.app_send = saved
        N.time = real_time


def part_h2(b: Box):
    """the same morning, but ntfy.sh refuses at the fill (a 429): the phone app has it, the 15-minute report still sends its ntfy copy
    (before: the app's 201 counted as delivered and the report dropped its copy too)."""
    import time as real_time
    from tools import pc_report as R
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    b.ntfy_ok = False
    try:
        ent, ex = replay_atlas(b, app)
        check("h2. ntfy refuses at 03:45 and 07:10: nothing on ntfy yet, the phone app has both", not ent and not ex and len(app) == 2, (ent, ex, app))
        rep = [{"key": f"open:atlas:{ATLAS_ENTRY_T}", "priority": "high"}, {"key": f"close:atlas:{ATLAS_ENTRY_T}", "priority": "default"}]
        kept = N.apply(rep, ATLAS_EXIT_T + 300, N.settings())
        check("h2. the 15-minute report KEEPS its copies of that entry and result (they still owe ntfy)",
              [m["key"] for m in kept] == [m["key"] for m in rep], kept)
        check("h2. ... and sends them to ntfy only, not to the phone app again (it had them)",
              all(R._trade_alert(m) and R._app_had(m) for m in kept) and not R._app_had({"key": f"open:atlas:{ATLAS_ENTRY_T + 3600}"}), kept)
        lines = [json.loads(x) for x in open(os.path.join(b.dir, N.TRADE_LOG_NAME), encoding="utf-8")]
        check("h2. the log says what ntfy answered", len(lines) == 2 and all(str(r["ntfy"]).startswith("ntfy did not") for r in lines), lines)
    finally:
        P.app_send = saved
        N.time = real_time
        b.ntfy_ok = True


def part_h2b(b: Box):
    """the bot server sees NO ntfy topic (another user profile / OLYMPUS_HOME than the 15-minute task): the phone app has the trade,
    and the report, which may see the topic, still owes its ntfy copy (never the app copy again)"""
    import time as real_time
    from tools import pc_report as R
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    b.cfg = {}
    try:
        ent, ex = replay_atlas(b, app)
        rep = [{"key": f"open:atlas:{ATLAS_ENTRY_T}", "priority": "high"}, {"key": f"close:atlas:{ATLAS_ENTRY_T}", "priority": "default"}]
        kept = N.apply(rep, ATLAS_EXIT_T + 300, N.settings())
        check("h2b. no topic in the bot's process: the report keeps both copies for its own ntfy topic, not for the app",
              not ent and not ex and len(app) == 2 and [m["key"] for m in kept] == [m["key"] for m in rep] and all(R._app_had(m) for m in kept),
              (ent, ex, kept))
    finally:
        P.app_send = saved
        N.time = real_time


def part_h3(b: Box):
    """no route at all on the PC (no phone, no ntfy topic): the alert is logged with a warning, and the self-check says NO ROUTE"""
    from engine import alert_check as AC
    b.cfg = {}
    ad = nt_adapter()
    ad._push_fill(leg(t=T0 + 7000))
    lines = [json.loads(x) for x in open(os.path.join(b.dir, N.TRADE_LOG_NAME), encoding="utf-8")]
    check("h3. a trade alert that reached no route is logged with a warning (app: no phone, ntfy: no topic)",
          len(lines) == 1 and lines[0].get("warn") and lines[0]["app"].get("skipped") == "no phone"
          and str(lines[0]["ntfy"]).startswith(P.NO_TOPIC), lines)
    r = AC.routes(ntfy_cfg={})
    check("h3. the self-check: NO ROUTE, in plain words, with the fix", not r["ok"] and r["phones"] == 0 and not r["ntfy"]
          and r["warn"] and r["warn"][0].startswith("NO ROUTE") and "Allow notifications" in r["warn"][0], r)
    from engine import alert_bus as AB
    saved_active = AB.active
    try:                                  # redteam 2026-11-21: only Telegram / Discord set up (the alert bus) is a route, not NO ROUTE
        AB.active = lambda env=None, cfg=None: True
        rb = AC.routes(ntfy_cfg={})
    finally:
        AB.active = saved_active
    check("h3. only Telegram / Discord (the alert bus): a route, ok, no NO ROUTE line; the console line names it",
          rb["ok"] and rb["bus"] and not any(w.startswith("NO ROUTE") for w in rb["warn"])
          and any("Telegram / Discord" in w for w in rb["warn"]) and "alert bus" in " ".join(AC.describe(rb)), rb)
    from tools import pc_report as PR
    rep = {on: " ".join(t for _k, lab, t in PR.card({"t": T0, "wp": {}, "alert_bus": on}, {}, {}) if lab == "REPORT") for on in (False, True)}
    check("h3. the PC card: 'NO PHONE ALERT ROUTE' without any route, not when the alert bus is set up",
          "NO PHONE ALERT ROUTE" in rep[False] and "NO PHONE ALERT ROUTE" not in rep[True] and "Telegram / Discord" in rep[True], rep)
    b.set_settings(json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8")))
    r2 = AC.routes(ntfy_cfg={"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"})
    check("h3. with the ntfy topic and the shipped settings: ok, entries + results on, silent at night (still shown), both routes",
          r2["ok"] and r2["ntfy"] and r2["trade_opened"] and r2["trade_closed"] and not r2["ring_at_night"] and r2["trade_routes"] == "both"
          and any("without sound" in w and "still show" in w for w in r2["warn"]), r2)


def part_h4(b: Box):
    """the owner's self-check (python -X utf8 -m engine.alert_check --test, the PC dashboard's Send test): a TEST entry + close on
    BOTH routes, the real alerts' words, never recorded as a trade"""
    from engine import alert_check as AC
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    posts = []
    try:
        t = T0 + 9000
        n0 = N.ntfy_today()
        AC._TEST["t"] = None
        r = AC.send_test(now=t, poster=lambda base, topic, msg: posts.append(msg) or True, ntfy_cfg=b.cfg, http=no_quota,
                         work=os.path.join(b.dir, "pc_report"))
        check("h4. Send test: the Olympus app gets a TEST entry and a TEST close (the close replaces the entry: same tag)",
              r["app"].get("sent") == 1 and r["app_close"].get("sent") == 1 and len(app) == 2
              and app[0]["title"] == "TEST alert: SHORT 1 MNQ @ 26,380.75" and app[1]["title"] == "TEST alert: closed SHORT +$514 (target)"
              and app[0]["tag"] == app[1]["tag"] and all(p["body"].startswith(AC.TEST_WORDS) for p in app), app)
        check("h4. ... and the ntfy app gets the same two, marked TEST, counted in the day's ntfy budget",
              r["ntfy"] == "sent" and len(posts) == 2 and all(m["body"].startswith(AC.TEST_WORDS) for m in posts)
              and N.ntfy_today() == n0 + 2, (r, posts))
        check("h4. a test is never a trade: the 15-minute report's matching is untouched",
              not N.instant_sent(t) and not N.instant_sent(t, what="exits") and not N.instant_sent(t, what="app_entries"))
        txt = "\n".join(AC.describe(r))
        check("h4. the console lines say which route took it, without the topic", "Olympus app: accepted for 1 phone" in txt
              and "ntfy: the TEST entry and close went" in txt and b.cfg["topic"] not in txt, txt)
    finally:
        P.app_send = saved


def no_quota(method, url, body=None, headers=None, timeout=15):
    """ntfy's GET /v1/account in a test: no answer (never the network)."""
    return 0, "no network in tests"


# ------------------------------------------------------------------------------------------------ i. per-account matching
def part_i(b: Box):
    """LIT enters the 50K, the 25K #2 and the Rapid on the same bar, ATLAS often within minutes: one account's instant alert must never
    stand for another's in the 15-minute report (skeptics 2026-11-20: matched on entry time only, so an alert could go missing)."""
    from tools import pc_report as R
    t = T0 + 12000
    atl = P.entry_payload("ATLAS 25K", "SHORT", 1, t, src="pc")
    atl["key"] += ":acctb"
    N.instant_record(atl, "entry", app_only=True)                 # ATLAS: only the phone app took it (ntfy refused)
    check("i. ATLAS's app-only entry does NOT make the report skip the Olympus copy of LIT's entry 30 s later (before: it did)",
          not R._app_had({"key": f"open:lit:{t + 30}"}) and R._app_had({"key": f"open:atlas:{t}"}))
    t2 = t + 600
    a2 = P.entry_payload("ATLAS 25K", "SHORT", 1, t2, src="pc")
    a2["key"] += ":acctb"
    N.instant_record(a2, "entry")                                 # ATLAS: ntfy took it ("entries")
    N.instant_record(P.entry_payload("Zlarior 50K", "LONG", 4, t2, src="pc"), "entry", app_only=True)   # LIT primary: the app only
    rep = [{"key": f"open:lit:{t2}", "priority": "high"}, {"key": f"open:atlas:{t2}", "priority": "high"}]
    kept = [m["key"] for m in N.apply(rep, t2 + 300, N.merge({"quiet_hours": {"off": True}}))]
    check("i. ATLAS's ntfy alert on the same bar never drops LIT's owed ntfy copy (before: both report copies dropped, LIT's entry "
          "never reached ntfy); ATLAS's own copy is dropped", kept == [f"open:lit:{t2}"] and R._app_had({"key": f"open:lit:{t2}"}), kept)
    t3 = t2 + 600
    N.instant_record(P.outcome_payload("ATLAS 25K", "SHORT", "TARGET", 120.0, t3, t3 + 900, src="pc") | {"key": f"out:{t3}:acctb"}, "exit")
    kept = [m["key"] for m in N.apply([{"key": f"close:lit:{t3}", "priority": "default"}, {"key": f"close:atlas:{t3}", "priority": "default"}],
                                      t3 + 1200, N.merge({"quiet_hours": {"off": True}}))]
    check("i. the same for results: ATLAS's ntfy exit drops only ATLAS's report copy", kept == [f"close:lit:{t3}"], kept)
    p25 = P.entry_payload("Zlarior 25K #2", "LONG", 2, t3, src="pc")
    p25["key"] += ":b25k_2"
    N.instant_record(p25, "entry", app_only=True)
    check("i. the keys' account part: '' = LIT's primary (and the 50K combo), 'acctb' = ATLAS, an extra account's id = itself",
          N.key_acct(p25["key"]) == "b25k_2" and N.key_acct(f"fill:{t3}") == "" and N.key_acct(f"out:{t3}:acctr") == "acctr"
          and N.report_acct({"key": f"open:lit:{t3}"}) == "" and N.report_acct({"key": f"close:atlas:{t3}"}) == "acctb"
          and N.report_acct({"key": "open:blitz:1"}) == "acctc" and N.report_acct({"key": "guard:dd:x"}) is None)
    check("i. acct_match: the report's 'lit' row ('') takes any LIT-family key (the 50K, the 25K #2, the Rapid's LIT lane), never "
          "ATLAS's (acctb, acctr) or BLITZ's (acctc); 'acctb' takes ATLAS's only",
          N.acct_match(f"fill:{t3}", "") and N.acct_match(f"fill:{t3}:b25k_2", "") and N.acct_match(f"out:{t3}:rapid", "")
          and not N.acct_match(f"fill:{t3}:acctb", "") and not N.acct_match(f"fill:{t3}:acctr", "") and not N.acct_match(f"fill:{t3}:acctc", "")
          and N.acct_match(f"fill:{t3}:acctb", "acctb") and not N.acct_match(f"fill:{t3}", "acctb") and N.acct_match(f"fill:{t3}:acctb", None))
    check("i. instant_sent per account: the 25K #2's app-only entry counts for the report's one LIT row (it cannot tell the LIT "
          "accounts apart), never for ATLAS's row; no account = any (the old rule)",
          N.instant_sent(t3, what="app_entries", acct="b25k_2") and N.instant_sent(t3, what="app_entries", acct="")
          and not N.instant_sent(t3, what="app_entries", acct="acctb") and N.instant_sent(t3, what="app_entries"))


def part_i2(b: Box):
    """the 25K #2 trades and the 50K does not (its order refused, its account off, its day stop first, passed / locked): the 25K #2's
    own alerts went out at once. The 15-minute report has ONE LIT row per bar (engine/live_board.trade_log files every PC LIT account
    under "lit", named as the 50K): it must not come back 15 minutes later as a false "Zlarior 50K opened / closed" on both apps
    (skeptic 2026-11-20: with the exact per-account match it did; the old time-only rule did not)."""
    from tools import pc_report as R
    card = {"room": 2000.0, "mll": 2000.0, "today_pnl": 0.0}

    def report(t):
        row = {"acct": "lit", "src": "live", "entry_t": t, "side": "SHORT", "qty": 2, "entry": 21000.0, "stop": 21020.0, "target": 20900.0,
               "exit": "OPEN", "open": True}
        st, m1 = R.events({"seen": {}, "cond": {}, "seeded": True}, {"t": t + 300, "live": {"board": {"lit": card, "trades": [row]}}})
        closed = {**row, "open": False, "exit": "TARGET", "exit_t": t + 1800, "usd": 514.0, "exit_px": 20900.0}
        st, m2 = R.events(st, {"t": t + 2100, "live": {"board": {"lit": card, "trades": [closed]}}})
        return [m["key"] for m in m1 + m2 if m["key"].startswith(("open:", "close:"))]
    t0 = T0 + 30000
    check("i2. control: with no instant alert at all, the report sends the LIT row's entry and its result (one each)",
          report(t0) == [f"open:lit:{t0}", f"close:lit:{t0}"], report(t0))
    t = t0 + 7200
    p = P.entry_payload("Zlarior 25K #2", "SHORT", 2, t, src="pc")
    p["key"] += ":b25k_2"
    N.instant_record(p, "entry")                                  # ntfy took the 25K #2's entry at once
    o = P.outcome_payload("Zlarior 25K #2", "SHORT", "TARGET", 514.0, t, t + 1800, src="pc")
    o["key"] += ":b25k_2"
    N.instant_record(o, "exit")                                   # ... and its result
    kept = report(t)
    check("i2. the 25K #2's entry + result already sent at once, the 50K had no trade: the report sends NO 'Zlarior 50K opened' and "
          "NO 'Zlarior 50K closed +$514' copy (before this fix: both, on both apps, with the 50K's day and room)", kept == [], kept)
    t2 = t + 7200
    p2 = P.entry_payload("Zlarior 25K #2", "LONG", 2, t2, src="pc")
    p2["key"] += ":b25k_2"
    N.instant_record(p2, "entry", app_only=True)                  # only the phone app took it (ntfy refused)
    a2 = P.entry_payload("ATLAS 25K", "LONG", 1, t2 + 3600, src="pc")
    a2["key"] += ":acctb"
    N.instant_record(a2, "entry", app_only=True)
    check("i2. the 25K #2's app-only entry (ntfy refused it): the report's LIT row sends NO copy at all, not even to ntfy (it would be "
          "titled the 50K, with the 50K's day $ and room; round-2 skeptics: it went to ntfy as 'Zlarior 50K SHORT opened'); ATLAS's "
          "app-only entry never counts for a LIT row",
          f"open:lit:{t2}" not in report(t2) and not R._app_had({"key": f"open:lit:{t2}"}) and N.report_copy({"key": f"open:lit:{t2}"}) == "none"
          and N.report_copy({"key": f"open:lit:{t2 + 3600}"}) == "both", report(t2))


def part_i3(b: Box):
    """round-2 skeptics 2026-11-20 (HIGH): the 25K #2 trades and the 50K does not; the Olympus app takes the 25K #2's instant alerts,
    ntfy refuses them at that moment (a 429, a timeout). They were recorded app-only, the report's one LIT row matched them and
    its real run_once posted ITS ntfy copy, written from the 50K's card: 'Zlarior 50K SHORT opened ...' / 'Zlarior 50K closed +$514 |
    day +$0 | room $2,000'. Now the row sends nothing (its Olympus alert already showed, with the 25K #2's own name) and the bot
    tries the 25K #2's own ntfy alert once more (engine/push._pc_send retry_s), so the ntfy copy keeps its real name."""
    from tools import pc_report as R
    app = []
    saved_app, saved_run = P.app_send, P.pc_notify
    P.app_send = phone_accepts(app)
    card = {"room": 2000.0, "mll": 2000.0, "today_pnl": 0.0, "plan": "MFFU Builder 50K"}
    t = T0 + 60000

    def rows(et_):
        op = {"acct": "lit", "src": "live", "entry_t": et_, "side": "SHORT", "qty": 2, "entry": 21000.0, "stop": 21020.0,
              "target": 20900.0, "exit": "OPEN", "open": True}
        return op, {**op, "open": False, "exit": "TARGET", "exit_t": et_ + 1800, "usd": 514.0, "exit_px": 20900.0}

    def trade_25k(et_, acc):
        lg = leg(t=et_, d=-1, q=2, fill=21000.0, stop=21020.0, target=20900.0)
        acc.adapter.clock = lambda: et_ + 3
        acc.adapter._push_fill(lg)
        acc.adapter._push_exit(lg, "TARGET", {"avg": 20900.0, "filled": 2})

    def report_run(et_):
        """the REAL 15-minute run (run_once, real events() on a board with the LIT row: open, then closed) -> (ntfy titles, app keys)"""
        op, cl = rows(et_)
        real = R.events
        st0 = {"seen": {}, "cond": {}, "seeded": True}
        bb, now, cfg, _f = _report_box(b, lambda now: [])
        titles, took = [], []
        try:
            for brd, dt_ in (([op], 300), ([cl], 2100)):
                def ev(state, snap, brd=brd, dt_=dt_):
                    st1, ms = real(st0, {"t": et_ + dt_, "live": {"board": {"lit": card, "trades": brd}}})
                    st0.clear()
                    st0.update(st1)
                    ms = [m for m in ms if m["key"].startswith(("open:", "close:"))]
                    return {"seen": {m["key"]: snap["t"] for m in ms}, "cond": {}, "seeded": True, "guard": {}}, ms
                R.events = ev
                h = BB_http()
                bb.run(h, now, app_push=lambda m: took.append(m["key"]) or True)
                titles += [c["h"].get("Title", "") for c in h.posts(cfg["topic"])]
        finally:
            R.events = real
            bb.cleanup()
        return titles, took

    try:
        r = router()
        acc = Acc("b25k_2", "MFFUEVBLDR000002222")
        acc.adapter = nt_adapter(acc.name, real=False)
        r._wire_push(acc)
        b.ntfy_ok = False
        trade_25k(t, acc)
        check("i3. setup: the 25K #2's entry + result reached the Olympus app with its own name, ntfy refused both (recorded app-only)",
              len(app) == 2 and all(a["title"].startswith("Zlarior 25K #2") for a in app) and not b.take()
              and N.instant_keys(t, what="app_entries", acct="") == [f"fill:{t}:b25k_2"], [a.get("title") for a in app])
        titles, took = report_run(t)
        check("i3. the real 15-minute run: NO ntfy post titled 'Zlarior 50K' and no second Olympus copy (before: 'Zlarior 50K SHORT "
              "opened' and 'Zlarior 50K closed +$514 | day +$0 | room $2,000' on ntfy)",
              not [x for x in titles if x.startswith("Zlarior") and not x.startswith("Zlarior 25K #2")] and not took, (titles, took))
        # control: the 50K's OWN app-only alert still earns the report's ntfy copy (its name is the row's name)
        t2 = t + 7200
        b.ntfy_ok = False
        nt_adapter()._push_fill(leg(t=t2, d=-1, q=2, fill=21000.0, stop=21020.0, target=20900.0))
        b.ntfy_ok = True
        app.clear()
        titles, took = report_run(t2)
        check("i3. control: the 50K's own entry, app-only -> the report sends its ntfy copy (titled the 50K), never the app again",
              len([x for x in titles if x.startswith("Zlarior 50K") and "opened" in x]) == 1 and not [k for k in took if k.startswith("open:")],
              (titles, took))
        # the bot's own retry: the 25K #2's ntfy alert once more, under its real name
        calls = []

        def flaky(base, topic, msg):
            calls.append(msg)
            return len(calls) > 1                                 # refused at once, taken on the retry

        P.pc_notify = lambda payload: P._pc_send(dict(payload), ntfy=lambda p: N.instant_entry(p, cfg=b.cfg, poster=flaky),
                                                 ntfy_exit=lambda p: N.instant_exit(p, cfg=b.cfg, poster=flaky), retry_s=0)
        t3 = t + 14400
        acc.adapter.clock = lambda: t3 + 3
        acc.adapter._push_fill(leg(t=t3, d=-1, q=2, fill=21000.0, stop=21020.0, target=20900.0))
        lines = [json.loads(x) for x in open(os.path.join(b.dir, N.TRADE_LOG_NAME), encoding="utf-8")]
        check("i3. the 25K #2's ntfy alert refused at once: tried once more by the bot, under its own name ('Zlarior 25K #2: SHORT "
              "2 MNQ'), recorded as sent, the report skips the row; the log keeps both answers",
              len(calls) == 2 and calls[1]["title"].startswith("Zlarior 25K #2: SHORT 2 MNQ") and N.instant_keys(t3) == [f"fill:{t3}:b25k_2"]
              and N.report_copy({"key": f"open:lit:{t3}"}) == "none" and lines[-1]["ntfy"] == "sent"
              and str(lines[-1].get("ntfy_first")).startswith("ntfy did not"), ([c["title"] for c in calls], lines[-1]))
        calls.clear()
        t4 = t + 21600
        nt_adapter()._push_fill(leg(t=t4, d=-1, q=2, fill=21000.0, stop=21020.0, target=20900.0))
        check("i3. the 50K's (and ATLAS's) refused ntfy alert is NOT retried by the bot: the report sends that copy under the right name",
              len(calls) == 1 and N.report_copy({"key": f"open:lit:{t4}"}) == "ntfy", len(calls))
        check("i3. a retry never re-sends what ntfy already took, and never runs for 'no topic' / 'off'",
              N.instant_entry(dict(P.entry_payload("Zlarior 25K #2", "SHORT", 2, t3, src="pc"), key=f"fill:{t3}:b25k_2", retry=True),
                              cfg=b.cfg, poster=flaky) == "already sent"
              and not P._retry_owed({"key": f"fill:{t3}:b25k_2"}, P.NO_TOPIC + " on this PC")
              and not P._retry_owed({"key": f"fill:{t3}:b25k_2"}, "trade_opened is off")
              and P._retry_owed({"key": f"out:{t3}:acctr"}, "failed: URLError") and not P._retry_owed({"key": f"out:{t3}:acctb"}, "failed: URLError"))
    finally:
        P.app_send, P.pc_notify = saved_app, saved_run
        b.ntfy_ok = True


def BB_http():
    from tests import test_bots_back as BB
    return BB.FakeHTTP()


# ------------------------------------------------------------------------------------------------ j. important alerts on both routes
IMPORTANT_MSGS = [
    {"key": "cond:bot_down:{now}", "title": "Bot down", "body": "The bot stopped reporting.", "priority": "high", "tags": "warning"},
    {"key": "life:atlas:failed:{now}", "title": "ATLAS 25K FAILED", "body": "Stood down.", "priority": "high", "tags": "rotating_light"},
    {"key": "guard:dd:lit:x:75", "title": "Zlarior 50K room low", "body": "75% of the room used.", "priority": "high"},
    {"key": "pc_silent:{now}", "title": "PC silent", "body": "No report for 20 min.", "priority": "high"},
    {"key": "guard:day:{now}", "title": "Day summary", "body": "Zlarior 50K +$0 today.", "priority": "default"},
    {"key": "back:bot_down:{now}", "title": "Back to normal", "body": "The bot reports again.", "priority": "default"},
]


class RefuseAlerts:
    """FakeHTTP that refuses every post to the private alert topic (a 429: ntfy's day cap), everything else as test_bots_back's."""

    def __init__(self, topic):
        from tests import test_bots_back as BB
        self.inner, self.topic = BB.FakeHTTP(), topic

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        if method == "POST" and url.endswith("/" + self.topic):
            self.inner.calls.append({"m": method, "url": url, "h": dict(headers or {})})
            return 429, "daily quota reached"
        return self.inner(method, url, body, headers, timeout)


def _report_box(b: Box, msgs_of):
    """test_bots_back's temp bot folder + a run_once whose alerts are msgs_of(now) (R.events stubbed; the rest is the real run)."""
    from tests import test_bots_back as BB
    from tools import pc_report as R
    bb = BB.Box()
    now = BB.weekday_10am_et()
    bb.hb(BB.hb_payload(now - 120))
    bb.topic()
    cfg = R.load_cfg(bb.env)

    def fake_events(state, snap):
        ms = [dict(m) for m in msgs_of(snap["t"])]
        st = {"seen": {**dict((state or {}).get("seen") or {}), **{m["key"]: snap["t"] for m in ms}}, "cond": {}, "seeded": True,
              "guard": {"sent": {m["key"]: snap["t"] for m in ms if m["key"].startswith("guard:")}}}
        return st, ms
    return bb, now, cfg, fake_events


def part_j(b: Box):
    """the important alerts (PASSED / FAILED / LOCKED, problems, room low, PC silent) go to Olympus AND ntfy, like trades (skeptics
    2026-11-20: they still went Olympus-first, ntfy skipped whenever Apple said 'accepted')"""
    from tests import test_bots_back as BB
    from tools import pc_report as R
    real = R.events
    msgs_of = lambda now: [{**m, "key": m["key"].format(now=now)} for m in IMPORTANT_MSGS]   # noqa: E731
    bb, now, cfg, fake = _report_box(b, msgs_of)
    R.events = fake
    try:
        took = []
        h = BB.FakeHTTP()
        rec = bb.run(h, now, app_push=lambda m: took.append(m["key"]) or True)
        titles = sorted(c["h"].get("Title") for c in h.posts(cfg["topic"]))
        check("j. a phone that accepts: bot down, FAILED and room low reach the phone app AND the private ntfy topic (before: Olympus "
              "only; a 'pc_silent:' key too, though the report makes none: PC silent comes from the cloud, on ntfy); the day summary "
              "and 'Back to normal' stay Olympus-first (no second sound for an all-clear at night)",
              len(took) == 6 and titles == sorted(["Bot down", "ATLAS 25K FAILED", "Zlarior 50K room low", "PC silent"]) and rec["sent"] == 10,
              (took, titles, rec.get("sent")))
        bars = R.read_json(os.path.join(bb.work, R.BARS_STATE), {}) or {}
        day = _d(_d(bars.get("days")).get(R._utc_day(now)))
        check("j. the ntfy day count (the chart's share of the 250) counts the 4 ntfy alert posts, not the 6 Olympus pushes",
              int(day.get("all") or 0) == len(h.posts()) , (day, len(h.posts())))
        ref = RefuseAlerts(cfg["topic"])
        bb.run(ref, now + 900, app_push=lambda m: True)
        st = R.read_json(os.path.join(bb.work, "state.json"), {})
        check("j. ntfy refuses (its day cap) but the phone app took them: no retry next run (never to the app twice)",
              "guard:dd:lit:x:75" in _d(_d(st.get("guard")).get("sent")) and len(ref.inner.posts(cfg["topic"])) == 4, st.get("guard"))
        bb.run(RefuseAlerts(cfg["topic"]), now + 1800, app_push=lambda m: False)
        st = R.read_json(os.path.join(bb.work, "state.json"), {})
        check("j. neither route took it: the guard alert is forgotten so the next run tries again (as before)",
              "guard:dd:lit:x:75" not in _d(_d(st.get("guard")).get("sent")), st.get("guard"))
        # an app-had trade result: its ntfy copy is retried for 2 hours, not hours later after ntfy's reset
        old_t, new_t = now - 5 * 3600, now - 1800
        for et_ in (old_t, new_t):
            N.instant_record(P.outcome_payload("Zlarior 50K", "LONG", "TARGET", 100.0, et_, et_ + 600, src="pc"), "exit", app_only=True)
        trades = [{"key": f"close:lit:{old_t}", "title": "Zlarior 50K closed +$100 (old)", "body": "x", "priority": "default", "ev_t": old_t + 600},
                  {"key": f"close:lit:{new_t}", "title": "Zlarior 50K closed +$100 (new)", "body": "x", "priority": "default", "ev_t": new_t + 600}]
        R.events = lambda state, snap: ({"seen": {m["key"]: snap["t"] for m in trades}, "cond": {}, "seeded": True, "guard": {}}, [dict(m) for m in trades])
        app = []
        ref = RefuseAlerts(cfg["topic"])
        bb.run(ref, now + 2700, app_push=lambda m: app.append(m["key"]) or True)
        st = R.read_json(os.path.join(bb.work, "state.json"), {})
        check("j. an app-had trade result (the app got it at once): ntfy only, never the app again; ntfy refuses: retried while the "
              "close is under 2 hours old, not after (skeptic: a late copy landed hours later, after ntfy's reset)",
              not app and len(ref.inner.posts(cfg["topic"])) == 2 and f"close:lit:{old_t}" in st["seen"] and f"close:lit:{new_t}" not in st["seen"],
              (app, st.get("seen")))
    finally:
        R.events = real
        bb.cleanup()


def _d(x):
    return x if isinstance(x, dict) else {}


# ------------------------------------------------------------------------------------------------ k. trade_routes
def part_k(b: Box):
    """notify_settings.json trade_routes: both (default) | olympus | ntfy; a single-route choice keeps the other as the fallback"""
    from tests import test_bots_back as BB
    from tools import pc_report as R
    check("k. trade_routes: default 'both', 'olympus' / 'ntfy' kept, anything else = 'both'",
          N.trade_routes(N.merge({})) == "both" and N.trade_routes(N.merge({"trade_routes": "Olympus"})) == "olympus"
          and N.trade_routes(N.merge({"trade_routes": "ntfy"})) == "ntfy" and N.trade_routes(N.merge({"trade_routes": "sms"})) == "both"
          and json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8")).get("trade_routes") == "both")
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    try:
        b.set_settings({"quiet_hours": {"off": True}, "trade_routes": "olympus"})
        ad = nt_adapter()
        t = T0 + 20000
        ad._push_fill(leg(t=t))
        posts = b.take()
        kept = N.apply([{"key": f"open:lit:{t}", "priority": "high"}], t + 300, N.merge({"quiet_hours": {"off": True}}))
        check("k. 'olympus': the phone app took it, so no ntfy post and the report skips its copies (the old one-route rule)",
              len(app) == 1 and not posts and not kept, (app, posts, kept))
        b.set_settings({"quiet_hours": {"off": True}, "trade_routes": "ntfy"})
        ad._push_fill(leg(t=t + 600))
        check("k. 'ntfy': ntfy took it, so the phone app is not used", len(app) == 1 and len(b.take()) == 1, app)
        b.ntfy_ok = False
        ad._push_fill(leg(t=t + 1200))
        kept = N.apply([{"key": f"open:lit:{t + 1200}", "priority": "high"}], t + 1500, N.merge({"quiet_hours": {"off": True}}))
        check("k. 'ntfy' and ntfy refuses: the phone app is the fallback, the report still owes only its ntfy copy",
              len(app) == 2 and not b.take() and len(kept) == 1 and R._app_had(kept[0]), (app, kept))
        b.ntfy_ok = True
    finally:
        P.app_send = saved
    real = R.events
    msgs_of = lambda now: [{**IMPORTANT_MSGS[0], "key": f"cond:bot_down:{now}"}]   # noqa: E731
    bb, now, cfg, fake = _report_box(b, msgs_of)
    R.events = fake
    try:
        took = []
        b.set_settings({"quiet_hours": {"off": True}, "trade_routes": "olympus"})
        h = BB.FakeHTTP()
        bb.run(h, now, app_push=lambda m: took.append(1) or True)
        check("k. report, 'olympus': a phone took 'Bot down', no ntfy copy", len(took) == 1 and not h.posts(cfg["topic"]))
        b.set_settings({"quiet_hours": {"off": True}, "trade_routes": "ntfy"})
        h = BB.FakeHTTP()
        bb.run(h, now + 900, app_push=lambda m: took.append(1) or True)
        check("k. report, 'ntfy': ntfy took 'Bot down', the phone app not used", len(took) == 1 and len(h.posts(cfg["topic"])) == 1)
        ref = RefuseAlerts(cfg["topic"])
        bb.run(ref, now + 1800, app_push=lambda m: took.append(1) or True)
        check("k. report, 'ntfy' refused: the phone app is the fallback", len(took) == 2 and len(ref.inner.posts(cfg["topic"])) == 1)
    finally:
        R.events = real
        bb.cleanup()


# ------------------------------------------------------------------------------------------------ l. Send test's limits
def part_l(b: Box):
    """/api/push/test (engine/alert_check.send_test): one test a minute; the ntfy half waits when the day's ntfy room is down to the
    trade alerts' reserve (skeptics 2026-11-20: no limit, each tap spent 2 of the posts the trade alerts need)"""
    from engine import alert_check as AC
    from tools import pc_report as R
    app = []
    saved = P.app_send
    P.app_send = phone_accepts(app)
    posts = []
    poster = lambda base, topic, msg: posts.append(msg) or True   # noqa: E731
    work = os.path.join(b.dir, "pc_report")
    os.makedirs(work, exist_ok=True)
    try:
        t = T0 + 30000
        AC._TEST["t"] = None
        r1 = AC.send_test(now=t, poster=poster, ntfy_cfg=b.cfg, http=no_quota, work=work)
        r2 = AC.send_test(now=t + 10, poster=poster, ntfy_cfg=b.cfg, http=no_quota, work=work)
        check("l. a second test within 60 s sends nothing (no Olympus push, no ntfy post) and says when to try again",
              r1["ntfy"] == "sent" and len(posts) == 2 and len(app) == 2 and r2.get("cooldown") == 51 and "try again in 51 s" in r2["say"],
              (r1.get("ntfy"), r2))
        r3 = AC.send_test(now=t + 61, poster=poster, ntfy_cfg=b.cfg, http=no_quota, work=work)
        check("l. after a minute it works again", r3["ntfy"] == "sent" and len(posts) == 4 and not r3.get("cooldown"), r3)
        n_today = N.ntfy_today(t + 200)
        R.write_json(os.path.join(work, R.BARS_STATE), {"days": {R._utc_day(t + 200): {"all": R.NTFY_DAY_CAP - R.TRADE_ALERT_RESERVE - n_today - 1}}})
        r4 = AC.send_test(now=t + 200, poster=poster, ntfy_cfg=b.cfg, http=no_quota, work=work)
        check("l. 1 post left before the trade alerts' reserve (this PC's count): the ntfy half is skipped, Olympus still tested",
              len(posts) == 4 and str(r4["ntfy"]).startswith("skipped: ") and "kept for trade alerts" in r4["ntfy"] and r4["app"].get("sent") == 1,
              r4)
        R.write_json(os.path.join(work, R.BARS_STATE), {"days": {}})
        quota = lambda m, url, body=None, headers=None, timeout=15: (200, json.dumps({"limits": {"messages": 250}, "stats": {"messages": 237, "messages_remaining": 13}})) if url.endswith("/v1/account") else (0, "")   # noqa: E731
        r5 = AC.send_test(now=t + 300, poster=poster, ntfy_cfg=b.cfg, http=quota, work=work)
        check("l. ntfy's own count says 13 left (every program on the PC): 13 - 2 < 12 kept for trade alerts, the ntfy half skipped",
              len(posts) == 4 and "ntfy says 13 posts left" in str(r5["ntfy"]), r5)
        check("l. the PC dashboard's toast line says what each route answered",
              r1["say"] == "Olympus: accepted for 1 phone(s), look at the iPhone · ntfy: TEST entry + close sent"
              and r5["say"].startswith("Olympus: accepted for 1 phone(s)") and "ntfy: skipped: ntfy says 13" in r5["say"], (r1["say"], r5["say"]))
        js = open(os.path.join(ROOT, "web", "js", "page-settings.js"), encoding="utf-8").read()
        srv = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
        check("l. the toast shows the reply's 'say' (both routes), not 'Test sent to 0 phone(s)'; the server answers 429 in the cooldown",
              "r.say ||" in js and "Test sent to ${r.sent} phone(s)" not in js and '"cooldown": r["cooldown"]}, 429)' in srv and '"say": r.get("say")' in srv)
    finally:
        P.app_send = saved
        AC._TEST["t"] = None


# ------------------------------------------------------------------------------------------------ m. older notice bug
def part_m(b: Box):
    """engine/autoupdate.notify(sync=True) called push._pc_send(p, True): with LE_PUSH_EXTRA=1, True became the sender and every
    phone got a TypeError (by default engine/push.pc_app_ok drops kind 'pc' before any sender is used)"""
    from engine import alerts as AL
    from engine import autoupdate as AU
    calls = []
    saved, saved_send = P._pc_send, AL.send
    P._pc_send = lambda p, *a, **k: calls.append((p.get("kind"), a, k)) or {}
    AL.send = lambda *a, **k: {}
    try:
        AU.notify("Bot update FAILED", "test", key=f"auto:update:test:{T0}", sync=True)
    finally:
        P._pc_send, AL.send = saved, saved_send
    check("m. the sync update notice uses the real sender (no stray True as the sender)", calls == [("pc", (), {})], calls)


QUIET_CARD = {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "status": "open", "balance": 49193.0,
              "floor": 47193.0, "room": 2000.0, "mll": 2000.0, "today_pnl": 0.0, "dll": 1000.0, "dll_used": 0.0, "trades_today": 0,
              "quiet_days": 6, "eval_start": "2026-11-02", "to_target": 3807.0, "position": None}


def part_n(b: Box):
    """MFFU's 7-day rule (owner 2026-11-20: "if a account hasn't traded in 7 days it needs a very small trade to reset counter?"):
    tools/pc_guard's "no trade for N days" alert (key guard:quiet:<acct>:<day>) was kind "other", OFF in the shipped
    notify_settings.json, so notify.apply dropped it before either route. Now account_status (on, both apps). The real events() +
    apply() with the shipped settings, then run_once's real routes, a phone that accepts."""
    from tests import test_bots_back as BB
    from tools import pc_report as R
    shipped = json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8"))
    b.set_settings(shipped)
    check("n. guard:quiet: is account_status (was 'other', OFF), on in the shipped settings",
          N.kind_of("guard:quiet:lit:2026-11-20") == "account_status" and N.on("account_status", N.merge(shipped))
          and not N.on("other", N.merge(shipped)))
    real = R.events
    bb, now, cfg, _fake = _report_box(b, lambda now: [])

    def with_quiet_lit(state, snap):
        lv = dict(snap.get("live") or {})
        bd = {**dict(lv.get("board") or {}), "lit": {**dict(_d(lv.get("board")).get("lit") or {}), **QUIET_CARD}}
        return real({**dict(state or {}), "seeded": True}, {**snap, "mode": "LIVE", "hb_age": 60, "live": {**lv, "board": bd}})
    R.events = with_quiet_lit
    try:
        took = []
        h = BB.FakeHTTP()
        bb.run(h, now, app_push=lambda m: took.append(dict(m)) or True)
        app_q = [m for m in took if str(m.get("key") or "").startswith("guard:quiet:lit:")]
        nt_q = [c for c in h.posts(cfg["topic"]) if "no trade for 6 days" in str(c["h"].get("Title"))]
        check("n. a live 50K eval 6 days without a trade, 10:00 ET: 'Zlarior 50K: no trade for 6 days' reaches the phone app AND the "
              "ntfy app, high priority, with MFFU's 7-day rule and the by-hand fix in it (before: dropped, no phone got it)",
              len(app_q) == 1 and len(nt_q) == 1 and app_q[0].get("priority") == "high"
              and "MFFU can close an eval after 7 days" in app_q[0].get("body", "") and "by hand" in app_q[0].get("body", ""),
              ([m.get("key") for m in took], [c["h"].get("Title") for c in h.posts(cfg["topic"])]))
    finally:
        R.events = real
        bb.cleanup()


def part_o(b: Box):
    """nights: an all-clear never doubles; the self-check and the settings file never tell the owner to edit a tracked file on the PC
    (engine/autoupdate skips every update after a local edit: 'local changes in tracked files')"""
    from engine import alert_check as AC
    check("o. 'Back to normal' / 'PC back' stay Olympus first; the problem itself goes to both apps (a FEED STALE flap at night: 3 "
          "sounds, not 4)", not N.dual("problems", "back:feed_stale:1") and not N.dual("pc_silent", "pc_back:1")
          and N.dual("problems", "cond:feed_stale:1") and N.dual("account_status", "life:x") and not N.dual("daily_summary", "guard:day:x"))
    shipped = json.load(open(os.path.join(ROOT, "notify_settings.json"), encoding="utf-8"))
    b.set_settings(shipped)
    r = AC.routes(ntfy_cfg={"ntfy": "https://ntfy.sh", "topic": "nq-test-topic-0000"})
    w = " ".join(r["warn"])
    check("o. the self-check's night line says 'tell Claude', never 'add ... to ring_in_quiet_hours in notify_settings.json'",
          "tell Claude" in w and "ring_in_quiet_hours" not in w and "Do not edit the settings file on the PC" in w, r["warn"])
    hp = shipped.get("_help", "")
    check("o. notify_settings.json's help: ringing at night is the owner's yes / no and Claude changes the file (no hand edit on the PC); "
          "PC silent named as the cloud's, on ntfy", "add trade_opened / trade_closed to ring_in_quiet_hours" not in hp
          and "never a hand edit on the PC" in hp and "PC silent comes from the cloud, on ntfy" in hp, hp[-600:])


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_g, part_h, part_h2, part_h2b, part_h3, part_h4, part_i, part_i2, part_i3, part_j, part_k,
              part_l, part_m, part_n, part_o):
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
