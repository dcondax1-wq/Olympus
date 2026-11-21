"""tools/site_refresh.py (day-archive 2026-11-20): the CRONOS-era builders run at site-build time, never fatal, never write the checkout.
No network, no browser: the steps are faked. python -m tests.test_site_refresh"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import site_refresh as R  # noqa: E402

ok = bad = 0


def check(name, cond, info=""):
    global ok, bad
    if cond:
        ok += 1; print(f"[PASS] {name}")
    else:
        bad += 1; print(f"[FAIL] {name}  -> {info}")


def main():
    check("the steps are Pantheon and Fates, each with an --out folder and a timeout",
          set(R.STEPS) == {"pantheon", "fates"} and all("--out" in cmd("X") and tmo > 0 for cmd, _, tmo in R.STEPS.values()))
    py = sys.executable
    good = (lambda d: [py, "-c", f"import os; open(os.path.join({d!r}, 'a.json'), 'w').write('{{}}')"], ("a.json",), 30)
    fail = (lambda d: [py, "-c", "raise SystemExit(3)"], ("b.json",), 30)
    slow = (lambda d: [py, "-c", "import time; time.sleep(5)"], ("c.json",), 1)
    saved = dict(R.STEPS)
    R.STEPS.clear(); R.STEPS.update({"good": good, "fail": fail, "slow": slow})
    try:
        before = sorted(os.listdir(R.WEB))
        with tempfile.TemporaryDirectory() as site:
            res = R.run(["good", "fail", "slow"], site, quiet=True)
            check("a good step lands in <site>/<app>/", res["good"][0] and os.path.isfile(os.path.join(site, "good", "a.json")), res)
            check("a failing or timed-out step is reported, never raised, and writes nothing", not res["fail"][0] and not res["slow"][0]
                  and not os.path.exists(os.path.join(site, "fail")) and not os.path.exists(os.path.join(site, "slow")), res)
        check("--site never writes the checkout (tools/web_public/ unchanged)", sorted(os.listdir(R.WEB)) == before)
    finally:
        R.STEPS.clear(); R.STEPS.update(saved)
    check("main() returns 0 even when every step fails (never fatal); --list works", R.main(["--list"]) == 0)
    print(f"{ok}/{ok + bad} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
