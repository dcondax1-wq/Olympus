"""Trade-alert AUDIT (nqdash3 2026-11-20, owner: "phone notifications exactly when a trade is taken AND closed with results").
Read-only on engine/: re-runs every account route of tests/test_trade_alerts.py (fake fills, temp files, no network) through BOTH
delivery paths of engine/push._pc_send and checks each route's ENTRY and CLOSE notice carries: the account name, the side, the $ and
(close) the result in $ and R.

  web push: a phone takes it (app_send stubbed to sent=1): the Olympus app notice (title/body from app_payload), ntfy stays quiet
  ntfy:     no phone (app_send -> sent=0): the private ntfy alert topic gets it instead

Routes: a. LIT on Zlarior 50K, b. Zlarior 25K #2 (extra account), c. ATLAS 25K funded (account B), d. Rapid EOD 25K (LIT lane + ATLAS lane),
e. ATLAS on Zlarior 50K (combo).
    python -X utf8 -m tests.test_alert_audit        (~3 s)
"""
from __future__ import annotations

import json
import re
import sys

from tests import test_trade_alerts as T
from engine import push as P

RES = []
ROUTES = {"part_real": ["ATLAS 25K funded"], "part_a": ["Zlarior 50K"], "part_b": ["Zlarior 25K #2"], "part_c": ["ATLAS 25K funded"], "part_c_time": ["ATLAS 25K funded"],
          "part_d": ["Rapid EOD 25K"], "part_e": ["ATLAS on Zlarior 50K"]}
SIDE = re.compile(r"\b(LONG|SHORT)\b")
USD = re.compile(r"[+-]\$[\d,]+")
R = re.compile(r"[+-]\d+(\.\d)?R\b")
ID = re.compile(r"MFFU[A-Z]{4}[A-Z]*\d{6,}")


# LEAD_WIRES.md patches (bot files: the lead applies them). Applied here IN MEMORY only, to prove them; each must still match the file exactly.
PATCHES = {
    "1 engine/ninjatrader.py NinjaTraderAdapter._push_exit (every stop / target close, every account)": ("engine.ninjatrader", "NinjaTraderAdapter", "_push_exit", [
        ('        reason = "TARGET" if name == "TARGET" else ("BE" if abs(ex - fill) <= 1.0 else "STOP")\n',
         '        reason = "TARGET" if name == "TARGET" else ("BE" if abs(ex - fill) <= 1.0 else "STOP")\n'
         '        risk = abs(fill - float(lg.get("stop0") or lg.get("stop") or 0))\n'
         '        rr = round((ex - fill) * lg["dir"] / risk, 2) if fill and ex and risk > 0 else None\n'),
        ('qty=x.get("filled"), who=lg["who"])', 'qty=x.get("filled"), who=lg["who"], R=rr)'),
        ('src="pc", exit_px=ex, qty=x.get("filled")))', 'src="pc", exit_px=ex, qty=x.get("filled"), R=rr))')]),
    "2 engine/account_b.py AccountB._push_outcome (ATLAS time / cut / kill closes)": ("engine.account_b", "AccountB", "_push_outcome", [
        ('                                     qty=q, strategy=pv.get("short"))',
         '                                     qty=q, strategy=pv.get("short"),\n'
         '                                     R=round(float(usd) / (float(pv["risk_pts"]) * q * 2.0), 2) if pv.get("risk_pts") and q else None)')]),
    "3 engine/multi_account.py AccountRouter.notify_outcome (extra accounts' time / day-end closes)": ("engine.multi_account", "AccountRouter", "notify_outcome", [
        ('pnl, tr["entry_t"], tr.get("exit_t"), src="pc", qty=qty), acc))', 'pnl, tr["entry_t"], tr.get("exit_t"), src="pc", qty=qty, R=tr.get("pnl_r")), acc))')]),
}


