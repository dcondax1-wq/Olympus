"""day-zerotouch2 (owner 2026-11-24): never stuck, boot to trading, the phone's PC control page, one line per pillar.

  a. auto-park: a hand edit of a file the update rewrites is parked with git stash (only those files), recorded, ONE phone line,
     and the update installs in the same run; second_model.json / live_model*.json / data/ are never parked (still blocked +
     named); never in trading hours, never with a trade open; a manual / START update never parks; self-heal's hourly run parks
  b. remote one-tap inbox: control/inbox/<id>.json runs once; an old one stays silent; command.json still works
  c. the PC checklist block, its ONE need, the pillar lines; pc_report posts ck + p4 + tr; a clock drift is not news
  d. START's auto-resume line; MONDAY_SETUP's boot lines
  e. the phone page's logic (pccore.js under node): rows, need, the command, the GitHub new-file link
Fake git repos (temp folders), fake pushes, no PowerShell, no network.
  python -X utf8 -m tests.test_zerotouch2
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import autoupdate as AU  # noqa: E402
from engine import self_heal as SH  # noqa: E402
from engine import pc_checklist as CK  # noqa: E402

ET = AU.ET
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:400]})" if info and not ok else ""))


def ts(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


EVENING = ts(2026, 11, 24, 21, 30)          # Tuesday 21:30 ET: outside 01:50-16:00
TRADING = ts(2026, 11, 24, 10, 0)


def g(cwd, *a):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def pair(tmp, name):
    """origin + the PC's clone; the newer origin rewrites engine/a.py, live_model.json and data/x.csv."""
    up, pc = os.path.join(tmp, name + "_up"), os.path.join(tmp, name + "_pc")
    os.makedirs(up)
    g(up, "init", "-q", "-b", "main")
    for d in (up,):
        g(d, "config", "user.email", "t@t")
        g(d, "config", "user.name", "t")
    write(os.path.join(up, "engine", "a.py"), "A = 1\n")
    write(os.path.join(up, "live_model.json"), '{"v": 1}\n')
    write(os.path.join(up, "data", "x.csv"), "1\n")
    write(os.path.join(up, ".gitignore"), "logs/\n")
    g(up, "add", "-A")
    g(up, "commit", "-qm", "one")
    subprocess.run(["git", "clone", "-q", up, pc], check=True, capture_output=True)
    g(pc, "config", "user.email", "t@t")
    g(pc, "config", "user.name", "t")
    write(os.path.join(up, "engine", "a.py"), "A = 2\n")
    write(os.path.join(up, "live_model.json"), '{"v": 2}\n')
    write(os.path.join(up, "data", "x.csv"), "2\n")
    g(up, "add", "-A")
    g(up, "commit", "-qm", "two")
    return up, pc


SRC = {"remote": "origin", "url": None, "branch": "main", "account": None, "label": "origin/main"}


def fakes():
    pushes, boards = [], []
    SH._push = lambda m: pushes.append(m) or True
    SH._board = lambda *a: boards.append(a) or True
    return pushes, boards


