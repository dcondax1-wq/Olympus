"""The phone's PC control checklist + the four pillars' one line each (day-zerotouch2 2026-11-24).

Owner 2026-11-24: "after ONE last PC step everything runs with zero clicks or from my phone in under 30 seconds". The 15-minute
PC report (tools/pc_report.py) adds ONE small public block "ck" to its ext post; the phone page tools/web_public/pc/ reads it:

  pc   1 (the post itself is the sign of life; the page ages it)       srv  the bot server answers (1 / 0)
  nt   [running 1/0/None, connected 1/0/None, auto-connect 1/0/None]   acc  [[label, armed 1/0, auto-resume 1/0, keep-alive 1/0], ...]
  ka   [on, of] keep-alive switches of the armed real accounts         up   {"v": HEAD sha7, "p": pending sha7 | None, "b": blocked by [..]}
  tr   [tick days, study days, recorder on 1/0] | None                bz   BLITZ "on" / "paper" / "off"
  clk  [ok 1/0/None, drift s]                                          pl   [[pillar, state, words], ...] LIT / ATLAS / BLITZ / OF
  need the ONE thing the owner must do AT THE PC (None = nothing) as {"k": key, "t": plain words}

Labels only (Zlarior 50K, ATLAS 25K, ...): never an account id, a name, a folder or a URL (the topic is public; the privacy pass
runs on top). Read-only: it never arms, starts, opens or changes anything. Every reader is soft: a missing piece is None.
  python -X utf8 -m engine.pc_checklist          this PC's block + the need line
Tests: python -X utf8 -m tests.test_pc_checklist
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILLARS = ("LIT", "ATLAS", "BLITZ", "OF")
_AUTOCONNECT = re.compile(r"(?i)<(?:ConnectOnStartup|IsConnectOnStartup|AutoConnect|ConnectAtStartup)>\s*(true|false)\s*<")


def _i(v):
    return None if v is None else int(bool(v))


def nt_autoconnect(folder: str | None) -> bool | None:
    """NinjaTrader 8's 'Connect on startup' from its config.xml when the file says so (best effort: NinjaTrader keeps no
    documented key, so None = not readable here; the owner ticks it once in Connections > Configure)."""
    if not folder:
        return None
    try:
        with open(os.path.join(folder, "config.xml"), encoding="utf-8", errors="replace") as fh:
            txt = fh.read(4_000_000)
    except OSError:
        return None
    vals = [m.group(1).lower() == "true" for m in _AUTOCONNECT.finditer(txt)]
    return (True if any(vals) else False) if vals else None


def _git(root):
    from .self_heal import make_git
    return make_git(root)


def version(root: str = ROOT, git=None) -> dict:
    """{"v": HEAD sha7, "p": the update source's newer sha7 (fetched by the hourly auto-update) | None}. Never raises."""
    git = git or _git(root)
    out = {"v": None, "p": None}
    try:
        c, head = git("rev-parse", "HEAD")
        head = head.strip() if c == 0 else ""
        out["v"] = head[:7] or None
        from . import autoupdate
        src = autoupdate.source(root)
        c, new = git("rev-parse", "--verify", "-q", f"{src['remote']}/{src['branch']}")
        new = new.strip() if c == 0 else ""
        if head and new and new != head and git("merge-base", "--is-ancestor", head, new)[0] == 0:
            out["p"] = new[:7]
    except Exception:  # noqa: BLE001
        pass
    return out


def local(root: str = ROOT, now=None, git=None) -> dict:
    """What only this PC can see (read from its own files): accounts + auto-resume + keep-alive, the version, NinjaTrader's
    connection + auto-connect, the clock. Never raises."""
    now = time.time() if now is None else now
    out = {"acc": [], "ka": None, "up": version(root, git), "nt_conn": None, "nt_auto": None, "clk": None}
    try:
        from . import go, keepalive
        from .ninjatrader import is_sim
        armed = [a for a in go.armed_accounts() if not is_sim(a[2])]
        on, _off = go.autoresume_rows(armed=armed)
        kc = keepalive.load_config(None, path=go._ka_path()).get("accounts") or {}
        for key, lbl, _name in armed:
            short = lbl.split(" ..")[0]
            out["acc"].append([short, 1, int(short in on), int(kc.get(key) is True)])
        out["ka"] = [sum(1 for r in out["acc"] if r[3]), len(out["acc"])]
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import autoresume
        out["nt_conn"] = autoresume.nt_connected({"adapter": "ninjatrader"})
    except Exception:  # noqa: BLE001
        pass
    try:
        from .self_heal import CLOCK_MAX_S, clock_drift, nt_folder
        out["nt_auto"] = nt_autoconnect(nt_folder())
        d = clock_drift(root, now)
        out["clk"] = None if d is None else [int(abs(d) <= CLOCK_MAX_S), round(d, 1)]
    except Exception:  # noqa: BLE001
        pass
    return out


def _bots(glance) -> dict:
    return {str(b.get("id")): b for b in (glance or {}).get("bots") or [] if isinstance(b, dict) and b.get("id")}


def pillars(glance, blitz, tr, running, bp=None) -> list:
    """[[pillar, state, words]] state: run (trading, armed) / on (running, not armed) / paper / off / wait."""
    bots = _bots(glance)
    out = []
    for pid, key in (("LIT", "lit"), ("ATLAS", "atlas")):
        b = bots.get(key)
        if not b:
            out.append([pid, "off" if running is False else "wait", "bot stopped" if running is False else "no word from the bot yet"])
        elif b.get("on") and b.get("armed"):
            out.append([pid, "run", "running, armed" + (f" ({b.get('mode')})" if b.get("mode") else "")])
        elif b.get("on"):
            out.append([pid, "on", "running, NOT armed" + (f": {str(b.get('nar'))[:50]}" if b.get("nar") else "")])
        else:
            out.append([pid, "off", "stopped"])
    bz = blitz if isinstance(blitz, dict) else {}
    pl = bp if isinstance(bp, dict) and bp.get("paper") and not bp.get("error") else None    # day-blitzready: the PAPER lane's own report
    if pl and bp.get("fresh"):
        out.append(["BLITZ", "paper", f"paper lane: {bp.get('today_n', 0)} trades today"])
    elif bz and not bz.get("off"):
        out.append(["BLITZ", "paper" if "PAPER" in str(bz.get("badge") or "").upper() else "run", f"on ({str(bz.get('badge') or 'running').lower()})"])
    else:
        out.append(["BLITZ", "off", "off (hidden, paper only)"])
    t = tr if isinstance(tr, dict) else {}
    if t.get("on"):
        out.append(["OF", "run", f"recording ticks: {t.get('d', 0)} of {t.get('of', 60)} study days"])
    elif t:
        out.append(["OF", "off", f"recorder off ({t.get('d', 0)} days on disk)"])
    else:
        out.append(["OF", "wait", "tick recorder not set up yet"])
    return out


def need(b: dict) -> dict | None:
    """The ONE thing that needs the owner AT THE PC, first match wins (None = nothing)."""
    nt = b.get("nt") or [None, None, None]
    if b.get("srv") == 0:
        return {"k": "server", "t": "Bot server is down: double-click tools/bat/BOTS_BACK.bat on the PC"}
    if nt[0] == 0:
        return {"k": "nt", "t": "NinjaTrader is closed: open it on the PC and log in (self-heal also tries within the hour)"}
    if nt[1] == 0:
        return {"k": "nt_conn", "t": "NinjaTrader is not connected: Connections > your MFFU connection (tick 'Connect on startup' once)"}
    acc = b.get("acc") or []
    bots = {p[0]: p for p in b.get("pl") or []}
    if any(bots.get(p, [None, None])[1] == "on" for p in ("LIT", "ATLAS")):
        return {"k": "arm", "t": "An account is running but NOT armed: START_BOT.bat on the PC and type I ACCEPT LIVE RISK"}
    if any(r[2] == 0 for r in acc):
        return {"k": "resume", "t": "Auto-resume is off for " + ", ".join(r[0] for r in acc if r[2] == 0)
                + ": START_BOT.bat once and type the phrase (it turns auto-resume on)"}
    blk = (b.get("up") or {}).get("b") or []
    if blk:
        return {"k": "update", "t": f"Update held back by {', '.join(blk[:2])} (a strategy / account file is never parked): send Claude this line"}
    clk = b.get("clk")
    if clk and clk[0] == 0:
        return {"k": "clock", "t": "PC clock is off: right-click FIX_CLOCK.bat > Run as administrator (once)"}
    if any(r[3] == 0 for r in acc):
        return {"k": "keepalive", "t": "Keep-alive is off for " + ", ".join(r[0] for r in acc if r[3] == 0) + ": KEEPALIVE_ON.bat on the PC"}
    if nt[2] == 0:
        # day-healthqa 2026-11-27: NinjaTrader's 'Connect on startup' read OFF (config.xml) and nothing above needed the owner. Today it is
        # connected, but after any restart (Windows Update, a crash, self-heal reopening NinjaTrader) it would sit DISCONNECTED: no trade,
        # and the 7-day keep-alive's order (MFFU closes an account after 7 days without a fill) would not reach MFFU. Last in the list:
        # only when nothing more urgent is open. None (not readable) says nothing.
        return {"k": "nt_auto", "t": "NinjaTrader 'Connect on startup' is OFF: Connections > Configure > your MFFU connection > tick "
                                     "'Connect on startup' > OK (once), so a restart reconnects by itself"}
    return None


def block(loc: dict | None, glance=None, blitz=None, tr=None, sh=None, nt_running=None, server=None, running=None, bp=None) -> dict:
    """The public "ck" block from this PC's local view + what the report already holds. Pure. <= ~600 bytes."""
    loc = loc or {}
    up = dict(loc.get("up") or {})
    shd = sh if isinstance(sh, dict) else {}
    if "update_blocked" in (shd.get("need") or []) and shd.get("blk"):
        up["b"] = [str(x)[:40] for x in shd["blk"][:3]]
    if isinstance(shd.get("pk"), dict):
        up["k"] = shd["pk"]                           # the last auto-park (engine/self_heal.park_tiny)
    t = tr if isinstance(tr, dict) else {}
    b = {"pc": 1, "srv": _i(server), "nt": [_i(nt_running), _i(loc.get("nt_conn")), _i(loc.get("nt_auto"))],
         "acc": [list(r) for r in (loc.get("acc") or [])][:8], "ka": loc.get("ka"), "up": {k: v for k, v in up.items() if v},
         "tr": [t.get("d", 0), t.get("of", 60), _i(t.get("on"))] if t else None,
         "clk": loc.get("clk"), "pl": pillars(glance, blitz, tr, running, bp)}
    bz = next((p for p in b["pl"] if p[0] == "BLITZ"), None)
    b["bz"] = bz[1] if bz else "off"
    b["need"] = need(b)
    return {k: v for k, v in b.items() if v is not None}


def pillar_lines(ck: dict | None) -> list:
    """One plain line per pillar (the PC post / the phone): 'LIT: running, armed'."""
    names = {"LIT": "LIT", "ATLAS": "ATLAS", "BLITZ": "BLITZ", "OF": "Order Flow"}
    return [f"{names.get(p[0], p[0])}: {p[2]}" for p in (ck or {}).get("pl") or []]


def main(argv=None) -> int:
    loc = local()
    b = block(loc)
    if "--json" in (argv or sys.argv[1:]):
        print(json.dumps(b, indent=1))
        return 0
    print(json.dumps(b, separators=(",", ":")))
    print("needs you at the PC: " + ((b.get("need") or {}).get("t") or "nothing"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