def patched(mod, cls, meth, reps):
    """the method with its patch applied (exact text match, else None = the patch no longer fits)"""
    import importlib
    import inspect
    import textwrap
    M = importlib.import_module(mod)
    src = textwrap.dedent(inspect.getsource(getattr(getattr(M, cls), meth)))
    src = "    " + src.replace("\n", "\n    ").rstrip() + "\n"
    for a, b in reps:
        if src.count(a) != 1:          # dedent + 4 spaces = the file's own indentation, so the patch text is the file's text
            return None
        src = src.replace(a, b)
    ns = {}
    exec("class _X:\n" + src, vars(M), ns)   # noqa: S102 - our own repo's source + the patch above
    return ns["_X"].__dict__[meth]


def part_real(b):
    """the lead's live case (2026-11-20): ATLAS short 1 MNQ @ 26,380.75 at 03:45 ET, stop moved to 26,379.50 (break-even), target 26,122.75.
    Its close comes from NinjaTrader's bracket: here the target fills (+$516). stop0 = the stop it was routed with (a 40-point stop, as an example:
    the chart feed only carries the moved one), so R = 258 / 40 = +6.45R."""
    b.live(T.T0 - 600, [], atlas={"balance": 24887.0, "profit": -113.0, "today_pnl": 0.0, "status": "funded", "broker": "MFFUSFBLDR000006018",
                                  "funded": {"max_request": 0}})
    a = T.atlas()
    t = T.T0 + 60
    lg = T.leg(t=t, d=-1, q=1, fill=26380.75, stop=26420.75, target=26122.75)
    lg["stop"] = 26379.5                                   # moved to break-even since
    a.adapter._push_fill(dict(lg, stop=26420.75))
    a.adapter._push_exit(lg, "TARGET", {"avg": 26122.75, "filled": 1})


def part_c_time(b):
    """ATLAS's own time-exit close with the provenance the bot really stores (engine/account_b.py line ~1192: risk_pts, qty)"""
    b.live(T.T0 - 600, [], atlas={"balance": 26050.0, "profit": 1050.0, "today_pnl": 0.0, "status": "funded", "broker": "MFFUSFBLDR000006018",
                                  "funded": {"max_request": 0}})
    a = T.atlas()
    a.adapter = object()
    t = T.T0 + 1020
    a._push_entry({"side": "buy", "entry_t": t, "entry": 21000.0, "stop": 20990.0, "target": 21030.0, "strategy": "MACD"}, 2)
    a._push_outcome({"dir": 1, "short": "MACD", "risk_pts": 10.0, "qty": 2}, "TIME", 40.0, t + 800, 2, t)


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  ({info})"))


def run(part, phone: bool):
    """-> (app notices [(kind, title, body)], ntfy posts [(kind, title, body)]) for one route"""
    app = []
    saved_send, saved_check = P.app_send, T.check

    def fake_send(payload, cfg=None, sender=None, path=None):
        app.append(payload)
        return {"sent": 1, "devices": 1} if phone else {"sent": 0, "skipped": "no phone"}
    posts, saved_take = [], T.Box.take

    def take(self):
        posts.extend(self.posts)
        return saved_take(self)
    P.app_send, T.check, T.Box.take = fake_send, (lambda *a, **k: None), take   # the route code runs as is; its own asserts are test_trade_alerts' job
    b = T.Box()
    try:
        (globals().get(part) or getattr(T, part))(b)
        posts.extend(b.posts)
    finally:
        b.close()
        P.app_send, T.check, T.Box.take = saved_send, saved_check, saved_take
    a = [("entry" if p.get("kind") == "fill" else "close", str(p.get("title") or ""), str(p.get("body") or "")) for p in app
         if p.get("kind") in ("fill", "outcome")]
    n = [("entry" if str(m.get("tags", "")).startswith("chart_with") else "close", str(m.get("title") or ""), str(m.get("message") or m.get("body") or ""))
         for m in posts]
    return a, n