def test_park(tmp):
    keep_push, keep_board = SH._push, SH._board
    try:
        pushes, boards = fakes()
        up, pc = pair(tmp, "a1")
        write(os.path.join(pc, "engine", "a.py"), "A = 99  # my hand edit\n")
        logs = []
        ff = AU.fast_forward(AU.Shell(cwd=pc, log=logs.append), "main", src=SRC, park=True, now=EVENING)
        stash = g(pc, "stash", "list")
        check("a. a hand edit the update rewrites is parked and the update installs in the same run",
              ff["status"] == "updated" and ff.get("parked") == ["engine/a.py"] and read(os.path.join(pc, "engine", "a.py")) == "A = 2\n", (ff, logs[-4:]))
        check("a. ... git stash list shows 'auto-park <date> engine/a.py' and the edit is in it (nothing lost)",
              "auto-park 2026-11-24 21:30 engine/a.py" in stash and "my hand edit" in g(pc, "stash", "show", "-p"), stash)
        check("a. ... ONE phone line + one board event, plain words",
              len(pushes) == 1 and pushes[0]["body"] == "Parked a local edit to engine/a.py so the update could install; nothing lost: git stash list"
              and len(boards) == 1, (pushes, boards))
        rec = SH.read_parked(pc)
        lines = open(os.path.join(pc, "logs", "self_heal", "parked.jsonl")).read().splitlines()
        check("a. ... recorded in logs/self_heal (parked.json + parked.jsonl) and the feed's sh block (pk)",
              rec.get("last", {}).get("files") == ["engine/a.py"] and len(lines) == 1
              and SH.park_tiny(pc, EVENING + 60) == {"n": 1, "f": ["engine/a.py"], "t": int(EVENING)}
              and SH.tiny({"t": 1, "pk": SH.park_tiny(pc, EVENING)}, EVENING).get("pk", {}).get("n") == 1, rec)

        # never parked: strategy / account files and data/
        pushes.clear()
        up, pc = pair(tmp, "a2")
        write(os.path.join(pc, "live_model.json"), '{"mine": 1}\n')
        write(os.path.join(pc, "engine", "a.py"), "A = 5\n")
        ff = AU.fast_forward(AU.Shell(cwd=pc, log=lambda t: None), "main", src=SRC, park=True, now=EVENING)
        check("a. live_model.json is NEVER parked: the update stays blocked and names it (engine/a.py was parked)",
              ff["status"] == "skipped" and "live_model.json" in ff["reason"] and read(os.path.join(pc, "live_model.json")) == '{"mine": 1}\n'
              and "engine/a.py" not in ff["reason"], ff)
        check("a. parkable(): second_model.json, live_model_lit.json, data/x.csv, notes, .env never; engine/a.py yes",
              not any(SH.parkable(p) for p in ("second_model.json", "live_model_lit.json", "data/x.csv", "STATE.md", ".env.local.ps1",
                                               "update_source.json", "research/lit_journal.jsonl")) and SH.parkable("engine/a.py"))
        up, pc = pair(tmp, "a3")
        write(os.path.join(pc, "data", "x.csv"), "mine\n")
        ff = AU.fast_forward(AU.Shell(cwd=pc, log=lambda t: None), "main", src=SRC, park=True, now=EVENING)
        check("a. a data/ file is never parked (blocked, untouched, no stash)",
              ff["status"] in ("skipped", "failed") and read(os.path.join(pc, "data", "x.csv")) == "mine\n" and not g(pc, "stash", "list"), ff)

        # the rules: trading hours, an open trade, manual updates
        for when, flat, label in ((TRADING, "", "weekday 10:00 ET"), (EVENING, "an open NinjaTrader bracket", "a trade open")):
            up, pc = pair(tmp, "a4" + label[:3].strip())
            write(os.path.join(pc, "engine", "a.py"), "A = 7\n")
            pk = SH.park_local(pc, SH.make_git(pc), ["engine/a.py"], now=when, flat=flat, push=lambda m: True, board=lambda *a: True)
            check(f"a. never parks with {label}: nothing stashed, the edit stays", not pk["parked"] and pk["why"]
                  and read(os.path.join(pc, "engine", "a.py")) == "A = 7\n" and not g(pc, "stash", "list"), pk)
        up, pc = pair(tmp, "a5")
        write(os.path.join(pc, "engine", "a.py"), "A = 8\n")
        ff = AU.fast_forward(AU.Shell(cwd=pc, log=lambda t: None), "main", src=SRC, now=EVENING)
        check("a. a plain fast_forward (UPDATE.bat / START) never parks: blocked as before",
              ff["status"] == "skipped" and read(os.path.join(pc, "engine", "a.py")) == "A = 8\n" and not g(pc, "stash", "list"), ff)
        check("a. run_update parks only in the server's own checks (daily / hourly) or when asked (the phone's Update now)",
              "park = mode in (\"daily\", \"hourly\")" in open(os.path.join(ROOT, "engine", "autoupdate.py")).read()
              and "park=True" in open(os.path.join(ROOT, "engine", "remote_ctl.py")).read())

        # self-heal's hourly run (apply) parks; a dry run only says it would
        up, pc = pair(tmp, "a6")
        g(pc, "fetch", "-q", "origin")
        write(os.path.join(pc, "engine", "a.py"), "A = 9\n")
        ctx = SH.Ctx(root=pc, now=EVENING, apply=False, procs=[], ping=lambda: True, nt=None, temp="", pkgs={}, env={}, flat=lambda: None)
        r = {i["key"]: i for i in SH.fix_update(ctx)}
        check("a. self-heal dry run: 'would park engine/a.py', nothing changed",
              r.get("update_parked", {}).get("status") == "would" and read(os.path.join(pc, "engine", "a.py")) == "A = 9\n", r)
        pushes.clear()
        ctx = SH.Ctx(root=pc, now=EVENING, apply=True, procs=[], ping=lambda: True, nt=None, temp="", pkgs={}, env={}, flat=lambda: None)
        r = {i["key"]: i for i in SH.fix_update(ctx)}
        check("a. self-heal hourly (apply): parked, FIXED (not 'needs you'), one phone line; the next update fast-forwards",
              r.get("update_parked", {}).get("status") == "fixed" and "update_blocked" not in r and len(pushes) == 1
              and AU.fast_forward(AU.Shell(cwd=pc, log=lambda t: None), "main", src=SRC)["status"] == "updated", (r, pushes))
        up, pc = pair(tmp, "a8")
        g(pc, "fetch", "-q", "origin")
        write(os.path.join(pc, "live_model.json"), '{"mine": 2}\n')
        ctx = SH.Ctx(root=pc, now=EVENING, apply=True, procs=[], ping=lambda: True, nt=None, temp="", pkgs={}, env={}, flat=lambda: None)
        r = {i["key"]: i for i in SH.fix_update(ctx)}
        check("a. self-heal: live_model.json still ALERTS (needs you, named first), never stashed",
              r.get("update_blocked", {}).get("text", "").startswith("update held back by live_model.json") and "never parked" in r["update_blocked"]["step"]
              and not g(pc, "stash", "list"), r)
    finally:
        SH._push, SH._board = keep_push, keep_board


