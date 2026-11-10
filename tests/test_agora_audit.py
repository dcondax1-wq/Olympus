"""AGORA theme audit (tools/agora_audit.py): the static scan finds no hard FAIL in any app, and the scanner itself catches what it should.
Run: python -X utf8 -m tests.test_agora_audit   (static only, no browser)"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import agora_audit as A  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, extra))
    ok = ok and cond


# the scanner knows the banned things
check("neon cyan is neon", A.is_neon("#22d3ee"))
check("old violet is neon", A.is_neon("#a68bff"))
check("mint neon is neon", A.is_neon("#2ee59d"))
check("gold is not neon", not A.is_neon("#c8a24a"))
check("aegean is not neon", not A.is_neon("#4b7a99"))
check("olive is not neon", not A.is_neon("#7f8a52"))
check("terracotta is not neon", not A.is_neon("#c96a4a"))
check("hsl neon seen", bool(A.neon_rgba("color: hsl(280 90% 60%)")))

# the tree is clean
res = A.static_scan()
hard = {n: A.static_fail(r) for n, r in res.items() if A.static_fail(r)}
check("no app has a hard FAIL", not hard, str(hard))
check("theme-color is #14110e in every app page", all(not r["hard"]["theme"] for r in res.values()))
sys.exit(0 if ok else 1)
