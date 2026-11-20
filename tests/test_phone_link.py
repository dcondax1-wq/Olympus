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

# h. server.py wires it at startup
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py"), encoding="utf-8").read()
check("h. server.py starts phone_link at startup", "phone_link" in src and "start_background" in src)

print(("%d/%d passed" % (N[0] - len(FAILS), N[0])) if not FAILS else "FAILED %d/%d: %s" % (len(FAILS), N[0], FAILS))
sys.exit(1 if FAILS else 0)