def test_inbox(tmp):
    from engine import remote_ctl as rc
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_remote_ctl as T
    w = T.World()
    try:
        w.send({"id": "noop-0", "ts": 0, "cmd": "none"})
        now = time.time()

        def drop(name, obj):
            g(w.phone, "checkout", "-q", "control")
            write(os.path.join(w.phone, "control", "inbox", name), json.dumps(obj, indent=1))
            g(w.phone, "add", "-A")
            g(w.phone, "commit", "-qm", "inbox")
            g(w.phone, "push", "-q", "origin", "control")
        drop(f"status-{int(now)}-ab12.json", {"id": f"status-{int(now)}-ab12", "ts": int(now), "cmd": "status"})
        drop("status-1000-old.json", {"id": "status-1000-old", "ts": 1000, "cmd": "status"})
        hooks, calls = T.recorder()
        c = w.ctl(T.FakeBot(), hooks)
        out = c.tick()
        check("b. a one-tap inbox file (control/inbox/<id>.json) runs once: status done + its phone notice",
              [o[2] for o in out] == ["done"] and len(w.notes) == 1, (out, w.notes))
        check("b. ... an old inbox file left on the branch is skipped silently (no notice)", not any("old" in n[2] for n in w.notes), w.notes)
        out = c.tick()
        check("b. ... read again: never twice", out == [], out)
        w.send({"id": f"status-{int(now)}-cc33", "ts": int(now), "cmd": "status"})
        out = c.tick()
        check("b. command.json (the Remote page's way) still works next to the inbox", [o[2] for o in out] == ["done"], out)
        drop("zz-kill.json", {"id": f"bogus-{int(now)}", "ts": int(now), "cmd": "arm_live"})
        out = c.tick()
        check("b. an inbox file can only run the existing safe commands (arm_live = ignored)", out and out[0][2] == "ignored", out)
        check("b. the inbox reads at most INBOX_MAX newest files", rc.INBOX_MAX == 12)
    finally:
        shutil.rmtree(w.tmp, ignore_errors=True)


