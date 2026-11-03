"""CRONOS freshness: is an app's data still current, and what its Jarvis card says about it (honest, never fake-fresh).

Jarvis greys a card 30 minutes after its `t` (tools/web_public/jarvis/apps.js STALE_AFTER_S). A research app's data is
made once a night or once a week, so at every site publish its card is re-stamped:

  fresh    the last good run (or the last check that found nothing new) is within the task's max age (weekday hours):
           t = the publish time, the engine's status kept, one line "Updated nightly · last run Tue Nov 3, 23:07 ET"
  stale    older than that: t = the publish time, level "warn" (amber), "Not updated since Tue Nov 3", the last numbers
           kept and labelled as the last status
  failed   the last scheduled run failed after the last good one: amber too, with the failure and its date
  no data  no time at all: amber "No data yet"

The engine's own card is kept in card["cronos"]["orig"], so stamping twice gives the same card (idempotent).
"""
from __future__ import annotations

import copy
import datetime as dt
import math
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LABEL_MAX, LINE_MAX, LINES_MAX = 48, 120, 3      # the Jarvis contract (docs/JARVIS_APPS.md)


def business_hours(a: float, b: float) -> float:
    """Hours from a to b (unix seconds) that fall on Mon-Fri in New York time (weekends do not age a nightly job)."""
    if not a or not b or b <= a:
        return 0.0
    if b - a > 400 * 86400:                     # far too old to matter: a rough count is enough
        return (b - a) / 3600.0 * 5 / 7
    t, total = dt.datetime.fromtimestamp(a, ET), 0.0
    end = dt.datetime.fromtimestamp(b, ET)
    while t < end:
        nxt = dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(0), ET)
        seg_end = min(nxt, end)
        if t.weekday() < 5:
            total += (seg_end.timestamp() - t.timestamp()) / 3600.0
        t = seg_end
    return total


def when(t: float | None, short: bool = False) -> str:
    if not t:
        return "never"
    d = dt.datetime.fromtimestamp(t, ET)
    day = f"{d:%a} {d:%b} {d.day}"
    return day if short else f"{day}, {d:%H:%M} ET"


def data_time(card: dict | None) -> int | None:
    """The time the card's data was made: the engine's own t (kept in cronos.orig once stamped)."""
    if not isinstance(card, dict):
        return None
    cr = card.get("cronos")
    if isinstance(cr, dict) and isinstance(cr.get("orig"), dict):
        t = cr["orig"].get("t")
    else:
        t = card.get("t")
    return int(t) if isinstance(t, (int, float)) and math.isfinite(t) and t > 0 else None


def verdict(task, card_t: int | None, entry: dict | None, now: float) -> dict:
    """{state: fresh|stale|failed|nodata, last_ok, age_h, error, run_t} for one task."""
    entry = entry if isinstance(entry, dict) else {}
    last_ok = max(int(entry.get("last_ok_t") or 0), int(card_t or 0)) or None
    run_t = int(entry.get("last_run_t") or 0) or None
    failed = entry.get("ok") is False and run_t is not None and run_t >= (last_ok or 0)
    age_h = business_hours(last_ok, now) if last_ok else None
    if failed:
        state = "failed"
    elif last_ok is None:
        state = "nodata"
    elif age_h <= task.max_age_h:
        state = "fresh"
    else:
        state = "stale"
    return {"state": state, "last_ok": last_ok, "age_h": None if age_h is None else round(age_h, 1),
            "error": str(entry.get("error") or "")[:200] if failed else "", "run_t": run_t}


def _cut(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def stamp(card: dict, task, v: dict, now: float) -> dict:
    """The card to publish for verdict v (see the module doc). Never invents numbers: kpis are the engine's own."""
    cr0 = card.get("cronos") if isinstance(card.get("cronos"), dict) else None
    orig = copy.deepcopy(cr0["orig"]) if cr0 and isinstance(cr0.get("orig"), dict) else \
        {"t": card.get("t"), "status": copy.deepcopy(card.get("status")), "lines": list(card.get("lines") or [])}
    out = {k: copy.deepcopy(val) for k, val in card.items() if k != "cronos"}
    st = orig.get("status") if isinstance(orig.get("status"), dict) else {"level": "off", "label": ""}
    lines = [str(x) for x in (orig.get("lines") or []) if isinstance(x, str)]
    every = task.every
    if v["state"] == "fresh":
        out["status"] = {"level": st.get("level", "ok"), "label": _cut(st.get("label", ""), LABEL_MAX)}
        tail = f"Updated {every} · last run {when(v['last_ok'])}"
        out["lines"] = [_cut(x, LINE_MAX) for x in lines[: LINES_MAX - 1]] + [_cut(tail, LINE_MAX)]
    else:
        if v["state"] == "nodata":
            label, why = "No data yet", f"Updates {every}: no run has finished yet"
        else:
            label = f"Not updated since {when(v['last_ok'], short=True)}"
            why = (f"Last {task.cadence} run failed {when(v['run_t'])}" + (f": {v['error']}" if v["error"] else "")
                   if v["state"] == "failed" else f"Updates {every}; last good data {when(v['last_ok'])}")
        out["status"] = {"level": "warn", "label": _cut(label, LABEL_MAX)}
        last = f"Last status: {st.get('label', '')}" if st.get("label") else ""
        out["lines"] = [_cut(x, LINE_MAX) for x in ([why] + ([last] if last else []) + lines)[:LINES_MAX]]
    out["t"] = int(now)
    # how long Jarvis keeps the card current between site publishes (apps.js stale_after): nightly 3 days, weekly 8 days
    out["stale_after"] = 3 * 86400 if task.cadence == "nightly" else 8 * 86400
    out["cronos"] = {"state": v["state"], "data_t": orig.get("t"), "checked_t": v["last_ok"], "age_h": v["age_h"],
                     "cadence": task.cadence, "max_age_h": task.max_age_h, "orig": orig}
    return out


def valid_card(card) -> list:
    """The Jarvis contract's checks that matter here (apps.js validateStatus); [] when the card is fine."""
    bad = []
    if not isinstance(card, dict):
        return ["not an object"]
    if card.get("v") != 1:
        bad.append("v must be 1")
    st = card.get("status")
    if not isinstance(st, dict) or st.get("level") not in ("ok", "warn", "bad", "off"):
        bad.append("status.level")
    elif not isinstance(st.get("label"), str) or len(st["label"]) > LABEL_MAX:
        bad.append("status.label")
    if not isinstance(card.get("t"), (int, float)) or not 0 < card["t"] < 1e11:
        bad.append("t")
    lines = card.get("lines") or []
    if not isinstance(lines, list) or len(lines) > LINES_MAX or any(not isinstance(x, str) or len(x) > LINE_MAX for x in lines):
        bad.append("lines")
    if len((card.get("kpis") or [])) > 3:
        bad.append("kpis")
    import json
    if len(json.dumps(card, ensure_ascii=False).encode("utf-8")) > 8192:
        bad.append("over 8 KB")
    return bad
