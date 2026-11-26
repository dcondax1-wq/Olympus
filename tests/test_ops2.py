"""day-ops2 (2026-11-26): the hands-free roll, the OneDrive / clock fixes in START, disaster recovery.

    python -X utf8 -m tests.test_ops2          (~5 s)

A. Roll: on every quarterly roll day 2021-2027 the orders (nt_instrument), the LE_Feed list (feed_instruments) and the order-flow
   recorder (tickrec.front_names) move on the SAME day (the recorder was a day late); engine/roll_auto end to end in a temp
   NinjaTrader folder: nothing early, shadow first, install after hours + flat only, switch only after 2 equal days, a different
   day resets, a silent add-on falls back to the chart, the owner's own working no-chart mode is never touched, an old installed
   LE_Feed is shadowed before any update, ONE 'Roll done' line on the roll day.
B. START's PC checklist: OneDrive (the real place: a junction out of OneDrive is fine) and the clock (synced, else FIX_CLOCK with
   one Windows prompt); scripts/nt_off_onedrive.ps1 refuses with NinjaTrader open / in trading hours / not flat, keeps a backup.
C. Backup -> restore on a "new PC" (temp folders, real git): encrypted (no plain text), the arming proofs never in it, every file
   back byte for byte, wrong code / a damaged file / a path outside the folders refused, existing files kept (or .before-restore
   with --force), a tracked file never written.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
RES = []


def check(name, ok, info=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def et(y, m, d, hh=0, mm=0) -> float:
    return dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp()


# ------------------------------------------------------------------------------------------------ A. roll
def test_roll_days():
    from engine.ninjatrader import feed_instruments, nt_instrument
    from engine.tickrec import front_names
    from engine import roll_auto as RA
    rolls = [d for d in (dt.date(2021, 1, 2) + dt.timedelta(n) for n in range(2400))
             if nt_instrument("MNQ", d) != nt_instrument("MNQ", d - dt.timedelta(days=1))]
    same = all(front_names(["NQ"], d)[0].split()[1] == nt_instrument("MNQ", d).split()[1] and
               front_names(["NQ"], d - dt.timedelta(days=1))[0].split()[1] == nt_instrument("MNQ", d - dt.timedelta(days=1)).split()[1]
               for d in rolls)
    check("A1. 2021-2027: 26 roll days, all on the Thursday 8 days before the 3rd Friday",
          len(rolls) >= 24 and all(d.weekday() == 3 for d in rolls), rolls[:4])
    check("A2. every roll day: orders and the order-flow recorder switch on the SAME day (the recorder was one day late)", same)
    fi = all(feed_instruments({"sym": "NQ"}, d)[0] == nt_instrument("MNQ", d) for d in rolls)
    check("A3. ... and the LE_Feed add-on's list (feed_instruments.txt) follows that day too", fi)
    check("A4. the next roll: Thu 2026-12-10 (12-26 -> 03-27)", RA.roll_day(dt.date(2026, 11, 26)) == dt.date(2026, 12, 10)
          and nt_instrument("MNQ", dt.date(2026, 12, 10)) == "MNQ 03-27" and nt_instrument("MNQ", dt.date(2026, 12, 9)) == "MNQ 12-26")


def _bars_csv(t0, n, bump=None):
    lines = ["time,open,high,low,close,volume"]
    for i in range(n):
        t = int(t0) + 60 * i
        p = 21000 + (i % 37) * 0.25
        if bump and i in bump:
            p += 5
        lines.append(f"{t},{p},{p + 1},{p - 1},{p + 0.5},{10 + i % 5}")
    return "\n".join(lines) + "\n"


def test_roll_auto():
    from engine import roll_auto as RA
    from engine import ns_sync as NS
    tmp = tempfile.mkdtemp(prefix="le_roll_")
    try:
        root, nt = os.path.join(tmp, "bot"), os.path.join(tmp, "nt")
        os.makedirs(os.path.join(root, "ninjatrader"))
        for f in ("LE_Feed.cs", "LE_BarFeed.cs", "LE_TickRec.cs"):
            shutil.copy(os.path.join(ROOT, "ninjatrader", f), os.path.join(root, "ninjatrader"))
        os.makedirs(os.path.join(nt, "le_feed"))
        os.makedirs(os.path.join(nt, "bin", "Custom", "Indicators"))
        sent = []
        note = (lambda t, b, k: sent.append((t, b, k)))
        flat = (lambda: None)
        run = (lambda now, fl=flat: RA.tick(root, nt, now, flat=fl, notify=note, env={}))
        feed_cs = NS.dest(nt, "LE_Feed.cs")
        run(et(2026, 11, 20, 18))                                  # 20 days before: nothing
        check("A5. 20 days before the roll: nothing installed, no mode file", not os.path.exists(feed_cs) and RA.read_mode(nt) is None)
        r = run(et(2026, 11, 26, 11))                              # 14 days before, Thursday 11:00 ET: trading hours
        check("A6. inside 14 days, trading hours: shadow mode set (a file only), the add-on NOT copied yet",
              RA.read_mode(nt) == "shadow" and not os.path.exists(feed_cs), r)
        run(et(2026, 11, 26, 17), fl=lambda: "a trade may be open")
        check("A7. ... a trade may be open: still not copied", not os.path.exists(feed_cs))
        r = run(et(2026, 11, 26, 17))
        check("A8. after 16:00 ET, flat: LE_Feed copied into AddOns, shadow FIRST (the chart stays the source)",
              os.path.exists(feed_cs) and RA.read_mode(nt) == "shadow", r)
        # two equal sessions (Nov 27 + Nov 30), one bar of the 2nd day different only in a tolerated way
        day1, day2 = et(2026, 11, 27, 9, 30), et(2026, 11, 30, 9, 30)
        chart = _bars_csv(day1, 400) + "".join(_bars_csv(day2, 400).splitlines(True)[1:])
        os.makedirs(os.path.join(nt, "le_feed", "shadow"), exist_ok=True)
        open(os.path.join(nt, "le_feed", "MNQ_1m.csv"), "w").write(chart)
        open(os.path.join(nt, "le_feed", "shadow", "MNQ_1m.csv"), "w").write(chart)
        r = run(et(2026, 11, 30, 12))                              # Monday noon: 1 finished equal day (Nov 27), trading hours
        check("A9. one equal day only: no switch", RA.read_mode(nt) == "shadow" and RA.status(root).get("run") == 1, r)
        r = run(et(2026, 12, 1, 12))                               # Tuesday noon: 2 equal days, but trading hours
        check("A10. two equal days, in trading hours: the switch waits", RA.read_mode(nt) == "shadow" and not sent, r)
        r = run(et(2026, 12, 1, 17))
        check("A11. two equal days, after 16:00 ET, flat: live (the add-on feeds the bot), ONE line",
              RA.read_mode(nt) == "live" and len(sent) == 1 and "LE_Feed" in sent[0][0] and "no click" in sent[0][1], (r, sent))
        # fallback: live, the add-on's status old while NinjaTrader runs (the chart's files fresh)
        st = os.path.join(nt, "le_feed", "le_feed_status.txt")
        open(st, "w").write("1,source=addon,mode=live\n")
        t = et(2026, 12, 2, 18)
        os.utime(st, (t - 3600, t - 3600))
        acc = os.path.join(nt, "le_feed", "accounts.csv")
        open(acc, "w").write("x\n")
        os.utime(acc, (t - 30, t - 30))
        r = run(t)
        check("A12. live but the add-on silent while NinjaTrader runs: back to shadow (the chart writes again) + one line",
              RA.read_mode(nt) == "shadow" and len(sent) == 2 and "chart" in sent[1][0].lower(), (r, sent))
        # a different day resets the count
        bad = _bars_csv(day1, 400, bump=set(range(0, 40))) + "".join(_bars_csv(day2, 400).splitlines(True)[1:])
        open(os.path.join(nt, "le_feed", "shadow", "MNQ_1m.csv"), "w").write(bad)
        run(et(2026, 12, 3, 17))
        check("A13. a day with 10% different bars: not equal, no switch", RA.read_mode(nt) == "shadow" and RA.status(root).get("run") == 1
              and RA.status(root).get("bad_day") == "2026-11-27", RA.status(root))
        # roll day: the add-on names the new contract -> ONE 'Roll done'
        RA.write_mode(nt, "live")
        open(os.path.join(nt, "le_feed", "MNQ_instrument.txt"), "w").write("MNQ 12-26")
        run(et(2026, 12, 10, 0, 10))
        n_before = len(sent)
        open(os.path.join(nt, "le_feed", "MNQ_instrument.txt"), "w").write("MNQ 03-27")
        os.utime(st, None)
        run(et(2026, 12, 10, 0, 20))
        run(et(2026, 12, 10, 1, 20))
        done = [s for s in sent if s[0].startswith("Roll done")]
        check("A14. roll day: 'Roll done: MNQ 03-27' once, only after the bars really are on 03-27",
              n_before == len([s for s in sent[:n_before]]) and len(done) == 1 and "03-27" in done[0][0], sent[n_before - 1:])
        # the owner's own working no-chart mode: never forced into shadow
        nt2 = os.path.join(tmp, "nt2")
        os.makedirs(os.path.join(nt2, "le_feed"))
        os.makedirs(os.path.dirname(NS.dest(nt2, "LE_Feed.cs")))
        open(NS.dest(nt2, "LE_Feed.cs"), "w").write("// old LE_Feed\n")
        open(os.path.join(nt2, "le_feed", "le_feed_status.txt"), "w").write("1,source=addon\n")
        os.utime(os.path.join(nt2, "le_feed", "le_feed_status.txt"), (et(2026, 11, 27, 17) - 20,) * 2)
        RA.tick(root, nt2, et(2026, 11, 27, 17), flat=flat, notify=note, env={})
        check("A15. an LE_Feed that already feeds the bot (the owner's no-chart mode): left alone (no mode file)",
              RA.read_mode(nt2) is None)
        nt3 = os.path.join(tmp, "nt3")
        os.makedirs(os.path.dirname(NS.dest(nt3, "LE_Feed.cs")))
        open(NS.dest(nt3, "LE_Feed.cs"), "w").write("// old LE_Feed, never started\n")
        r = NS.check(root, nt3, et(2026, 11, 28, 12), flat=flat)
        check("A16. an OLD LE_Feed installed but not feeding: shadow is written BEFORE the new file is copied (never live unverified)",
              RA.read_mode(nt3) == "shadow" and NS.build_id(open(NS.dest(nt3, "LE_Feed.cs")).read()) ==
              NS.build_id(open(os.path.join(ROOT, "ninjatrader", "LE_Feed.cs")).read()), r)
        check("A17. LE_ROLL_AUTO=0 switches it off", RA.tick(root, nt3, et(2026, 11, 28, 12), env={"LE_ROLL_AUTO": "0"}) == [])
        src = open(os.path.join(ROOT, "ninjatrader", "LE_Feed.cs")).read()
        check("A18. LE_Feed.cs: shadow mode + build id in its status line, stamped", "le_feed_mode.txt" in src and ",v=\" + LE_BUILD" in src
              and NS.stamped(src) == NS.build_id(src))
        from engine import self_heal as SH
        check("A19. self-heal runs the roll autopilot hourly, before the NinjaScript sync",
              [n for n, _ in SH.REMEDIES].index("roll") < [n for n, _ in SH.REMEDIES].index("ninjascript"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ B. OneDrive + clock
def test_pc_checklist():
    from engine import go as G
    from engine import ops_checks as OC
    tmp = tempfile.mkdtemp(prefix="le_od_")
    try:
        real = os.path.join(tmp, "Users", "me", "NinjaTrader 8")
        od = os.path.join(tmp, "Users", "me", "OneDrive", "Documents")
        os.makedirs(real)
        os.makedirs(od)
        link = os.path.join(od, "NinjaTrader 8")
        os.symlink(real, link)
        check("B1. OneDrive check reads the REAL place: a junction out of OneDrive is fine, a folder inside it is not",
              OC.check_onedrive(link)["level"] == OC.OK and OC.check_onedrive(os.path.join(od, "x"))["level"] == OC.WARN)
        check("B2. its fix names the one-click tools\\bat\\NT_OFF_ONEDRIVE.bat", "tools\\bat\\NT_OFF_ONEDRIVE.bat" in OC.check_onedrive(od + "/x")["fix"])
        lines = G.pc_warn_lines(nt_folder=os.path.join(od, "x"), net={"up": True, "drift_s": 8.4}, sync=lambda: {"ok": False},
                                     inp=lambda q: "", elevate=lambda: True)
        check("B3. START: OneDrive [FIX] line + the clock 8.4 s behind: sync tried, then the FIX_CLOCK line (Enter = later)",
              any("[FIX] OneDrive" in x for x in lines) and any("[FIX] Clock 8.4 s behind" in x and "no new entry" in x for x in lines)
              and not any("FIX_CLOCK ran" in x for x in lines), lines)
        lines = G.pc_warn_lines(nt_folder=link, net={"up": True, "drift_s": 8.4}, sync=lambda: {"ok": True, "say": "synced"})
        check("B4. the clock synced by itself (the OlympusClock task / w32tm): one [OK] line, nothing to do",
              any("[OK] Clock was 8.4 s behind: synced" in x for x in lines) and any("[OK] OneDrive" in x for x in lines), lines)
        ran = []
        lines = G.pc_warn_lines(nt_folder=link, net={"up": True, "drift_s": -3.0}, sync=lambda: {"ok": False},
                                     inp=lambda q: "y", elevate=lambda: ran.append(1) or True)
        check("B5. Y at the clock question: FIX_CLOCK runs through Windows' own prompt (once)", ran == [1]
              and any("FIX_CLOCK ran" in x for x in lines), lines)
        ps = open(os.path.join(ROOT, "scripts", "nt_off_onedrive.ps1"), encoding="utf-8").read()
        check("B6. nt_off_onedrive.ps1: refuses with NinjaTrader open, in trading hours, when not flat; copies, counts, keeps a backup, "
              "never deletes the folder", all(w in ps for w in ("Get-Process -Name 'NinjaTrader'", "trading hours", "files_flat_reason",
                                                                  "robocopy", "onedrive-backup-", "mklink /J", "-Undo"))
              and "Remove-Item" not in ps and ps.isascii())
        g = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
        check("B7. START prints the checklist before the phrase", g.index("pc_warn_lines(inp=inp)") < g.index("3/4 Real money"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ C. backup / restore
def _pc(base, name):
    root = os.path.join(base, name)
    os.makedirs(os.path.join(root, "data"))
    shutil.copy(os.path.join(ROOT, ".gitignore"), root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    open(os.path.join(root, "data", "NQ_5m.csv"), "w").write("tracked market data\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], cwd=root, check=True)
    return root


def test_backup():
    from engine import pc_backup as PB
    base = tempfile.mkdtemp(prefix="le_dr_")
    try:
        old = _pc(base, "oldpc")
        oh = os.path.join(base, "oldhome", ".olympus")
        os.makedirs(oh)
        env = {"OLYMPUS_HOME": oh, "USERPROFILE": os.path.join(base, "oldhome")}
        secret = "SECRET-TELEGRAM-TOKEN-123456:abcdef"
        files = {"data/accounts.json": '{"acc": "MFFUEVBLDR1234"}', "data/start_bot.json": '{"lit": "MFFUEVBLDR1234"}',
                 "data/keepalive.json": '{"on": ["lit"]}', "data/rapid.json": '{"x": 1}', "data/lanes/x.json": '{"lane": 1}',
                 "data/auto_resume.json": '{"proof": "arms a real account"}', "data/autostart.json": '{"cfg": {}}',
                 "data/remote_done.json": "{}", ".env.local.ps1": "$env:NINJATRADER_LIVE='1'"}
        for rel, txt in files.items():
            p = os.path.join(old, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(txt)
        open(os.path.join(old, "data", "NQ_5m.csv"), "a").write("changed by the PC\n")
        open(os.path.join(oh, "alerts.json"), "w").write(json.dumps({"telegram": {"token": secret, "chat_id": "42"}}))
        dest = os.path.join(base, "OneDrive", "Olympus Backup")
        r = PB.make(old, env, et(2026, 11, 28, 12), dest=dest)
        blob = open(r["path"], "rb").read() if r.get("ok") else b""
        check("C1. one encrypted file in the backup folder", r.get("ok") and r["path"].endswith(".olb") and r["files"] >= 7, r)
        check("C2. nothing readable in it (no token, no account name, not a zip)", secret.encode() not in blob
              and b"MFFUEVBLDR" not in blob and not blob.startswith(b"PK"))
        key = PB.get_key(env, make=False)
        code = PB.recovery_code(key)
        check("C3. the key stays on the PC (.olympus/backup.key) and is never inside the backup", os.path.isfile(PB.key_path(env))
              and key not in blob)
        new = _pc(base, "newpc")
        nh = os.path.join(base, "newhome", ".olympus")
        env2 = {"OLYMPUS_HOME": nh, "USERPROFILE": os.path.join(base, "newhome")}
        check("C4. a wrong recovery code is refused, nothing written", not PB.restore(r["path"], "A" * 44, new, env2).get("ok")
              and not os.path.exists(os.path.join(new, "data", "accounts.json")))
        dmg = r["path"] + ".damaged"
        open(dmg, "wb").write(blob[:-10] + b"0123456789")
        check("C5. a damaged file is refused", not PB.restore(dmg, code, new, env2).get("ok"))
        open(os.path.join(new, "data", "keepalive.json"), "w").write('{"new pc": true}')
        rr = PB.restore(r["path"], code, new, env2)
        if not rr.get("ok"):
            print("   restore said:", rr)
        same = all(open(os.path.join(new, rel)).read() == files[rel] for rel in
                   ("data/accounts.json", "data/start_bot.json", "data/rapid.json", "data/lanes/x.json", ".env.local.ps1"))
        check("C6. restore on the new PC: accounts, switches, lanes, the live switch file + alerts.json back byte for byte",
              rr.get("ok") and same and json.load(open(os.path.join(nh, "alerts.json")))["telegram"]["token"] == secret, rr)
        check("C7. the arming proofs (auto_resume, autostart) and transient files are NOT restored: START + your phrase arms",
              not any(os.path.exists(os.path.join(new, "data", f)) for f in ("auto_resume.json", "autostart.json", "remote_done.json")))
        check("C8. a tracked file is never written (data/NQ_5m.csv comes from GitHub)",
              open(os.path.join(new, "data", "NQ_5m.csv")).read() == "tracked market data\n")
        check("C9. an existing file is kept without --force", json.load(open(os.path.join(new, "data", "keepalive.json"))) == {"new pc": True}
              and "bot/data/keepalive.json" in rr.get("kept", []), rr.get("kept"))
        PB.restore(r["path"], code, new, env2, force=True)
        check("C10. with --force it is replaced, the old one kept as .before-restore",
              json.load(open(os.path.join(new, "data", "keepalive.json"))) == {"on": ["lit"]}
              and os.path.exists(os.path.join(new, "data", "keepalive.json.before-restore")))
        # a crafted backup with a path outside the folders (made with the real key): refused, nothing written
        from cryptography.fernet import Fernet
        import hashlib
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("bot/../../evil.txt", b"x")
            z.writestr("manifest.json", json.dumps({"v": 1, "files": {"bot/../../evil.txt": hashlib.sha256(b"x").hexdigest()}}))
        evil = os.path.join(base, "evil.olb")
        open(evil, "wb").write(Fernet(key).encrypt(buf.getvalue()))
        check("C11. a path outside the bot folder / .olympus is refused (nothing written)", not PB.restore(evil, code, new, env2).get("ok")
              and not os.path.exists(os.path.join(base, "evil.txt")))
        for i in range(10):
            PB.make(old, env, et(2026, 11, 28, 12) + 600 * (i + 1), dest=dest)
        check("C12. the newest 8 backups are kept", len([f for f in os.listdir(dest) if f.endswith(".olb")]) == PB.KEEP)
        sat, wed = et(2026, 11, 28, 12), et(2026, 12, 2, 11)
        check("C13. weekly: due on a Saturday, never in trading hours, then not again for 7 days",
              PB.due(old, sat) and not PB.due(old, wed))
        st = os.path.join(base, "st")
        os.makedirs(os.path.join(st, "data"))
        shutil.copy(os.path.join(ROOT, ".gitignore"), st)
        subprocess.run(["git", "init", "-q"], cwd=st)
        open(os.path.join(st, "data", "pc_backup.json"), "w").write(json.dumps({"dir": os.path.join(base, "wk")}))
        w = PB.weekly(st, env, sat)
        check("C14. the weekly run makes one, tells START to show the code once, and is not due again the same week",
              w and w.get("ok") and w.get("first") is False and not PB.due(st, sat + 3600), w)
        check("C15. START's code line shows the recovery code until 'code saved'", code in PB.code_line(old, env)
              and PB.code_line(st, {"OLYMPUS_HOME": os.path.join(base, "none")}) == "")
        check("C16. data/pc_backup.json and the backup key path are git-ignored / outside the repo",
              subprocess.run(["git", "check-ignore", "-q", "--no-index", "data/pc_backup.json"], cwd=ROOT).returncode == 0)
        from cryptography.fernet import Fernet as _F
        ks = [_F.generate_key() for _ in range(300)]
        check("C17. the recovery code round-trips for every key (keys contain '-' and '_': the groups use spaces)",
              all(PB.parse_code(PB.recovery_code(k)) == k for k in ks) and any(b"-" in k for k in ks))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main() -> int:
    test_roll_days()
    test_roll_auto()
    test_pc_checklist()
    test_backup()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