# test_trade_alerts.part_c's time exit hands account B a provenance with no risk_pts (the real bot always stores it): R is checked on
# that route's bracket close only; part_c_time covers ATLAS's time exit with the real provenance.
NO_RISK_FIXTURE = {"part_c"}


def audit(rows, names, label, part=""):
    ent = [r for r in rows if r[0] == "entry"]
    cl = [r for r in rows if r[0] == "close"]
    mine = lambda rs: [r for r in rs if any(r[1].startswith(nm + ":") for nm in names)]  # noqa: E731
    ent, cl = mine(ent), mine(cl)
    has = lambda rs: bool(rs)  # noqa: E731
    ok = (len(ent) >= 1 and len(cl) >= 1 and has(ent) and has(cl)
          and all(SIDE.search(r[1]) for r in ent + cl)
          and all(USD.search(r[1] + " " + r[2]) for r in ent + cl)
          and all(R.search(r[2]) for r in cl if part not in NO_RISK_FIXTURE or "(time exit)" not in r[1])
          and not any(ID.search(r[1] + r[2]) for r in rows))
    return ok, len(ent), len(cl)


def main() -> int:
    table = []
    import importlib
    today = gaps() if "--now" not in sys.argv else []
    saved = []
    for name, (mod, cls, meth, reps) in PATCHES.items():
        C = getattr(importlib.import_module(mod), cls)
        fixed = patched(mod, cls, meth, reps)
        check(f"LEAD_WIRES patch {name}: still fits the file exactly", fixed is not None)
        if fixed is not None and "--now" not in sys.argv:
            saved.append((C, meth, C.__dict__[meth]))
            setattr(C, meth, fixed)
    try:
        return _main(table, today)
    finally:
        for C, meth, f in saved:
            setattr(C, meth, f)


def gaps() -> list:
    """the bot as it is today (no patch): which routes' close notices miss R"""
    out = []
    for part, names in ROUTES.items():
        a, _n = run(part, True)
        out += [(names[0], r[1]) for r in a if r[0] == "close" and not R.search(r[2])]
    return out


def _main(table, today) -> int:
    for part, names in ROUTES.items():
        for phone in (True, False):
            app, ntfy = run(part, phone)
            via = "web push" if phone else "ntfy"
            rows = app if phone else ntfy
            ok, ne, nc = audit(rows, names, via, part)
            other_quiet = (not ntfy) if phone else True
            check(f"{part} {names[0]} via {via}: {ne} entry + {nc} close, each with account, side, $; close with $ and R; no account id"
                  + ("; ntfy quiet when the phone took it" if phone else ""), ok and other_quiet, rows if not ok else ntfy)
            ex = next((r for r in rows if r[0] == "close"), ("", "", ""))
            en = next((r for r in rows if r[0] == "entry"), ("", "", ""))
            table.append({"route": names[0], "via": via, "entries": ne, "closes": nc, "entry": en[1], "close": ex[1], "close_body": ex[2], "ok": ok})
    if "--now" not in sys.argv:
        print("today, without the patch, these closes have no R:", today or "none")
    if "--json" in sys.argv:
        print(json.dumps(table, indent=1))
    real = next((r for r in table if r["route"] == "ATLAS 25K funded" and r["via"] == "web push" and "26,380.75" in r["entry"]), None)
    check("the real case: entry 'ATLAS 25K funded: SHORT 1 MNQ @ 26,380.75'; close 'closed SHORT +$516 (target)' with +6.5R",
          bool(real) and real["close"] == "ATLAS 25K funded: closed SHORT +$516 (target)" and "+6.5R" in real["close_body"], real)
    n, k = len(RES), sum(RES)
    print(f"\nalert audit: {k}/{n} " + ("ALL PASS" if k == n else "FAILED"))
    return 0 if k == n else 1


if __name__ == "__main__":
    sys.exit(main())
