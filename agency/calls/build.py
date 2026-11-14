"""Build the call list for the phone from team B1's leads (team B2, 2026-11-14).

    python -m agency.calls.build                          # team B1's day lists (agency/out/<city>/leads.json) + its CRM data, today
    python -m agency.calls.build --leads my_leads.csv     # one file (JSON list, {"leads": [...]}, or CSV with a header row)
    python -m agency.calls.build --dnc 813.txt --dnc 727.txt   # the National Do Not Call downloads for your area codes (free for 5 a year)
    python -m agency.calls.build --merge call-export.json # the phone's export: its "do not call" numbers join the master opt-out list for good
    python -m agency.calls.build --state FL               # the state to assume when a lead has none (your own)

Writes agency/calls/out/call_list.json (import it on the phone: Call copilot > Your data > Import a file), call_list.csv (a printable sheet) and
optouts.json (every "do not call" ever: never shrinks). Everything stays on this PC (git-ignored). Nothing here dials, texts, emails or uploads.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agency.calls import core as C

AGENCY = C.ROOT / "agency"
OUT = AGENCY / "calls" / "out"


def read_leads(path: Path) -> list:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(text)))
        return [{(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in r.items()} for r in rows]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and (data.get("demo") is True or data.get("sample") is True):
        print(f"skip {path}: it is marked demo / sample (example data, not your leads)", file=sys.stderr)
        return []
    if isinstance(data, dict):
        for k in ("leads", "items", "rows", "results"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


SKIP_PARTS = {"calls", "fixtures", "cache", "examples", "templates", "__pycache__", "node_modules"}


def find_lead_files(base: Path = AGENCY) -> list:
    """Team B1's day lists: every leads.json under agency/ (its lead finder writes agency/out/<city>/leads.json), a leads.csv only where that
    folder has no leads.json, plus B1's published CRM data (tools/web_public/agency/leads.json). Never all_leads.csv (everything found, not the
    day's list), other teams' demo fixtures, caches, or our own output in agency/calls/."""
    out = []
    for p in sorted(base.glob("**/leads.json")) + sorted(base.glob("**/leads.csv")):
        if SKIP_PARTS & set(p.relative_to(base).parts[:-1]):
            continue
        if p.suffix == ".csv" and p.with_suffix(".json").is_file():
            continue
        out.append(p)
    crm = C.WEB / "leads.json"
    if base == AGENCY and crm.is_file():
        out.append(crm)
    return out


def load_optouts(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return {"phones": sorted({p for p in map(C.norm_phone, d.get("phones", [])) if p}), "emails": sorted({e.lower() for e in d.get("emails", []) if C.valid_email(e)})}
    except (OSError, ValueError, AttributeError):
        return {"phones": [], "emails": []}


def load_dnc_store(path: Path) -> dict:
    """{phone: {"dnc": "listed" | "clear", "on": "YYYY-MM-DD"}} from earlier builds (never shrinks; junk -> empty)."""
    try:
        d = json.loads(path.read_text(encoding="utf-8")).get("numbers", {})
        return {C.norm_phone(p): v for p, v in d.items() if C.norm_phone(p) and isinstance(v, dict) and v.get("dnc") in ("listed", "clear")}
    except (OSError, ValueError, AttributeError):
        return {}


def merge_export(path: Path, opt: dict) -> int:
    """The phone's export (app agency-calls): its opt-outs and every lead marked do-not-call / email stop join the master list."""
    d = json.loads(path.read_text(encoding="utf-8"))
    phones, emails = set(opt["phones"]), set(opt["emails"])
    n0 = len(phones) + len(emails)
    for p in d.get("optouts", []):
        if C.norm_phone(p):
            phones.add(C.norm_phone(p))
    for L in d.get("leads", []):
        if not isinstance(L, dict):
            continue
        if (L.get("optout") or L.get("stage") == "dnc") and C.norm_phone(L.get("phone")):
            phones.add(C.norm_phone(L.get("phone")))
        if (L.get("emailOptOut") or L.get("stage") == "dnc") and C.valid_email(L.get("email")):
            emails.add(str(L["email"]).lower())
    opt["phones"], opt["emails"] = sorted(phones), sorted(emails)
    return len(phones) + len(emails) - n0


