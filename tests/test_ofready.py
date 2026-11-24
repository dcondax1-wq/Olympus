"""day-ofready 2026-11-24: engine/ofsum.py (per-day order-flow summaries) + research/orderflow/of_battery.py (the pre-registered
battery, research/orderflow/DESIGN.md). Synthetic ticks only, no data/ written, no network.
    python -X utf8 -m tests.test_ofready
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES: list = []
BANNED = ("engine.ninjatrader", "engine.live", "engine.tradovate", "engine.lit_live", "engine.account_b", "server")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"), flush=True)


def imports(path):
    t = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mod = ("engine." if n.level and "engine" in path else "") + (n.module or "")
            out |= {mod} | {f"{mod}.{a.name}".strip(".") for a in n.names}
    return out


def main():
    from engine import ofsum
    check("ofsum selftest (sums, footprint, prints, histogram, sides)", ofsum.selftest())
    imp = imports(os.path.join(ROOT, "engine", "ofsum.py"))
    check("ofsum imports nothing that can trade", not any(i.startswith(b) for i in imp for b in BANNED), imp)
    users = subprocess.run(["git", "grep", "-l", "ofsum", "--", "engine/live.py", "engine/lit_live.py", "server.py", "engine/ninjatrader.py"],
                           cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("nothing in the bot imports ofsum", users == "", users)
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "research", "orderflow", "of_battery.py"), "--selftest"],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    check("of_battery selftest (OF1/OF2 parity with of_study.prereg, 40-day gate, all 6 tests run)",
          r.returncode == 0 and "selftest: OK" in r.stdout, (r.stdout + r.stderr)[-400:])
    print(f"{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
