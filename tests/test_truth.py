"""One number, every app (QA round 6, bug 2): the drawdown left, the balance and the data age come from ONE place, olympus/truth.js.

    python -X utf8 -m tests.test_truth

Node only (no browser). For the same home.json it runs the real code of every page that shows those numbers:
  Aegis (aegiscore.buildAccounts on truth.canonHome), Helios (helioscore.buildAccounts / build), NQ (nqcore.build), and Zenith Home
  (the root page's missioncore.js MissionUI.accounts on the published board, a classic script run in a node vm),
and checks that Zlarior / ATLAS show the same "Drawdown left" and balance everywhere, that the cloud paper twin of LIT never wins, that an old
PC report is not called "connected", and that the age line names its source. Cases: the real shape (board + accounts + second + live.pc),
the cloud twin listed first, a legacy file with accounts only, and junk.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
FAILS: list = []
N = [0]


def check(name, ok, detail=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        FAILS.append(name)


NOW = 1794433990          # 2026-11-11 21:53 UTC
HOME = {
    "built": "2026-11-11T20:54:00+00:00",
    "accounts": [
        {"id": "cloud_paper", "name": "Paper (cloud)", "plan": "MFFU 50K rules", "kind": "paper", "source": "cloud",
         "conn": {"t": NOW - 60, "connected": True}, "eval": {"balance": 48389.1, "floor": 48000.0, "room": 389.1, "mll": 2000.0, "dll": 1000.0}},
        {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "plan": "Builder 50K", "kind": "eval", "source": "pc",
         "conn": {"t": NOW - 5 * 86400, "connected": True}, "stats": {"avg_loss": -425},
         "eval": {"start_balance": 50000.0, "balance": 49313.54, "floor": 48168.2, "room": 1145.34, "mll": 2000.0, "dll": 1000.0, "dll_used": 0.0, "to_target": 3686.46, "target_balance": 53000.0},
         "pnl": {"today": 0.0, "week": 0.0}},
    ],
    "board": {"t": NOW - 60, "data_t": NOW - 5 * 86400,
              "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "balance": 49313.54, "floor": 48168.2, "room": 1145.34, "mll": 2000.0, "to_target": 3686.46, "target_balance": 53000.0, "today_pnl": 0.0, "status": "open"},
              "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "balance": 25182.19, "floor": 24359.95, "room": 822.24, "mll": 1000.0, "to_target": 1317.81, "target_balance": 26500.0, "today_pnl": -168.81, "status": "open"}},
    "second": {"pc_t": NOW - 5 * 86400, "account_b": {"eval": {"start_balance": 25000.0, "balance": 25182.19, "floor": 24359.95, "room": 822.24, "target": 26500.0, "dll": 600.0}}},
    "live": {"pc": {"t": NOW - 5 * 86400, "running": True, "blitz": {"t": NOW - 5 * 86400, "eval": {"start_balance": 25000, "balance": 24607.28, "floor": 24000, "room": 607.28, "mll": 1000}}}},
}
LEGACY = {"accounts": [
    {"id": "cloud_paper", "name": "Paper (cloud)", "plan": "MFFU 50K rules", "source": "cloud", "eval": {"room": 389.1, "mll": 2000}},
    {"id": "mffu50k_eval", "kind": "eval", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000, "balance": 50420, "dll": 1000, "dll_used": 100}, "pnl": {"today": 312}},
    {"id": "acctb", "eval": {"room": 240, "mll": 1000, "balance": 25080, "dll": 600, "dll_used": 60}, "stats": {"avg_loss": -150}, "pnl": {"today": -60}}]}

HARNESS = r"""
const fs = require('fs'), path = require('path'), vm = require('vm');
const [dir, now] = [process.argv[2], +process.argv[3]];
const cases = JSON.parse(fs.readFileSync(path.join(dir, 'cases.json'), 'utf8'));
(async () => {
  const T = await import(path.join(dir, 'truth.mjs')), A = await import(path.join(dir, 'aegiscore.mjs')), H = await import(path.join(dir, 'helioscore.mjs')), Q = await import(path.join(dir, 'nqcore.mjs'));
  const win = {}; vm.runInNewContext(fs.readFileSync(path.join(dir, 'missioncore.js'), 'utf8'), { window: win, document: undefined, console, Intl, Date, Math, Number, String, Object, Array, JSON, Map, Set });
  const out = {};
  for (const [name, home] of Object.entries(cases)) {
    const r = {};
    try {
      const c = T.canonHome(home, now), t = T.accountsOf(home);
      r.truth = { lit: [t.lit.has, t.lit.room, t.lit.balance, t.lit.src], atlas: [t.atlas.has, t.atlas.room, t.atlas.balance, t.atlas.src], blitz: [t.blitz.has, t.blitz.room, t.blitz.src] };
      r.ages = T.agesOf(home, now);
      r.aegisRaw = A.buildAccounts(home, null, null).accounts.map((a) => [a.key, a.room]);     // what Aegis read before the truth (home.accounts as published)
      const ag = A.buildAccounts(c, null, null).accounts; r.aegis = ag.map((a) => [a.key, a.has, a.room, a.balance, a.has && a.room != null ? A.drawdownLine(a.room, a.mll) : '']);
      const he = H.buildAccounts(c).accounts; r.helios = he.map((a) => [a.key, a.has, a.room, a.connected, a.has && a.room != null ? H.drawdownLine(a.room, a.mll) : '']);
      const hb = H.build({ home: c, events: null, money: null }, now * 1000); r.heliosSigns = hb.signs.map((s) => [s.id, s.ok, s.text]); r.heliosActs = hb.actions.map((x) => x.id);
      const nq = Q.build(c, now); r.nq = nq.bots.map((b) => [b.key, b.has, b.room, b.balance, b.ddLine]);
      const mi = win.MissionUI.accounts({ board: home && typeof home === 'object' ? home.board : null }); r.root = mi.map((a) => [a.key, a.room, a.balance]);
    } catch (e) { r.error = String(e && e.stack || e); }
    out[name] = r;
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def run():
    exe = shutil.which("node")
    if not exe:
        check("node is installed (skipped: no node)", True)
        return None
    tmp = tempfile.mkdtemp(prefix="truth-")
    try:
        shutil.copy(os.path.join(WEB, "olympus", "truth.js"), os.path.join(tmp, "truth.mjs"))
        for app in ("aegis", "helios", "nq"):
            shutil.copy(os.path.join(WEB, app, f"{app}core.js"), os.path.join(tmp, f"{app}core.mjs"))
        shutil.copy(os.path.join(WEB, "missioncore.js"), os.path.join(tmp, "missioncore.js"))
        real = json.loads(json.dumps(HOME)); real["accounts"].reverse()          # the PC's row first, the cloud twin second
        twin_first = json.loads(json.dumps(HOME))
        no_board = json.loads(json.dumps(HOME)); no_board.pop("board")
        cases = {"real": real, "twin_first": twin_first, "no_board": no_board, "legacy": LEGACY, "junk": {"accounts": "x", "board": 5, "live": [], "second": None}}
        with open(os.path.join(tmp, "cases.json"), "w", encoding="utf-8") as fh:
            json.dump(cases, fh)
        h = os.path.join(tmp, "harness.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, tmp, str(NOW)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-1500:])
            return {"_error": r.stderr[-600:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    o = run()
    if o is None:
        return 0
    check("the node harness runs", "_error" not in o and all("error" not in v for v in o.values()), o.get("_error") or {k: v.get("error") for k, v in o.items() if "error" in v})
    if "_error" in o:
        return 1
    R = o["real"]
    check("truth: Zlarior $1,145.34 and ATLAS $822.24 from the published board, BLITZ $607.28 from the PC's paper block",
          R["truth"]["lit"] == [True, 1145.34, 49313.54, "board.lit"] and R["truth"]["atlas"] == [True, 822.24, 25182.19, "board.atlas"] and R["truth"]["blitz"] == [True, 607.28, "live.pc.blitz"], R["truth"])
    for name in ("real", "twin_first"):
        C = o[name]
        line_z, line_a = "Drawdown left $1,145 of $2,000 max loss", "Drawdown left $822 of $1,000 max loss"
        check(f"{name}: Aegis shows Zlarior {line_z!r} and ATLAS {line_a!r}", C["aegis"][0][2] == 1145.34 and C["aegis"][0][4] == line_z and C["aegis"][1][2] == 822.24 and C["aegis"][1][4] == line_a, C["aegis"])
        check(f"{name}: Helios shows the same two lines", C["helios"][0][4] == line_z and C["helios"][1][4] == line_a, C["helios"])
        check(f"{name}: NQ shows the same two lines", C["nq"][0][4] == line_z and C["nq"][1][4] == line_a, C["nq"])
        root = {k: (room, bal) for k, room, bal in C["root"]}
        check(f"{name}: Zenith Home (MissionUI on the board) has the same room and balance", root.get("lit") == (1145.34, 49313.54) and root.get("atlas") == (822.24, 25182.19), C["root"])
        same_bal = C["aegis"][0][3] == C["nq"][0][3] == root.get("lit", (0, 0))[1] and C["aegis"][1][3] == C["nq"][1][3] == root.get("atlas", (0, 0))[1]
        check(f"{name}: the balance is the same in Aegis, NQ and Home", same_bal, [C["aegis"], C["nq"], C["root"]])
    check("before the truth: Aegis read the cloud paper twin's $389 as Zlarior and had no ATLAS when the twin came first (the bug this test guards)",
          o["twin_first"]["aegisRaw"][0] == ["zlarior", 389.1] and o["twin_first"]["aegisRaw"][1] == ["atlas", None], o["twin_first"]["aegisRaw"])
    nb = o["no_board"]
    check("no board: the PC's own account row wins over the cloud paper twin ($1,145, not $389) in Aegis, Helios and NQ; ATLAS from second.account_b",
          nb["aegis"][0][2] == 1145.34 and nb["helios"][0][2] == 1145.34 and nb["nq"][0][2] == 1145.34 and nb["aegis"][1][2] == 822.24 and nb["nq"][1][2] == 822.24, [nb["aegis"], nb["nq"]])
    L = o["legacy"]
    check("legacy accounts-only file: Zlarior $1,420 and ATLAS $240 in Aegis, Helios and NQ alike (the cloud twin never counts)",
          [a[2] for a in L["aegis"][:2]] == [1420, 240] and [a[2] for a in L["helios"][:2]] == [1420, 240] and [a[2] for a in L["nq"][:2]] == [1420, 240], [L["aegis"], L["helios"], L["nq"]])
    check("legacy: a 'connected' with no report time is kept (we cannot tell it is old)", L["helios"][0][3] is True, L["helios"])
    check("an old PC report (5 days) is not called connected: Helios says 'No fresh word from the bots', not 'The bots are connected'",
          R["helios"][0][3] is None and any(s[0] == "bots" and not s[1] and s[2] == "No fresh word from the bots" for s in R["heliosSigns"]), R["heliosSigns"])
    check("Helios flags the 5-day-old account numbers (feeds_old) because the truth sets home.t to the PC report", "feeds_old" in R["heliosActs"], R["heliosActs"])
    A = R["ages"]
    check("the age line names both sources: 'Numbers from the PC report 5 days ago (cloud copy 59 minutes old).'",
          A["line"] == "Numbers from the PC report 5 days ago (cloud copy 59 minutes old)." and A["stale"] and A["silent"] and A["pc"]["text"] == "PC report 5 days ago", A)
    J = o["junk"]
    check("junk never throws and gives no numbers", "error" not in J and not any(a[1] for a in J["aegis"]) and not any(b[1] for b in J["nq"]), J)
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
