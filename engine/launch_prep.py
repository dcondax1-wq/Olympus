"""One owner command for the 2026-10-25 launch: allowlist both NinjaTrader accounts, load the 50K's real MFFU balance and
floor (eval anchor) and point ATLAS at the 25K (account B). Never arms anything: arming stays the owner's own step.

    python -m engine.launch_prep --atlas "<25K NinjaTrader Name>"

Defaults: LIT account = data/autostart.json "nt_account" (else --lit), anchor = the 2026-10-24 dashboard snapshot
(balance 49,710.80, floor 48,168.20, as of 2026-10-23), ATLAS plan builder25k starting the next session.
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTOSTART = os.path.join(ROOT, "data", "autostart.json")


def _lit_account(given):
    if given:
        return given
    try:
        with open(AUTOSTART, encoding="utf-8") as fh:
            return (json.load(fh).get("nt_account") or "").strip() or None
    except Exception:
        return None


def _next_session(today=None):
    d = today or dt.date.today()
    d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def _kept_start(atlas, path=None):
    """The eval_start already set for this same 25K (second_model.json "account_b"), else None. A second run of this
    command (the launch checklist names it as the fix for several red lines) must not move the 25K's first session to the
    next weekday: that would drop the eval's earlier days from account B's book (bug hunt 2026-10-25)."""
    try:
        from . import account_b
        ab = account_b.raw_cfg(path) or {}
        if str(ab.get("account") or "").strip() == str(atlas).strip() and ab.get("eval_start"):
            return str(ab["eval_start"])
    except Exception:
        pass
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atlas", required=True, metavar="NAME", help="the 25K account Name exactly as NinjaTrader shows it")
    ap.add_argument("--lit", default=None, metavar="NAME", help="the 50K account Name (default: data/autostart.json)")
    ap.add_argument("--balance", type=float, default=49710.80)
    ap.add_argument("--floor", type=float, default=48168.20)
    ap.add_argument("--as-of", default="2026-10-23")
    ap.add_argument("--atlas-start", default=None, help="ATLAS eval first session (default: the one already set for this 25K, else the next weekday)")
    a = ap.parse_args(argv)
    from . import ninjatrader, eval_life, account_b
    lit = _lit_account(a.lit)
    if not lit:
        print('LIT account Name not found: add --lit "<50K Name>"')
        return 1
    if lit == a.atlas:
        print("the 50K and the 25K must be two different accounts")
        return 1
    print(f"1/3 allow both accounts: {ninjatrader.allow_account(lit)}")
    ninjatrader.allow_account(a.atlas)
    print(f"    allowlist now: {ninjatrader.allow_account(a.atlas)}")
    print("2/3 50K eval anchor (real MFFU balance + floor):")
    try:
        cur = eval_life.load_anchor(None)
    except Exception:
        cur = None
    given = any(x in (argv if argv is not None else sys.argv[1:]) for x in ("--balance", "--floor", "--as-of"))
    if cur and str(cur.get("as_of") or "") > str(a.as_of) and not given:
        # a re-run (the launch checklist names this command as a fix) must not put the 2026-10-23 defaults back over a
        # newer anchor (eval_life --anchor or the day-close real balance): bug hunt 2026-10-25
        print(f"    kept the newer anchor as of {cur['as_of']}: balance ${cur['balance']:,.2f}, floor ${cur['floor']:,.2f} "
              "(give --balance --floor --as-of to replace it)")
    else:
        rc = eval_life.set_anchor(a.balance, a.floor, a.as_of)
        if rc:
            return rc
    start = a.atlas_start or _kept_start(a.atlas) or _next_session()
    print(f"3/3 ATLAS on the 25K {a.atlas!r}, builder25k, first session {start}:")
    r = account_b.set_account_b(a.atlas, plan="builder25k", start=start)
    print("   ", json.dumps(r, default=str)[:400])
    if not (isinstance(r, dict) and r.get("ok")):
        print("ATLAS NOT switched on (see above); LIT is unaffected.")
        return 1
    print("Done. Nothing is armed: arm both accounts yourself as for the 50K (docs/GO_LIVE_TONIGHT.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