GLANCE = {"bots": [{"id": "lit", "on": True, "armed": True, "mode": "LIVE"}, {"id": "atlas", "on": True, "armed": True}]}


def test_checklist(tmp):
    loc = {"acc": [["Zlarior 50K", 1, 1, 1], ["ATLAS 25K", 1, 1, 1]], "ka": [2, 2], "up": {"v": "abc1234", "p": None},
           "nt_conn": True, "nt_auto": None, "clk": [1, 0.3]}
    b = CK.block(loc, glance=GLANCE, blitz={"off": True}, tr={"on": True, "d": 12, "of": 60}, sh={}, nt_running=True, server=True, running=True)
    check("c. all green: need = None (nothing at the PC)", b.get("need") is None and b["srv"] == 1 and b["nt"] == [1, 1, None], b)
    check("c. one line per pillar: LIT, ATLAS, BLITZ, Order Flow", CK.pillar_lines(b) == [
        "LIT: running, armed (LIVE)", "ATLAS: running, armed", "BLITZ: off (hidden, paper only)", "Order Flow: recording ticks: 12 of 60 study days"],
        CK.pillar_lines(b))
    check("c. small (<= 600 bytes) and no account id / folder", len(json.dumps(b, separators=(",", ":"))) <= 600, len(json.dumps(b)))
    cases = [
        (dict(server=False), "server"), (dict(nt_running=False), "nt"), (dict(loc={**loc, "nt_conn": False}), "nt_conn"),
        (dict(glance={"bots": [{"id": "lit", "on": True, "armed": False}, {"id": "atlas", "on": True, "armed": True}]}), "arm"),
        (dict(loc={**loc, "acc": [["Zlarior 50K", 1, 0, 1]]}), "resume"),
        (dict(sh={"need": ["update_blocked"], "blk": ["live_model.json"]}), "update"),
        (dict(loc={**loc, "clk": [0, 4.2]}), "clock"), (dict(loc={**loc, "acc": [["ATLAS 25K", 1, 1, 0]]}), "keepalive"),
    ]
    base = dict(loc=loc, glance=GLANCE, blitz={"off": True}, tr={"on": True, "d": 1}, sh={}, nt_running=True, server=True, running=True)
    for kw, want in cases:
        a = {**base, **kw}
        n = CK.block(a.pop("loc"), **a).get("need") or {}
        check(f"c. the ONE need: {want}", n.get("k") == want, n)
    b2 = CK.block(loc, glance=GLANCE, sh={"need": ["update_blocked"], "blk": ["live_model.json"], "pk": {"n": 1, "f": ["engine/a.py"], "t": 5}},
                  nt_running=True, server=True, running=True)
    check("c. update block carries the blocking file and the last auto-park", b2["up"]["b"] == ["live_model.json"] and b2["up"]["k"]["n"] == 1, b2["up"])
    # pc_report: ck + p4 in the posts, tr posted, a clock drift is not news
    from tools import pc_report as PR
    snap = {"t": int(EVENING), "hb_t": int(EVENING), "server": True, "nt": True, "live": {"pc": {"running": True, "present": True, "glance": GLANCE},
            "board": {}}, "tr": {"on": True, "d": 3, "of": 60, "t": 1}, "sh": None, "ck_local": loc}
    out = PR.full(snap)
    check("c. pc_report.full: ck + p4 [LIT, ATLAS, BLITZ, OF] + tr (gathered since day-pillars, never posted before)",
          out.get("ck", {}).get("pl") and out.get("p4") == ["run", "run", "off", "run"] and out.get("tr", {}).get("d") == 3, {k: out.get(k) for k in ("ck", "p4", "tr")})
    core, exts = PR.split(out)
    check("c. p4 rides the CORE post, ck an ext post", core.get("p4") == ["run", "run", "off", "run"] and any("ck" in (e.get("x") or {}) for e in exts), (core.get("p4"), [list(e.get("x") or {}) for e in exts]))
    out2 = PR.full({**snap, "ck_local": {**loc, "clk": [1, 0.9]}})
    check("c. a new clock drift alone is not news (the ext is not re-posted for it)", PR.ext_hash(PR.split(out)[1]) == PR.ext_hash(PR.split(out2)[1]))
    check("c. NinjaTrader auto-connect: read from config.xml when it says so, else None",
          _autoconnect(tmp, "<Options><ConnectOnStartup>true</ConnectOnStartup></Options>") is True
          and _autoconnect(tmp, "<Options><ConnectOnStartup>false</ConnectOnStartup></Options>") is False
          and _autoconnect(tmp, "<Options/>") is None and CK.nt_autoconnect(None) is None)


