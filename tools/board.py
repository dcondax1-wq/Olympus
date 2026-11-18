#!/usr/bin/env python3
"""BOARD for Claude (owner 2026-11-17: "I don't want to keep being a middleman between you and the bot"). docs/BOARD.md.

  python tools/board.py read                 everything a new Claude session needs, under 40 lines: every account (plan, stage,
                                             balance, room, to pass, locked?, last event, source + age), the newest events, owner
                                             notes not answered, what waits on the owner, when the PC last reported (STALE said plainly)
  python tools/board.py read --offline       the same from the repo only (no git fetch, no ntfy)
  python tools/board.py read --json          the board as JSON
  python tools/board.py note "text" [--acct atlas] [--answers all|id,id] [--kind claude_note|plan_changed]
                                             a Claude note in data/board/shared.jsonl (TRACKED): it ships to the bot with the next
                                             update (the PC pulls the repo) and shows on the Board page; --answers marks owner notes done
  python tools/board.py owner "ATLAS 26,946.10 passed" [--acct atlas]
                                             something the owner told Claude in chat, so the bot and the page see it too (marked "via chat")
  python tools/board.py publish [--offline]  rewrite tools/web_public/board/board.json (the published, privacy-safe copy)

Sources: the `heartbeat` branch (git fetch origin heartbeat; heartbeat.json "board" + its time), the public ntfy status feed
(tools/web_public/status_feed.json: the PC's lite live.json, "brd" + the account cards), data/board/shared.jsonl, the plan
tools/web_public/business/accounts.json. Read only, except note / owner / publish, which write only the two files above.
Never trades, arms or routes anything.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import board_events as B  # noqa: E402

PUBLISHED = os.path.join(ROOT, "tools", "web_public", "board", "board.json")
STATUS_FEED = os.path.join(ROOT, "tools", "web_public", "status_feed.json")
REMOTES = ("origin", "olympus")
CARD_KEY = {"lit": "zlarior", "atlas": "atlas"}            # the PC's board cards -> accounts.json keys (BLITZ stays hidden)
MAX_LINES = 40


# ------------------------------------------------------------------------------------------------ sources
def fetch_hb(remotes=REMOTES) -> dict:
    """The newest heartbeat.json of the heartbeat branch over the remotes. {"present": False, "reason"} when none."""
    from engine import heartbeat
    best = {"present": False, "reason": "no heartbeat branch"}
    for r in remotes:
        try:
            hb = heartbeat.read(cwd=ROOT, remote=r)
        except Exception as e:  # noqa: BLE001
            hb = {"present": False, "reason": f"{e.__class__.__name__}"}
        if hb.get("present") and (not best.get("present") or float(hb.get("t") or 0) > float(best.get("t") or 0)):
            best = {**hb, "remote": r}
    return best


def fetch_lite(get=None) -> dict | None:
    """The newest PC status post (kind le-live) on the public ntfy topic with its ext blocks merged in (brd, mf, ...), or None."""
    try:
        from tools import pc_silent_check as P
        with open(STATUS_FEED, encoding="utf-8") as fh:
            feed = json.load(fh)
        ok, msgs = P.poll(str(feed.get("ntfy") or "https://ntfy.sh").rstrip("/"), str(feed.get("topic") or ""), since="12h", get=get)
    except Exception:  # noqa: BLE001
        return None
    from tools import pc_feed                      # the core post + its newest ext post(s) merged (the old single post as it was)
    return pc_feed.pick(msgs) if ok else None


def lite_live(lite: dict | None, plan_accounts=None) -> dict:
    """{plan key: {balance, room, floor, to_pass, stage, t, name}} from the PC's live numbers: the board cards (lit, atlas) and
    every PC account of "accounts" (b25k_2 ...). Matched to the plan by the PC id / Name (engine/board_events.plan_key), never
    by plan size (2026-11-18: the new 25K eval had landed on ATLAS's row). A PC account the plan lacks keeps its own row."""
    out = {}
    lite = B._d(lite)
    bd = B._d(lite.get("board"))
    pa = plan_accounts if plan_accounts is not None else B.plan().get("accounts")
    t = B._f(bd.get("data_t")) or B._f(bd.get("t")) or B._f(lite.get("t"))
    for ck, key in CARD_KEY.items():
        c = B._d(bd.get(ck))
        if c and B._f(c.get("balance")) is not None:
            st = str(c.get("status") or "").lower()
            k = B.plan_key(pa, ck, "") or key
            out[k] = {"balance": c.get("balance"), "room": c.get("room"), "floor": c.get("floor"), "to_pass": c.get("to_target"), "t": t,
                      "name": c.get("name"), "plan": c.get("plan"),
                      "stage": "funded" if st == "funded" or c.get("stage") == "funded" else "failed" if st in ("failed", "lost") else "eval"}
    at = B._f(lite.get("t")) or t
    for a in lite.get("accounts") or []:
        a = B._d(a)
        if not a.get("id") or a.get("kind") not in ("eval", "funded") or a.get("source") in ("cloud", "pc_blitz") or a.get("id") == "acct_c":
            continue
        e = B._d(a.get("eval"))
        if B._f(e.get("balance")) is None:
            continue
        k = B.plan_key(pa, a.get("id"), a.get("name"))
        lit = B._d(bd.get("lit"))
        if not k and lit and B._f(lit.get("balance")) == B._f(e.get("balance")) and B._f(lit.get("floor")) == B._f(e.get("floor")):
            k = B.plan_key(pa, "lit", "") or CARD_KEY["lit"]     # the bot's main account = the lit card (a plan without "pc" ids)
        k = k or str(a["id"])
        if k in out:                                         # the board card of the same account (same numbers): keep the card
            continue
        st = str(e.get("status") or "").lower()
        out[k] = {"balance": e.get("balance"), "room": e.get("room"), "floor": e.get("floor"), "to_pass": e.get("to_target"),
                  "t": B._f(B._d(a.get("conn")).get("t")) or at, "name": a.get("name"), "plan": a.get("plan"),
                  "stage": "funded" if a.get("kind") == "funded" else "failed" if st == "failed" else "eval"}
    return out


def published() -> dict:
    try:
        with open(PUBLISHED, encoding="utf-8") as fh:
            j = json.load(fh)
        return j if isinstance(j, dict) else {}
    except (OSError, ValueError):
        return {}


def gather(offline: bool = False, hb=None, lite=None, now=None) -> dict:
    """The board as Claude sees it from the cloud: every source merged, the PC's live numbers when they are the newest."""
    now = int(now or time.time())
    notes = []
    if hb is None:
        hb = {"present": False, "reason": "offline"} if offline else fetch_hb()
    if lite is None and not offline:
        lite = fetch_lite()
    plan_doc = B.plan()
    pcb = B._d(hb.get("board")) if hb.get("present") else {}
    ev_hb = pcb.get("events") or []
    ev_nt, live_nt = B.from_status(B._d(B._d(lite).get("brd")))
    live = {}
    for r in pcb.get("accounts") or []:                     # the PC's own rows (its emit()s), as of its heartbeat
        if isinstance(r, dict) and r.get("key") and r.get("src") in ("PC", "PC live") and B._f(r.get("balance")) is not None:
            live[r["key"]] = {**{f: r.get(f) for f in ("balance", "room", "floor", "to_pass")}, "t": r.get("src_t") or hb.get("t")}
    for k, v in live_nt.items():                            # the PC's own board rows (plan + events on the PC): only where no live card
        if k not in live and (B._f(v.get("t")) or 0) >= 0:
            live[k] = {**v, "src": "PC board"}
    for k, v in lite_live(lite, plan_doc.get("accounts")).items():   # the PC's live account numbers win over both
        if (B._f(v.get("t")) or 0) >= (B._f(B._d(live.get(k)).get("t")) or 0) or B._d(live.get(k)).get("src") == "PC board":
            live[k] = v
    events = B.merge(published().get("events") or [], ev_hb, ev_nt, B.load(plan_doc=plan_doc))
    hb_t = B._f(hb.get("t")) if hb.get("present") else None
    rep_t = B._f(B._d(B._d(lite).get("reporter")).get("t"))
    lite_t = B._f(B._d(lite).get("t"))
    pc_t = max([x for x in (hb_t, rep_t, lite_t) if x] or [0]) or None
    via = "heartbeat" if pc_t and pc_t == hb_t else ("ntfy" if pc_t else "")
    if not hb.get("present"):
        notes.append(f"heartbeat branch: {hb.get('reason') or 'not read'}")
    if lite is None and not offline:
        notes.append("ntfy status feed: nothing in the last 12 h")
    board = B.public(B.build(events=events, plan_doc=plan_doc, live=live, pc={"t": pc_t, "via": via}, now=now, src="cloud"))
    board["sources"] = {"heartbeat_t": int(hb_t) if hb_t else None, "ntfy_t": int(rep_t or lite_t) if (rep_t or lite_t) else None,
                        "plan_updated": plan_doc.get("updated"), "notes": notes}
    return board


# ------------------------------------------------------------------------------------------------ the 40 lines
def lines(board: dict, now=None) -> list:
    now = int(now or time.time())
    pc = B._d(board.get("pc"))
    out = []
    head = f"BOARD {B.et_text(now)} | "
    if pc.get("t"):
        age = now - int(pc["t"])
        head += f"PC last reported {B.et_text(pc['t'])} ({B.ago(age)}, via {pc.get('via') or '?'})"
        head += ": STALE, PC SILENT. Live numbers below are old or from the plan." if age > B.STALE_S else ": fresh"
    else:
        head += "PC never reported here: STALE, PC SILENT. Numbers below are the plan / owner-typed only."
    out.append(head)
    for n in B._d(board.get("sources")).get("notes") or []:
        out.append("  (" + n + ")")
    out.append("ACCOUNTS  name | plan | stage | balance | room | to pass | source, age | last event")
    for r in board.get("accounts") or []:
        stage = r.get("chip") or r.get("stage")
        if r.get("locked") and stage != "locked":
            stage += " + LOCKED"
        if r.get("plan_only"):
            stage = "PLAN ONLY (" + str(stage) + ", no PC numbers)"
        elif r.get("not_in_plan"):
            stage += " (PC account, not in accounts.json yet)"
        src = r.get("src") or "PLAN"
        if r.get("age_s") is not None:
            src += f", {B.ago(r['age_s'])}"
        last = B._d(r.get("last"))
        lt = f"{B.day_text(last['t'])} {last.get('kind')}: {B.clean(last.get('text'), 60)}" if last.get("t") else "-"
        out.append(f"  {r.get('name')} | {r.get('plan') or '-'} | {stage} | {B.usd(r.get('balance'))} | {B.usd(r.get('room'))} | "
                   f"{B.usd(r.get('to_pass'))} | {src} | {lt}")
    evs = [e for e in board.get("events") or [] if e.get("kind") != "balance" or e.get("src") != "bot"][:10]
    out.append(f"NEWEST EVENTS ({len(evs)} shown, newest first)" if evs else "NEWEST EVENTS: none yet")
    for e in evs:
        out.append(f"  {B.et_text(e.get('t'))} {e.get('acct') or 'pc'} {e.get('kind')} [{B.SRC_LABEL.get(e.get('src'), e.get('src'))}]: "
                   f"{B.clean(e.get('text'), 110)}")
    on = board.get("open_notes") or []
    out.append(f"OWNER NOTES NOT ANSWERED: {len(on)}" + (" (answer: python tools/board.py note \"...\" --answers all)" if on else ""))
    for e in on[-5:]:
        out.append(f"  [{e.get('id')}] {B.et_text(e.get('t'))} {e.get('acct') or ''}: {B.clean(e.get('text'), 110)}")
    w = board.get("waiting") or []
    out.append(f"WAITING ON THE OWNER (accounts.json decisions, plan {board.get('plan_updated') or '?'}): {len(w)}")
    for x in w[:5]:
        out.append("  - " + B.clean(x, 120))
    return out[:MAX_LINES]


# ------------------------------------------------------------------------------------------------ writes
def _clean_public(text: str) -> str:
    try:
        from tools import site_privacy
        return site_privacy.clean_string(B.clean(text))
    except Exception:  # noqa: BLE001
        return B.clean(text)


def write_note(text: str, kind: str = "claude_note", acct: str = "", answers=None, src: str = "claude", via: str | None = None,
               path: str | None = None, now=None) -> dict | None:
    """Append one note to data/board/shared.jsonl (tracked). Text privacy-cleaned first (it ships with the repo)."""
    data = {}
    if answers:
        data["answers"] = list(answers)
    if via:
        data["via"] = via
    if kind == "owner_note":
        p = B.owner_parse(text, B.plan().get("accounts"))
        acct = acct or p.pop("acct", "")
        p.pop("acct", None)
        data.update(p)
    rec = B.make(kind, acct, _clean_public(text), data or None, src=src, t=now)
    if rec is None:
        return None
    return B.append(rec, path or B.shared_file())


def publish(board: dict, path: str = PUBLISHED) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = {k: v for k, v in board.items() if k != "sources"}
    doc["about"] = "The Board: what the bot, the owner and Claude know. Privacy-safe copy (python tools/board.py publish)."
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The Board: read it, add a Claude note, publish the safe copy.")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("read")
    r.add_argument("--offline", action="store_true")
    r.add_argument("--json", action="store_true")
    n = sub.add_parser("note")
    n.add_argument("text")
    n.add_argument("--acct", default="")
    n.add_argument("--answers", default="")
    n.add_argument("--kind", default="claude_note", choices=("claude_note", "plan_changed"))
    o = sub.add_parser("owner")
    o.add_argument("text")
    o.add_argument("--acct", default="")
    p = sub.add_parser("publish")
    p.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    cmd = a.cmd or "read"
    if cmd == "read":
        b = gather(offline=getattr(a, "offline", False))
        print(json.dumps(b, indent=1, ensure_ascii=False) if getattr(a, "json", False) else "\n".join(lines(b)))
        return 0
    if cmd in ("note", "owner"):
        if cmd == "note":
            ans = None
            if a.answers == "all":
                ans = [e["id"] for e in B.open_notes(B.merge(published().get("events") or [], B.load()))]
            elif a.answers:
                ans = [x.strip() for x in a.answers.split(",") if x.strip()]
            rec = write_note(a.text, kind=a.kind, acct=a.acct, answers=ans)
        else:
            rec = write_note(a.text, kind="owner_note", acct=a.acct, src="owner", via="chat")
        if rec is None:
            print("not saved")
            return 1
        path = publish(gather(offline=True))
        print(f"saved {rec['kind']} [{rec['id']}] in {os.path.relpath(B.shared_file(), ROOT)}; board copy {os.path.relpath(path, ROOT)}. "
              "It reaches the bot with the next update (commit + ship).")
        return 0
    if cmd == "publish":
        path = publish(gather(offline=a.offline))
        print("wrote " + os.path.relpath(path, ROOT))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
