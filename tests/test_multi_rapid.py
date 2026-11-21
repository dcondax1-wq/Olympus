"""Two MFFU Rapid EOD accounts at once (day-multirapid 2026-11-20: the 5th slot = a Rapid EOD 50K next to today's 25K).

    python -X utf8 -m tests.test_multi_rapid          # ~15 s

Paper bots, temp files, Sim / made-up names only: nothing routed to a real NinjaTrader, nothing real armed.
  a. today's Rapid (slot 1, data/rapid.json) is byte-for-byte today's: lane entry, ATLAS block, state file, order tag, alert
     key and file path equal the frozen baseline from the code before this change (tests/fixtures/rapid_slot1_baseline.json)
  b. two Rapids in one bot (25K slot 1 + 50K slot 2): both LIT lanes (ids rapid / rapid2) and both ATLAS lanes start, each with
     its own preset (25K: $500 day, 20 micros; 50K: $1,000 day, 30 micros), state file, NinjaTrader order tag and alert key
  c. no cross-talk: each lane's "same account" partner is its own ATLAS; a loss on one Rapid never shrinks the other's size
     or day; ATLAS on one Rapid never blocks LIT on the other (different accounts) but the main LIT still waits for an
     opposite ATLAS position on either Rapid (no hedge across the PC's accounts)
  d. alerts + reports: LIT lane names "Rapid EOD 25K" / "Rapid EOD 50K", distinct ATLAS alert keys ending ":acctr"
     (labelled "(ATLAS)"); heartbeat acct block + live.json Accounts sections list both; the PC report names them "Rapid 25K"
     / "Rapid 50K"; the trades feed keys rapid25 / rapid2; lifecycle keys rapid / rapid2 (one passing never stands the
     other down); START BOT's launch checklist has a line per Rapid
  e. restart mid-day: a close booked on each Rapid comes back on the same Rapid after a new bot start (nothing mixed)
  f. the 1st Rapid's file is never rewritten by a bot start; an old bot (one Rapid) reads data/rapid.json the same and never
     sees data/rapid2.json (rollback = delete nothing)
  g. adding: a 2nd Rapid = slot 2, DISARMED; only the typed phrase (START BOT / the add box's Start) arms it; a 3rd is refused;
     the same Name never takes both slots
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import multi_account as MA, rapid  # noqa: E402
from engine.live import LiveBot  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests.test_rapid import Clock, DAY, T0  # noqa: E402

RESULTS = []
P25, P50 = "mffu_rapid_eod_25k", "mffu_rapid_eod_50k"
N1, N2 = "Sim205", "Sim206"


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:500]}"))


def make_bot(tmp, clock, b1, b2):
    os.makedirs(tmp, exist_ok=True)
    MA.ADAPTER_FACTORY = None
    b = LiveBot()
    b.clock = clock
    b.state_path = os.path.join(tmp, "live_state.json")
    cfg = {"sym": "NQ", "tf": "5m", "adapter": "paper", "model": "lit", "params": {"max_micros": 40, "flat_mod": 955},
           "accounts_parallel": False, "account_b": None, "account_c": None, "fleet": None, "rapid": b1, "rapid2": b2}
    r = b.start(cfg, spawn=False)
    assert r.get("ok"), r
    ls = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8")).get("lit_sizing") or {}
    b._lit_sizing = {**ls, "mode": "normal"}
    return b


def lanes(b):
    L = {a.id: a for a in b.accts.accounts if a.spec.get("lane") == "rapid"} if b.accts is not None else {}
    return L.get("rapid"), L.get("rapid2")


def part_a():
    base = json.load(open(os.path.join(ROOT, "tests", "fixtures", "rapid_slot1_baseline.json"), encoding="utf-8"))
    blk = {"v": 1, "account": "Sim205", "plan": P25, "stage": "eval", "eval_start": "2026-11-20", "armed": True, "payouts": {},
           "set": "2026-11-20"}
    fb = dict(blk, stage="funded", funded_start="2026-12-20", payouts={"2027-01-05": 600.0})
    now = {"lane_eval": rapid.lane_spec(blk, {"adapter": "ninjatrader", "confirm": "X"}), "lane_funded": rapid.lane_spec(fb, {}),
           "atlas_eval": rapid.atlas_block(blk), "atlas_funded": rapid.atlas_block(fb),
           "state_path": rapid._state_path("/x/data/live_state.json"), "push_suffix": rapid.RapidAtlas.PUSH_SUFFIX,
           "default_path": os.path.relpath(rapid.path(), rapid.ROOT)}
    now = json.loads(json.dumps(now, sort_keys=True))
    for k in base:
        check(f"a. slot 1 unchanged vs the code before this change: {k}", now.get(k) == base[k], (now.get(k), base[k]))
    check("a. slot 2 lives in data/rapid2.json, ids rapid2 / acctr2", os.path.relpath(rapid.slot_path("rapid2"), rapid.ROOT)
          .replace("\\", "/") == "data/rapid2.json" and rapid.lane_spec(blk, {}, slot="rapid2")["id"] == "rapid2"
          and rapid._state_path("/x/data/live_state.json", "rapid2").endswith("live_state_acctr2.json"))


def part_b_to_e(tmp):
    b1 = {"account": N1, "eval_start": DAY, "armed": False, "plan": P25}
    b2 = {"account": N2, "eval_start": DAY, "armed": False, "plan": P50}
    clock = Clock(T0)
    bd = os.path.join(tmp, "bot")
    b = make_bot(bd, clock, b1, b2)
    l1, l2 = lanes(b)
    a1, a2 = b.acct_r, b.acct_r2
    check("b. both LIT lanes start (ids rapid / rapid2) on their own accounts", l1 is not None and l2 is not None
          and l1.spec["nt_account"] == N1 and l2.spec["nt_account"] == N2, [(a.id, a.spec.get("nt_account")) for a in b.accts.accounts])
    check("b. both ATLAS lanes start on their own accounts", a1 is not None and a2 is not None and a1.name == N1 and a2.name == N2,
          (a1 and a1.name, a2 and a2.name))
    if not (l1 and l2 and a1 and a2):
        return
    check("b. presets: 25K = $500 day / 20 micros / $1,500; 50K = $1,000 day / 30 micros / $3,000",
          (l1.rules["dll"], l1.rules["max_micros"], l1.rules["target"], l2.rules["dll"], l2.rules["max_micros"], l2.rules["target"])
          == (500.0, 20, 1500.0, 1000.0, 30, 3000.0), (l1.rules, l2.rules))
    check("b. ATLAS sizes: $250 cap on the 25K, $500 on the 50K", (a1.P["atlas_usd"], a2.P["atlas_usd"]) == (250.0, 500.0))
    c1, c2 = a1.adapter_cfg(), a2.adapter_cfg()
    check("b. own state files, order tags, alert keys", a1.state_path != a2.state_path and a2.state_path.endswith("_acctr2.json")
          and a1.state_path.endswith("_acctr.json") and c1["nt_file_tag"] == "acctr_" and c2["nt_file_tag"] == "acctr2_"
          and c1["nt_state_path"] != c2["nt_state_path"] and a1.PUSH_SUFFIX == ":acctr" and a2.PUSH_SUFFIX == ":r2:acctr",
          (a1.state_path, a2.state_path, c1, c2))
    check("b. not armed (the blocks say armed false)", not l1.spec.get("armed") and not l2.spec.get("armed")
          and not a1.spec.get("armed") and not a2.spec.get("armed"))

    # c. no cross-talk
    check("c. each lane's same-account partner is its own ATLAS; each ATLAS's lane is its own",
          l1.shared() is a1 and l2.shared() is a2 and a1.lane() is l1 and a2.lane() is l2)
    l1.closes.append([DAY, T0 + 60, -400.0, T0])
    check("c. a -$400 day on the 25K: the 25K's ATLAS sees it, the 50K's day stays $0",
          a1.day_pnl(DAY) == -400.0 and a2.day_pnl(DAY) == 0.0 and l2.day_pnl(DAY) == 0.0, (a1.day_pnl(DAY), a2.day_pnl(DAY)))
    s1, s2 = a1._state_raw(T0 + 120), a2._state_raw(T0 + 120)
    tr = {"risk_pts": 10.0, "tgt_pts": 20.0}
    z1, z2 = a1.size(tr, s1), a2.size(tr, s2)
    q50, _, _ = rapid.stack_qty(10.0, s2["room"], 0.0, 30, 1000.0, 500.0)
    q25, _, _ = rapid.stack_qty(10.0, s1["room"], -400.0, 20, 500.0, 250.0)
    check("c. sizes: the 50K's ATLAS is sized on its own $0 day (no cut from the 25K's loss), the 25K's on its -$400",
          z2["qty"] == min(q50, z2["qty"]) and q50 > 0 and z1["qty"] <= q25 and z1["qty"] < z2["qty"], (z1, z2, q25, q50))
    from engine.multi_account import Account  # noqa: F401
    a2.open_t = T0
    a2.prov[T0] = {"dir": 1, "key": "x", "short": "EMA"}
    check("c. ATLAS LONG on the 50K: the 25K's LIT lane is not held by it (another account)", l1._shared_holds() is None,
          l1._shared_holds())
    check("c. ...but the 50K's own LIT lane is (one position per account)", bool(l2._shared_holds()), l2._shared_holds())
    try:
        h = b.accts.others_opposite(-1, l1)
    except Exception as e:  # noqa: BLE001
        h = f"error {e}"
    check("c. no hedge across accounts: a SHORT on the 25K is refused while the 50K's ATLAS is LONG", bool(h) and "Rapid" in str(h), h)
    a2.open_t = None
    a2.prov.pop(T0, None)
    calls = []
    for ar in (a1, a2):                                  # both Rapids' ATLAS LONG, Zlarior's LIT goes SHORT on its own account
        ar.yield_to_lit = (lambda d, sym, now, px=None, any_side=False, ar=ar: calls.append((ar.slot, d)) or False)
    ok = b._hedge_clear({"dir": -1, "entry_t": T0 + 600, "entry": 25000.0}, "NQ", T0 + 600)
    check("c. LIT SHORT while both Rapids' ATLAS are LONG: both asked to close in the same poll, LIT waits",
          ok is False and calls == [("rapid", -1), ("rapid2", -1)], (ok, calls))
    del a1.yield_to_lit, a2.yield_to_lit
    b._hedge_wait.clear()

    # d. alerts + reports
    check("d. LIT lane alert names: Rapid EOD 25K / Rapid EOD 50K", (l1.name, l2.name) == ("Rapid EOD 25K", "Rapid EOD 50K"),
          (l1.name, l2.name))
    from engine import notify, push
    k1 = push.entry_payload(a1.label, "LONG", 2, T0)["key"] + a1.PUSH_SUFFIX
    k2 = push.entry_payload(a2.label, "LONG", 2, T0)["key"] + a2.PUSH_SUFFIX
    n1 = notify.display_name({"account": "Rapid EOD 25K", "key": k1})
    n2 = notify.display_name({"account": "Rapid EOD 50K", "key": k2})
    check("d. ATLAS alerts on the same bar: different keys, both labelled (ATLAS)", k1 != k2 and "(ATLAS)" in n1 and "(ATLAS)" in n2,
          (k1, k2, n1, n2))
    from engine import accounts
    clock.t = T0 + 600
    act = accounts.pc_activity(b, now=clock.t, journal_path=os.path.join(tmp, "none.jsonl"))
    ids = [s.get("id") for s in act.get("accounts") or []]
    check("d. heartbeat acct block: both Rapids, no phrase, no temp path", "rapid" in ids and "rapid2" in ids
          and LIVE_PHRASE not in json.dumps(act) and tmp not in json.dumps(act), ids)
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    secs = accounts.build_accounts({"last_run": clock.t, "pc": {"present": True, "t": clock.t - 60, "acct": act}, "ledger": {}}, lm,
                                   now=clock.t)
    sec = {s.get("id"): s for s in secs}
    st = lambda x: float(((x or {}).get("eval") or {}).get("start_balance") or ((x or {}).get("plan_rules") or {}).get("start") or 0)  # noqa: E731
    check("d. live.json Accounts: a section per Rapid on its own start ($25,000 / $50,000)",
          st(sec.get("rapid")) == 25000.0 and st(sec.get("rapid2")) == 50000.0, {k: st(v) for k, v in sec.items()})
    from tools import pc_report as PR, live_trades as LT
    live = {"accounts": [{**s, "kind": s.get("kind") or "eval", "source": s.get("source") or "pc"} for s in secs
                         if s.get("id") in ("rapid", "rapid2")]}
    labels = {r[0]: r[1] for r in PR._chart_accounts(live)}
    check("d. PC report: Rapid 25K / Rapid 50K, never an id", labels.get("rapid25") == "Rapid 25K" and labels.get("rapid2") == "Rapid 50K",
          labels)
    check("d. trades feed keys: rapid/acctr -> rapid25, rapid2/acctr2 -> rapid2",
          [LT.acct_key(x) for x in ("rapid", "acctr", "rapid2", "acctr2", "rapid_25k")] == ["rapid25", "rapid25", "rapid2", "rapid2", "rapid25"])
    from engine import lifecycle as LC
    check("d. lifecycle keys rapid / rapid2 (one passing never stands the other down), labels by size",
          (LC.key_of(l1), LC.key_of(a1), LC.key_of(l2), LC.key_of(a2)) == ("rapid", "rapid", "rapid2", "rapid2")
          and LC.label_of("rapid2", a2) == "Rapid EOD 50K (#2)" and LC.label_of("rapid", a1) == "Rapid EOD 25K")
    from engine import launch_check as LCK
    rp1 = rapid.PATH
    try:
        rapid.PATH = os.path.join(tmp, "files", "rapid.json")
        rapid.save(b1)
        rapid.save(b2, rapid.slot_path("rapid2"))
        f1, f2 = LCK.rapid_fact(b), LCK.rapid_fact(b, slot="rapid2")
    finally:
        rapid.PATH = rp1
    items = {x["key"]: x for x in LCK.checklist({"rapid": f1, "rapid2": f2}, None, True, T0)["items"] if x["key"] in ("rapid", "rapid2")}
    check("d. START BOT checklist: one line per Rapid (both lanes found, not armed yet)", set(items) == {"rapid", "rapid2"}
          and f1["lit"] and f1["atlas"] and f2["lit"] and f2["atlas"] and "#2" in items["rapid2"]["label"], (f1, f2, items))

    # e. restart mid-day
    a2.closes.append([DAY, T0 + 300, 120.0, T0 + 100])
    l2.closes.append([DAY, T0 + 400, -80.0, T0 + 200])
    a2.save()
    b.accts.save()
    a1.save()
    b.stop()
    clock2 = Clock(T0 + 900)
    bb = make_bot(bd, clock2, b1, b2)
    m1, m2 = lanes(bb)
    check("e. restart: each Rapid gets back its own closes (25K -$400; 50K +$120 ATLAS, -$80 LIT), nothing mixed",
          m1 is not None and m2 is not None and bb.acct_r is not None and bb.acct_r2 is not None
          and bb.acct_r.day_pnl(DAY) == -400.0 and bb.acct_r2.day_pnl(DAY) == 40.0,
          (bb.acct_r and bb.acct_r.day_pnl(DAY), bb.acct_r2 and bb.acct_r2.day_pnl(DAY)))
    bb.stop()
    # one Rapid only (rapid2 off): the bot is today's
    b3 = make_bot(os.path.join(tmp, "bot3"), Clock(T0), b1, None)
    n1, n2 = lanes(b3)
    check("e. no 2nd Rapid: one lane + one ATLAS, acct_r2 None (today's bot)", n1 is not None and n2 is None and b3.acct_r is not None
          and b3.acct_r2 is None and [a.id for a in b3.accts.accounts] == ["rapid"], [a.id for a in b3.accts.accounts])
    b3.stop()
    b4 = make_bot(os.path.join(tmp, "bot4"), Clock(T0), b1, dict(b2, account=N1))
    check("e. the same Name in both slots: the 2nd is not started", lanes(b4)[1] is None and b4.acct_r2 is None)
    b4.stop()


def part_f_g(tmp):
    from tests import test_accounts_cli as TC
    from engine import account_cli as AC, go as G
    keep = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH", "bot_running")}
    keep_r = rapid.PATH
    w = os.path.join(tmp, "world")
    try:
        TC.setup(w) if hasattr(TC, "setup") else None
        rapid.PATH = os.path.join(w, "rapid.json")
        G.CFG = os.path.join(w, "go.json")
        G.SECOND_PATH = os.path.join(w, "account_b.json")
        G.ALLOW_PATH = os.path.join(w, "allow.json")
        G.ACCOUNTS_PATH = os.path.join(w, "accounts.json")
        G.ANCHOR_PATH = os.path.join(w, "anchor.json")
        G.bot_running = lambda: False
        os.makedirs(w, exist_ok=True)
        r1 = AC.add("rapideod25", N1)
        raw1 = open(rapid.path(), "rb").read()
        r2 = AC.add("rapideod", N2)
        b2 = rapid.read(rapid.slot_path("rapid2")) or {}
        check("g. 1st Rapid -> data/rapid.json, 2nd -> data/rapid2.json, both DISARMED", r1.get("ok") and r1.get("slot") == "rapid"
              and r2.get("ok") and r2.get("slot") == "rapid2" and b2.get("plan") == P50 and b2.get("armed") is False
              and (rapid.read() or {}).get("armed") is False, (r1, r2))
        check("f. adding the 2nd never rewrites the 1st's file", open(rapid.path(), "rb").read() == raw1)
        r3 = AC.add("rapideod", "Sim207")
        check("g. a 3rd Rapid is refused (both slots taken)", r3.get("ok") is False and "both Rapid slots" in str(r3.get("error")), r3)
        r4 = AC.add("rapideod", N1)
        check("g. the 1st Rapid's Name never goes into slot 2", r4.get("ok") is False and (rapid.read(rapid.slot_path("rapid2")) or {})
              .get("account") == N2, r4)
        inv = [(x["id"], x["plan"]) for x in AC.inventory() if x["role"] == "rapid"]
        check("g. inventory lists both (rapid 25K, rapid2 50K)", inv == [("rapid", "rapideod25"), ("rapid2", "rapideod")], inv)
        AC.arm("i accept")
        check("g. a wrong phrase arms nothing", (rapid.read(rapid.slot_path("rapid2")) or {}).get("armed") is False)
        lines = AC.arm(LIVE_PHRASE)
        check("g. the typed phrase (START BOT / the add box's Start) arms Rapid #2",
              (rapid.read(rapid.slot_path("rapid2")) or {}).get("armed") is True and any("#2" in x and "armed" in x for x in lines), lines)
        check("f. old code's view: data/rapid.json alone, unchanged by the 2nd Rapid", open(rapid.path(), "rb").read() == raw1)
        AC.remove(N2)
        check("g. removing Rapid #2 leaves the 1st on", rapid.read(rapid.slot_path("rapid2")) is None and (rapid.read() or {}).get("account") == N1)
    finally:
        rapid.PATH = keep_r
        for k, v in keep.items():
            setattr(G, k, v)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="multi_rapid_")
    try:
        part_a()
        part_b_to_e(tmp)
        part_f_g(tmp)
    finally:
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n}/{len(RESULTS)} passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
