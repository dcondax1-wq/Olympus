"""research/kalshi_edge_K8 (Kalshi commodity 15-minute markets, research only, offline): fee rounding, the roll calendar,
the friend's posted wins re-computed from contracts x price, and the flat-stake bet maths. No network."""
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "kalshi_edge_K8"))
import k8lib  # noqa: E402

RES = []


def check(name, ok):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def main():
    # Kalshi taker fee 0.07*C*p*(1-p), rounded up to the cent on the whole order
    check("fee 29 @ 49c = $0.51", abs(k8lib.fee(0.49, 29) - 0.51) < 1e-9)
    check("fee 36 @ 41c = $0.61", abs(k8lib.fee(0.41, 36) - 0.61) < 1e-9)
    check("fee rounds up (13 @ 63c = 0.2121 -> 0.22)", abs(k8lib.fee(0.63, 13) - 0.22) < 1e-9)
    # the friend's posted wins: contracts x (1 - price) - fee (posted +$14.28 and +$20.63)
    check("friend silver up 29 @ 49c", abs(29 * 0.51 - k8lib.fee(0.49, 29) - 14.28) < 0.011)
    check("friend gold up 36 @ 41c", abs(36 * 0.59 - k8lib.fee(0.41, 36) - 20.63) < 0.011)
    # roll window = 5th..9th business day (US holidays skipped): Labor Day 2026-09-07 is skipped
    sep = k8lib.gsci_roll_days(2026, 9)
    check("Sep roll days", sep == [datetime.date(2026, 9, d) for d in (8, 9, 10, 11, 14)])
    nov = k8lib.gsci_roll_days(2026, 11)
    check("Nov roll days", nov == [datetime.date(2026, 11, d) for d in (6, 9, 10, 11, 12)])
    check("Dec roll days", k8lib.gsci_roll_days(2026, 12)[0] == datetime.date(2026, 12, 7))
    # flat-stake bet: $15 at 50c = 30 contracts, fee 0.53
    net, cost = k8lib.pnl_taker(0.50, True, 15.0)
    check("flat $15 win at 50c", abs(cost - (15.0 + 0.53)) < 1e-9 and abs(net - (30 - cost)) < 1e-9)
    net, cost = k8lib.pnl_taker(0.50, False, 15.0)
    check("flat $15 loss at 50c", abs(net + cost) < 1e-9)
    check("event code -> ET date", k8lib.day_of("26NOV12") == datetime.date(2026, 11, 12))
    n = sum(RES)
    print(f"\nkalshi k8: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
