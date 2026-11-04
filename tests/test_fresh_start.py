"""Fresh start on a new PC with no state pack (owner 2026-11-04): scripts/move_bot.ps1 -Fresh, the site launcher
tools/web_public/pc/FRESH_START.ps1, FRESH_START.bat and `python -m engine.eval_life --anchor-from-site`.

    python -X utf8 -m tests.test_fresh_start

1. Static: menu choice 3, the -Fresh path, the launcher asks first, the build copies pc/, nothing arms live trading, the old
   "5-minute LE_BarFeed chart" text is gone from the new-PC text (LE_Feed no-chart mode replaced it).
2. With pwsh (Linux PowerShell 7; skipped when missing): -Fresh -DryRun with a mocked heartbeat file (LE_HEARTBEAT_FILE) and a
   fake host name (LE_FAKE_HOST): another PC beat 1 min ago -> REFUSES (exit 1, plain message, nothing installed); a young
   site copy that showed it alive -> refuses; another PC silent for 50 min -> goes on; the same host -> goes on; -Force
   overrides; an unreadable heartbeat -> asks (no answer = stops). The real-site shape (live.pc.t / live.pc.host) is used.
3. Python: the anchors the published board implies (home.json shape: board.lit / board.atlas), taken back to the previous
   weekday's close, Y/N confirm, saved through eval_life.save_anchor into a temp file (never the owner's data/).
Not run here: a real Windows 5.1 host, winget, git clone, the real site read.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:700]})" if detail and not cond else ""), flush=True)
    return bool(cond)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------------------ static
def static():
    ps = read("scripts/move_bot.ps1")
    check("move_bot.ps1: -Fresh switch and menu choice 3", "[switch]$Fresh" in ps and "3 = No old PC: start fresh here" in ps)
    check("move_bot.ps1: refuses with the plain message", "shut the Surface down first, wait 3 minutes, run this again" in ps)
    check("move_bot.ps1: 6-minute rule and -Force override", "$BeatFreshS = 360" in ps and "if ($Force)" in ps)
    check("move_bot.ps1: reads the published heartbeat (live.pc.host / t)", "live.pc.t" in ps and "live.pc.host" in ps and "demetrades2000-coder.github.io/nq-dashboard/home.json" in ps)
    check("move_bot.ps1: eval numbers step and NO_CHART_MODE, then ONE_TIME_SETUP",
          ps.index("--anchor-from-site") < ps.index("no_chart_mode.ps1") < ps.index("ONE_TIME_SETUP.bat", ps.index("no_chart_mode.ps1")))
    new = ps[ps.index("# ================================================================== new PC: set up"):]
    check("-NewPC text: LE_Feed no-chart mode, not the 5-minute LE_BarFeed chart", "NO_CHART_MODE" in new and "5-minute chart" not in new)
    fresh = ps[ps.index("if ($Fresh) {"):ps.index("# ================================================================== new PC: set up")]
    check("-Fresh never arms live trading (no live switch, no phrase, no .env write)",
          not re.search(r"LE_LIVE|ARMED|\.env|Set-Content|Out-File|--arm|phrase\s*=", fresh), re.findall(r"LE_LIVE|ARMED|\.env|Set-Content|Out-File", fresh))
    check("-Fresh asks before anything (Read-Host before the safety check)", fresh.index("Read-Host") < fresh.index("Read-Beat"))
    ln = read("tools/web_public/pc/FRESH_START.ps1")
    check("launcher: shows the plan and asks Y before downloading", ln.index("Read-Host") < ln.index("Invoke-WebRequest") and "Live trading is NOT turned on" in ln)
    check("launcher: runs the site copy with -Fresh", "pc'" in ln and "move_bot.ps1" in ln and "-Fresh" in ln)
    for f in ("scripts/move_bot.ps1", "tools/web_public/pc/FRESH_START.ps1"):
        raw = open(os.path.join(ROOT, f), "rb").read()
        try:
            raw.decode("ascii")
            ok = True
        except UnicodeDecodeError:
            ok = raw.startswith(b"\xef\xbb\xbf")
        check(f"{f}: ASCII (or BOM)", ok)
    bat = open(os.path.join(ROOT, "FRESH_START.bat"), "rb").read()
    check("FRESH_START.bat: CRLF, runs the one line", b"\n" not in bat.replace(b"\r\n", b"") and b"irm https://demetrades2000-coder.github.io/nq-dashboard/pc/FRESH_START.ps1 | iex" in bat)
    b = read("tools/build_web_dashboard.py")
    check("build: copies pc/ and move_bot.ps1 to the site", 'os.path.join(WEB, "pc")' in b and '"move_bot.ps1"' in b)
    sw = read("tools/web_public/sw.js")
    check("sw.js untouched by pc/ (plain files, no worker bump)", "'pc/'" not in sw)


# ------------------------------------------------------------------------------------------------------------- pwsh
def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh")
    return p if p and os.path.exists(p) else None


def run_fresh(pwsh, beat, host, extra=(), stdin=""):
    td = tempfile.mkdtemp(prefix="le_fresh_")
    try:
        hb = os.path.join(td, "hb.json")
        if beat is not None:
            with open(hb, "w", encoding="utf-8") as fh:
                fh.write(beat if isinstance(beat, str) else json.dumps(beat))
        env = dict(os.environ, LE_HEARTBEAT_FILE=hb, LE_FAKE_HOST=host, USERPROFILE=td, HOME=td)
        r = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-File", os.path.join(ROOT, "scripts", "move_bot.ps1"), "-Fresh", "-DryRun", *extra],
                           capture_output=True, text=True, env=env, timeout=120, input=stdin)
        return r.returncode, r.stdout + r.stderr
    finally:
        shutil.rmtree(td, ignore_errors=True)


def home_shape(age_s, host, built_age_s=None, now=None):
    """The published home.json shape the script reads: built, live.pc{t, host}."""
    now = now or int(time.time())
    h = {"live": {"pc": {"present": True, "t": now - age_s, "host": host}}, "board": {"data_t": now - age_s, "host": host}}
    if built_age_s is not None:
        h["built"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now - built_age_s))
    return h


def pwsh_cases(pwsh):
    rc, out = run_fresh(pwsh, home_shape(60, "OLDPC"), "MAINPC")
    check("other PC beat 1 min ago -> refuses (exit 1)", rc == 1, out)
    check("  plain message", "shut the Surface down first, wait 3 minutes, run this again" in out and "OLDPC" in out, out)
    check("  nothing installed / cloned", "Would" not in out and "Dry run" not in out, out)
    rc, out = run_fresh(pwsh, home_shape(60, "oldpc"), "MAINPC", ("-Force",))
    check("  -Force overrides", rc == 0 and "-Force" in out and "Dry run" in out, out)
    rc, out = run_fresh(pwsh, home_shape(500, "OLDPC", built_age_s=300), "MAINPC")
    check("site copy built 5 min ago that showed the old PC alive 3 min before -> refuses (can have stopped since, wait 15)",
          rc == 1 and "15 minutes" in out, out)
    rc, out = run_fresh(pwsh, home_shape(3000, "OLDPC", built_age_s=300), "MAINPC")
    check("other PC silent for 50 min -> goes on", rc == 0 and "No other PC has sent a heartbeat" in out and "Dry run" in out, out)
    rc, out = run_fresh(pwsh, home_shape(3000, "OLDPC", built_age_s=3000), "MAINPC")
    check("old site copy (50 min) -> goes on", rc == 0, out)
    rc, out = run_fresh(pwsh, home_shape(30, "MAINPC"), "mainpc")
    check("same host beating (a re-run on this PC, any letter case) -> goes on", rc == 0 and "from this PC" in out, out)
    rc, out = run_fresh(pwsh, {"t": int(time.time()) - 20, "host": "OLDPC"}, "MAINPC")
    check("plain heartbeat.json shape also refuses", rc == 1, out)
    rc, out = run_fresh(pwsh, "not json at all", "MAINPC", stdin="no\n")
    check("unreadable heartbeat (dry run) -> says so and carries on only because it is a dry run",
          rc == 0 and "Could not read the cloud heartbeat" in out, out)


# ------------------------------------------------------------------------------------------------------------ python
def board(today="2026-11-04", lit_bal=49313.54, pnl=0.0):
    return {"board": {"today": today,
                      "lit": {"broker": "MFFUEVBLDR602936016", "balance": lit_bal, "floor": 48168.2, "today_pnl": pnl, "mll": 2000.0},
                      "atlas": {"broker": "MFFUEVBLDR602936017", "balance": 25351.0, "floor": 24351.0, "today_pnl": 0.0, "mll": 1000.0}}}


def python_cases():
    from engine import eval_life as EL
    rows = EL.anchors_from_board(board())
    lit, atl = rows
    check("anchors: 50K floor 48,168.20 / 25K floor 24,351.00 from the board", lit["floor"] == 48168.2 and atl["floor"] == 24351.0 and lit["room"] == 1145.34 and atl["room"] == 1000.0, rows)
    check("anchors: as_of is the previous weekday (Wed 11-04 -> Tue 11-03; Mon 11-09 -> Fri 11-06)",
          lit["as_of"] == "2026-11-03" and EL.anchors_from_board(board("2026-11-09"))[0]["as_of"] == "2026-11-06")
    check("anchors: today's P&L is taken back out of the balance", EL.anchors_from_board(board(pnl=150.0, lit_bal=49463.54))[0]["balance"] == 49313.54)
    check("anchors: LIT = main account, ATLAS = its own account name", lit["account"] is None and atl["account"] == "MFFUEVBLDR602936017")
    check("anchors: empty / bad board -> nothing", EL.anchors_from_board({}) == [] and EL.anchors_from_board({"board": {"today": "x"}}) == [])
    td = tempfile.mkdtemp(prefix="le_anchor_")
    try:
        site = os.path.join(td, "home.json")
        json.dump(board(), open(site, "w"))
        path = os.path.join(td, "eval_anchor.json")
        import builtins
        old = builtins.input
        try:
            builtins.input = lambda *_: "n"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = EL.anchor_from_site(site, False, path)
            check("N -> nothing saved, shows the numbers and the by-hand command", rc == 1 and not os.path.exists(path) and "49,313.54" in buf.getvalue() and "48,168.20" in buf.getvalue() and "--anchor --balance" in buf.getvalue(), buf.getvalue())
            builtins.input = lambda *_: "Y"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = EL.anchor_from_site(site, False, path)
            check("Y -> both anchors saved", rc == 0 and os.path.exists(path), buf.getvalue())
        finally:
            builtins.input = old
        EL._ANCHOR_CACHE.clear()
        m = EL.load_anchor(None, path=path)
        a = EL.load_anchor("MFFUEVBLDR602936017", path=path, main=False)
        check("saved: LIT main anchor and ATLAS by account name read back",
              m == {"as_of": "2026-11-03", "balance": 49313.54, "floor": 48168.2, **({"set_t": m["set_t"]} if m and "set_t" in m else {})}
              and a and a["balance"] == 25351.0 and a["floor"] == 24351.0, (m, a))
        bad = os.path.join(td, "bad.json")
        rc = EL.anchor_from_site(os.path.join(td, "missing.json"), True, bad)
        check("unreadable board -> no file, by-hand command", rc == 1 and not os.path.exists(bad))
        # the CLI route
        r = subprocess.run([sys.executable, "-m", "engine.eval_life", "--anchor-from-site", "--site-file", site, "--anchor-file", os.path.join(td, "cli.json")],
                           capture_output=True, text=True, cwd=ROOT, input="y\n", timeout=60)
        check("CLI: python -m engine.eval_life --anchor-from-site works end to end", r.returncode == 0 and os.path.exists(os.path.join(td, "cli.json")), r.stdout + r.stderr)
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    static()
    pwsh = find_pwsh()
    if pwsh:
        pwsh_cases(pwsh)
    else:
        print("[SKIP] -Fresh -DryRun heartbeat cases: pwsh not found (set LE_PWSH or install PowerShell 7)")
    python_cases()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_fresh_start():                      # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
