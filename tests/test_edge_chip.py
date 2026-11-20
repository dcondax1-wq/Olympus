"""ZEUS edge chip (2026-11-18): the edge-health light where the owner looks for trading (Board, Trading, MFFU view), with ATLAS.
  a. tools/edge_health.tiny: <= 120 bytes even with big numbers, G / A / R letters, ATLAS = fixed-size R-PF (not eval $);
     the committed research/lab/edge_health.json carries an ATLAS light + card, and tools/web_public/edge.json = its tiny
  b. tools/edge_pc (the PC side, no pandas): read_tiny (missing / junk / too big / too old -> None), pc_due (once an ET day after
     17:00 ET, LE_EDGE=0 off, Windows only unless LE_EDGE=1, 3 tries a day), maybe_run (spawn_fn, LE_PR_NO_NET never spawns)
  c. tools/pc_report.lite carries "eh" and drops it before "accounts" when too big; pc_report starts the daily hook
  d. edge_chip.js in node: the exact chip line, ATLAS row, the PC's fresher day wins, junk -> null, the tap text (nothing
     automatic, ZEUS Lab will propose, the AMBER / RED buy rule)
  e. the pages: Board, Trading, MFFU load ../edge_chip.js and hold a [data-edge-chip]; board.js / mffu.js hand over the PC
     status; edge_chip.js builds no markup from data
    python -X utf8 -m tests.test_edge_chip
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []
NOW = 1794967830                                     # 2026-11-17 21:10 ET


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:300]}"))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def part_a():
    from tools import edge_health as EH
    big = {"built": "2026-11-18T02:10:30+00:00",
           "card": {"light": "AMBER", "data_to": "2026-11-17", "pf40": 99.0, "pf40_2026_h1": 12.345,
                    "atlas": {"light": "RED", "pf_r40": 99.0, "pf_r40_2026_h1": 10.55, "data_to": "2026-11-17"}}}
    t = EH.tiny(big)
    check("a. tiny: <= 120 bytes with the biggest numbers, letters G/A/R, ATLAS row with its own data day",
          EH._bytes(t) <= 120 and t["z"][0] == "A" and t["a"][0] == "R" and t["a"][3] == "2026-11-17" and t["t"] > 1.7e9, t)
    d = json.loads(read(EH.OUT))
    ac = (d.get("card") or {}).get("atlas") or {}
    check("a. the committed edge_health.json: ATLAS light from fixed-size R (pf_r), its 2026 baseline, the eval-sized $ PF kept apart",
          ac.get("light") in ("GREEN", "AMBER", "RED") and isinstance(ac.get("pf_r40"), (int, float)) and isinstance(ac.get("pf_r40_2026_h1"), (int, float))
          and "usd_pf40_eval_sized" in ac and (d["atlas"].get("light") or {}).get("cuts"), ac)
    w = d["atlas"]["windows"]["40"]["now"]
    # pin moved 2026-11-20 (day-atlasedge): ATLAS input is now run atlas_fresh_fixed (fixed $250, data to Nov 19), was the eval-path run to Oct 16 (1.89 / 1.41)
    check("a. ATLAS last 40 R-PF = R won / R lost of the stored run (atlas_fresh_fixed to Nov 19: R-PF 2.38, $ PF 2.27 at a fixed $250)",
          w.get("pf_r") is not None and abs(w["pf_r"] - 2.38) < 0.05 and abs((w.get("pf") or 0) - 2.27) < 0.05, w)
    site = json.loads(read(EH.SITE))
    check("a. tools/web_public/edge.json = the tiny result of the committed run", site.get("kind") == "le-edge" and site.get("eh") == d.get("tiny")
          and EH._bytes(site["eh"]) <= 120, site)
    bots = site.get("bots") or {}
    check("a. edge.json bots (night-zask, ZEUS 'trades per week'): Zlarior + ATLAS last-40 trades/week, win %, PF, $/month, light = the run",
          bots == EH.site_bots(d) and bots["lit"]["tpw"] == d["lit"]["windows"]["40"]["now"]["tpw"] and bots["lit"]["light"] == d["card"]["light"]
          and bots["atlas"]["usd_month"] == w.get("usd_month") and all(k in bots["lit"] for k in ("n", "tpw", "win", "pf", "usd_month", "to")), bots)


def part_b():
    from tools import edge_pc as P
    tmp = tempfile.mkdtemp(prefix="edge_pc_")
    try:
        p = os.path.join(tmp, "tiny.json")
        check("b. read_tiny: missing -> None", P.read_tiny(p, now=NOW) is None)
        for junk in ("{", "[1]", json.dumps({"z": "x"}), json.dumps({"z": ["G"], "pad": "x" * 200, "t": NOW})):
            open(p, "w").write(junk)
            if P.read_tiny(p, now=NOW) is not None:
                check("b. read_tiny: junk / too big -> None", False, junk)
                break
        else:
            check("b. read_tiny: junk / too big -> None", True)
        good = {"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["A", 1.9, 2.8, "2026-11-17"], "t": NOW - 3600}
        P._write_json(p, good)
        check("b. read_tiny: good -> as written; over 4 days old -> None",
              P.read_tiny(p, now=NOW) == good and P.read_tiny(p, now=NOW + 5 * 86400) is None)
        env = {"LE_EDGE": "1"}
        # NOW - 3600 = 20:10 ET the same day: done for today; next day 10:00 ET: still done (under 30 h); next day 17:30 ET: due
        nxt10 = NOW + 13 * 3600 - 600 + 3600            # 2026-11-18 10:00 ET
        nxt1730 = NOW + 20 * 3600 + 20 * 60              # 2026-11-18 17:30 ET
        check("b. pc_due: done today after 17:00 ET; the next morning still done; the next day after 17:00 ET due",
              P.pc_due(NOW, p, env)[0] is False and P.pc_due(nxt10, p, env)[0] is False and P.pc_due(nxt1730, p, env)[0] is True,
              [P.pc_due(x, p, env) for x in (NOW, nxt10, nxt1730)])
        check("b. pc_due: LE_EDGE=0 off; no result yet = due at once; Linux without LE_EDGE=1 never (the cloud)",
              P.pc_due(nxt1730, p, {"LE_EDGE": "0"})[0] is False and P.pc_due(NOW, os.path.join(tmp, "x", "tiny.json"), env)[0] is True
              and (os.name == "nt" or P.pc_due(nxt1730, p, {})[0] is False))
        seen = []
        pid = P.maybe_run(nxt1730, say=seen.append, env=env, spawn_fn=lambda: 4242, out_dir=tmp)
        st = json.loads(read(os.path.join(tmp, "state.json")))
        check("b. maybe_run: spawns once, writes state (day + tries), then 'started under an hour ago'",
              pid == 4242 and st["tries"] == 1 and st["day"] == "2026-11-18" and P.maybe_run(nxt1730 + 60, say=seen.append, env=env,
                                                                                            spawn_fn=lambda: 1, out_dir=tmp) is None, (pid, st))
        P._write_json(os.path.join(tmp, "state.json"), {"started": 0, "day": "2026-11-18", "tries": 3})
        check("b. maybe_run: 3 tries a day without a result -> stops for the day",
              P.maybe_run(nxt1730, say=seen.append, env=env, spawn_fn=lambda: 1, out_dir=tmp) is None)
        check("b. maybe_run: LE_PR_NO_NET=1 (the PC report's tests) never starts a real child",
              P.maybe_run(nxt1730, say=seen.append, env={"LE_EDGE": "1", "LE_PR_NO_NET": "1"}, out_dir=os.path.join(tmp, "y")) is None)
        check("b. tools/edge_pc.py imports no pandas / numpy (the 15-minute report stays light)",
              not re.search(r"^\s*(import|from)\s+(pandas|numpy)", read(os.path.join(ROOT, "tools", "edge_pc.py")), re.M))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_c():
    os.environ.setdefault("LE_PR_NO_NET", "1")
    from tools import pc_report as R
    from engine import board_events
    board_events.status_block = lambda *a, **k: None       # this machine's Board events stay out of the size test
    eh = {"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["A", 1.9, 2.8, "2026-11-17"], "t": NOW}
    L = {"accounts": [{"id": "lit_eval", "name": "Zlarior", "plan": "builder50k", "eval": {"balance": 50100.0, "room": 1900.0}}]}
    snap = {"t": NOW, "hb_t": NOW - 60, "live": L, "hb": {}, "server": True, "nt": True, "market_open": False, "mode": "live", "eh": eh}
    lt = R.lite(snap)
    check("c. pc_report.lite carries eh as is (<= 120 bytes) under the ntfy cap", lt.get("eh") == eh and R._size(lt) <= R.MAX_STATUS_BYTES, lt.get("eh"))
    cut = R.lite(snap, max_bytes=R._size(lt) - 20)
    check("c. too big: eh goes before the accounts block", "eh" not in cut and cut.get("accounts"), sorted(cut))
    no = R.lite({**snap, "eh": None})
    check("c. no result on the PC -> no eh key", "eh" not in no)
    src = read(os.path.join(ROOT, "tools", "pc_report.py"))
    check("c. pc_report reads data/edge/tiny.json into the snapshot and starts the daily hook (soft)",
          'snap["eh"] = _ep.read_tiny(' in src and "_ep.maybe_run(" in src)


HARNESS = r"""
const C = require(process.argv[2]);
const o = {};
const site = { kind: 'le-edge', eh: { d: '2026-11-06', z: ['G', 3.84, 3.91], a: ['A', 1.89, 2.83, '2026-10-16'], t: 1794967830 } };
const pcNew = { eh: { d: '2026-11-17', z: ['A', 2.2, 3.9], a: ['R', 0.8, 2.8, '2026-11-17'], t: 1795000000 } };
const pcOld = { eh: { d: '2026-11-01', z: ['R', 0.5, 3.9], t: 1796000000 } };
o.siteOnly = C.pick(site, null);
o.pcWins = C.pick(site, pcNew);
o.siteWins = C.pick(site, pcOld);
o.junk = [C.pick(null, null), C.pick({ eh: { d: 'x', z: ['G'] } }, { eh: 3 }), C.lines(null), C.valid({ d: '2026-11-06', z: ['Q', 1, 2] })];
o.lines = C.lines(site.eh, Date.parse('2026-11-10T12:00:00Z') / 1000);
o.linesOld = C.lines(site.eh, Date.parse('2026-11-18T12:00:00Z') / 1000);
o.linesPc = C.lines(pcNew.eh, Date.parse('2026-11-18T12:00:00Z') / 1000);
o.helpG = C.help({ d: '2026-11-06', z: ['G', 3, 3], a: ['G', 2, 2, '2026-11-06'] });
o.helpA = C.help(site.eh);
o.helpR = C.help(pcNew.eh);
console.log(JSON.stringify(o));
"""


def part_d():
    exe = shutil.which("node")
    if not exe:
        check("d. node is installed (the chip's rules run in node)", False, "no node")
        return
    tmp = tempfile.mkdtemp(prefix="edge_chip_")
    try:
        h = os.path.join(tmp, "h.cjs")
        open(h, "w").write(HARNESS)
        r = subprocess.run([exe, h, os.path.join(WEB, "edge_chip.js")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("d. edge_chip.js runs in node", False, r.stderr[-500:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    L = o["lines"]
    check("d. the chip line, exactly: 'ZEUS edge: GREEN · last 40 sessions PF 3.8 vs 2026 3.9 · data to Nov 6'",
          L["main"] == "ZEUS edge: GREEN · last 40 sessions PF 3.8 vs 2026 3.9 · data to Nov 6" and L["level"] == "good", L)
    check("d. ATLAS the same way, said to be fixed size: 'ATLAS: AMBER · last 40 sessions PF 1.9 vs 2026 2.8 (fixed size) · data to Oct 16' (+ old: 25 days)",
          L["atlas"] == "ATLAS: AMBER · last 40 sessions PF 1.9 vs 2026 2.8 (fixed size) · data to Oct 16 (old)" and L["atlasLevel"] == "warn", L)
    check("d. data over a week old says (old)", o["linesOld"]["main"].endswith("data to Nov 6 (old)") and o["linesOld"]["atlas"].endswith("(old)"), o["linesOld"])
    check("d. the PC's later data day wins over the cloud copy; an older PC day loses even when built later; site only -> site",
          o["pcWins"]["src"] == "pc" and o["pcWins"]["eh"]["d"] == "2026-11-17" and o["siteWins"]["src"] == "site" and o["siteOnly"]["src"] == "site", o)
    check("d. junk in -> null (no chip), never throws", o["junk"] == [None, None, None, None], o["junk"])
    check("d. RED / AMBER rows", o["linesPc"]["light"] == "AMBER" and o["linesPc"]["atlasLevel"] == "bad" and "data to Nov 17" in o["linesPc"]["main"], o["linesPc"])
    allh = " ".join(o["helpG"] + o["helpA"] + o["helpR"])
    check("d. tap text: what it means, nothing automatic, ZEUS Lab will propose, the buy rule (AMBER wait for a payout, RED do not buy)",
          "last 40 sessions" in allh and "Nothing automatic" in allh and "ZEUS Lab will propose" in allh and "Wait for the next payout" in allh
          and "Do not buy a new eval while RED" in allh and "fixed size" in allh)
    check("d. 'now' line follows the worst light: GREEN nothing to do, AMBER (ATLAS) wait, RED (ATLAS) ZEUS Lab will propose",
          o["helpG"][4].startswith("Now GREEN") and o["helpA"][4].startswith("Now AMBER") and o["helpR"][4].startswith("Now RED")
          and "ZEUS Lab will propose" in o["helpR"][4], [o["helpG"][4], o["helpA"][4], o["helpR"][4]])


def part_e():
    js = read(os.path.join(WEB, "edge_chip.js"))
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js)]
    check("e. edge_chip.js: text only (no innerHTML / eval), reads only ../edge.json and the PC status, sends nothing",
          not bad and "textContent" in js and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|POST|https?://", js), bad)
    for page, js_name, call in (("board/index.html", "board/board.js", "EDGE_CHIP.update(lite)"), ("business/mffu.html", "business/mffu.js", "EDGE_CHIP.update(lite)"),
                                ("trading/index.html", None, None)):
        html = read(os.path.join(WEB, page))
        ok = '<script src="../edge_chip.js' in html and re.search(r'<div id="\w+" data-edge-chip data-edge-src="\.\./edge\.json"', html)
        if js_name:
            ok = ok and call in read(os.path.join(WEB, js_name))
        else:
            ok = ok and "data-edge-feed" in html and html.index('id="zeusEdge"') < html.index('id="todayCard"')
        check(f"e. {page}: loads ../edge_chip.js and shows the chip" + (" (the page hands over its PC status)" if js_name else " (top of the page, reads the PC status itself)"),
              ok)


def main():
    print("ZEUS edge chip")
    for f in (part_a, part_b, part_c, part_d, part_e):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} ran", False, f"{e.__class__.__name__}: {e}")
    n, ok = len(RES), sum(RES)
    print(f"{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