def build(lead_files, dnc_files=(), merges=(), default_state="", now_ms=None, out_dir: Path = OUT, write=True) -> dict:
    rules = C.load_rules()
    now_ms = now_ms or int(time.time() * 1000)
    raw, used = [], []
    for p in lead_files:
        try:
            got = read_leads(Path(p))
        except (OSError, ValueError) as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        raw.extend(got)
        used.append(str(p))
    leads, dupes, skipped = C.norm_leads(raw, rules)
    opt = load_optouts(out_dir / "optouts.json")
    merged = sum(merge_export(Path(m), opt) for m in merges)
    for L in leads:
        if L["phone"] in opt["phones"]:
            L["optout"] = True
        if L["email"] and L["email"].lower() in opt["emails"]:
            L["emailOptOut"] = True
    dnc = {"listed": 0, "clear": 0, "not_covered": 0, "files": 0}
    nums, codes = set(), set()
    for f in dnc_files:
        n, c = C.parse_dnc_file(Path(f).read_text(encoding="utf-8", errors="replace"))
        nums |= n
        codes |= c
        dnc["files"] += 1
    if dnc["files"]:
        dnc.update(C.apply_dnc(leads, nums, codes, C.utc_date(now_ms)))
    # every registry result is kept on the PC (dnc_checked.json): a listed number stays locked for good, a clear one counts for 31 days (callcore dncState)
    store = load_dnc_store(out_dir / "dnc_checked.json")
    for L in leads:
        if not L["phone"]:
            continue
        if L["dnc"] in ("listed", "clear") and (L["dnc"] == "listed" or L.get("dncChecked")):
            old = store.get(L["phone"])
            if not old or old.get("dnc") != "listed":
                store[L["phone"]] = {"dnc": L["dnc"], "on": L.get("dncChecked") or C.utc_date(now_ms)}
        elif L["phone"] in store:
            L["dnc"], L["dncChecked"] = store[L["phone"]]["dnc"], store[L["phone"]]["on"]
    settings = {"defaultState": default_state}
    st = {"leads": leads, "log": [], "optouts": opt["phones"], "settings": settings}
    rows = []
    for L in leads:
        b = C.block_of(L, st, now_ms, rules)
        w = None if b and b.get("lock") else C.window_status(L, now_ms, rules, settings)
        rows.append({"lead": L, "block": b, "win": w})
    summary = {
        "leads": len(leads), "duplicates": dupes, "skipped": skipped, "locked": sum(1 for r in rows if r["block"] and r["block"].get("lock")),
        "no_phone": sum(1 for r in rows if r["block"] and r["block"]["code"] == "nophone"), "no_state": sum(1 for r in rows if r["win"] and r["win"]["code"] == "nozone"),
        "good_now": sum(1 for r in rows if r["win"] and r["win"]["code"] == "best"), "needs_dnc_check": sum(1 for L in leads if C.needs_confirm(L, now_ms, rules)),
        "optouts": len(opt["phones"]), "merged_optouts": merged, "dnc": dnc,
    }
    out = {"v": 1, "app": "agency-calls", "kind": "call_list", "built": datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(timespec="seconds"),
           "source": used, "summary": summary, "leads": leads, "optouts": opt["phones"]}
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "call_list.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        (out_dir / "optouts.json").write_text(json.dumps({"v": 1, "updated": out["built"], "phones": opt["phones"], "emails": opt["emails"]}, indent=1), encoding="utf-8")
        (out_dir / "dnc_checked.json").write_text(json.dumps({"v": 1, "updated": out["built"], "numbers": store}, indent=1, sort_keys=True), encoding="utf-8")
        with (out_dir / "call_list.csv").open("w", encoding="utf-8", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(["name", "phone", "trade", "city", "state", "their_time_now", "status", "next_good_time", "dnc", "demo"])
            for r in rows:
                L, w, b = r["lead"], r["win"], r["block"]
                nxt = C.when_words(w["next"]["start"], w["zones"][0], now_ms) if w and w.get("next") else ""
                wr.writerow([L["name"], C.pretty_phone(L["phone"]), L["trade"], L["city"], L["state"], w["local"] if w else "", b["text"] if b else w["code"], nxt,
                             C.dnc_state(L, now_ms, rules), L["demo"]])
    out["rows"] = rows
    out["now"] = now_ms
    return out


def table(res: dict, limit: int = 30) -> str:
    lines = ["| Business | Trade | Their time | Status | Next good time |", "|---|---|---|---|---|"]
    for r in res["rows"][:limit]:
        L, w, b = r["lead"], r["win"], r["block"]
        nxt = C.when_words(w["next"]["start"], w["zones"][0], res.get("now")) if w and w.get("next") else "-"
        lines.append(f"| {L['name'][:28]} | {L['trade']} | {w['local'] if w else '-'} | {(b['text'][:40] if b else w['code'])} | {nxt} |")
    s = res["summary"]
    lines.append(f"\n{s['leads']} leads ({s['duplicates']} duplicates merged), {s['good_now']} good to call now, {s['locked']} locked (do not call), "
                 f"{s['needs_dnc_check']} not checked against the Do Not Call list yet, {s['no_state']} without a state.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the Call copilot list from team B1's leads (stays on this PC).")
    ap.add_argument("--leads", action="append", default=[], help="a leads file or folder (JSON or CSV); default: team B1's agency/out/<city>/leads.json files")
    ap.add_argument("--dnc", action="append", default=[], help="a National Do Not Call download (one per area code)")
    ap.add_argument("--merge", action="append", default=[], help="the phone's export JSON (adds its do-not-call numbers to the master list)")
    ap.add_argument("--state", default="", help="the state to assume for leads without one (2 letters)")
    ap.add_argument("--out", default=str(OUT), help="output folder (default agency/calls/out, git-ignored)")
    ap.add_argument("--now", default="", help="ISO time to build for (tests), default now")
    a = ap.parse_args(argv)
    files = []
    for p in a.leads:
        q = Path(p)
        files.extend(find_lead_files(q) if q.is_dir() else [q])
    if not a.leads:
        files = find_lead_files()
    if not files:
        print("No leads found. Run team B1's lead finder first (python -m agency.leads --city \"Your City, ST\"), or pass --leads <file>.")
        return 1
    now = int(datetime.fromisoformat(a.now.replace("Z", "+00:00")).timestamp() * 1000) if a.now else None
    res = build(files, a.dnc, a.merge, a.state, now, Path(a.out))
    print(table(res))
    print(f"\nWrote {Path(a.out) / 'call_list.json'} (import it on the phone) and call_list.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
