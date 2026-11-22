"""Full-fleet dry run (day-redteam3, 2026-11-21): tools/rehearse_day.py (the real LiveBot, PAPER, every lane on ONE simulated
NinjaTrader) with the two NinjaTrader files the PC's LE_BarFeed writes and the rehearsal never wrote:

  le_feed\\MNQ_1m.csv    the newest 1-minute bars (the bars the rig replays), so engine/hand_hedge sees NinjaTrader as RUNNING
                        (without it the hand-hedge guard and its accounts.csv check step aside: they were never exercised)
  le_feed\\accounts.csv  one row per account each minute: name, time, cash, realized, unrealized (from the fake's positions)

(NinjaTrader's position files keep their real mtimes: stamping them with the replay clock makes the adapter's wall-clock
close checks fail, a harness artifact; so accounts.csv rows always read older than the files here, and the accounts.csv
"blind" refusal's file-time rule is tested in tests/test_fleet_dryrun_guards.py instead). Works on any checkout (--root), so the same days run on the base and on the landing.

    python -X utf8 tools/fleet_dryrun.py --root <checkout> --rapid --days 2026-11-17 --quick --out x.json [--sunday 2026-11-16]
          [--early 2026-11-13=13:15]   (replays that day as a CME early close at 13:15 ET)
Temp files only, never the owner's NinjaTrader folder, never armed outside the fake.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--days", required=True)
    ap.add_argument("--rapid", action="store_true")
    ap.add_argument("--lucid", action="store_true", help="+ a LucidPro 50K lane (the second firm; tools/rehearse_day --lucid)")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--no-ntfiles", action="store_true", help="the rehearsal as it was (no le_feed files)")
    ap.add_argument("--early", default="", help="day=HH:MM: replay that day as a CME early close")
    ap.add_argument("--hand", default="", help="ACCOUNT=LONG|SHORT: a hand position file on that account all day (guard check)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    sys.path.insert(0, root)
    os.chdir(root)
    import tools.rehearse_day as RD           # the checkout's own harness and engine
    from engine import cme_calendar as C
    if a.early:
        d, hm = a.early.split("=")
        mins = int(hm[:2]) * 60 + int(hm[3:5])
        orig = C._early.__wrapped__ if hasattr(C._early, "__wrapped__") else C._early

        def _early(x, orig=orig):
            return mins if x.isoformat() == d else orig(x)
        C._early = _early
        C._HC.clear()
        try:
            from engine import lit_live
            lit_live.early_close = lambda day, orig=lit_live.early_close: mins if str(day)[:10] == d else orig(day)
        except Exception:
            pass
    if not a.no_ntfiles:
        base_init, base_walk = RD.Rig.__init__, RD.Rig.walk

        def __init__(self, *k, **kw):
            base_init(self, *k, **kw)
            fk = self.fake
            raw = fk._write_pos

            def _write_pos(acct, inst, raw=raw, fk=fk, rig=self):
                raw(acct, inst)
                p = os.path.join(fk.out, f"{inst} {fk.exchange}_{acct}_Position.txt")
                t = float(rig.now or 0)
                if t > 0 and os.environ.get("FD_STAMP"):    # off: the adapter compares file times with the wall
                    os.utime(p, (t, t))                       # clock in places (close_sent): replay-clock stamps fake a stuck close
            fk._write_pos = _write_pos
            self._cash = {}
            if a.hand:
                acct, side = a.hand.split("=")
                os.makedirs(fk.out, exist_ok=True)
                with open(os.path.join(fk.out, f"MNQ 12-26 {fk.exchange}_{acct}_Position.txt"), "w", encoding="utf-8") as fh:
                    fh.write(f"{side.upper()};1;25000")

        def walk(self, t_bar):
            # fills while this bar trades happen inside it: NinjaTrader stamps its files then, not at the last poll (the
            # rehearsal's clock still reads the previous poll here; real files carry real, monotonic times)
            if self.bars1.get(int(t_bar)) and float(self.now or 0) < int(t_bar) + 1:
                self.now = int(t_bar) + 1
            base_walk(self, t_bar)
            feed(self, int(t_bar))
        RD.Rig.__init__, RD.Rig.walk = __init__, walk
    if os.environ.get("FD_LOGS"):                 # every lane's risk / skip line of the day, full text
        base_tp = RD.trades_print

        def trades_print(bot, base_tp=base_tp):
            base_tp(bot)
            pat = os.environ["FD_LOGS"].lower()
            for e in reversed(list(getattr(bot, "log", []) or [])):
                if pat in str(e.get("text", "")).lower():
                    print(f"    LOG {RD.hm(e.get('t') or 0)} {e.get('type')}: {e.get('text')}")
        RD.trades_print = trades_print
    buf = io.StringIO()
    rc = 0
    argv2 = ["--days", a.days, "--scenarios", "none"] + (["--rapid"] if a.rapid else []) + (["--lucid"] if a.lucid else []) + (["--quick"] if a.quick else []) + \
        (["--full"] if a.full else [])
    out_json = RD.OUT
    RD.OUT = os.path.abspath(a.out) + ".rehearse.json"
    try:
        rc = RD.main(argv2)
    finally:
        RD.OUT = out_json
    try:
        res = json.load(open(os.path.abspath(a.out) + ".rehearse.json", encoding="utf-8"))
    except Exception:
        res = {}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"root": root, "days": a.days, "early": a.early, "ntfiles": not a.no_ntfiles, "rc": rc, "result": res}, fh,
                  indent=1, default=str)
    return rc


def feed(rig, t_bar: int):
    """LE_BarFeed's two files at the replay clock: the 1m bars up to the one that just closed, and accounts.csv."""
    from engine.ninjatrader import FEED_DIR
    d = os.path.join(rig.folder, FEED_DIR)
    os.makedirs(d, exist_ok=True)
    keys = [k for k in sorted(rig.bars1) if k <= t_bar][-400:]
    if keys:
        with open(os.path.join(d, "MNQ_1m.csv"), "w", encoding="utf-8") as fh:
            for k in keys:
                o, h, l, c = rig.bars1[k]
                fh.write(f"{k},{o},{h},{l},{c},100\n")
    px = float(rig.fake.price)
    accts = {acct for (acct, _i) in rig.fake.pos} | {getattr(ad, "account", None) for ad in rig.adapters}
    rows = ["name,time,cash,realized,unrealized,netliq"]
    t = int(t_bar) + 60
    for acct in sorted(x for x in accts if x):
        u = 0.0
        for (ac, inst), (q, avg) in rig.fake.pos.items():
            if ac == acct and q:
                pv = 20.0 if inst.upper().startswith("NQ ") else 2.0
                u += q * (px - float(avg)) * pv
        cash = 50000.0 if "50K" in acct.upper() else 25000.0
        rows.append(f"{acct},{t},{cash:.2f},0,{u:.2f},{cash + u:.2f}")
    with open(os.path.join(d, "accounts.csv"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
