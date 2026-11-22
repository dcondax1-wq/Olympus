"""The SECOND FIRM, Lucid (day-nqdash3 2026-11-22, research/writeups/corvette-plan-2026-11-21.md): OFF by default, added DISARMED.

    python -X utf8 -m tests.test_lucid       (temp files only, made-up names; nothing armed for real, ~10 s)

  a. rules    engine/multi_account preset lucid_pro_50k = Lucid's help center as cited in research/lit/lucid_rules.json (target,
              EOD trailing $2,000 locking at +$100, $1,200 DLL, 40 micros, no eval best-day rule, news allowed); every cited
              value has a support.lucidtrading.com URL; the unverified ones say so
  b. add      `engine.accounts add --plan lucidpro50k`: a LIT copy (preset lucid_pro_50k), DISARMED, allowlisted, the Lucid
              notes (hedging across firms, 30 days, the written OK); never an MFFU slot; Lucid's own caps (10 evals, 5 funded)
  c. arming   START BOT's arm(<phrase>) arms the other added accounts but HOLDS the Lucid one until `lucid-ok` recorded
              Lucid's written yes; lucid-ok itself never arms; a wrong phrase arms nothing
  d. sizing   every entry on the Lucid account: a full stop-out (2 ticks of slippage + commission) stays inside the $1,200
              daily loss left today (also after a losing day so far), never more than 40 micros, never a 0-risk entry sized up
  e. hedging  the router refuses an order opposite to the Lucid account's open position, and the Lucid account cannot go
              opposite an MFFU account's (one guard over every account, every firm)
  f. clocks   engine/clock7: a Lucid account gets Lucid's 30 days (no MFFU keep-alive), MFFU accounts keep 7
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_cli as AC  # noqa: E402
from engine import go as G  # noqa: E402
from engine import multi_account as MA  # noqa: E402
from engine import sizing as sz  # noqa: E402
from engine.tradovate import LIVE_PHRASE  # noqa: E402
from tests import test_accounts_cli as TA  # noqa: E402

RES = []
NL = "LTP50K-FAKE0001"            # a made-up Lucid account Name (Lucid's real Names come from Tradovate)
NL2 = "LTP50K-FAKE0002"


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def quiet(fn, *a):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = fn(*a)
    return rc, out.getvalue()


def test_rules():
    J = json.load(open(os.path.join(ROOT, "research", "lit", "lucid_rules.json"), encoding="utf-8"))
    R = MA.PRESETS["lucid_pro_50k"]["rules"]
    E = J["eval"]
    check("a. preset = Lucid's cited rules: $50,000 start, $3,000 target, $2,000 MLL EOD trailing, lock +$100, $1,200 DLL, 40 micros",
          (R["start"], R["target"], R["mll"], R["lock"], R["dll"], R["max_micros"], R["trail"]) ==
          (E["start"]["value"], E["target"]["value"], E["mll"]["value"], E["lock"]["value"], E["dll"]["value"], E["max_micros"]["value"], "eod"), R)
    check("a. no eval best-day rule (none found), news allowed on Pro", R["best_day"] is None and R["news_ban"] is False and E["consistency"]["value"] is None
          and "allowed" in J["news"]["value"], (R, J["news"]))
    urls = []

    def walk(x):
        if isinstance(x, dict):
            if "url" in x:
                urls.append(x["url"])
            for v in x.values():
                walk(v)
    walk(J)
    check("a. every cited value has a Lucid help-center URL (support.lucidtrading.com)", len(urls) >= 20
          and all(u.startswith("https://support.lucidtrading.com/en/articles/") for u in urls), [u for u in urls if "support.lucidtrading.com" not in u])
    check("a. the unverified ones say so (price, platform for LucidPro, same strategy at other firms)",
          J["price"]["value"] is None and "UNVERIFIED" in J["price"]["note"] and "UNVERIFIED" in J["platform"]["value"]
          and "UNREAD" in J["same_strategy_other_firms"]["value"])
    check("a. Lucid's household caps (10 evals, 5 funded) and its 30-day inactivity are in the file the code reads",
          AC.lucid_limits() == {"evals": 10, "funded": 5} and J["inactivity"]["days"] == 30)
    fd = MA.PRESETS["lucid_pro_50k"]["sizing"]["funded"]
    check("a. funded: a winner <= $1,500, inside Lucid's 40% best-day rule for the first max payout ($2,000 needs $4,100 of profit: 40% = $1,640)",
          fd["max_win"] == 1500 and fd["max_win"] <= 0.4 * (J["payout"]["max_first"]["min_balance"] - 50000), fd)


def test_cli(tmp):
    TA.world(tmp)
    nt = os.environ["NINJATRADER_FOLDER"]
    now = int(time.time())
    with open(os.path.join(nt, "le_feed", "accounts.csv"), "a") as fh:
        fh.write(f"{NL},{now},50000,0,0,50000\n{NL2},{now},50000,0,0,50000\n")
    before = AC.slots()
    r1 = AC.add("builder25k", TA.N25)
    r = AC.add("lucidpro50k", NL)
    rows = TA.file_rows()
    row = next((x for x in rows if x.get("nt_account") == NL), {})
    check("b. add --plan lucidpro50k: a LIT copy on preset lucid_pro_50k, two_week eval, DISARMED, plan recorded",
          r1["ok"] and r["ok"] and row.get("preset") == "lucid_pro_50k" and row.get("armed") is False and row.get("mode") == "two_week"
          and (row.get("cli") or {}).get("plan") == "lucidpro50k" and (row.get("cli") or {}).get("bots") == "lit", (r, row))
    notes = " ".join(r.get("notes") or [])
    check("b. the Lucid notes: hedging banned across firms, the 30-day rule, START BOT waits for Lucid's written OK",
          "across firms" in notes and "30 days" in notes and "lucid-ok" in notes, notes)
    check("b. the real Name goes on the NinjaTrader allowlist (that alone never trades)", NL in TA.allowed())
    after = AC.slots()
    check("b. never an MFFU slot: MFFU evals +1 (the 25K) only; Lucid evals 1", after["evals"] == before["evals"] + 1
          and after["lucid_evals"] == 1 and after["lucid_funded"] == 0, (before, after))
    rc, out = quiet(AC.main, ["list"])
    check("b. list shows it + a Lucid slots line", rc == 0 and NL in out and "Lucid: evals 1 of 10" in out, out[-400:])
    bad = AC.add("lucidpro50k", "LTP25K-FAKE0009")
    check("b. a 25K Name on the 50K plan is refused", not bad["ok"] and "25K" in bad.get("error", ""), bad)
    dup = AC.add("lucidpro50k", NL)
    check("b. the same Name twice is refused", not dup["ok"], dup)
    rows_fake = [{"name": f"L{i}", "plan": "lucidpro50k", "stage": "funded", "sim": False, "mffu": False, "role": "extra"} for i in range(5)]
    why = AC.limit_problem("lucidpro50k", "funded", "LTP50K-NEW", rows_fake)
    why_e = AC.limit_problem("lucidpro50k", "eval", "LTP50K-NEW", [{**x, "stage": "eval"} for x in rows_fake * 2])
    check("b. Lucid's caps: a 6th funded and an 11th eval are refused; MFFU's caps never count Lucid",
          why and "5 funded" in why and why_e and "10 evals" in why_e and AC.limit_problem("builder25k", "funded", "MFFU-X", rows_fake) is None, (why, why_e))

    # c. arming
    out0 = AC.arm("wrong phrase")
    rows = TA.file_rows()
    check("c. a wrong phrase arms nothing", out0 == [] and not any(x.get("armed") for x in rows))
    out = AC.arm(LIVE_PHRASE)
    rows = TA.file_rows()
    lu = next(x for x in rows if x.get("nt_account") == NL)
    b25 = next(x for x in rows if x.get("nt_account") == TA.N25)
    check("c. START BOT's arm: the MFFU 25K armed, the Lucid account HELD (no written OK recorded), and it says how",
          b25.get("armed") is True and lu.get("armed") is False and any("NOT armed (no written OK from Lucid" in x for x in out), out)
    rok = AC.lucid_ok(NL, "2026-11-23")
    rows = TA.file_rows()
    lu = next(x for x in rows if x.get("nt_account") == NL)
    check("c. lucid-ok records the written yes and does NOT arm", rok["ok"] and lu["cli"].get("lucid_ok") == "2026-11-23" and lu.get("armed") is False, (rok, lu))
    check("c. lucid-ok on a non-Lucid account is refused", not AC.lucid_ok(TA.N25)["ok"])
    AC.arm(LIVE_PHRASE)
    lu = next(x for x in TA.file_rows() if x.get("nt_account") == NL)
    check("c. the next START BOT (typed phrase) arms it", lu.get("armed") is True)
    rc, out = quiet(AC.main, ["lucid-ok", "--name", "NOPE"])
    check("c. the CLI entry: lucid-ok on an unknown Name = NOT RECORDED, exit 1", rc == 1 and "NOT RECORDED" in out, out)
    return row


def router_for(tmp, rows):
    class Bot:
        cfg, state, ledger, state_path, _open_routed = {"adapter": "paper"}, {}, [], os.path.join(tmp, "live_state.json"), None
        clock = staticmethod(time.time)

        def _log(self, k, t):
            pass
    paper = [{**x, "adapter": "paper", "confirm": "", "armed": False} for x in rows]
    return MA.AccountRouter(Bot(), MA.specs_from_cfg({"adapter": "paper", "accounts": paper}), state_path=os.path.join(tmp, "acc_state.json"))


def test_sizing_hedge(tmp):
    rows = [x for x in TA.file_rows() if x.get("cli")]
    router = router_for(tmp, rows)
    L = next(a for a in router.accounts if a.spec.get("preset") == "lucid_pro_50k")
    M = next(a for a in router.accounts if a.spec.get("preset") != "lucid_pro_50k")
    now = time.time()
    worst, bad = 0.0, []
    for day_loss in (0.0, -400.0, -900.0, -1150.0):
        L.day_pnl = (lambda _d, v=day_loss: v)
        for risk in (5.0, 8.0, 12.0, 20.0, 30.0, 45.0, 60.0, 90.0):
            for model_q in (1, 10, 40, 80):
                ent = {"entry_t": int(now), "qty": model_q, "risk_pts": risk, "tgt_pts": risk * 3, "entry": 25000.0, "stop": 25000.0 - risk, "side": "buy"}
                q = int(L.qty_for(ent, now) or 0)
                loss = q * ((risk + sz.TW_DLL_SLIP) * sz.TW_PV + sz.TW_COMM)
                left = 1200.0 + day_loss
                worst = max(worst, loss)
                if q > 40 or (q and loss > left + 1e-6):
                    bad.append((day_loss, risk, model_q, q, round(loss, 2), left))
    check("d. Lucid sizing grid (4 day-losses x 8 stops x 4 model sizes): a full stop-out never exceeds the $1,200 daily loss left, never > 40 micros",
          not bad and worst > 0, (bad[:5], worst))
    L.day_pnl = (lambda _d: -1190.0)
    q = L.qty_for({"entry_t": int(now), "qty": 10, "risk_pts": 20.0, "tgt_pts": 60.0, "entry": 25000.0, "stop": 24980.0, "side": "buy"}, now)
    check("d. $10 of daily loss left: 1 micro's stop-out does not fit -> no trade (never sized up to 1)", q == 0, q)
    L.day_pnl = (lambda _d: 0.0)
    # e. hedging across firms
    L.open_t = 1_000
    L.ledger.append({"side": "buy", "entry_t": 1_000, "qty": 2})
    check("e. the Lucid account is LONG: a SHORT on any account (MFFU's too) is refused", "hedging guard" in (router.opposite_open(-1) or "")
          and router.opposite_open(1) is None, router.opposite_open(-1))
    L.open_t = None
    L.ledger.clear()
    M.open_t = 2_000
    M.ledger.append({"side": "sell", "entry_t": 2_000, "qty": 1})
    check("e. an MFFU account is SHORT: the Lucid account cannot go LONG", "hedging guard" in (router.opposite_open(1, exclude=L) or ""),
          router.opposite_open(1, exclude=L))


def test_clock():
    from engine import clock7 as C
    T = int(time.mktime(time.strptime("2026-11-23 12:00", "%Y-%m-%d %H:%M")))
    k = C.build({"a": [{"id": "lucid_2", "nm": "Zlarior LucidPro 50K #1", "lt": "2026-11-16", "sd": "2026-11-10"},
                       {"id": "b25k_2", "nm": "Zlarior 25K #2", "lt": "2026-11-16"}]}, None, T)
    r = {x["id"]: x for x in k["a"]}
    check("f. clock7: Lucid's 30 days (11-16 -> 12-16, ok, no keep-alive act day), MFFU keeps 7 (11-23)",
          r["lucid_2"]["hard"] == "2026-12-16" and r["lucid_2"]["lvl"] == "ok" and r["lucid_2"]["act"] is None and r["b25k_2"]["hard"] == "2026-11-23"
          and "Lucid last day" in C.line(r["lucid_2"]) and "MFFU last day" in C.line(r["b25k_2"]), k)


def main() -> int:
    test_rules()
    tmp = tempfile.mkdtemp(prefix="le_lucid_")
    saved = {k: getattr(G, k) for k in ("CFG", "SECOND_PATH", "ALLOW_PATH", "ACCOUNTS_PATH", "ANCHOR_PATH")}
    from engine import rapid
    saved_rp = rapid.PATH
    env = os.environ.get("NINJATRADER_FOLDER")
    try:
        test_cli(tmp)
        test_sizing_hedge(tmp)
    finally:
        for k, v in saved.items():
            setattr(G, k, v)
        rapid.PATH = saved_rp
        if env is None:
            os.environ.pop("NINJATRADER_FOLDER", None)
        else:
            os.environ["NINJATRADER_FOLDER"] = env
        shutil.rmtree(tmp, ignore_errors=True)
    test_clock()
    print(f"\nlucid: {sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
