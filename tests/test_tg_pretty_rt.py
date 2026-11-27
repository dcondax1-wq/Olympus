"""red team #39 (day-tgpretty 2026-11-27): (1) is_paper is whole words: an MFFU 'Sim Funded' account (the payout accounts) is never
paper; NinjaTrader Sim101 / Playback101, BLITZ, paper, demo, replay, Account C are. (2) A Telegram skip (paper) / rate-limit hold is
no delivery: ntfy / the app still get the alert, the held Telegram is never retried, a failure elsewhere is not hidden.
    python -X utf8 -m tests.test_tg_pretty_rt
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main():
    from engine import alert_bus as A, tg_pretty as T
    real = ["ATLAS 25K Sim Funded", "Builder 50K SIM FUNDED", "Zlarior 50K", "Rapid EOD 25K", "Simon", "Keep-alive on ATLAS 25K sim-funded"]
    for a in real:
        check(f"real account '{a}' is not paper", not T.is_paper({"kind": "entry", "account": a}))
    check("preset builder_25k_sim_funded in web.strategy is not paper",
          not T.is_paper({"kind": "exit", "account": "ATLAS", "web": {"strategy": "builder_25k_sim_funded"}}))
    for a in ("Sim101", "Playback101", "BLITZ", "BLITZ paper", "demo 1", "replay", "acctc", "acct_c", "Paper ATLAS"):
        check(f"'{a}' is paper", T.is_paper({"kind": "entry", "account": a}))

    calls = []
    orig = A._one

    def fake(fail=()):
        def f(ch, cfg, ev, title, body, silent):
            calls.append(ch)
            if ch == "telegram":
                return orig(ch, cfg, ev, title, body, silent)
            return (None, "down") if ch in fail else (f"id-{ch}", "ok")
        return f
    slept = []
    A._SLEEP = lambda s: slept.append(s)
    with tempfile.TemporaryDirectory() as td:
        st, lg = os.path.join(td, "s.json"), os.path.join(td, "f.log")
        cfg = {"telegram": {"token": "1:x", "chat_id": "1"}, "ntfy": True, "webpush": False}
        try:
            A._one = fake()
            calls.clear()
            r = A.deliver({"kind": "entry", "account": "Sim101", "key": ""}, cfg=cfg, path=st, log_path=lg)
            check("paper entry: Telegram skipped, ntfy still delivers", r["ok"] and "ntfy" in r["receipts"] and "telegram" in r.get("held", {}),
                  r)
            A._one = fake(fail=("ntfy",))
            calls.clear()
            slept.clear()
            r = A.deliver({"kind": "entry", "account": "Sim101", "key": ""}, cfg=cfg, path=st, log_path=lg)
            check("paper entry with ntfy down: not ok (the failure is not hidden), Telegram never retried",
                  not r["ok"] and calls.count("telegram") == 1 and calls.count("ntfy") >= 2, (r, calls))
            A._one = fake()
            calls.clear()
            slept.clear()
            r = A.deliver({"kind": "entry", "account": "Sim101", "key": ""}, cfg={"telegram": {"token": "1:x", "chat_id": "1"},
                                                                                  "ntfy": False, "webpush": False}, path=st, log_path=lg)
            check("Telegram the only channel + paper: ok, no backoff sleeps", r["ok"] and not slept, (r, slept))
            calls.clear()
            r = A.deliver({"kind": "entry", "account": "ATLAS 25K Sim Funded", "key": ""}, cfg=cfg, path=st, log_path=lg)
            check("Sim Funded entry: Telegram is tried (not skipped)", "telegram" in calls and "telegram" not in r.get("held", {}), r)
        finally:
            A._one = orig
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