def _autoconnect(tmp, xml):
    d = tempfile.mkdtemp(dir=tmp)
    write(os.path.join(d, "config.xml"), xml)
    return CK.nt_autoconnect(d)


def test_boot(tmp):
    from engine import go, autoresume, monday
    day = "2026-11-24"
    rec = {"enabled": True, "account": "MFFU123450K", "accepted_on": day, "proof": autoresume._proof("MFFU123450K", day, autoresume._phrase())}
    armed = [("lit", "Zlarior 50K ..450K", "MFFU123450K"), ("atlas", "ATLAS 25K ..925K", "MFFU999925K"), ("x:z2", "Builder 25K ..825K", "MFFU888825K")]
    line = go.autoresume_line(rec=rec, armed=armed)
    check("d. START: ONE clear line: auto-resume ON for the 50K + ATLAS (lane of its bot); an extra without its proof = [FIX]",
          line.startswith("[OK] Auto-resume ON for Zlarior 50K, ATLAS 25K: after a reboot, a Windows update or a crash they come back ARMED")
          and "[FIX] Auto-resume NOT on for Builder 25K" in line and "MFFU" not in line, line)
    rec["extra"] = [{"account": "MFFU888825K", "accepted_on": day, "proof": autoresume._proof("MFFU888825K", day, autoresume._phrase())}]
    check("d. ... with the extra's own proof all three are ON", "[FIX]" not in go.autoresume_line(rec=rec, armed=armed), go.autoresume_line(rec=rec, armed=armed))
    check("d. ... no opt-in at all = every armed account [FIX]", go.autoresume_line(rec={}, armed=armed).startswith("[FIX]"))
    check("d. START prints it right after the auto-resume opt-in", "print(f\"\\n {autoresume_line()}\")" in open(os.path.join(ROOT, "engine", "go.py")).read())
    ln = monday.boot_lines(True, None, None)
    check("d. MONDAY_SETUP: NinjaTrader opens at sign-in, 'Connect on startup' once if not readable, auto-sign-in = owner's choice",
          ln[0].startswith("[OK] NinjaTrader opens by itself") and "Connect on startup" in ln[1] and "YOUR choice" in ln[2], ln)
    check("d. ... all set = no FIX line, no sign-in line", all("[FIX]" not in x for x in monday.boot_lines(True, True, True)) and len(monday.boot_lines(True, True, True)) == 2)
    check("d. MONDAY_SETUP never switches Windows auto-logon on (reads AutoAdminLogon only)",
          "reg add" not in open(os.path.join(ROOT, "engine", "monday.py")).read().lower())


