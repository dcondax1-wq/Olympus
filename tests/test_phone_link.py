"""engine/phone_link.py: the bot server gets its own private Tailscale https port, never 443, never Funnel.
python -X utf8 -m tests.test_phone_link"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import phone_link as P  # noqa: E402

FAILS, N = [], [0]


def check(name, ok, info=""):
    N[0] += 1
    if not ok:
        FAILS.append(name)
        print("FAIL", name, info)


class R:
    def __init__(self, out):
        self.stdout, self.returncode = out, 0


def fake(serve_states, running=True):
    """serve_states: list of serve-status dicts returned in turn; records every command."""
    calls, states = [], list(serve_states)

    def runner(cmd):
        calls.append(cmd[1:])
        if cmd[1:3] == ["status", "--json"]:
            return R(json.dumps({"BackendState": "Running" if running else "NeedsLogin"}))
        if cmd[1:4] == ["serve", "status", "--json"]:
            return R(json.dumps(states.pop(0) if len(states) > 1 else states[0]))
        return R("")
    return runner, calls


H = "desktop-x.tail123.ts.net"
JARVIS = {"TCP": {"443": {"HTTPS": True}}, "Web": {H + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5000"}}}}}
OURS_8444 = {"TCP": {"443": {"HTTPS": True}, "8444": {"HTTPS": True}},
             "Web": {H + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5000"}}},
                     H + ":8444": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}}}}
ENV = {"LE_PHONE_LINK": "1"}

# a. 443 belongs to Jarvis -> 8444 is added for the bot, 443 never touched, no funnel
run, calls = fake([JARVIS, OURS_8444])
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
sets = [c for c in calls if c[:1] == ["serve"] and "status" not in c]
check("a. switched on at 8444", r == {"ok": True, "port": 8444, "why": "switched on"}, r)
check("a. one serve call, --https=8444 -> 127.0.0.1:8766", sets == [["serve", "--bg", "--yes", "--https=8444", "http://127.0.0.1:8766"]], sets)
check("a. never 443 / funnel / off / reset", not any(("--https=443" in c) or ("funnel" in c) or ("off" in c) or ("reset" in c) for c in calls), calls)

# b. already ours (on 443 via LIVE_LINK) -> nothing changed
LL = {"TCP": {"443": {"HTTPS": True}}, "Web": {H + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}}}}
run, calls = fake([LL])
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("b. already on 443: no change", r["ok"] and r["port"] == 443 and not [c for c in calls if c[:2] == ["serve", "--bg"]], (r, calls))

# c. ours but Funnel on -> not counted as ours, a new private port is made instead (Funnel left to the owner)
FUN = {"TCP": {"443": {"HTTPS": True}}, "Web": {H + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}}},
       "AllowFunnel": {H + ":443": True}}
check("c. funnel mapping is not 'ours'", P.scan(FUN)["ours"] == [] and P.scan(FUN)["funnel"] == [443])

# d. 8444 used by another app -> 8446
OTHER = {"TCP": {"443": {}, "8444": {}}, "Web": {H + ":8444": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9999"}}}}}
run, calls = fake([OTHER, {"TCP": {"8446": {}}, "Web": {H + ":8446": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}}}}])
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("d. next free port 8446", r["ok"] and r["port"] == 8446 and ["serve", "--bg", "--yes", "--https=8446", "http://127.0.0.1:8766"] in calls, (r, calls))

# e. not signed in / not installed / switched off / tailscale refused -> no change, no raise
run, calls = fake([JARVIS], running=False)
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("e. not signed in: no serve call", not r["ok"] and not [c for c in calls if c[:2] == ["serve", "--bg"]], (r, calls))
check("e. off switch", P.ensure(env={"LE_PHONE_LINK": "0"}, runner=run, ts="ts")["why"].startswith("off"))
check("e. not installed", not P.ensure(env={"LE_TAILSCALE": "/nope/tailscale.exe"}, runner=run)["ok"])
run, calls = fake([JARVIS, JARVIS])
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("e. tailscale did not take it: ok False", not r["ok"] and "did not take" in r["why"], r)


def boom(cmd):
    raise OSError("x")


check("e. runner raising never raises", P.ensure(env=ENV, runner=boom, ts="ts")["ok"] is False)

# f. start hook: never on this Linux test box / cloud
check("f. start_background is a no-op off Windows", P.start_background(env={}) is None if os.name != "nt" else True)
check("f. start_background off in cloud", P.start_background(env={"LE_CLOUD": "1"}) is None)

# g. the pages accept the :8444 Host (private_why strips the port, keeps .ts.net)
from engine import live_site as L  # noqa: E402
hdr = {"host": H + ":8444", "x-forwarded-for": "100.101.102.103", "tailscale-user-login": "owner@example.com"}
check("g. private_why allows <pc>.ts.net:8444 from a tailnet device", L.private_why("127.0.0.1", hdr) is None, L.private_why("127.0.0.1", hdr))
hdr2 = dict(hdr, **{"tailscale-funnel-request": "1"})
check("g. ... but never a Funnel request", L.private_why("127.0.0.1", hdr2) is not None)

# i. Windows review 2026-11-20: the default runner reads UTF-8 (not the cp1252 console page), closes stdin, has a timeout
import subprocess  # noqa: E402
seen = {}
real_run = subprocess.run


def spy(cmd, **kw):
    seen.update(kw)
    return R(json.dumps({"BackendState": "Running", "User": {"1": {"DisplayName": "\u039d\u0399\u039a\u039f\u03a3"}}}))


subprocess.run = spy
try:
    got = P._json("ts", ["status", "--json"])
finally:
    subprocess.run = real_run
check("i. default runner: encoding utf-8, errors replace, stdin closed, timeout", seen.get("encoding") == "utf-8"
      and seen.get("errors") == "replace" and seen.get("stdin") == subprocess.DEVNULL and seen.get("timeout") == P.TIMEOUT, seen)
check("i. a Greek display name in status --json still reads as Running", got.get("BackendState") == "Running", got)
out = P._default_runner([sys.executable, "-c", "import sys; sys.stdout.buffer.write('{\"n\": \"\u039d\u03a3\"}'.encode('utf-8'))"])
check("i. real process: UTF-8 bytes decoded as UTF-8", json.loads(out.stdout) == {"n": "\u039d\u03a3"}, out.stdout)
P.TIMEOUT, t0 = 1, P.TIMEOUT
try:
    out = P._default_runner([sys.executable, "-c", "import sys,time; print('visit https://login.tailscale.com/f/serve?node=abc', flush=True); time.sleep(30)"])
finally:
    P.TIMEOUT = t0
check("i. a hanging tailscale (it asks a question): returncode -9 after the timeout, what it printed kept",
      out.returncode == -9 and "login.tailscale.com" in (out.stdout or "") and "timed out" in out.stderr, (out.returncode, out.stdout, out.stderr))

# j. serve status --json prints null / {} when nothing is served -> 8444
for empty in ("null", "{}", ""):
    calls = []

    def run_e(cmd, empty=empty):
        calls.append(cmd[1:])
        if cmd[1:3] == ["status", "--json"]:
            return R(json.dumps({"BackendState": "Running"}))
        if cmd[1:4] == ["serve", "status", "--json"]:
            return R(empty if len([c for c in calls if c[:2] == ["serve", "--bg"]]) == 0 else json.dumps(OURS_8444))
        return R("")
    r = P.ensure(env=ENV, runner=run_e, ts="ts", say=lambda *_: None)
    check("j. nothing served yet (%r): 8444 switched on" % empty, r == {"ok": True, "port": 8444, "why": "switched on"}, r)

# k. a foreground `tailscale serve` session holds 8444 (and even proxies the bot): used, not ours -> 8446
FG = {"TCP": {"443": {}}, "Web": {H + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5000"}}}},
      "Foreground": {"sess1": {"TCP": {"8444": {"HTTPS": True}},
                               "Web": {H + ":8444": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8766"}}}}}}}
sc = P.scan(FG)
check("k. foreground ports are used, never 'ours'", 8444 in sc["used"] and sc["ours"] == [] and 443 in sc["used"], sc)
check("k. odd shapes never raise", P.scan({"Web": None, "TCP": [], "Foreground": {"x": None}, "AllowFunnel": None})["ours"] == [])


class RF:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


def fake_fail(answer, then=None):
    calls = []

    def runner(cmd):
        calls.append(cmd[1:])
        if cmd[1:3] == ["status", "--json"]:
            return R(json.dumps({"BackendState": "Running"}))
        if cmd[1:4] == ["serve", "status", "--json"]:
            n = len([c for c in calls if c[:1] == ["serve"] and "status" not in c])
            return R(json.dumps(then if (then and n >= 2) else JARVIS))
        return answer(cmd[1:], calls)
    return runner, calls


# l. a server run as another Windows user: the reason says which user must run it
run, calls = fake_fail(lambda a, c: RF(1, "", "Access denied: serve config denied"))
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("l. serve refused: the reason names the Windows user / Tailscale app", not r["ok"] and "Windows user" in r["why"], r)

# m. an older Tailscale without --yes: asked once more without it
run, calls = fake_fail(lambda a, c: RF(2, "", "flag provided but not defined: -yes") if "--yes" in a else RF(0), then=OURS_8444)
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
sets = [c for c in calls if c[:1] == ["serve"] and "status" not in c]
check("m. no --yes flag: retried as `serve --bg --https=8444 http://127.0.0.1:8766`, on",
      r["ok"] and sets == [["serve", "--bg", "--yes", "--https=8444", "http://127.0.0.1:8766"],
                           ["serve", "--bg", "--https=8444", "http://127.0.0.1:8766"]], (r, sets))

# n. Tailscale waits for Serve / HTTPS to be switched on for the tailnet: the link reaches the reason
run, calls = fake_fail(lambda a, c: RF(-9, "Serve is not enabled on your tailnet.\nTo enable, visit:\n  https://login.tailscale.com/f/serve?node=n1\nWaiting...",
                                       "(timed out after 20 s)"))
r = P.ensure(env=ENV, runner=run, ts="ts", say=lambda *_: None)
check("n. waiting for Serve / HTTPS: the reason carries the login.tailscale.com link",
      not r["ok"] and "https://login.tailscale.com/f/serve?node=n1" in r["why"], r)

# o. at logon Tailscale is not connected yet: start_background tries again (here 3 tries), then stops trying
answers = [{"ok": False, "port": None, "why": "Tailscale is not signed in / running"}] * 2 + [{"ok": True, "port": 8444, "why": "switched on"}]
said, slept, real_ensure = [], [], P.ensure
P.ensure = lambda env=None, say=None: answers.pop(0)
try:
    t = P.start_background(env={}, say=said.append, tries=5, wait_s=7, sleep=slept.append, force=True)
    t.join(5)
finally:
    P.ensure = real_ensure
check("o. not connected at logon: tried again after 7 s twice, then on", slept == [7, 7] and said[-1] == "[phone_link] port 8444: switched on", (slept, said))
answers = [{"ok": False, "port": None, "why": "Tailscale is not installed on this PC"}] * 3
slept = []
P.ensure = lambda env=None, say=None: answers.pop(0)
try:
    t = P.start_background(env={}, say=lambda *_: None, tries=5, wait_s=7, sleep=slept.append, force=True)
    t.join(5)
finally:
    P.ensure = real_ensure
check("o. not installed: no retries", slept == [] and len(answers) == 2, slept)

# p. tailscale.exe: ProgramW6432 (a 32-bit Python's ProgramFiles points to Program Files (x86))
import tempfile  # noqa: E402
d = tempfile.mkdtemp(prefix="le_ts_")
os.makedirs(os.path.join(d, "Tailscale"))
exe = os.path.join(d, "Tailscale", "tailscale.exe")
open(exe, "w").close()
import shutil  # noqa: E402
if not shutil.which("tailscale"):
    check("p. found under %ProgramW6432%\\Tailscale", P.find_tailscale({"ProgramW6432": d, "ProgramFiles": "/nope"}) == exe)
check("p. LE_TAILSCALE wins", P.find_tailscale({"LE_TAILSCALE": exe}) == exe)
shutil.rmtree(d, ignore_errors=True)

# h. server.py wires it at startup
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py"), encoding="utf-8").read()
check("h. server.py starts phone_link at startup", "phone_link" in src and "start_background" in src)

print(("%d/%d passed" % (N[0] - len(FAILS), N[0])) if not FAILS else "FAILED %d/%d: %s" % (len(FAILS), N[0], FAILS))
sys.exit(1 if FAILS else 0)
