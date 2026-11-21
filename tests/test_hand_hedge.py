"""Hand-trade hedge guard (engine/hand_hedge.py + engine/multi_account.AccountRouter.opposite_open + engine/guards.reconcile_tick;
day-redteam2 2026-11-20, idea #1 of research/handoff/2026-11-20/TOP25_IDEAS.txt). Temp dirs, fake clock, no phone.

    python -X utf8 -m tests.test_hand_hedge
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RESULTS = []
T0 = 1_795_000_000            # a fixed fake "now"


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:600]}"), flush=True)


def setup(tmp):
    folder = os.path.join(tmp, "NinjaTrader 8")
    os.makedirs(os.path.join(folder, "outgoing"), exist_ok=True)
    os.makedirs(os.path.join(folder, "le_feed"), exist_ok=True)
    return folder


def feed(folder, last_open):
    with open(os.path.join(folder, "le_feed", "MNQ_1m.csv"), "w", encoding="utf-8") as fh:
        fh.write(f"{int(last_open) - 60},1,1,1,1,1\n{int(last_open)},1,1,1,1,1\n")


def pos(folder, inst, acct, text):
    with open(os.path.join(folder, "outgoing", f"{inst}_{acct}_Position.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)


def router(folder, main="MFFUEVLB50K0001111", extras=(), legs=None):
    from engine import multi_account as MA
    sent = []
    bot = types.SimpleNamespace(adapter=types.SimpleNamespace(folder=folder, account=main, legs=legs or [], watch=[]),
                                ledger=[], _open_routed=None, fleet=None)
    r = object.__new__(MA.AccountRouter)
    r.bot, r.accounts = bot, list(extras)
    r.clock = lambda: T0
    r.notify = lambda title, body, key: sent.append((title, key))
    return r, sent


def main():
    from engine import hand_hedge as HH
    tmp = tempfile.mkdtemp(prefix="xhedge_")
    try:
        f = setup(tmp)
        feed(f, T0 - 70)                                       # NinjaTrader running: the newest 1m bar closed 10 s ago
        pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "LONG;2;21000.25")   # the owner's HAND long on the 25K #2
        HH._C["rows"] = None
        r, sent = router(f)
        why = r.opposite_open(-1)
        check("1. hand LONG 2 MNQ on account A (25K #2) + the bot's SHORT signal on its 50K -> refused, the account named by its "
              "last 4 only", why and "hand trade" in why and "..2222" in why and "0002222" not in why, why)
        check("2. same side (bot LONG) -> allowed", r.opposite_open(1) is None)
        acct = types.SimpleNamespace(spec={"nt_account": "MFFUEVLB25K0002222"}, open_t=None, ledger=[], adapter=None)
        r2, _ = router(f, extras=[acct])
        check("3. an extra account's own position is not a cross-account hedge for that account (own = its nt_account)",
              r2.opposite_open(-1, exclude=acct) is None)
        lane = types.SimpleNamespace(account="MFFUEVLB25K0002222", legs=[{"status": "protected"}], watch=[])
        r3, _ = router(f, extras=[types.SimpleNamespace(spec={"nt_account": "X"}, open_t=None, ledger=[], adapter=lane)])
        check("4. a position a bot lane explains (an open bracket of that account's adapter) is left to the ledger checks "
              "(LIT-closes-ATLAS-first flow untouched)", r3.opposite_open(-1) is None)
        for n in os.listdir(os.path.join(f, "outgoing")):
            os.remove(os.path.join(f, "outgoing", n))
        pos(f, "MNQ 12-26 Globex", "Sim101", "LONG;1;21000")
        pos(f, "MES 12-26 Globex", "MFFUEVLB25K0002222", "LONG;1;6000")
        HH._C["rows"] = None
        check("5. a Sim101 position and an ES (MES) position -> ignored (not MFFU / not NQ)", router(f)[0].opposite_open(-1) is None)
        pos(f, "NQ 12-26 Globex", "MFFUFUNDB25K0003333", "SHORT;1;21000")
        HH._C["rows"] = None
        check("6. a hand SHORT 1 NQ mini on ATLAS's funded 25K blocks a LIT LONG on the 50K",
              "SHORT 1 NQ" in str(router(f)[0].opposite_open(1)))
        pos(f, "MNQ 12-26 Globex", "MFFU_EV_25K_4444", "LONG;1;21000")
        HH._C["rows"] = None
        check("6b. an account Name with '_' in it is still read (hand LONG on MFFU_EV_25K_4444 blocks a SHORT)",
              "..4444" in str(router(f)[0].opposite_open(-1)))
        os.remove(os.path.join(f, "outgoing", "MNQ 12-26 Globex_MFFU_EV_25K_4444_Position.txt"))
        pos(f, "NQ 12-26 Globex", "MFFUFUNDB25K0003333", "FLAT;0;0")
        HH._C["rows"] = None
        check("7. that position closed (FLAT) -> allowed again", router(f)[0].opposite_open(1) is None)
        # stale feed: fall back to the ledger check + ONE notice a day
        pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "LONG;2;21000.25")
        feed(f, T0 - 60 - HH.STALE_S - 30)
        HH._C["rows"] = None
        HH._PUSHED.clear()
        r4, sent4 = router(f)
        a1, a2 = r4.opposite_open(-1), r4.opposite_open(-1)
        check("8. NinjaTrader feed stale (files not trusted) -> the hand check steps aside (the ledger checks still run) and "
              "pushes ONE 'Hand-trade check off' notice", a1 is None and a2 is None and [t for t, _ in sent4] == ["Hand-trade check off"], sent4)
        os.remove(os.path.join(f, "le_feed", "MNQ_1m.csv"))
        check("9. no feed file at all -> steps aside too (never blocks on a guess)", router(f)[0].opposite_open(-1) is None)
        paper = types.SimpleNamespace(adapter=types.SimpleNamespace(name="paper"))
        check("10. a paper bot (no NinjaTrader folder) -> nothing read, None", HH.opposite_hand(-1, paper) is None)
        # the hand-trade window and guards.reconcile_tick
        from engine import guards as G
        wp = os.path.join(tmp, "hand_trade.json")
        old = HH.WINDOW_PATH
        HH.WINDOW_PATH = wp
        try:
            routed, notes = [], []
            ad = types.SimpleNamespace(account="MFFUEVLB50K0001111", legs=[], watch=[], disabled=None, readonly=False,
                                       positions=lambda: {"positions": [{"instrument": "MNQ 12-26", "side": "LONG", "qty": 1}]},
                                       _instruments=lambda: {"micro": "MNQ 12-26", "mini": "NQ 12-26"})
            b = types.SimpleNamespace(adapter=ad, kill=False, ledger=[], _open_routed=None, cfg={"sym": "NQ"}, _recon=None,
                                      clock=lambda: T0, _log=lambda *a: notes.append(a), _push_send=lambda p: None,
                                      _note_error=lambda *a: None, _route=lambda a: routed.append(a))
            c = dict(G.DEFAULTS)
            HH.set_window(30, path=wp, now=T0)
            G.reconcile_tick(b, c, T0)
            G.reconcile_tick(b, c, T0 + 60)
            check("11. hand-trade window open: the bot's own 50K shows LONG 1 the ledger does not explain -> NO CLOSEPOSITION, "
                  "one 'Hand trade left alone' notice", not routed and sum("Hand trade left alone" in str(n) for n in notes) == 1, (routed, notes[-3:]))
            HH.clear_window(path=wp)
            b._recon = None
            G.reconcile_tick(b, c, T0 + 120)
            G.reconcile_tick(b, c, T0 + 200)
            check("12. window closed -> the old rule: CLOSEPOSITION (reason RECONCILE) after the grace",
                  any(a.get("reason") == "RECONCILE" for a in routed), routed)
            w = HH.set_window(999, path=wp, now=T0)
            check("13. the window is capped at 240 minutes and ends by itself",
                  w["until"] == T0 + 240 * 60 and HH.window(wp, now=T0 + 240 * 60 + 1) is None)
        finally:
            HH.WINDOW_PATH = old
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RESULTS)
    print(f"\nhand hedge: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
