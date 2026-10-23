"""AI watch API for the PC dashboard (read-only GET; engine/ai_watch.py, engine/rulelog.py).

  GET /api/next/ai     the bot's AI-watch block (anomalies, drift per strategy, both-accounts loss, rule changes, switches)
                       + the rule-change log (git: who / when / why, and this PC's runtime changes) + the exact switches.
Shown on the PC: Modules > System > "AI watch" card (web_next/js/next/hubpages.js). Nothing here changes the bot.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

SWITCHES = [
    {"key": "anomaly_pause", "off": True, "what": "No new entry (LIT + account B) for 15 min after a price spike / bad tick, and while "
     "the feed is frozen mid-trade", "on": 'live_model.json "guards": {"anomaly_pause": true} (minutes: "anomaly_pause_min")'},
    {"key": "combined_loss", "off": True, "what": "No new entry on either account once LIT + account B together are at -$1,500 today "
     "or -$3,000 this week", "on": 'live_model.json "guards": {"combined_loss": true, "combined_day_usd": 1500, "combined_week_usd": 3000}'},
    {"key": "alerts", "off": False, "what": "Pushes: anomaly, freeze (critical), drift, loss_cap, rules_change",
     "on": "phone Settings > Alert levels (on / silent / off per kind)"},
]


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def view(bot=None, now=None) -> dict:
    from . import ai_watch, rulelog
    now = int(now or time.time())
    blk = ai_watch.hb_block(bot) if bot is not None else None
    if blk is None and bot is not None:
        st = ai_watch._read(ai_watch.state_path(bot), {}) or {}
        if st:
            blk = {"v": ai_watch.VERSION, "t": st.get("t"), "anomalies": (st.get("anomalies") or [])[-6:], "drift": st.get("drift") or [],
                   "loss": st.get("loss"), "rule_changes": (st.get("rule_changes") or [])[-5:], "stored": True}
    rl = rulelog.view()
    if not rl.get("commits"):
        rl["commits"] = rulelog.history(30)
    rl["commits"] = (rl.get("commits") or [])[:30]
    return {"v": 1, "t": now, "ai": blk, "rule_log": rl, "switches": SWITCHES,
            "note": "Alerts only by default. The two blocks are OFF until switched on; open trades always keep their stop / target."}


@router.get("/api/next/ai")
def r_ai():
    try:
        from . import pcdash_api
        bot = pcdash_api._bot()
    except Exception:
        bot = None
    try:
        return _J(view(bot))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)
