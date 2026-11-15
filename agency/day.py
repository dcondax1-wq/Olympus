"""THE AGENCY DAY, end to end, in one double-click (AGENCY_DAY.bat runs this; team BIZ, 2026-11-15):

    python -m agency.day                         leads in your city -> 3 demo sites + pitch kits -> the call list -> the Business page
    python -m agency.day --city "Boise, ID"      another city for one run
    python -m agency.day --skip-leads            reuse today's batch (no map search): call list + Business page only

1. agency.run          today's leads (OpenStreetMap), demo sites, pitch kits, the Agency page data      (agency/out/<city>/)
2. agency.calls.build  the call list for the phone, every "do not call" removed, call windows set       (agency/calls/out/)
3. tools/biz_publish   the Business page: every money model's next action and money                    (tools/web_public/business/business.json)
4. the day's sheet     one page to read before calling: who, the opener, the price, the rules           (agency/out/TODAY.txt)

Nothing is sent and nobody is called: you dial by hand, in business hours, and press send yourself (docs/COLD_CALLING_RULES.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import OUT_DIR, ROOT
from . import config as CFG

RULES = ("Dial by hand, 9:00-17:00 their time, Monday to Friday. Never a robot, a recording or a text they did not ask for.",
         "Say who you are in the first sentence. Anyone who says stop: mark Do not contact at once.",
         "Emails only once your real name, email and postal address are in agency/config.json (CAN-SPAM).")


def latest_batch(base: str = OUT_DIR) -> str | None:
    """the newest agency/out/<city>/ folder that has a run.json"""
    runs = sorted(Path(base).glob("*/run.json"), key=lambda p: p.stat().st_mtime, reverse=True) if os.path.isdir(base) else []
    return str(runs[0].parent) if runs else None


def day_sheet(batch: str, calls: dict | None, cfg: dict, limit: int = 10) -> str:
    """the plain text sheet for the day: the price list (the one source), the demo sites, the first calls, the rules"""
    run = json.load(open(os.path.join(batch, "run.json"), encoding="utf-8"))
    pr = CFG.prices(cfg)
    lines = [f"AGENCY DAY {dt.date.today().isoformat()}  {run.get('city', '')}", "",
             "PRICES (agency/config.json, the one source): " + "; ".join(f"{p['name']} ${p['setup']:,.0f} + ${p['monthly']:,.0f}/mo" for p in pr.values()), "",
             "DEMO SITES (drag each folder onto app.netlify.com/drop, press Publish):"]
    for s in run.get("sites") or []:
        lines.append(f"  - {s['name']}: {s['folder']}  ->  {s['demo_url']}  ({s['package']} ${s['setup']:,.0f} + ${s['monthly']:,.0f}/mo)")
    lines += ["", "CALL FIRST (the call list on your phone has the rest):"]
    rows = (calls or {}).get("rows") or []
    for r in rows[:limit]:
        lines.append(f"  {r.get('name', '')[:34]:34} {r.get('phone', ''):16} {r.get('when', '')}")
    if not rows:
        lines.append("  (no call list yet: the Agency page's Call today has the same leads)")
    lines += ["", "RULES:"] + [f"  - {x}" for x in RULES]
    lines += ["", "Emails: " + ("ready to send" if run.get("sender_ready") else "NOT ready: put your real name, email and postal address in agency/config.json")]
    return "\n".join(lines) + "\n"


def call_rows(res: dict) -> list:
    """agency.calls.build's result -> short rows for the day sheet (name, phone, when), callable ones first"""
    from .calls import core as CC
    out = []
    for r in (res or {}).get("rows") or []:
        L, w, b = r.get("lead") or {}, r.get("win"), r.get("block")
        if b and b.get("lock") or not L.get("phone"):
            continue                                        # do not call / opted out / no phone: never on the sheet
        when = "good now" if w and w.get("code") == "best" else (CC.when_words(w["next"]["start"], w["zones"][0], res.get("now")) if w and w.get("next") else "")
        out.append({"name": str(L.get("name") or ""), "phone": CC.pretty_phone(L["phone"]), "when": when})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agency.day", description="The agency day: leads -> demo sites -> call list -> Business page. Sends nothing.")
    ap.add_argument("--city", default=None)
    ap.add_argument("--extract", default=None, help="a local OpenStreetMap extract when the free map server is busy")
    ap.add_argument("--skip-leads", action="store_true", help="reuse the newest batch in agency/out/ (no map search)")
    ap.add_argument("--out", default=None, help="batch folder (default agency/out/<city>/)")
    ap.add_argument("--calls-out", default=None, help="call list folder (default agency/calls/out, git-ignored)")
    ap.add_argument("--no-publish", action="store_true", help="do not refresh the Business page data (tests)")
    a = ap.parse_args(argv)
    if not os.environ.get("AGENCY_CONFIG"):
        CFG.ensure_owner_copy()
    cfg = CFG.load()
    ph = cfg.get("_placeholders") or []
    if "search.city" in ph and not a.city and not a.skip_leads:
        print("[STOP] Put your city in agency/config.json (search.city, like \"Boise, ID\") or run with --city \"Boise, ID\".")
        return 2
    print("AGENCY DAY: leads -> demo sites -> call list -> Business page (nothing is sent, nobody is called)")
    if not a.skip_leads:
        from . import run as RUN
        rargs = [x for x in (["--city", a.city] if a.city else []) + (["--extract", a.extract] if a.extract else []) + (["--out", a.out] if a.out else [])]
        rc = RUN.main(rargs)
        if rc == 2:
            return 2
    batch = a.out or latest_batch()
    if not batch or not os.path.isfile(os.path.join(batch, "run.json")):
        print("[STOP] No batch yet: run without --skip-leads first.")
        return 2
    calls = None
    try:
        from .calls import build as CB
        files = [Path(batch) / "leads.json"] if (Path(batch) / "leads.json").is_file() else []
        if files:
            co = Path(a.calls_out) if a.calls_out else CB.OUT
            res = CB.build(files, out_dir=co)
            calls = {"rows": call_rows(res)}
            print(f"Call list: {len(calls['rows'])} to call -> {co / 'call_list.json'} (import it on the phone: Call copilot > Your data > Import)")
    except Exception as e:                                   # the call list is a help, never a reason to lose the batch
        print(f"[NOTE] call list not made: {e}")
    if not a.no_publish:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import biz_publish as BP
            p = BP.write(BP.build())
            print(f"Business page data: {p}")
        except Exception as e:
            print(f"[NOTE] Business page not refreshed: {e}")
    sheet = day_sheet(batch, calls, cfg)
    sp = os.path.join(os.path.dirname(batch.rstrip("/\\")) or OUT_DIR, "TODAY.txt")
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write(sheet)
    print()
    print(sheet)
    print(f"Saved: {sp}")
    print("Next: 1) drop the 3 site folders on app.netlify.com/drop  2) open the Agency page (Call today) on your phone  3) call, by hand, in business hours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
