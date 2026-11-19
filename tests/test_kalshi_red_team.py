"""research/kalshi_red_team/verify.py (offline): exact Kalshi fees, the strictly-before timing check, time split, bootstrap,
multiple-testing bar and the verdicts, on small made-up trade lists. No network.

    python -m tests.test_kalshi_red_team"""
import json
import os
import sys
import tempfile
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research", "kalshi_red_team"))
import verify as V  # noqa: E402

RES = []


def check(name, ok):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name)


def row(ts, price, won, n=10, info=None, **kw):
    r = {"ts": ts, "info_ts": ts - 60 if info is None else info, "price": price, "contracts": n, "outcome": 1 if won else 0}
    r.update(kw)
    return r


def main():
    # 1. exact fees, rounded UP to the cent per order
    check("fee 100 @ 50c = $1.75", V.fee("0.50", 100) == Decimal("1.75"))
    check("fee 1 @ 50c rounds 1.75c up to 2c", V.fee("0.50", 1) == Decimal("0.02"))
    check("fee 10 @ 98c = 1.372c -> 2c", V.fee("0.98", 10) == Decimal("0.02"))
    check("fee 1 @ 1c = 0.0693c -> 1c", V.fee("0.01", 1) == Decimal("0.01"))
    check("fee 3 @ 33c = 4.6431c -> 5c", V.fee("0.33", 3) == Decimal("0.05"))
    check("maker fee 100 @ 50c (0.0175) = $0.44", V.fee("0.50", 100, V.MAKER_RATE) == Decimal("0.44"))
    one_order = [row(1000 + i, "0.10", False, n=1, order_id="A") for i in range(10)]
    split_orders = [row(1000 + i, "0.10", False, n=1, ticker="T%d" % i) for i in range(10)]
    a, _ = V.recompute(one_order)
    b, _ = V.recompute(split_orders)
    check("one order of 10 x 1 @ 10c is rounded once: $0.07", abs(sum(x["fee"] for x in a) - Decimal("0.07")) < Decimal("1e-9"))
    check("ten separate orders: $0.10", sum(x["fee"] for x in b) == Decimal("0.10"))
    m, _ = V.recompute([row(1000, "0.50", True, n=100, role="maker")])
    mf, _ = V.recompute([row(1000, "0.50", True, n=100, role="maker", maker_fee=True)])
    check("maker: no fee unless the series charges makers", m[0]["fee"] == 0 and mf[0]["fee"] == Decimal("0.44"))
    ix, _ = V.recompute([row(1000, "0.50", True, n=100, fee_rate="0.035")])
    check("fee_rate override (index markets 0.035)", ix[0]["fee"] == Decimal("0.88"))
    # 2. P&L per $1 on a known pair: 10 @ 40c win + 10 @ 40c loss, fee 0.168 -> 0.17 each
    v = V.verify([row(1000, "0.40", True, ticker="A"), row(2000, "0.40", False, ticker="B")], rules_tried=1, boot=200)
    check("net $ = 5.83 - 4.17", abs(v["all"]["net_usd"] - 1.66) < 1e-9)
    check("net per $1 = 1.66 / 8.34", abs(v["all"]["net_per_1"] - round(1.66 / 8.34, 4)) < 1e-9)
    check("break-even win rate = cost / contracts = 41.7%", abs(v["all"]["breakeven_win_rate"] - 0.417) < 1e-9)
    check("win rate 50%", abs(v["all"]["win_rate"] - 0.5) < 1e-12)
    ex, _ = V.recompute([row(1000, "0.40", False, exit_price="0.50")])
    check("sold before settlement: 5.00 - 0.18 exit fee - 4.17 cost = +0.65", abs(ex[0]["pnl"] - Decimal("0.65")) < Decimal("1e-9"))
    mk, mp = V.recompute([{"ts": 1000, "info_ts": 900, "price": "0.40", "contracts": 10, "mark_price": "0.55"}])
    check("not settled: valued at the mark, no exit fee (5.50 - 4.17)", abs(mk[0]["pnl"] - Decimal("1.33")) < Decimal("1e-9")
          and mk[0]["marked"] and not mp["no_outcome"])
    # 3. timing: information must be STRICTLY before the trade
    same = V.verify([row(1000, "0.40", True, info=1000), row(2000, "0.40", True)], rules_tried=1, boot=100)
    check("info at the trade time = look-ahead -> false", same["verdict"] == "false" and same["problem_counts"].get("lookahead") == 1)
    late = V.verify([row(1000, "0.40", True, info=1001)], rules_tried=1, boot=100)
    check("info after the trade = look-ahead", late["problem_counts"].get("lookahead") == 1)
    miss = V.verify([{"ts": 1000, "price": "0.4", "contracts": 1, "outcome": 1}], rules_tried=1, boot=100)
    check("missing info_ts is a failure", miss["verdict"] == "false" and miss["problem_counts"].get("missing_info_ts") == 1)
    st = V.verify([row(1000, "0.40", True, settle_ts=1000)], rules_tried=1, boot=100)
    check("a trade at or after settlement is a failure", st["problem_counts"].get("after_settle") == 1)
    iso = V.verify([{"ts": "2026-11-01T00:00:01Z", "info_ts": "2026-11-01T00:00:00Z", "price": "0.40", "contracts": 10, "outcome": 1}],
                   rules_tried=1, boot=100)
    check("ISO times work (1 s before is fine)", "lookahead" not in iso["problem_counts"])
    dup = V.verify([row(1000, "0.40", True, ticker="A", id="t1"), row(1000, "0.40", True, ticker="A", id="t1")], rules_tried=1, boot=100)
    check("the same trade id twice is a double count -> false", dup["problem_counts"].get("duplicates") == 1 and dup["verdict"] == "false")
    same = V.verify([row(1000, "0.40", True, ticker="A"), row(1000, "0.40", True, ticker="A")], rules_tried=1, boot=100)
    check("identical rows without ids (a sweep's prints) are only a warning", same["problem_counts"].get("same_rows") == 1
          and "duplicates" not in same["problem_counts"])
    junk = V.verify([{"ts": 1000, "info_ts": 900, "price": "", "contracts": "x", "outcome": 1}, row(2000, "0.40", True)], rules_tried=1, boot=100)
    check("a row with no price / bad contracts is flagged, not a crash", junk["verdict"] == "false" and junk["problem_counts"].get("bad_price") == 1)
    # 4. split, bootstrap, luck
    flip = [row(1000 + i, "0.50", False, ticker="L%d" % i) for i in range(20)] + [row(5000 + i, "0.50", True, ticker="W%d" % i) for i in range(20)]
    vf = V.verify(flip, rules_tried=1, boot=300)
    check("halves split at the median time", vf["first_half"]["n"] == 20 and vf["second_half"]["n"] == 20)
    check("halves that disagree are called out", not vf["halves_agree"] and any("disagree" in r for r in vf["reasons"]))
    vd = V.verify(flip, rules_tried=1, split="1970-01-01T01:00:00Z", boot=300)
    check("a given split date is used", vd["first_half"]["n"] == 20 and vd["split_at"].startswith("1970-01-01T01:00"))
    pat = [1, 1, 0, 1, 1, 0, 1, 0, 1, 1]
    good = [row(1000 + 3600 * i, "0.50", pat[i % 10] == 1, ticker="E%d" % i) for i in range(80)]
    vg = V.verify(good, rules_tried=1, boot=1000)
    check("a real edge, stated 1 rule tried -> holds", vg["verdict"] == "holds")
    lo, hi = vg["all"]["ci95"]
    check("the bootstrap range brackets the estimate", lo < vg["all"]["net_per_1"] < hi)
    check("the bootstrap is repeatable (seeded)", V.verify(good, rules_tried=1, boot=1000)["all"]["ci95"] == [lo, hi])
    vm = V.verify(good, rules_tried=100000, boot=1000)
    check("the same edge after 100,000 rules tried -> weak", vm["verdict"] == "weak" and any("multiple-testing" in r for r in vm["reasons"]))
    vu = V.verify(good, boot=300)
    check("rules tried not stated -> warned", vu["verdict"] == "weak" and any("not stated" in r for r in vu["reasons"]))
    check("bar for 1 rule = 1.645", abs(V.bar_t(1) - 1.6449) < 1e-3)
    check("bar for 100 rules = 3.29", abs(V.bar_t(100) - 3.2905) < 1e-3)
    check("2 of 8 positive in both halves by luck: 63%", abs(V.chance_both_halves(2, 8) - 0.6329) < 1e-3)
    check("0 of n is certain", abs(V.chance_both_halves(0, 8) - 1) < 1e-12)
    bad = V.verify([row(1000 + i, "0.90", i % 10 != 0, ticker="B%d" % i) for i in range(50)], rules_tried=1, boot=300)
    check("90% winners at 90c + fees lose -> false", bad["verdict"] == "false" and bad["all"]["net_per_1"] < 0)
    fm = V.verify([row(1000, "0.40", True, fee_reported="0.10", ticker="A"), row(2000, "0.40", True, ticker="B")], rules_tried=1, boot=100)
    check("a reported fee that is too small is listed", fm["problem_counts"].get("fee_mismatch") == 1)
    pm = V.verify([row(1000, "0.40", True, pnl_reported="5.83")], rules_tried=1, boot=100)
    check("a right reported P&L passes", "pnl_mismatch" not in pm["problem_counts"])
    rw = V.verify([row(1000, "0.40", False, reward="1.00", ticker="A"), row(2000, "0.40", False, reward="1.00", ticker="B")], rules_tried=1, boot=100)
    check("rewards are reported apart from fills", rw["all"]["reward_usd"] == 2.0 and rw["all"]["net_per_1"] < 0 < rw["all"]["net_per_1_with_reward"] + 1)
    # 5. the command line, JSON and CSV
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.json")
    json.dump({"rule": {"name": "demo", "rules_tried": 3}, "trades": good}, open(p, "w"))
    rc = V.main([p, "--out", os.path.join(d, "r.json"), "--boot", "200"])
    out = json.load(open(os.path.join(d, "r.json")))
    check("CLI on JSON writes the report", rc == 0 and out["rule"] == "demo" and out["rules_tried"] == 3)
    c = os.path.join(d, "t.csv")
    with open(c, "w") as f:
        f.write("ts,info_ts,price,contracts,outcome,ticker\n2026-11-01T10:00:00Z,2026-11-01T09:59:00Z,0.40,10,1,A\n"
                "2026-11-02T10:00:00Z,2026-11-02T10:00:00Z,0.40,10,1,B\n")
    rc2 = V.main([c, "--rules-tried", "1", "--boot", "100"])
    check("CLI on CSV: the look-ahead row makes it exit 2", rc2 == 2)
    n = sum(RES)
    print("\nkalshi red team verify: %d/%d %s" % (n, len(RES), "ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
