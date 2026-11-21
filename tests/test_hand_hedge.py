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


def acsv(folder, rows):
    with open(os.path.join(folder, "le_feed", "accounts.csv"), "w", encoding="utf-8") as fh:
        fh.write("name,time,cash,realized,unrealized,netliq\n" + "".join(f"{n},{t},25000,0,{u},25000\n" for n, t, u in rows))


def clear(folder):
    for n in os.listdir(os.path.join(folder, "outgoing")):
        os.remove(os.path.join(folder, "outgoing", n))


def blind(f):
    """fix-trade 2026-11-21: NinjaTrader restarted (outgoing\\ wiped, the file back only when the position changes) while a
    hand trade is open: accounts.csv still shows its open P&L -> no entry either way (the side is unknown)."""
    from engine import hand_hedge as HH
    feed(f, T0 - 70)
    clear(f)
    acsv(f, [("MFFUEVLB25K0002222", T0 - 20, -145.5), ("MFFUEVLB50K0001111", T0 - 20, 0)])
    HH._C["rows"] = None
    w1, w2 = router(f)[0].opposite_open(1), router(f)[0].opposite_open(-1)
    check("14. no position file + a fresh accounts.csv row with open P&L -$145.50 on the 25K #2 -> refused both ways, masked",
          w1 and w2 and "..2222" in w1 and "0002222" not in w1 and "open P&L" in w1, (w1, w2))
    acsv(f, [("MFFUEVLB25K0002222", T0 - 600, -145.5)])
    check("15. the same row 10 min old (stale) -> not used", router(f)[0].opposite_open(1) is None)
    acsv(f, [("MFFUEVLB25K0002222", T0 - 20, -145.5), ("Sim101", T0 - 20, 300.0)])
    pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "FLAT;0;0")
    os.utime(os.path.join(f, "outgoing", "MNQ 12-26 Globex_MFFUEVLB25K0002222_Position.txt"), (T0 - 5, T0 - 5))
    HH._C["rows"] = None
    check("16. a FLAT file written AFTER that row (the bot's or a hand close a moment ago) -> the row is stale, allowed; Sim101 "
          "P&L never counts", router(f)[0].opposite_open(1) is None)
    os.utime(os.path.join(f, "outgoing", "MNQ 12-26 Globex_MFFUEVLB25K0002222_Position.txt"), (T0 - 900, T0 - 900))
    HH._C["rows"] = None
    check("17. a FLAT file OLDER than the row (P&L opened after it, file not rewritten) -> refused",
          "open P&L" in str(router(f)[0].opposite_open(1)))
    clear(f)
    pos(f, "MES 12-26 Globex", "MFFUEVLB25K0002222", "LONG;1;6000")
    HH._C["rows"] = None
    check("18. the open P&L is explained by a non-FLAT file (an MES trade: no NQ hedge) -> allowed",
          router(f)[0].opposite_open(1) is None)
    clear(f)
    HH._C["rows"] = None
    lane = types.SimpleNamespace(account="MFFUEVLB25K0002222", legs=[{"status": "protected"}], watch=[])
    r, _ = router(f, extras=[types.SimpleNamespace(spec={"nt_account": "X"}, open_t=None, ledger=[], adapter=lane)])
    check("19. a bot lane holds that account (its own trade's P&L) -> allowed", r.opposite_open(1) is None)
    acsv(f, [("MFFUEVLB25K0002222", T0 - 20, 0)])
    HH._C["rows"] = None


