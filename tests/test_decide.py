"""THE DECIDE CARD (tools/web_public/business/decide.js + decisions.json, 2026-11-18, night-decide; docs/BOARD.md).
  a. decisions.json: the one list Claude keeps (id, question, why, $ impact, options, status), seeded with tonight's 7 open items,
     no account ids / emails
  b. the page part: text only, no outside address, the only write is POST /inbox/board (X-Olympus-Inbox) and only on the PC link
     (/site/); both the Board and the ZEUS page load it and carry a data-decide box
  c. node, the pure part: onPc, openItems, answers (data.decision or the "Decide <id>: YES" text), body / noteText (<= 200)
  d. the inbox: a tap = one owner note with decision + answer (day_inbox kind board), a bad answer refused, its text never read as
     a balance / stage (keep $1,000 in each Rapid must not set the Rapid row), it shows in open notes, board.py read names the card
  e. Chromium 390 x 844: on /site/ (the PC link) every open item has Yes / No / Later (44 px), a tap posts one note and the card
     says so; on the public path: "Open on your PC link to answer" + the question, no buttons, nothing posted; no sideways scroll
    python -X utf8 -m tests.test_decide     (DECIDE_NO_BROWSER=1 skips e; run e only under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
RES: list = []
TMP = tempfile.mkdtemp(prefix="decide_test_")
os.environ.update(LE_BOARD_DIR=os.path.join(TMP, "board"), LE_INBOX_DIR=os.path.join(TMP, "inbox"),
                  LE_BOARD_SHARED=os.path.join(TMP, "shared.jsonl"))

from engine import board_events as B  # noqa: E402

NOW = 1794960000
SEED = ["payout-ping-1000", "zlarior-funded25", "rapid25-lit-bank", "atlas-on-50k-funded", "atlas-on-rapid", "keep-1000-rapid", "ask-mffu-parallel"]
PLAN = {"updated": "2026-11-18", "decisions": [],
        "accounts": [{"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "status": "live"},
                     {"key": "rapid1", "name": "Rapid EOD", "plan": "MFFU Rapid EOD 50K", "stage": "eval", "status": "buying"}]}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[-600:]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


N_OPEN = sum(1 for _d in json.loads(open(os.path.join(BIZ, 'decisions.json'), encoding='utf-8').read()).get('items', []) if _d.get('status', 'open') == 'open')


def part_a():
    doc = json.loads(rd(BIZ, "decisions.json"))
    items = doc.get("items") or []
    check("a. decisions.json: kind olympus-decisions, updated, a note that a tap changes nothing live",
          doc.get("kind") == "olympus-decisions" and doc.get("updated") and "Nothing here changes a live setting" in doc.get("note", ""))
    bad = [d.get("id") for d in items if not (re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", str(d.get("id"))) and d.get("question") and d.get("why")
                                              and "$" in str(d.get("impact")) and isinstance(d.get("impact_usd"), (int, float))
                                              and set(d.get("options") or []) <= {"yes", "no", "later"} and d.get("options")
                                              and d.get("status") in ("open", "yes", "no", "later", "done", "superseded", "waiting") and d.get("source")
               and (d.get("status") != "superseded" or d.get("superseded_by")) and (d.get("status") != "waiting" or d.get("waiting_on")))]
    check("a. every item: id, question, a one-line why, $ impact (+ impact_usd), yes/no/later options, status, source", items and not bad, bad)
    ids = [d["id"] for d in items]
    check("a. seeded: payout ping $1,000, Zlarior on the funded 25K, Rapid 25K bank, ATLAS on the 50K funded / on the Rapid, keep $1,000, ask MFFU",
          all(i in ids for i in SEED) and len(set(ids)) == len(ids), ids)
    srcs = [d["source"] for d in items if d["source"].startswith("research/")]
    check("a. every research source exists", all(os.path.isfile(os.path.join(ROOT, s)) for s in srcs), srcs)
    s = json.dumps(doc)
    check("a. no account ids, no emails", not re.search(r"[A-Z]{3,}\d{5,}", s) and "@" not in s)


def part_b():
    js = rd(BIZ, "decide.js")
    check("b. text only: no innerHTML / insertAdjacentHTML / document.write / eval, no outside address",
          not re.search(r"innerHTML|insertAdjacentHTML|document\.write|\beval\(", js) and not re.search(r"https?://", js))
    methods = re.findall(r"method:\s*'([A-Z]+)'", js)
    check("b. the only write: POST /inbox/board with X-Olympus-Inbox, behind the PC-link check (/site/)",
          methods == ["POST"] and "fetch('/inbox/board'" in js and "'X-Olympus-Inbox': '1'" in js and "!onPc(location.pathname)" in js
          and "/^\\/site\\//" in js and "localStorage" not in js, methods)
    check("b. off the PC link: 'Open on your PC link to answer', no buttons", "Open on your PC link to answer" in js and "if (pc) {" in js)
    bh, zh = rd(WEB, "board", "index.html"), rd(WEB, "hub", "zeus.html")
    check("b. the Board and the ZEUS page load ../business/decide.js and carry a data-decide box",
          '<script src="../business/decide.js?v=' in bh and 'id="decide" data-decide' in bh and '<script src="../business/decide.js?v=' in zh
          and 'id="decide" data-decide' in zh)
    bj = rd(WEB, "board", "board.js")
    check("b. the Board's old 'waiting' list steps aside for the card (plan decisions shown once)", "window.DECIDE && window.DECIDE.ok !== false" in bj)


def node(body):
    script = ("const D = require(" + json.dumps(os.path.join(BIZ, "decide.js")) + "); const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def part_c():
    doc = rd(BIZ, "decisions.json")
    r = node(f"""
      const doc = {doc}; const it = doc.items[0];
      const ev = [{{ kind: 'owner_note', t: 10, text: 'Decide payout-ping-1000: NO - x' }},
                  {{ kind: 'owner_note', t: 20, text: 'whatever', data: {{ decision: 'payout-ping-1000', answer: 'yes' }} }},
                  {{ kind: 'owner_note', t: 5, text: 'Decide atlas-on-rapid: later - y' }}, {{ kind: 'claude_note', t: 30, text: 'Decide atlas-on-rapid: YES' }},
                  {{ kind: 'owner_note', t: 9, text: 'Decide keep-1000-rapid: MAYBE' }}];
      const long = {{ id: 'x1', question: 'q'.repeat(400) }};
      out({{ pc: D.onPc('/site/board/'), pub: D.onPc('/board/'), pub2: D.onPc('/nq-dashboard/site/x'), n: D.openItems(doc).length,
             closed: D.openItems({{ items: [{{ id: 'a1', question: 'q', status: 'yes' }}, {{ id: 'a2', question: 'q' }}] }}).map((d) => d.id),
             got: D.answers(ev), b: D.body(it, 'yes'), bad: D.body(it, 'maybe'), len: D.noteText(long, 'later').length }});
    """)
    check("c. onPc: only the /site/ path (the PC's private link)", r.get("pc") is True and r.get("pub") is False and r.get("pub2") is False, r)
    check("c. openItems: status open (or none) only", r.get("n") == N_OPEN and r.get("closed") == ["a2"], r)
    g = r.get("got") or {}
    check("c. answers: newest per id from data.decision or the text; claude notes and unknown answers ignored",
          g.get("payout-ping-1000") == {"answer": "yes", "t": 20} and g.get("atlas-on-rapid") == {"answer": "later", "t": 5} and "keep-1000-rapid" not in g, g)
    b = r.get("b") or {}
    check("c. body: {text 'Decide <id>: YES - <question>', decision, answer}; a bad answer -> null; text <= 200",
          b.get("decision") == "payout-ping-1000" and b.get("answer") == "yes" and b.get("text", "").startswith("Decide payout-ping-1000: YES - Funded 25K")
          and r.get("bad") is None and r.get("len") == 200, r)


def part_d():
    try:
        from engine import day_inbox as DI
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] d. inbox (fastapi missing: {e})")
        return
    H = {"X-Olympus-Inbox": "1"}
    body = {"text": "Decide keep-1000-rapid: YES - Rapid funded payouts: always leave $1,000 above the buffer in each Rapid? Zlarior funded",
            "decision": "keep-1000-rapid", "answer": "yes"}
    st, out = DI.accept("board", json.dumps(body).encode(), "application/json", H, now_s=NOW)
    rows = B.read_jsonl(os.path.join(TMP, "inbox", "board.jsonl"))
    check("d. a tap -> 200, one line in data/inbox/board.jsonl with decision + answer, the reply says Claude applies it, nothing live",
          st == 200 and out.get("ok") and len(rows) == 1 and rows[0].get("decision") == "keep-1000-rapid" and rows[0].get("answer") == "yes"
          and "Claude" in out.get("said", "") and "nothing live" in out.get("said", ""), (st, out, rows))
    st2, out2 = DI.accept("board", json.dumps({**body, "answer": "maybe"}).encode(), "application/json", H, now_s=NOW + 1)
    st3, _ = DI.accept("board", json.dumps({**body, "decision": "../x"}).encode(), "application/json", H, now_s=NOW + 2)
    check("d. a bad answer or id -> 400, nothing written", st2 == 400 and st3 == 400 and len(B.read_jsonl(os.path.join(TMP, "inbox", "board.jsonl"))) == 1, (st2, out2))
    evs = B.load(plan_doc=PLAN)
    on = [e for e in evs if e.get("kind") == "owner_note"]
    rows = {r["key"]: r for r in B.build(events=evs, plan_doc=PLAN, now=NOW + 5)["accounts"]}
    check("d. on the board as an owner note with data {decision, answer}; its '$1,000 ... Rapid ... funded' text sets no balance / stage / account",
          len(on) == 1 and on[0].get("data") == {"decision": "keep-1000-rapid", "answer": "yes"} and not on[0].get("acct")
          and rows["rapid1"].get("balance") in (None, 0) and rows["zlarior"].get("stage") != "funded", (on, rows.get("rapid1")))
    check("d. it is an owner note not answered yet (Claude sees it in board.py read)", [e["id"] for e in B.open_notes(evs)] == [on[0]["id"]])
    st4, _ = DI.accept("board", b'{"text": "Zlarior 49,192.78"}', "application/json", H, now_s=NOW + 400)
    z = {r["key"]: r for r in B.build(plan_doc=PLAN, now=NOW + 401)["accounts"]}["zlarior"]
    check("d. a plain typed note still updates its row (unchanged)", st4 == 200 and z.get("balance") == 49192.78, z)
    from tools import board as T
    b = B.build(events=evs, plan_doc=PLAN, now=NOW + 5)
    ln = [x for x in T.lines(b, now=NOW + 5) if x.startswith("DECIDE CARD")]
    # 2026-11-20 lead: the owner answered every card (0 open is a real state): the line then says "0 open" and lists no ids
    first_open = next((c["id"] for c in json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "decisions.json"), encoding="utf-8"))["items"]
                       if c.get("status") == "open"), None)
    check("d. board.py read: one DECIDE CARD line with the open count and ids", ln and f"{N_OPEN} open" in ln[0]
          and (first_open in ln[0] if first_open else N_OPEN == 0), ln)


# the browser part serves its OWN decisions.json: the real cards, every one set open (2026-11-20 the owner answered all of them, and a page
# with 0 open cards hides the box, so a check pinned to the live file had nothing to tap). E_OPEN = the cards the page must show.
E_DOC = json.loads(open(os.path.join(BIZ, "decisions.json"), encoding="utf-8").read())
E_DOC["items"] = [dict(d, status="open") for d in E_DOC.get("items", [])]
E_OPEN = len(E_DOC["items"])


class Site(http.server.SimpleHTTPRequestHandler):
    """The public site at /, the PC link's copy at /site/ (same files), and POST /inbox/board answered like the PC."""
    posts: list = []

    def do_GET(self):
        if self.path.split("?")[0].endswith("/business/decisions.json"):
            out = json.dumps(E_DOC).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        super().do_GET()

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        if path.startswith("/site/"):
            path = path[5:]
        return super().translate_path(path)

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n)
        Site.posts.append({"path": self.path, "hdr": self.headers.get("X-Olympus-Inbox"), "body": raw.decode("utf-8", "replace")})
        out = json.dumps({"ok": True, "id": "t1", "kind": "board", "said": "Saved your YES. Claude reads it next session; nothing live changes by itself."}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def part_e():
    try:
        from playwright.sync_api import sync_playwright
        from tests import browser_kit
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] e. browser (playwright missing: {e})")
        return
    import functools
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Site, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            br = browser_kit.launch(pw)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            errs = []
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(base + "/site/hub/zeus.html")
            p.wait_for_function("window.DECIDE && window.DECIDE.last && document.querySelectorAll('#decide .dc-item').length > 0")
            r = p.evaluate("""(() => { const its = [...document.querySelectorAll('#decide .dc-item')];
              const btn = its.map((i) => [...i.querySelectorAll('.dc-btns button')].map((b) => b.textContent));
              const h = Math.min(...[...document.querySelectorAll('#decide .dc-btns button')].map((b) => b.getBoundingClientRect().height));
              return { n: its.length, btn, h, hidden: document.getElementById('decide').hidden, imp: its[0].querySelector('.dc-imp').textContent,
                       why: its[0].querySelector('.dc-why').textContent, wide: document.documentElement.scrollWidth <= window.innerWidth + 1 }; })()""")
            check("e. ZEUS on the PC link (390 px): 7 decisions, each Yes / No / Later >= 44 px, why + $ impact, no sideways scroll",
                  r["n"] == E_OPEN and all(b == ["Yes", "No", "Later"] for b in r["btn"]) and r["h"] >= 44 and not r["hidden"] and r["imp"].startswith("$: ")
                  and r["why"].startswith("Why: ") and r["wide"], r)
            p.click("#decide .dc-item[data-id='payout-ping-1000'] button[data-ans='yes']")
            p.wait_for_function("document.querySelector(\"#decide .dc-item[data-id='payout-ping-1000'] .dc-sent\")")
            sent = p.text_content("#decide .dc-item[data-id='payout-ping-1000']")
            body = json.loads(Site.posts[-1]["body"]) if Site.posts else {}
            check("e. a tap on Yes posts ONE note to /inbox/board (header + decision + answer) and the card says it was sent",
                  len(Site.posts) == 1 and Site.posts[0]["path"] == "/inbox/board" and Site.posts[0]["hdr"] == "1" and body.get("decision") == "payout-ping-1000"
                  and body.get("answer") == "yes" and body.get("text", "").startswith("Decide payout-ping-1000: YES") and "You said Yes" in sent
                  and "nothing live" in sent, (Site.posts, sent))
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs.append(str(e)))
            p2.goto(base + "/board/")
            p2.wait_for_function("window.DECIDE && window.DECIDE.last && window.BOARD && window.BOARD.last")
            r2 = p2.evaluate("""(() => { const its = [...document.querySelectorAll('#decide .dc-item')];
              return { n: its.length, btns: document.querySelectorAll('#decide button').length,
                       off: its.map((i) => (i.querySelector('.dc-off b') || {}).textContent), q: its.length ? its[0].querySelector('.dc-q').textContent : '',
                       wide: document.documentElement.scrollWidth <= window.innerWidth + 1, wait: document.getElementById('waiting').textContent }; })()""")
            check("e. the Board on the public site: 'Open on your PC link to answer' + the exact question, no buttons, nothing posted, no sideways scroll",
                  r2["n"] == E_OPEN and r2["btns"] == 0 and all(x == "Open on your PC link to answer" for x in r2["off"]) and r2["q"].startswith("Funded 25K: ask for the full $1,000")
                  and len(Site.posts) == 1 and r2["wide"] and "ATLAS trades on" not in r2["wait"], r2)
            check("e. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def part_f():
    """day-arenas 2026-11-20: business/plan.html's "Answer these first" (decide.js data-decide-mode="rank"): open cards by $ a month (the fleet
    plan's top_decide number first, else usd_month), top 3 = answer now, the rest later, answered / closed = done; the skeptic badge."""
    r = node("""
      const doc = { items: [
        { id: 'a', question: 'qa', status: 'open', usd_month: 50, risk: 'lost 10% -> 12% (Jul-Oct-like; more); x' },
        { id: 'b', question: 'qb', status: 'open', usd_month: 600, source: 'research/writeups/skeptic-atlas-streak-2026-11-20.md' },
        { id: 'c', question: 'qc', status: 'open', usd_month: -20 }, { id: 'd', question: 'qd', status: 'open', usd_month: 10 },
        { id: 'e', question: 'qe', status: 'done', usd_month: 900 }, { id: 'f', question: 'qf', status: 'open', usd_month: 300 } ] };
      const fleet = { top_decide: [{ id: 'a', usd: 700 }] };
      const R = D.rank(doc, fleet, { f: { answer: 'yes', t: 9 }, d: { answer: 'later', t: 3 } });
      const R0 = D.rank(doc, null, {});
      out({ now: R.now.map((x) => x.item.id), later: R.later.map((x) => x.item.id), done: R.done.map((x) => x.item.id), by: R.now.map((x) => x.by),
            s: R.now[0].sentence, twice: R.now.map((x) => x.twice), now0: R0.now.map((x) => x.item.id), junk: D.rank(null, 5, null) });
    """)
    check("f. rank: open cards by $ a month, the fleet plan's number first (a: $700 beats its own $50); top 3 answer now; an answered card (yes) is done, 'later' stays open",
          r.get("now") == ["a", "b", "d"] and r.get("later") == ["c"] and r.get("done") == ["e", "f"] and r.get("by") == ["fleet plan", "this card", "this card"], r)
    check("f. without the fleet plan: the cards' own usd_month (b $600, f $300, a $50)", r.get("now0") == ["b", "f", "a"], r)
    check("f. one plain sentence: 'Yes = +$700 a month (fleet plan); risk: <first clause, brackets closed>.'",
          r.get("s") == "Yes = +$700 a month (fleet plan); risk: lost 10% -> 12% (Jul-Oct-like).", r.get("s"))
    check("f. 'checked twice' only when a skeptic write-up is named on the card", r.get("twice") == [False, True, False], r.get("twice"))
    check("f. junk in -> empty lists, no throw", r.get("junk") == {"now": [], "later": [], "done": []}, r.get("junk"))
    html = rd(BIZ, "plan.html")
    check("f. plan.html mounts the ranked view near the top (data-decide-mode=\"rank\", decisions.json + fleet_plan.json) and loads decide.js",
          'data-decide-mode="rank"' in html and 'data-decide-fleet="fleet_plan.json"' in html and '<script src="decide.js?v=' in html
          and html.index('id="decide"') < html.index('id="mktH"'))
    js = rd(BIZ, "decide.js")
    check("f. the tap is unchanged: the ranked view uses the same itemView / send (one POST /inbox/board, X-Olympus-Inbox)",
          js.count("fetch('/inbox/board'") == 1 and "mountRanked" in js and "itemView(r.item, st, pc)" in js)


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_f()
    if not os.environ.get("DECIDE_NO_BROWSER"):
        part_e()
    n = sum(RES)
    print(f"\ndecide: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
