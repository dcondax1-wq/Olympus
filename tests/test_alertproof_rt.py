"""Alert-proof red team (2026-11-23): the readiness "told" de-dupe never swallows a NEW clock problem.
The guard's clock alarm is once a DAY (key guard:clock:<day>): drift at 02:05 (guard told), fixed, drift again at 05:00 = a new
episode; readiness must alert for it (the guard will not again today). Offline: temp files, a fake sender.
    python -X utf8 -m tests.test_alertproof_rt
"""
import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import readiness as R  # noqa: E402

RES = []
ET = ZoneInfo("America/New_York")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(info)[:300]}]"))


OKC = [{"key": k, "level": "ok", "text": "x"} for k in ("server", "bot", "heartbeat", "nt_conn", "feed_1m", "feed_5m", "internet")]
HB = {"t": 1, "health": {"account": {"label": "LIVE", "armed": True, "enabled": True}, "accounts": []},
      "second": {"route": {"account_b": {"label": "live", "armed": True}}}}


def facts(drift):
    return {"hb": HB, "drift_s": drift, "disk_free_gb": 100, "checks": OKC, "k7": []}


def main():
    d = tempfile.mkdtemp()
    ip = os.path.join(d, "instant.json")
    t_guard = dt.datetime(2026, 11, 24, 2, 5, tzinfo=ET).timestamp()
    json.dump({"keys": {"crit:guard:clock:2026-11-24": t_guard}}, open(ip, "w"))
    check("a. the guard told at 02:05, readiness sees the drift at 02:10 (same episode): told", R.guard_told("clock", path=ip, now=t_guard + 300, since=t_guard + 300))
    check("b. a NEW episode at 05:00 (the guard told at 02:05, it will not again today): NOT told -> readiness alerts",
          not R.guard_told("clock", path=ip, now=t_guard + 3 * 3600, since=t_guard + 3 * 3600))
    check("c. no start known: the old 6 h rule", R.guard_told("clock", path=ip, now=t_guard + 3600))
    sp, lp = os.path.join(d, "st.json"), os.path.join(d, "last.json")
    got = []
    t0 = dt.datetime(2026, 11, 24, 2, 10, tzinfo=ET).timestamp()
    R.tick(t0, facts=facts(25), sender=got.append, last_path=lp, state_path=sp)
    R.tick(t0 + 300, facts=facts(25), sender=got.append, last_path=lp, state_path=sp)
    s1 = json.load(open(sp))["since"].get("clock")
    R.tick(t0 + 600, facts=facts(0.2), sender=got.append, last_path=lp, state_path=sp)        # fixed
    s2 = json.load(open(sp)).get("since", {}).get("clock")
    R.tick(t0 + 3 * 3600, facts=facts(25), sender=got.append, last_path=lp, state_path=sp)   # back 3 h later
    s3 = json.load(open(sp))["since"].get("clock")
    check("d. the episode start: kept while it lasts, cleared when fixed, NEW when it comes back", s1 == int(t0) and s2 is None and s3 == int(t0 + 3 * 3600),
          (s1, s2, s3))
    check("e. the alert carries its episode start", got and got[-1].get("blocker_since") == int(t0 + 3 * 3600), got[-1:] if got else got)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
