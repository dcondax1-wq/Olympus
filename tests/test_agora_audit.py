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

# one accent per app (2026-11-11): jarvis/apps.js is the table; the kit's APPS and each page's pre-paint say the same; none is neon;
# a tint is never shared, except the six AGORA palette colours themselves (new apps start on gold)
import re  # noqa: E402
WEB = os.path.join(ROOT, "tools", "web_public")
PALETTE = {"#c8a24a", "#e0b060", "#9c6b3c", "#7f8a52", "#c96a4a", "#4b7a99"}
apps = {m[0]: m[1].lower() for m in re.findall(r"app\('([a-z0-9]+)', *'[^']*', *'[a-z]+', *'(#[0-9a-fA-F]{6})'",
                                                open(os.path.join(WEB, "jarvis", "apps.js"), encoding="utf-8").read())}
kit = open(os.path.join(WEB, "olympus", "olympus.js"), encoding="utf-8").read()
kit = kit[kit.index("var APPS = {"):]
kit = {m[0]: m[1].lower() for m in re.findall(r"\b([a-z0-9]+): \['[^']*', *'[^']*', *'(#[0-9a-fA-F]{6})'\]", kit[:kit.index("};")])}
page = {}
for d in apps:
    ip = os.path.join(WEB, d, "index.html")
    m = os.path.isfile(ip) and re.search(r"oly-accent', '(#[0-9a-fA-F]{6})'", open(ip, encoding="utf-8").read())
    if m:
        page[d] = m.group(1).lower()
neon = [k for k, v in apps.items() if A.is_neon(v)]
check("accents: 60+ apps in the table, none neon", len(apps) >= 60 and not neon, str(neon))
bad = [k for k in apps if (k in kit and kit[k] != apps[k]) or (k in page and page[k] != apps[k])]
check("accents: the kit's APPS and every page's pre-paint agree with jarvis/apps.js", len(kit) >= 60 and len(page) >= 40 and not bad, str(bad))
seen = {}
for k, v in apps.items():
    seen.setdefault(v, []).append(k)
dup = {v: ks for v, ks in seen.items() if len(ks) > 1 and v not in PALETTE}
check("accents: a tint outside the six palette colours belongs to one app only", not dup, str(dup))
sys.exit(0 if ok else 1)