def hedge_first_and_guard(f):
    """fix-trade 2026-11-21: the hand check runs BEFORE the bot's hedge close (LiveBot._hedge_clear closes ATLAS / BLITZ /
    followers at market): a hand trade that refuses the entry anyway never costs ATLAS its trade. Also the one-account bot."""
    from engine import account_b as AB, account_c as AC, guards as GD, hand_hedge as HH
    feed(f, T0 - 70)
    clear(f)
    pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "SHORT;1;21000")    # hand SHORT on the 25K #2
    HH._C["rows"] = None
    r, _ = router(f)
    r._kill = False
    r.log = lambda kind, text: closes.append(("log", kind, text))
    closes = []
    r.bot._hedge_clear = lambda ent, sym, now: closes.append(ent) or True
    r.others_opposite = lambda d, a=None: "ATLAS's 25K holds a SHORT position"
    acc = types.SimpleNamespace(seen=set(), entry_block=lambda now: None)
    ctx = {"state": {"position": {"entry_t": T0 - 30, "dir": 1}}, "start": T0, "secs": 300, "now": T0, "sym": "NQ"}
    r._hedge_first([acc], ctx)
    check("20. router: a LIT LONG every account would refuse (hand SHORT) -> ATLAS is NOT closed for it (_hedge_clear not called)",
          not closes, closes)
    clear(f)
    HH._C["rows"] = None
    r._hedge_first([acc], ctx)
    check("21. ... no hand trade -> the hedge close runs as before", len(closes) == 1, closes)
    pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "SHORT;1;21000")
    HH._C["rows"] = None
    keep = GD.config, GD.entry_problems
    notes = []
    bot = types.SimpleNamespace(adapter=types.SimpleNamespace(folder=f, account="MFFUEVLB50K0001111", legs=[], watch=[]),
                                accts=None, fleet=None, ledger=[], _open_routed=None, clock=lambda: T0,
                                _log=lambda *a: notes.append(a), _push_send=lambda p: None, _note_error=lambda *a: None)
    try:
        GD.config = lambda b: {}
        GD.entry_problems = lambda *a, **k: []
        why = GD.entry_block(bot, {"entry_t": T0 - 30}, {"side": "buy", "qty": 2, "sym": "NQ"}, 2, T0)
        same = GD.entry_block(bot, {"entry_t": T0 - 30}, {"side": "sell", "qty": 2, "sym": "NQ"}, 2, T0)
    finally:
        GD.config, GD.entry_problems = keep
    check("22. LiveBot's guard step (before _hedge_clear / _second_preempt), one-account bot too: the hand SHORT blocks LIT's "
          "LONG; a SHORT (same side) passes", why and "hand trade" in why and same is None, (why, same))
    atl = types.SimpleNamespace(bot=bot, name="MFFUEVLB25K0003333", clock=lambda: T0)
    bot.state, bot.acct_r, bot.acct_r2, bot.acct_b = {}, None, None, None
    wa = AB.AccountB.lit_opposite(atl, 1)
    check("23. ATLAS with no extra accounts (accts None): the hand SHORT refuses its LONG", wa and "hand trade" in wa, wa)
    blz = types.SimpleNamespace(bot=bot, name="MFFUEVLB25K0004444", clock=lambda: T0)
    wc = AC.AccountC.opposite(blz, 1)
    check("24. BLITZ with no extra accounts: the same", wc and "hand trade" in wc, wc)
    clear(f)
    HH._C["rows"] = None


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
        check("3. a hand LONG on an extra account's OWN account refuses that account's SHORT too (same-account hedge; fix-trade "
              "2026-11-21: own was skipped)", "..2222" in str(r2.opposite_open(-1, exclude=acct)), r2.opposite_open(-1, exclude=acct))
        check("3b. ... and its LONG (same side) is still allowed", r2.opposite_open(1, exclude=acct) is None)
        os.remove(os.path.join(f, "outgoing", "MNQ 12-26 Globex_MFFUEVLB25K0002222_Position.txt"))
        pos(f, "NQ 12-26 Globex", "MFFUEVLB50K0001111", "LONG;1;21000")          # a hand NQ MINI on the bot's own 50K
        HH._C["rows"] = None
        why3 = router(f)[0].opposite_open(-1)
        check("3c. hand-trade window case: a hand NQ mini LONG on the bot's OWN 50K + LIT's SHORT in MNQ there -> refused (the "
              "adapter checks only the MNQ file it sends)", why3 and "..1111" in why3 and "LONG 1 NQ" in why3, why3)
        os.remove(os.path.join(f, "outgoing", "NQ 12-26 Globex_MFFUEVLB50K0001111_Position.txt"))
        pos(f, "MNQ 12-26 Globex", "MFFUEVLB25K0002222", "LONG;2;21000.25")
        HH._C["rows"] = None
        r2b = router(f)[0]
        r2b.bot.acct_r2 = types.SimpleNamespace(adapter=types.SimpleNamespace(account="MFFUEVLB25K0002222",
                                                                             legs=[{"status": "protected"}], watch=[]))
        check("3d. ATLAS on the 2nd Rapid (acct_r2) holding that account explains its position (no false block)",
              r2b.opposite_open(-1) is None and "mffuevlb25k0002222" in HH.bot_held(r2b.bot, r2b))
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
        blind(f)
        hedge_first_and_guard(f)
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
            mm = [str(n) for n in notes if "Position mismatch" in str(n)]
            check("11b. the first 'Position mismatch' push in the window says 'Left alone', never 'Closing it'",
                  mm and "Left alone" in mm[0] and "Closing it" not in mm[0], mm)
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
