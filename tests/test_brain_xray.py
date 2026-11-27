"""BRAIN X-RAY (engine/brain_xray.py; day-brains-feed 2026-11-27): the ext block "bx" for nq/brainview.js. No network, ~5 s.
  a. LIT from a real replayed day (engine/brain.replay 2026-11-20 -> compact, as the heartbeat carries it): stage, ATR, the rules
     [0.5, 0.8, 1.5], the forming setups per side, the newest setups with EVERY check as "value / rule" (depth "4.38 / 0.5 ATR",
     stop "196.5 pts (8-80)", target "9.1R / 1.5R"), the first failing check, setups today, the sizing (micros, $ risk, $ at target)
  b. ATLAS (routed lobes only) with checks (name, pass, value, need) + the armed plan; BLITZ (paper) state + signals; none = None
  c. size: <= 1,400 bytes; fit() shrinks it to 900 / 500 (texts, older setups, checks, BLITZ out) and keeps the gates' keys
  d. no account ids / names (the hb's ATLAS account label never copied); junk never raises
  e. pc_report: "bx" built in full() in its own try/except, rides LAST (EXT_LAST after bf / glog), has its cuts
    python -X utf8 -m tests.test_brain_xray
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import brain_xray as X  # noqa: E402

RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:700]}"))


def main():
    from engine import brain
    b = brain.replay("2026-11-20", None)
    hb = {"t": 1795200000, "brain": brain.compact(b)}
    sec = {"route": {"account_b": {"keys": ["ema_lon_vix"], "label": "MFFUSFBLDR123456018"}}, "strategies": {
        "ema_lon_vix": {"short": "EMA", "route": True, "state": {"stage": "armed"}, "brain": {"stage": "armed", "first_fail": "",
                        "checks": [{"k": "window", "name": "Entry 02:00-05:00 ET", "ok": True, "val": "03:10 ET"}, {"k": "pull", "name": "Pullback reached the 5m EMA 50", "ok": True, "val": "0.62 ATR run", "need": "0.1"}],
                        "plan": {"side": "short", "entry": 26380.75, "stop": 26419.5, "target": 26122.75, "risk_usd": 77.5, "qty_500": 6}}},
        "macd_x": {"short": "MACD", "candidate": True, "brain": {"stage": "window"}}}}
    hb["second"] = sec
    hb["blitz"] = {"paper": True, "state": "BLITZ (paper): band ready, no break yet", "signals": [{"hm": "09:41", "side": "long", "text": "upper band break"}], "band": {"day_ok": True}}
    x = X.build(hb)
    L = x["lit"]
    last = L["s"][-1]
    ch = {c[0]: c for c in last[4]}
    check("a. LIT: stage 'done', ATR, the rules [0.5, 0.8, 1.5], forming setups per side ([side, stage, depth, disp, allowed])",
          L["st"] == "done" and L["a"] > 0 and L["r"] == [0.5, 0.8, 1.5] and all(len(w) == 5 and w[0] in ("L", "S") for w in L["w"]), {k: L[k] for k in ("st", "a", "r", "w")})
    check("a. the newest setup 15:50 LONG rejected by 'window', every check as value / rule (depth 4.38 / 0.5 ATR, disp 1.72 / 0.8 ATR, idm 0 / 1, stop 196.5 pts (8-80), target 9.1R / 1.5R)",
          last[:4] == ["15:50", "L", "rejected", "window"] and ch["depth"][1:] == [1, "4.38 / 0.5 ATR"] and ch["disp"][2] == "1.72 / 0.8 ATR"
          and ch["idm"][1:] == [0, "0 / 1"] and ch["stop"][1:] == [0, "196.5 pts (8-80)"] and ch["target"][2] == "9.1R / 1.5R" and ch["window"][2] == "15:50 in 02:00-15:30", last)
    check("a. 4 newest setups, setups today [9, 0], sizing [4 micros, $376, 45.8 pts, $3,805, what]",
          len(L["s"]) == 4 and L["n"] == [9, 0] and L["sz"][:4] == [4, 376.0, 45.8, 3805.0] and isinstance(L["sz"][4], str), (len(L["s"]), L["n"], L["sz"]))
    A = x["atlas"]["l"]
    check("b. ATLAS: the routed lobe only (EMA, not the MACD candidate), its checks [name, pass, value, need] and the plan [short, entry, stop, target, $77.5 -> 78, 6]",
          [a[0] for a in A] == ["EMA"] and A[0][1] == "armed" and A[0][3][1] == ["Pullback reached the 5m EMA 50", 1, "0.62 ATR run", "0.1"]
          and A[0][4] == ["short", 26380.75, 26419.5, 26122.75, 78.0, 6], A)
    check("b. BLITZ (paper): state, signals, band ok; a non-paper BLITZ = None; no brains at all = None",
          x["blitz"]["st"].startswith("BLITZ (paper)") and x["blitz"]["sg"] == [["09:41", "long", "upper band break"]] and x["blitz"]["ok"] is True
          and X.blitz({"state": "x"}) is None and X.build({"t": 1}) is None, x["blitz"])
    s0 = X.size(x)
    check("c. size <= 1,600 bytes", s0 <= X.MAX_BYTES, s0)
    for n in (900, 500):
        y = json.loads(json.dumps(x))
        X.fit(y, n)
        check(f"c. fit({n}): <= {n} bytes, the LIT stage / rules / newest setup's gate keys stay", X.size(y) <= n and y["lit"]["st"] == "done" and y["lit"]["r"] == [0.5, 0.8, 1.5]
              and [c[0] for c in y["lit"]["s"][-1][4]][:4] == ["day", "window", "depth", "disp"], (X.size(y), y))
    txt = json.dumps(x)
    check("d. no account id or name (the ATLAS route label MFFUSFBLDR... never copied, no 5+ digit run but prices)",
          "MFFUSFBLDR" not in txt and "123456" not in txt and "label" not in txt, re.findall(r"[A-Z]{4,}\d+", txt))
    check("d. junk never raises", all(X.build(j) is None or isinstance(X.build(j), dict) for j in (None, 1, "x", [], {"brain": 5}, {"second": {"strategies": 3}}, {"blitz": []})))
    rep = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    from tools import pc_report as PR
    check("e. pc_report: bx built in full() (try/except), rides last (EXT_LAST = bf, glog, bx), cut 900 / 500 then out",
          "bx = brain_xray.build(hb)" in rep and PR.EXT_LAST[-1] == "bx" and len(PR._cuts("bx")) == 2)
    core, exts = PR.split({"v": 1, "kind": "le-live", "t": 1, "lite": True, "bx": x, "glog": {"lit": [["01:00", "a"]]}})
    got = [e for e in exts if "bx" in (e.get("x") or {})]
    check("e. split(): bx lands in an ext post (not the core), under the post limit", got and "bx" not in core and "bx" not in (core.get("x") or {}) and all(len(json.dumps(e)) <= PR.MAX_STATUS_BYTES for e in exts), [list(e) for e in exts])
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