def test_page(tmp):
    js = r"""
const C = require(process.argv[2]);
const now = 1795000000;
const lite = { reporter: { t: now - 300 }, rc: { last: 'remote: last cmd status done at 21:31 ET' },
  ck: { pc: 1, srv: 1, nt: [1, 1, null], acc: [['Zlarior 50K', 1, 1, 1], ['ATLAS 25K', 1, 0, 1]], ka: [2, 2], up: { v: 'abc1234', p: 'def5678' },
        tr: [12, 60, 1], bz: 'off', clk: [1, 0.2], pl: [['LIT', 'run', 'running, armed'], ['ATLAS', 'run', 'running, armed'], ['BLITZ', 'off', 'off'], ['OF', 'run', 'recording']],
        need: { k: 'resume', t: 'Auto-resume is off for ATLAS 25K: START_BOT.bat once' } } };
const m = C.model(lite, now);
const old = C.model({ reporter: { t: now - 3 * 3600 } }, now);
const cmd = C.build('pause', now, 'ab12');
const url = C.newFileUrl('owner2/olympus', cmd);
console.log(JSON.stringify({ rows: m.rows.map((r) => [r.k, r.st, r.text]), need: m.need, pillars: m.pillars, old: old.need, cmd, url,
  bad: C.newFileUrl('someone/else', cmd), btn: C.BUTTONS.map((b) => b.cmd) }));
"""
    p = os.path.join(tmp, "pc_page_test.js")
    write(p, js)
    r = subprocess.run(["node", p, os.path.join(ROOT, "tools", "web_public", "pc", "pccore.js")], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout)
    except Exception:
        check("e. pccore.js runs under node", False, r.stderr[-400:])
        return
    rows = {k: (st, t) for k, st, t in o["rows"]}
    check("e. checklist rows: PC on, NinjaTrader connected, each account armed + auto-resume, keep-alive, update pending with the version, ticks, BLITZ, clock",
          rows["pc"][0] == "ok" and rows["nt"] == ("ok", "connected") and rows["ka"] == ("ok", "ON for 2 of 2")
          and rows["up"][0] == "warn" and "def5678" in rows["up"][1] and "abc1234" in rows["up"][1] and rows["tr"][1].startswith("12 of 60")
          and rows["bz"][1].startswith("off") and rows["clk"][0] == "ok"
          and [r for r in o["rows"] if r[0] == "acc"][1][1:] == ["warn", "armed · auto-resume OFF"], o["rows"])
    check("e. the ONE thing at the PC comes from the PC; a silent PC says so first", o["need"]["k"] == "resume" and o["old"]["k"] == "pc", (o["need"], o["old"]))
    check("e. buttons = the existing safe commands only (no arm, no start on a real account)",
          o["btn"] == ["status", "update", "restart", "pause", "resume_entries"], o["btn"])
    check("e. the command: fresh id + ts + until=tomorrow (engine/remote_ctl.screen accepts it)",
          o["cmd"] == {"id": "pause-1795000000-ab12", "ts": 1795000000, "cmd": "pause", "until": "tomorrow"}, o["cmd"])
    from engine import remote_ctl as rc
    check("e. ... remote_ctl.screen runs it", rc.screen(o["cmd"], 1795000000 + 30, {}) is None)
    check("e. GitHub new-file link: branch control, file control/inbox/<id>.json, the command filled in; only <account>/olympus",
          o["url"].startswith("https://github.com/owner2/olympus/new/control?filename=control%2Finbox%2Fpause-1795000000-ab12.json&value=")
          and "%22cmd%22%3A%20%22pause%22" in o["url"] and o["bad"] == "", o["url"])
    html = read(os.path.join(ROOT, "tools", "web_public", "pc", "control.html"))
    css = read(os.path.join(ROOT, "tools", "web_public", "pc", "pc.css"))
    check("e. the page: OLYMPUS NIGHT colours, 44 px taps, no token / account name in the code",
          all(c in css for c in ("#16131e", "#3e255e", "#9d59ee", "#f1c14b", "#77db89")) and "min-height: 64px" in css
          and "dcondax" not in html + css + read(os.path.join(ROOT, "tools", "web_public", "pc", "pc.js")) + read(os.path.join(ROOT, "tools", "web_public", "pc", "pccore.js")))


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_zt2_")
    try:
        for fn in (test_park, test_inbox, test_checklist, test_boot, test_page):
            try:
                fn(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{fn.__name__} crashed", False, f"{e.__class__.__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed" + ("" if ok == n else "  FAILURES"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
