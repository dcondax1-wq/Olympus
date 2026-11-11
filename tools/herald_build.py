#!/usr/bin/env python3
"""THE OLYMPUS HERALD builder: today's edition of the daily newspaper, written only from files OLYMPUS already publishes. READ ONLY, OFFLINE, stdlib only.

    python tools/herald_build.py                          # repo -> tools/web_public/herald/edition.json (+ editions/<date>.json, last 14, + jarvis.json, + the demo fixture.json)
    python tools/herald_build.py --date 2026-11-11        # a given day (the default is today, UTC; the clock is used for nothing else)
    python tools/herald_build.py --web site               # read the BUILT site (then home.json and money/*.json are there) and write site/herald/
    python tools/herald_build.py --check                  # exit 1 when edition.json is not what this script writes now for its date (the git part is ignored)
    python tools/herald_build.py --selftest

The rule of the paper: NO INVENTED FACTS. Every article is put together from "facts": each one is a value read from a named file (with the place in that file),
a quote copied from a file, or a count worked out from a file (with the sum spelled out). Every number printed in a headline, standfirst or body must be one of
the article's facts: audit() checks it here, tests/test_herald_page.py checks it again against the files, and the page shows the sources under each article.
When a source is missing the article is simply not written (and listed under "skipped" with the reason). Same files + same date = the same edition, byte for byte.

What it reads (all optional): handoff/agents_now.json (+ git, only for the "shipped" list, never part of --check), research/writeups/kalshi_edge_*.md, and from the
site folder: ergasterion/queue.json, kalshicity/suggestions.json, pythia/events.json, archive/index.json, money/index.json, money/mercury.json (else the labelled
sample mercury/fixture.json), home.json, jarvis/apps.js, lyceum/lyceumcore.js.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
KEEP = 14
NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
PERIOD = "."


# ------------------------------------------------------------------------------------------------ small helpers
def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def read_json(path):
    t = read_text(path)
    if t is None:
        return None
    try:
        return json.loads(t)
    except ValueError:
        return None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def money(v):
    a = abs(v)
    whole = abs(a - round(a)) < 0.005
    s = f"{round(a):,}" if whole else f"{a:,.2f}"
    return ("-" if v < 0 and float(s.replace(",", "")) != 0 else "") + "$" + s


def num(v):
    if isinstance(v, int) or float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def pct(v):
    return num(v) + "%"


def clean(text, n=220):
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def sentence(text):
    s = clean(text, 400)
    return s if s.endswith((".", "!", "?", "…")) else s + PERIOD


def tokens(text):
    """The numbers printed in a text, commas dropped: '1,836 buys at 4.7%' -> {'1836', '4.7'}."""
    return {t.replace(",", "") for t in NUM_RE.findall(str(text))}


def date_words(ymd):
    d = dt.date.fromisoformat(ymd)
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B')} {d.year}"


def day_words(ymd):
    d = dt.date.fromisoformat(ymd)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def at(doc, path):
    node = doc
    for k in [p for p in path.split("/") if p != ""]:
        if isinstance(node, list) and k.isdigit() and int(k) < len(node):
            node = node[int(k)]
        elif isinstance(node, dict) and k in node:
            node = node[k]
        else:
            return None
    return node


class Story:
    """An article being written. Every number goes in through one of the three doors, so it can be traced."""

    def __init__(self, aid, kicker):
        self.id, self.kicker, self.facts, self.files = aid, kicker, [], []

    def _add(self, fact):
        self.facts.append(fact)
        if fact["src"] not in self.files:
            self.files.append(fact["src"])
        return fact["t"]

    def val(self, text, src, path, raw):
        """A value read from `src` at `path` (raw = what the file holds), printed as `text`."""
        return self._add({"t": str(text), "src": src, "at": path, "raw": raw})

    def quote(self, text, src):
        """Words copied from `src` (they may carry numbers of their own)."""
        return self._add({"t": str(text), "src": src, "quote": True})

    def calc(self, text, src, how, raw):
        """A count or sum worked out from `src`; `how` says the sum in plain words."""
        return self._add({"t": str(text), "src": src, "calc": how, "raw": raw})

    def done(self, headline, standfirst, body, sample=False, by=None):
        body = [sentence(b) for b in body if b]
        if len(body) < 3:
            return None
        art = {"id": self.id, "kicker": self.kicker, "headline": clean(headline, 120), "standfirst": sentence(standfirst), "body": body[:6], "facts": self.facts, "sources": self.files, "sample": bool(sample)}
        if by:
            art["by"] = by
        return art


def audit(article):
    """The numbers printed in an article that are not among its facts (must be empty)."""
    allowed = set()
    for f in article.get("facts", []):
        allowed |= tokens(f["t"])
    printed = tokens(" ".join([article.get("headline", ""), article.get("standfirst", "")] + list(article.get("body", []))))
    return sorted(printed - allowed)


# ------------------------------------------------------------------------------------------------ the sources
class Desk:
    """Everything the newsroom may read, loaded once. rel() gives the name a source is cited by."""

    def __init__(self, root, web, date):
        self.root, self.web, self.date = root, web, date
        self.read, self.missing = [], []
        self.agents = self._json(os.path.join(root, "handoff", "agents_now.json"), "handoff/agents_now.json")
        self.queue = self._json(os.path.join(web, "ergasterion", "queue.json"), "ergasterion/queue.json")
        self.kalshi = self._json(os.path.join(web, "kalshicity", "suggestions.json"), "kalshicity/suggestions.json")
        self.events = self._json(os.path.join(web, "pythia", "events.json"), "pythia/events.json")
        self.archive = self._json(os.path.join(web, "archive", "index.json"), "archive/index.json")
        self.money = self._json(os.path.join(web, "money", "index.json"), "money/index.json")
        self.home = self._json(os.path.join(web, "home.json"), "home.json")
        self.mercury, self.mercury_src = self._json(os.path.join(web, "money", "mercury.json"), "money/mercury.json"), "money/mercury.json"
        if self.mercury is None:
            self.mercury, self.mercury_src = self._json(os.path.join(web, "mercury", "fixture.json"), "mercury/fixture.json"), "mercury/fixture.json"
        self.writeups = []
        for p in sorted(glob.glob(os.path.join(root, "research", "writeups", "kalshi_edge_*.md"))):
            t = read_text(p)
            if t:
                self.writeups.append(("research/writeups/" + os.path.basename(p), t))
                self.read.append("research/writeups/" + os.path.basename(p))
        js = read_text(os.path.join(web, "jarvis", "apps.js"))
        self.apps = sorted(set(re.findall(r"app\('([a-z0-9_]+)',\s*'([^']*)'", js))) if js else []
        (self.read if js else self.missing).append("jarvis/apps.js")
        lyc = read_text(os.path.join(web, "lyceum", "lyceumcore.js"))
        self.questions = parse_questions(lyc) if lyc else []
        (self.read if self.questions else self.missing).append("lyceum/lyceumcore.js")

    def _json(self, path, rel):
        d = read_json(path)
        (self.read if d is not None else self.missing).append(rel)
        return d


def parse_questions(js):
    """Lyceum's question bank out of lyceumcore.js: [{id, topic, q, o: [..], a, why}]."""
    out = []
    s = r"'((?:[^'\\]|\\.)*)'"
    for m in re.finditer(r"\{ id: '(\w+)', topic: '(\w+)', q: " + s + r", o: \[(.*?)\], a: (\d), why: " + s + r" \}", js):
        opts = [x.replace("\\'", "'") for x in re.findall(s, m.group(4))]
        if len(opts) >= 2 and int(m.group(5)) < len(opts):
            out.append({"id": m.group(1), "topic": m.group(2), "q": m.group(3).replace("\\'", "'"), "o": opts, "a": int(m.group(5)), "why": m.group(6).replace("\\'", "'")})
    return out


def pick(seq, date, n, salt=0):
    """n items of seq, rotating with the date (no randomness: the same day gives the same picks)."""
    if not seq:
        return []
    start = (dt.date.fromisoformat(date).toordinal() * 7 + salt) % len(seq)
    return [seq[(start + i * max(1, len(seq) // max(1, n))) % len(seq)] for i in range(min(n, len(seq)))]


# ------------------------------------------------------------------------------------------------ the articles (each returns None when its source is missing)
def a_builders(d):
    src, doc = "handoff/agents_now.json", d.agents
    ags = [a for a in (doc or {}).get("agents", []) if isinstance(a, dict) and a.get("name") and a.get("job")]
    if len(ags) < 2:
        return None, "handoff/agents_now.json is missing or lists fewer than two agents"
    s = Story("builders", "The workshop")
    n = s.calc(num(len(ags)), src, "count of agents", len(ags))
    idx = [doc["agents"].index(a) for a in pick(ags, d.date, 3)]
    lines = []
    for i in idx:
        a = doc["agents"][i]
        lines.append(f"{s.quote(a['name'], src)}: {s.quote(clean(a['job'], 140), src)}")
    areas = sorted({str(a.get("area")) for a in ags if a.get("area")})
    body = [f"The roster the lead keeps lists {n} build agents at work on OLYMPUS, each on a branch of its own",
            f"On the bench today: {lines[0]}", f"Next to it: {lines[1]}"]
    if len(lines) > 2:
        body.append(f"And a third: {lines[2]}")
    if areas:
        body.append(f"Between them they cover {s.calc(num(len(areas)), src, 'count of different areas', len(areas))} areas: {', '.join(s.quote(x, src) for x in areas[:14])}")
    stamp = doc.get("asof")
    if isinstance(stamp, str):
        body.append(f"The roster was last updated at {s.val(stamp, src, 'asof', stamp)}")
    return s.done(f"{n} builders at work in the workshop", "Who is building what today, straight from the lead's roster.", body), ""


def a_queue(d):
    src, q = "ergasterion/queue.json", d.queue
    if not isinstance(q, dict) or not isinstance(q.get("queue"), dict):
        return None, "ergasterion/queue.json is not published"
    s = Story("queue", "The workshop")
    qq = q["queue"]
    if not all(is_num(qq.get(k)) for k in ("open", "total", "done")):
        return None, "ergasterion/queue.json has no task counts"
    o, t, dn = s.val(num(qq["open"]), src, "queue/open", qq["open"]), s.val(num(qq["total"]), src, "queue/total", qq["total"]), s.val(num(qq["done"]), src, "queue/done", qq["done"])
    body = [f"The build queue holds {t} tasks: {o} open and {dn} done"]
    tasks = qq.get("tasks") or []
    if tasks and isinstance(tasks[0], dict) and tasks[0].get("text"):
        body.append(f"First in line{(' (' + s.quote(tasks[0]['section'], src) + ')') if tasks[0].get('section') else ''}: {s.quote(clean(tasks[0]['text'], 170), src)}")
    wu = q.get("writeups") or {}
    if is_num(wu.get("count")):
        body.append(f"The research shelf now counts {s.val(num(wu['count']), src, 'writeups/count', wu['count'])} write-ups")
    ls = [x for x in (q.get("learnings") or []) if isinstance(x, dict) and x.get("text")]
    if ls:
        body.append(f"The newest lesson on file, dated {s.quote(str(ls[0].get('d', '')), src)}, reads: {s.quote(clean(ls[0]['text'], 200), src)}")
        body.append(f"It was filed under \"{s.quote(str(ls[0].get('kind', 'note')), src)}\" and comes from {s.quote(str(ls[0].get('src', 'the queue')), src)}")
    return s.done(f"{o} tasks open, {dn} done", "The state of the build queue and the newest lesson written down.", body), ""


def a_money(d):
    src, m = "money/index.json", d.money
    if not isinstance(m, dict) or not isinstance(m.get("total"), dict) or not is_num(m["total"].get("base")):
        return None, "money/index.json is not published here (it is written by the site build)"
    s = Story("money", "Money")
    tot, cnt = m["total"], m.get("counts") or {}
    sample = bool(cnt.get("sample")) or str(m.get("status", "")).lower() == "sample"
    base = s.val(money(tot["base"]), src, "total/base", tot["base"])
    body = [f"The money machines' own estimate for a month is {base}" + (f", between {s.val(money(tot['low']), src, 'total/low', tot['low'])} on a bad month and {s.val(money(tot['high']), src, 'total/high', tot['high'])} on a good one" if is_num(tot.get("low")) and is_num(tot.get("high")) else "")]
    if is_num(cnt.get("streams")):
        body.append(f"{s.val(num(cnt['streams']), src, 'counts/streams', cnt['streams'])} streams report in" + (f"; {s.val(num(cnt['sample']), src, 'counts/sample', cnt['sample'])} of them are still running on sample data" if is_num(cnt.get("sample")) else ""))
    if is_num(tot.get("real_base")):
        body.append(f"The part of that estimate that rests on real finds, not samples, is {s.val(money(tot['real_base']), src, 'total/real_base', tot['real_base'])}")
    for i, st in enumerate((m.get("streams") or [])[:2]):
        if isinstance(st, dict) and st.get("name") and st.get("headline"):
            body.append(f"{s.quote(st['name'], src)} says: {s.quote(clean(st['headline'], 190), src)}")
    body.append("It is an estimate on paper, not a promise, and no machine here places an order")
    return s.done(f"Money machines put a month at {base}" + (" (sample data)" if sample else ""), "What the five paper money machines add up to, by their own count.", body, sample=sample), ""


def a_bots(d):
    src, h = "home.json", d.home
    accts = [a for a in (h or {}).get("accounts", []) if isinstance(a, dict) and a.get("name")] if isinstance(h, dict) else []
    if not accts:
        return None, "home.json is not published here (it is written by the site build)"
    s = Story("bots", "The floor")
    body, total, have = [], 0.0, 0
    for a in accts[:3]:
        i = h["accounts"].index(a)
        today, ev = (a.get("pnl") or {}).get("today"), a.get("eval") or {}
        bit = s.quote(a["name"], src)
        if is_num(today):
            total += today
            have += 1
            r = (a.get("pnl") or {}).get("today_r")
            bit += f" is {s.val(money(today), src, f'accounts/{i}/pnl/today', today)} on the day" + (f" ({s.val(('+' if r > 0 else '') + f'{r:.2f}R', src, f'accounts/{i}/pnl/today_r', r)})" if is_num(r) else "")
        if is_num(ev.get("room")) and is_num(ev.get("mll")):
            bit += f"{', with' if is_num(today) else ' has'} drawdown left {s.val(money(ev['room']), src, f'accounts/{i}/eval/room', ev['room'])} of {s.val(money(ev['mll']), src, f'accounts/{i}/eval/mll', ev['mll'])} max loss"
        if bit != a["name"]:
            body.append(bit)
    if not have:
        return None, "home.json carries no P&L for today"
    tot = s.calc(money(round(total, 2)), src, "sum of pnl/today over the accounts named", round(total, 2))
    body.insert(0, f"Across the {s.calc(num(have), src, 'count of accounts with a P&L today', have)} accounts that reported, the day stands at {tot}")
    body.append("The file gives the day in dollars; where it also gives R, the R is printed next to its dollars")
    body.append("These are the figures the phone's home page reads; the bots trade on paper or on an eval the owner arms himself")
    return s.done(f"The day so far: {tot} across the accounts", "Each account's day and how much drawdown is left, from the live summary.", body), ""


def a_kalshi_stop(d):
    src, k = "kalshicity/suggestions.json", d.kalshi
    items = [i for i in (k or {}).get("items", []) if isinstance(i, dict) and i.get("verdict") and i.get("kind")] if isinstance(k, dict) else []
    stops = [i for i in items if i["verdict"] == "stop"]
    if not stops:
        return None, "kalshicity/suggestions.json is missing or has no stop list"
    s = Story("kalshi-stop", "Kalshi desk")
    cnt = k.get("counts") or {}
    body = []
    if all(is_num(cnt.get(x)) for x in ("stop", "pause", "watch", "keep")):
        body.append(f"The Kalshi review sorts the bot's habits into {s.val(num(cnt['stop']), src, 'counts/stop', cnt['stop'])} to stop, {s.val(num(cnt['pause']), src, 'counts/pause', cnt['pause'])} to pause, {s.val(num(cnt['watch']), src, 'counts/watch', cnt['watch'])} to watch and {s.val(num(cnt['keep']), src, 'counts/keep', cnt['keep'])} to keep")
    for it in stops[:3]:
        i = k["items"].index(it)
        line = f"Stop: {s.quote(it['kind'], src)}"
        if is_num(it.get("n")) and is_num(it.get("net_usd")):
            line += f", {s.val(num(it['n']), src, f'items/{i}/n', it['n'])} bets for {s.val(money(it['net_usd']), src, f'items/{i}/net_usd', it['net_usd'])} after fees"
        if is_num(it.get("roi_pct")):
            line += f" ({s.val(pct(it['roi_pct']), src, f'items/{i}/roi_pct', it['roi_pct'])} per dollar staked)"
        body.append(line)
    if stops[0].get("rule"):
        body.append(f"The rule as written: {s.quote(clean(stops[0]['rule'], 200), src)}")
    if k.get("basis"):
        body.append(f"What it rests on: {s.quote(clean(k['basis'], 200), src)}")
    if k.get("label"):
        body.append(s.quote(clean(k["label"], 160), src))
    n_stop = s.calc(num(len(stops)), src, "count of items with verdict stop", len(stops))
    return s.done(f"Kalshi stop list: {n_stop} habits to drop", "What the bot's own settled bets say it should stop doing. Suggestions only.", body), ""


def verdict_line(text):
    """(title, one honest sentence) of a research write-up: its first heading and the first bold sentence with what follows it."""
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
    m = re.search(r"\*\*(.+?)\*\*([^\n]*)", text)
    if not title or not m:
        return None
    rest = re.split(r"(?<=[.!?])\s", (m.group(1) + m.group(2)).strip())
    line = rest[0] if len(rest[0]) > 40 or len(rest) < 2 else rest[0] + " " + rest[1]
    return title, re.sub(r"[*`]", "", line)


def a_kalshi_research(d):
    rows = [(f, verdict_line(t), re.search(r"(\d{4}-\d{2}-\d{2})", t)) for f, t in d.writeups]
    rows = [(f, v, m.group(1) if m else "") for f, v, m in rows if v]
    if not rows:
        return None, "no research/writeups/kalshi_edge_*.md write-up was found"
    s = Story("kalshi-research", "Kalshi desk")
    body = []
    for f, (title, line), day in rows[:4]:
        body.append(f"{s.quote(title, f)}" + (f" (dated {s.quote(day, f)})" if day else ""))
        body.append(f"In its own words: {s.quote(clean(line, 260), f)}")
    n = s.calc(num(len(rows)), rows[0][0], "count of kalshi_edge_*.md write-ups read", len(rows))
    none = all("NO EDGE" in t.upper() for _, (t, _), _ in rows)
    body.append("Every test was on paper with fees in and a held-out block; no order was placed" if none else "Every line above is copied from the write-up it names; no order was placed")
    head = f"{n} Kalshi edge hunts report: no edge found" if none else f"{n} Kalshi edge hunts report in"
    return s.done(head, "The research teams' verdicts, one honest sentence each, copied from their write-ups.", body), ""


def upcoming(d, n=4):
    ev = [e for e in (d.events or {}).get("events", []) if isinstance(e, dict) and isinstance(e.get("date"), str) and e.get("title")] if isinstance(d.events, dict) else []
    return sorted([e for e in ev if e["date"] >= d.date], key=lambda e: (e["date"], str(e.get("time") or "")))[:n], ev


def a_calendar(d):
    src = "pythia/events.json"
    nxt, ev = upcoming(d, 4)
    if not nxt:
        return None, "pythia/events.json is missing or has no event on or after this date"
    s = Story("calendar", "Market calendar")
    body = []
    for e in nxt:
        i = d.events["events"].index(e)
        body.append(f"{s.quote(e['title'], src)}: {s.val(e['date'], src, f'events/{i}/date', e['date'])}" + (f" at {s.val(e['time'], src, f'events/{i}/time', e['time'])} New York time" if e.get("time") else "")
                    + f", impact {s.quote(str(e.get('impact', 'not rated')), src)}" + (", to be confirmed on the official page" if e.get("verify") else ""))
    high = [e for e in nxt if e.get("impact") == "high"]
    body.append("A high-impact release is on the list: size down around it" if high else "Nothing on this short list is rated high impact")
    upd = d.events.get("updated")
    if isinstance(upd, str):
        body.append(f"The calendar was last rebuilt on {s.val(upd, src, 'updated', upd)}; agencies move dates, so check the official page")
    first = nxt[0]
    return s.done(f"Next on the calendar: {s.quote(clean(first['title'], 60), src)}", "The next dated market events, from Pythia's calendar.", body), ""


def a_archive(d):
    src, ix = "archive/index.json", d.archive
    c = (ix or {}).get("counts") if isinstance(ix, dict) else None
    if not isinstance(c, dict) or not all(is_num(c.get(k)) for k in ("runs", "adopted", "rejected", "open")):
        return None, "archive/index.json is not published"
    s = Story("archive", "Research")
    body = [f"The Archive now holds {s.val(num(c['runs']), src, 'counts/runs', c['runs'])} research runs: {s.val(num(c['adopted']), src, 'counts/adopted', c['adopted'])} adopted, {s.val(num(c['rejected']), src, 'counts/rejected', c['rejected'])} rejected and {s.val(num(c['open']), src, 'counts/open', c['open'])} still open"]
    cols, runs, verd = ix.get("cols") or [], ix.get("runs") or [], ix.get("verdicts") or []
    try:
        ci = {k: cols.index(k) for k in ("title", "verdict", "built", "family")}
        newest = max(str(r[ci["built"]]) for r in runs)
        todays = [r for r in runs if str(r[ci["built"]]) == newest]
        by = {}
        for r in todays:
            by[verd[r[ci["verdict"]]]] = by.get(verd[r[ci["verdict"]]], 0) + 1
        body.append(f"The newest batch in the index is stamped {s.quote(newest, src)}: {s.calc(num(len(todays)), src, 'count of runs in the index with the newest built stamp', len(todays))} runs kept there"
                    + "".join(f", {s.calc(num(v), src, f'count of those with verdict {k}', v)} {k}" for k, v in sorted(by.items())))
        for want, word in (("adopted", "Adopted"), ("open", "Still open")):
            hit = next((r for r in todays if verd[r[ci["verdict"]]] == want), None)
            if hit:
                body.append(f"{word}, from the {s.quote(str(hit[ci['family']]), src)} family: {s.quote(clean(hit[ci['title']], 170), src)}")
    except (ValueError, IndexError, TypeError, KeyError):
        pass
    rej = [r for r in (ix.get("rejected") or []) if isinstance(r, dict)]
    if rej:
        txt = next((rej[0].get(k) for k in ("title", "idea", "text", "what") if rej[0].get(k)), None)
        if txt:
            body.append(f"On the rejected shelf, so nobody redoes it: {s.quote(clean(txt, 180), src)}")
    if is_num(c.get("writeups")):
        body.append(f"{s.val(num(c['writeups']), src, 'counts/writeups', c['writeups'])} write-ups explain the results in plain language")
    return s.done(f"Archive: {s.val(num(c['adopted']), src, 'counts/adopted', c['adopted'])} adopted, {s.val(num(c['rejected']), src, 'counts/rejected', c['rejected'])} rejected", "What the research library holds and its newest batch.", body), ""


def a_new_apps(d, prev_apps):
    src = "jarvis/apps.js"
    if not d.apps:
        return None, "jarvis/apps.js is missing"
    if prev_apps is None:
        return None, "this is the first edition, so there is no earlier app list to compare with"
    names = dict(d.apps)
    new = [i for i in sorted(names) if i not in set(prev_apps)]
    if not new:
        return None, "no app was added since the last edition"
    s = Story("new-apps", "Openings")
    n = s.calc(num(len(new)), src, "count of app ids not in the last edition's list", len(new))
    body = [f"{n} new {'app has' if len(new) == 1 else 'apps have'} opened since the last edition: {', '.join(s.quote(names[i], src) for i in new[:8])}",
            f"That brings the bar to {s.calc(num(len(names)), src, 'count of app ids in jarvis/apps.js', len(names))} apps",
            "Each one reads only published files and falls back to labelled demo data, so none can be blank"]
    return s.done(f"{n} new {'app opens' if len(new) == 1 else 'apps open'} on the agora", "What was added to the app bar since the last edition.", body), ""


def a_mind(d):
    src, q = "ergasterion/queue.json", d.queue
    m = (q or {}).get("mind") if isinstance(q, dict) else None
    obs = [o for o in (m or {}).get("observations", []) if isinstance(o, dict) and o.get("text")] if isinstance(m, dict) else []
    if not obs or not is_num(m.get("tested")):
        return None, "the Mind's observations are not in ergasterion/queue.json"
    s = Story("mind", "The Mind")
    body = [f"The Mind has tested {s.val(num(m['tested']), src, 'mind/tested', m['tested'])} of its own ideas" + (f"; its notes are dated {s.val(m['date'], src, 'mind/date', m['date'])}" if isinstance(m.get("date"), str) else "")]
    for o in obs[:3]:
        body.append(f"It noticed: {s.quote(clean(o['text'], 200), src)}")
    body.append("These are observations for context, not rules: the Mind never changes a setting on its own")
    return s.done("The Mind's notebook: " + clean(s.quote(clean(obs[0]["text"], 70), src), 80), "What the nightly self-research wrote down. Context only.", body, by="mind"), ""


# ------------------------------------------------------------------------------------------------ the boxes
def box_numbers(arts):
    out = []
    for a in arts:
        f = next((f for f in a["facts"] if "at" in f or "calc" in f), None)
        if f:
            out.append({"value": f["t"], "label": a["headline"], "src": f["src"], "article": a["id"]})
    return out[:7]


def box_corrections(d):
    src, k = "kalshicity/suggestions.json", d.kalshi
    out = []
    for it in (k or {}).get("items", []) if isinstance(k, dict) else []:
        if isinstance(it, dict) and it.get("verdict") in ("stop", "pause") and it.get("kind") and it.get("rule"):
            row = {"was": f"The Kalshi bot kept doing this: {clean(it['kind'], 80)}.", "now": sentence(clean(it["rule"], 220)), "src": src}
            if is_num(it.get("n")) and is_num(it.get("net_usd")):
                row["proof"] = f"{num(it['n'])} bets, {money(it['net_usd'])} after fees."
            out.append(row)
    for f, t in d.writeups:
        v = verdict_line(t)
        if v and "NO EDGE" in v[0].upper():
            out.append({"was": "We hoped a Kalshi edge was hiding in the data.", "now": sentence(clean(v[1], 240)), "src": f})
    return out[:5]


def box_classifieds(d):
    m = d.mercury
    if not isinstance(m, dict):
        return None
    sample = m.get("demo") is True or str(m.get("status", "")).lower() == "sample" or d.mercury_src.endswith("fixture.json")
    items = []
    for it in m.get("items", []):
        if not isinstance(it, dict) or not it.get("title"):
            continue
        exp = it.get("expires") if isinstance(it.get("expires"), str) else None
        if exp and exp[:10] < d.date:
            continue
        row = {"title": clean(it["title"], 90), "detail": clean(it.get("detail") or it.get("text") or "", 200)}
        if is_num(it.get("usd")):
            row["usd"] = it["usd"]
        if exp:
            row["expires"] = exp[:10]
        items.append(row)
    items.sort(key=lambda r: (r.get("expires") or "9999", -(r.get("usd") or 0), r["title"]))
    return {"sample": bool(sample), "src": d.mercury_src, "items": items[:5], "note": "Savings are estimates. " + ("Sample offers, not real ones." if sample else "Check each offer on the firm's own page.")}


def box_weather(d):
    if not isinstance(d.events, dict):
        return None
    _, ev = upcoming(d, 1)
    today = [e for e in ev if e["date"] == d.date]
    rank = {"high": 2, "med": 1, "medium": 1}
    top = max([rank.get(str(e.get("impact")), 0) for e in today], default=0)
    level = ("calm", "busy", "careful")[top]
    words = {"calm": "Calm: nothing rated medium or high is on today's calendar.", "busy": "Busy: a medium-impact release is on today's calendar.", "careful": "Careful: a high-impact release is on today's calendar. Size down around it."}[level]
    return {"level": level, "text": words, "src": "pythia/events.json", "events": [{"time": e.get("time") or "", "title": clean(e["title"], 90), "impact": str(e.get("impact", ""))} for e in sorted(today, key=lambda e: str(e.get("time") or ""))[:5]],
            "note": "From the saved calendar. It is not a forecast of price."}


def box_quiz(d):
    return [dict(q) for q in pick(d.questions, d.date, 3, salt=3)]


def short_branch(b):
    return re.sub(r"^worktree-agent-", "", str(b))[:8]


def box_interviews(d):
    out = []
    ags = [a for a in (d.agents or {}).get("agents", []) if isinstance(a, dict) and a.get("name") and a.get("job") and a.get("branch")] if isinstance(d.agents, dict) else []
    m = (d.queue or {}).get("mind") if isinstance(d.queue, dict) else None
    if isinstance(m, dict) and is_num(m.get("tested")) and m.get("observations"):
        o = m["observations"][0]
        out.append({"id": "mind", "name": "The Mind", "title": "Nightly self-research", "src": "ergasterion/queue.json",
                    "qa": [{"q": "How many of your own ideas have you tested?", "a": f"{num(m['tested'])}. I keep the count in my notes."},
                           {"q": "What is the clearest thing you noticed?", "a": sentence(clean(o.get("text", ""), 220))},
                           {"q": "Do you change the bot when you notice something?", "a": "No. I write it down. I never change anything myself."}]})
    cl = box_classifieds(d)
    if cl and cl["items"]:
        first = cl["items"][0]
        out.append({"id": "scanner:mercury", "name": "Mercury", "title": "Deal scanner" + (" (sample data)" if cl["sample"] else ""), "src": cl["src"], "sample": cl["sample"],
                    "qa": [{"q": "How many offers are on your desk?", "a": f"{num(len(cl['items']))} that have not run out, in the list I publish."},
                           {"q": "Which one comes first?", "a": sentence(first["title"] + (f", ending {first['expires']}" if first.get("expires") else ""))},
                           {"q": "Can you buy it for me?", "a": "No. I only read public pages and write a list. I can't place orders."}]})
    for a in pick(ags, d.date, 3, salt=1):
        if len(out) >= 3:
            break
        out.append({"id": "builder:" + short_branch(a["branch"]), "name": a["name"], "title": "Build agent" + (f", {a['area']}" if a.get("area") else ""), "src": "handoff/agents_now.json",
                    "qa": [{"q": "What are you building?", "a": sentence(clean(a["job"], 200))},
                           {"q": "Where does your work live?", "a": f"On my own branch, {a['branch']}. The lead merges it when it is ready."},
                           {"q": "Which part of OLYMPUS is yours?", "a": sentence(f"The {a['area']} area" if a.get("area") else "The roster does not say")}]})
    return out[:3]


def press_block(root, agents):
    """Who shipped what, from git at build time. Never required and never part of --check."""
    names = {a.get("branch"): a.get("name") for a in (agents or {}).get("agents", []) if isinstance(a, dict)} if isinstance(agents, dict) else {}
    try:
        refs = subprocess.run(["git", "-C", root, "for-each-ref", "refs/heads", "--sort=-committerdate", "--count=40", "--format=%(refname:short)|%(committerdate:unix)|%(subject)"],
                              capture_output=True, text=True, timeout=15, check=True).stdout
    except Exception:  # noqa: BLE001 - git is never required
        return {"available": False, "shipped": []}
    shipped = []
    for ln in refs.splitlines():
        a = ln.split("|", 2)
        if len(a) == 3 and a[1].isdigit() and a[0] in names:
            shipped.append({"who": names[a[0]], "id": "builder:" + short_branch(a[0]), "t": int(a[1]), "text": clean(a[2], 150)})
    return {"available": bool(shipped), "shipped": shipped[:10]}


# ------------------------------------------------------------------------------------------------ the edition
WRITERS = (("bots", a_bots), ("kalshi-research", a_kalshi_research), ("builders", a_builders), ("kalshi-stop", a_kalshi_stop), ("money", a_money), ("archive", a_archive),
           ("calendar", a_calendar), ("queue", a_queue), ("mind", a_mind))


def newest_stamp(d):
    cands = []
    for doc, key in ((d.agents, "asof"), (d.queue, "asof"), (d.money, "asof"), (d.events, "updated"), (d.archive, "built"), (d.mercury, "asof"), (d.home, "asof")):
        v = doc.get(key) if isinstance(doc, dict) else None
        if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}", v):
            cands.append(v if len(v) > 10 else v + "T00:00:00Z")
    return max(cands) if cands else ""


def build(root=ROOT, web=WEB, date=None, prev=None, with_git=True, demo=False):
    """prev = the edition before this date (for the number and the new-apps diff), or None."""
    date = date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    d = Desk(root, web, date)
    arts, skipped = [], []
    for aid, fn in WRITERS:
        art, why = fn(d)
        if art and not audit(art):
            arts.append(art)
        else:
            skipped.append({"article": aid, "why": why or ("a number in it could not be sourced: " + ", ".join(audit(art)) if art else "not enough facts for three sentences")})
    art, why = a_new_apps(d, prev.get("apps") if isinstance(prev, dict) else None)
    if art and not audit(art):
        arts.append(art)
    else:
        skipped.append({"article": "new-apps", "why": why or "not enough facts"})
    arts = arts[:11]
    sample = demo or any(a["sample"] for a in arts)
    ed = {"v": 1, "date": date, "number": (prev.get("number", 0) + 1) if isinstance(prev, dict) and is_num(prev.get("number")) else 1, "built": newest_stamp(d), "demo": bool(demo),
          "masthead": {"title": "The Olympus Herald", "motto": "Only what the files say", "date_words": date_words(date)},
          "label": "DEMO edition: example files, not real numbers." if demo else ("Some stories rest on sample data and say so." if sample else "Written from the published files. Nothing is invented."),
          "lead": arts[0] if arts else None, "articles": arts[1:], "numbers": box_numbers(arts), "corrections": box_corrections(d), "classifieds": box_classifieds(d), "weather": box_weather(d),
          "quiz": box_quiz(d), "interviews": box_interviews(d), "sources": {"read": sorted(set(d.read)), "missing": sorted(set(d.missing))}, "skipped": skipped, "apps": sorted(i for i, _ in d.apps),
          "press": press_block(root, d.agents) if with_git else {"available": False, "shipped": []}}
    return ed


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def stable(ed):
    e = dict(ed)
    e.pop("press", None)
    return e


def jarvis_card(ed):
    lead = ed.get("lead") or {}
    try:
        t = int(dt.datetime.strptime(ed["date"], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        t = 0
    n = (1 if ed.get("lead") else 0) + len(ed.get("articles", []))
    return {"v": 1, "name": "Herald", "status": {"level": "ok" if n else "off", "label": f"Edition {ed.get('number', 1)}, {n} stories"},
            "kpis": [{"label": "Edition", "value": str(ed.get("number", 1))}, {"label": "Stories", "value": str(n)}, {"label": "Outlook", "value": ((ed.get("weather") or {}).get("level") or "n/a").capitalize()}],
            "lines": [re.sub(r"[<>&]", "", clean(lead.get("headline", "No stories today: the sources are missing."), 118))], "t": t, "open": "#", "theme": "#14110e", "stale_after": 172800}


def editions_dir(out_dir):
    return os.path.join(out_dir, "editions")


def load_prev(out_dir, date):
    """The newest stored edition dated before `date`."""
    best = None
    for p in sorted(glob.glob(os.path.join(editions_dir(out_dir), "????-??-??.json"))):
        day = os.path.basename(p)[:10]
        if day < date:
            best = p
    return read_json(best) if best else None


def write(out_dir, ed):
    os.makedirs(editions_dir(out_dir), exist_ok=True)
    text = dump(ed)
    for p in (os.path.join(out_dir, "edition.json"), os.path.join(editions_dir(out_dir), ed["date"] + ".json")):
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    files = sorted(glob.glob(os.path.join(editions_dir(out_dir), "????-??-??.json")))
    for p in files[:-KEEP]:
        os.remove(p)
    days = [os.path.basename(p)[:10] for p in files[-KEEP:]]
    heads = []
    for day in days:
        e = read_json(os.path.join(editions_dir(out_dir), day + ".json")) or {}
        heads.append({"date": day, "number": e.get("number"), "headline": ((e.get("lead") or {}).get("headline") or "")})
    with open(os.path.join(editions_dir(out_dir), "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump({"v": 1, "keep": KEEP, "editions": heads}))
    with open(os.path.join(out_dir, "jarvis.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(jarvis_card(ed), ensure_ascii=False, separators=(",", ":")) + "\n")
    return days


# ------------------------------------------------------------------------------------------------ the sample newsroom (the demo fixture and the selftest)
def sample_root(tmp, with_built=True):
    """A tiny made-up repo + site: every source the paper can read, with easy numbers."""
    web = os.path.join(tmp, "tools", "web_public")
    for sub in ("handoff", "research/writeups", "tools/web_public/ergasterion", "tools/web_public/kalshicity", "tools/web_public/pythia", "tools/web_public/archive", "tools/web_public/money",
                "tools/web_public/mercury", "tools/web_public/jarvis", "tools/web_public/lyceum"):
        os.makedirs(os.path.join(tmp, sub), exist_ok=True)

    def put(rel, obj):
        with open(os.path.join(tmp, rel), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))
    put("handoff/agents_now.json", {"v": 1, "asof": "2026-11-10T09:00:00Z", "agents": [
        {"branch": "worktree-agent-aaaa1111bbbb2222c", "name": "Example mason", "job": "Laying the marble floor of an example app", "area": "design"},
        {"branch": "worktree-agent-cccc3333dddd4444e", "name": "Example scribe", "job": "Writing the example daily paper", "area": "press"},
        {"branch": "worktree-agent-eeee5555ffff6666a", "name": "Example smith", "job": "Fixing 3 example tests", "area": "quality"}]})
    put("research/writeups/kalshi_edge_Z.md", "# Example edge hunt, team Z: NO EDGE FOUND\n\n2026-11-09. Example only.\n\n## The answer\n\n**No edge found.** Out of the 12 example cells none beat the noise after fees.\n")
    put("tools/web_public/ergasterion/queue.json", {"v": 1, "asof": "2026-11-09", "queue": {"total": 9, "open": 4, "done": 5, "tasks": [{"id": "x", "text": "Example task: polish the example page", "section": "P1", "done": False}]},
                                                     "writeups": {"count": 21}, "learnings": [{"d": "2026-11-09", "who": "lit", "text": "Example lesson: a wide stop means fewer micros", "src": "research/writeups/example.md", "kind": "adopted"}],
                                                     "mind": {"tested": 6, "date": "2026-11-08", "observations": [{"text": "Example: 7 of the last 10 example losses came after lunch", "bot": "lit", "score": 0.6}]}})
    put("tools/web_public/kalshicity/suggestions.json", {"v": 1, "basis": "Example basis: 200 made-up settled buys.", "label": "Suggestions only: nothing here places a bet.", "counts": {"keep": 1, "pause": 1, "stop": 1, "watch": 2},
                                                          "items": [{"kind": "Example habit A", "verdict": "stop", "n": 80, "net_usd": -31.5, "roi_pct": -4.2, "rule": "Do not do example habit A. It loses after fees."},
                                                                    {"kind": "Example habit B", "verdict": "pause", "n": 40, "net_usd": -6.0, "roi_pct": -1.1, "rule": "Pause example habit B until there is more data."},
                                                                    {"kind": "Example habit C", "verdict": "keep", "n": 50, "net_usd": 12.0, "roi_pct": 2.0, "rule": "Keep it."}]})
    put("tools/web_public/pythia/events.json", {"v": 1, "updated": "2026-11-09", "events": [
        {"date": "2026-11-09", "time": "08:30", "kind": "other", "title": "Old example release", "impact": "low", "verify": False},
        {"date": "2026-11-10", "time": "08:30", "kind": "cpi", "title": "Example CPI", "impact": "high", "verify": True},
        {"date": "2026-11-10", "time": "10:00", "kind": "other", "title": "Example confidence survey", "impact": "med", "verify": True},
        {"date": "2026-11-12", "time": None, "kind": "holiday", "title": "Example holiday", "impact": "low", "verify": False},
        {"date": "2026-11-13", "time": "08:30", "kind": "ppi", "title": "Example PPI", "impact": "med", "verify": True}]})
    put("tools/web_public/archive/index.json", {"v": 1, "built": "2026-11-09", "cols": ["id", "title", "family", "strategy", "verdict", "status", "built"], "verdicts": ["adopted", "rejected", "open"],
                                                 "counts": {"runs": 40, "writeups": 21, "adopted": 3, "rejected": 30, "open": 7},
                                                 "runs": [["ex_a", "Example run that was adopted", "example family", 0, 0, "adopted", "26-11-09"], ["ex_b", "Example run still open", "example family", 0, 2, "open", "26-11-09"],
                                                          ["ex_c", "An older example run", "old family", 0, 0, "adopted", "26-10-01"]],
                                                 "rejected": [{"title": "Example idea that was dropped: a fixed 20-point stop"}]})
    put("tools/web_public/mercury/fixture.json", {"v": 1, "demo": True, "note": "Example offers, not real.", "asof": "2026-11-09T12:00:00Z", "status": "sample", "items": [
        {"title": "Example: 30% off an eval", "detail": "Example code EXAMPLE30.", "usd": 27.54, "expires": "2026-11-13"}, {"title": "Example: offer already over", "detail": "Gone.", "usd": 5, "expires": "2026-11-01"},
        {"title": "Example: free reset", "detail": "No end date.", "usd": 22.95}]})
    put("tools/web_public/jarvis/apps.js", "app('alpha', 'Alpha', 'trading', '#c8a24a', 'x'),\napp('beta', 'Beta', 'money', '#c8a24a', 'x'),\napp('herald', 'Herald', 'life', '#c8a24a', 'x'),\n")
    put("tools/web_public/lyceum/lyceumcore.js", "export const QUESTIONS = [\n  { id: 's1', topic: 'stop', q: 'Where does the stop go?', o: ['Beyond the sweep extreme', 'A fixed distance', 'Wherever feels safe'], a: 0, why: 'The stop sits at the protected low or high.' },\n"
        "  { id: 'z1', topic: 'size', q: 'A wider stop means', o: ['More micros', 'Fewer micros'], a: 1, why: 'Size follows the stop: it\\'s smaller when the stop is wide.' },\n"
        "  { id: 't1', topic: 'target', q: 'How many targets?', o: ['One clear target', 'As many as possible'], a: 0, why: 'One clear target, no greed.' },\n];\n")
    if with_built:
        put("tools/web_public/money/index.json", {"v": 1, "asof": "2026-11-10T06:00:00Z", "total": {"low": -40.0, "base": 310.5, "high": 900.0, "real_base": 0.0}, "counts": {"streams": 5, "ok": 0, "stale": 0, "sample": 5},
                                                   "streams": [{"id": "chrysos", "name": "Chrysos", "headline": "Example estimate: an example fleet nets about $100 a month. Not a promise."}]})
        put("tools/web_public/home.json", {"asof": "2026-11-10T13:00:00Z", "accounts": [
            {"id": "a", "name": "Example 50K", "eval": {"room": 1420, "mll": 2000}, "pnl": {"today": 312, "today_r": 0.73}}, {"id": "b", "name": "Example 25K", "eval": {"room": 840, "mll": 1000}, "pnl": {"today": -60}}]})
    return web


def fixture():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        web = sample_root(tmp)
        prev = {"number": 6, "apps": ["alpha", "beta"]}
        ed = build(tmp, web, "2026-11-10", prev, with_git=False, demo=True)
    return {"v": 1, "demo": True, "note": "DEMO edition: written from made-up example files so the page is never empty. These are not real numbers.", "edition": ed}


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    import tempfile
    res = []

    def t(name, ok, info=""):
        res.append(bool(ok))
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))

    t("money / numbers / tokens: $1,836, -$248.30, $0 (never -$0), 4.7%, tokens drop commas", [money(1836), money(-248.3), money(-0.001), pct(4.7), num(2273), num(2.50)] == ["$1,836", "-$248.30", "$0", "4.7%", "2,273", "2.5"]
      and tokens("1,836 buys at 4.7% on 2026-11-10") == {"1836", "4.7", "2026", "11", "10"})
    s = Story("x", "k")
    body = [f"There are {s.val('12', 'a.json', 'n', 12)} of them", f"They cost {s.calc(money(30.5), 'a.json', 'sum', 30.5)}", f"Someone wrote: {s.quote('7 days', 'b.md')}"]
    art = s.done("Twelve", "A test.", body)
    bad = dict(art, body=art["body"] + ["And 99 more turned up."])
    t("audit: an article whose numbers all come from its facts is clean; one stray number (99) is caught; under three sentences no article is written",
      audit(art) == [] and audit(bad) == ["99"] and Story("y", "k").done("h", "s", ["one", "two"]) is None and art["sources"] == ["a.json", "b.md"], (audit(art), audit(bad)))
    t("a write-up's verdict line: its heading and its first bold sentence", verdict_line("# Team Z: NO EDGE FOUND\n\nx\n\n**No edge found.** Out of 12 cells none beat the noise. More text.") == ("Team Z: NO EDGE FOUND", "No edge found. Out of 12 cells none beat the noise.")
      and verdict_line("no heading") is None)
    with tempfile.TemporaryDirectory() as tmp:
        web = sample_root(tmp)
        ed = build(tmp, web, "2026-11-10", None, with_git=False)
        ids = [ed["lead"]["id"]] + [a["id"] for a in ed["articles"]]
        allarts = [ed["lead"]] + ed["articles"]
        t("a full newsroom: 9 stories, the bots lead, every story has 3 to 6 sentences and passes the audit; the first edition has no 'new apps' story and says why",
          ids == ["bots", "kalshi-research", "builders", "kalshi-stop", "money", "archive", "calendar", "queue", "mind"] and all(3 <= len(a["body"]) <= 6 and not audit(a) for a in allarts)
          and ed["number"] == 1 and [s_["article"] for s_ in ed["skipped"]] == ["new-apps"] and "first edition" in ed["skipped"][0]["why"], (ids, ed["skipped"]))
        t("the same files and date give the same edition, byte for byte; another date changes the picks, not the facts", dump(ed) == dump(build(tmp, web, "2026-11-10", None, with_git=False))
          and build(tmp, web, "2026-11-11", None, with_git=False)["date_words" if False else "masthead"]["date_words"] == "Wednesday, 11 November 2026")
        lead = ed["lead"]
        t("the lead: today's P&L in $ with its R next to it, drawdown left of max loss, a total that is the sum", "$312 on the day (+0.73R)" in " ".join(lead["body"]) and "drawdown left $1,420 of $2,000 max loss" in " ".join(lead["body"])
          and "$252" in lead["headline"] and any(f.get("calc") and f["raw"] == 252 for f in lead["facts"]), lead["body"])
        t("boxes: weather 'careful' on a high-impact day with today's events only, classifieds without the offer that ran out (sample marked), corrections from the stop / pause list and the no-edge verdict, 3 quiz questions, 3 interviews",
          ed["weather"]["level"] == "careful" and [e["title"] for e in ed["weather"]["events"]] == ["Example CPI", "Example confidence survey"] and ed["classifieds"]["sample"] is True
          and [i["title"] for i in ed["classifieds"]["items"]] == ["Example: 30% off an eval", "Example: free reset"] and len(ed["corrections"]) == 3 and "80 bets, -$31.50 after fees." == ed["corrections"][0]["proof"]
          and len(ed["quiz"]) == 3 and "it's smaller" in json.dumps(ed["quiz"]) and [i["id"] for i in ed["interviews"]][:2] == ["mind", "scanner:mercury"] and ed["interviews"][2]["id"].startswith("builder:")
          and len(ed["interviews"][2]["id"]) == len("builder:") + 8, (ed["weather"], [i["id"] for i in ed["interviews"]]))
        t("weather: 'busy' on a medium day, 'calm' on an empty one", build(tmp, web, "2026-11-13", None, with_git=False)["weather"]["level"] == "busy" and build(tmp, web, "2026-11-11", None, with_git=False)["weather"]["level"] == "calm")
        out = os.path.join(web, "herald")
        write(out, ed)
        ed2 = build(tmp, web, "2026-11-11", load_prev(out, "2026-11-11"), with_git=False)
        t("the next day: edition 2, and no 'new apps' story because nothing was added", ed2["number"] == 2 and "new-apps" in [s_["article"] for s_ in ed2["skipped"]] and "no app was added" in [s_["why"] for s_ in ed2["skipped"] if s_["article"] == "new-apps"][0])
        with open(os.path.join(web, "jarvis", "apps.js"), "a", encoding="utf-8") as fh:
            fh.write("app('gamma', 'Gamma', 'life', '#c8a24a', 'x'),\n")
        ed2 = build(tmp, web, "2026-11-11", load_prev(out, "2026-11-11"), with_git=False)
        na = [a for a in ed2["articles"] if a["id"] == "new-apps"]
        t("an app added since the last edition makes the 'new apps' story: 1 new app, named, 4 apps in all", len(na) == 1 and na[0]["headline"] == "1 new app opens on the agora" and "Gamma" in na[0]["body"][0] and "4 apps" in na[0]["body"][1] and not audit(na[0]), na)
        days = write(out, ed2)
        for i in range(12, 28):
            write(out, build(tmp, web, f"2026-11-{i}", load_prev(out, f"2026-11-{i}"), with_git=False))
        kept = sorted(os.path.basename(p)[:10] for p in glob.glob(os.path.join(out, "editions", "????-??-??.json")))
        ix = read_json(os.path.join(out, "editions", "index.json"))
        t("the archive keeps the last 14 editions (and an index with their headlines); the number keeps counting", days == ["2026-11-10", "2026-11-11"] and len(kept) == 14 and kept[-1] == "2026-11-27" and kept[0] == "2026-11-14"
          and [e["date"] for e in ix["editions"]] == kept and read_json(os.path.join(out, "edition.json"))["number"] == 18 and ix["editions"][-1]["number"] == 18, (kept, ix["editions"][-1]))
        t("--check: what was written is what is built now; an edited file is caught; the git part is ignored", check(out, tmp, web) and not check_edit(out, tmp, web))
    with tempfile.TemporaryDirectory() as tmp:
        web = sample_root(tmp, with_built=False)
        os.remove(os.path.join(tmp, "handoff", "agents_now.json"))
        os.remove(os.path.join(web, "pythia", "events.json"))
        ed = build(tmp, web, "2026-11-10", None, with_git=False)
        ids = [ed["lead"]["id"]] + [a["id"] for a in ed["articles"]]
        why = {s_["article"]: s_["why"] for s_ in ed["skipped"]}
        t("missing data: no home.json, money index, roster or calendar -> those stories are NOT written (each with its reason), the rest still are, the weather box is absent, nothing is made up",
          ids == ["kalshi-research", "kalshi-stop", "archive", "queue", "mind"] and "site build" in why["bots"] and "site build" in why["money"] and "agents_now" in why["builders"] and "pythia" in why["calendar"]
          and ed["weather"] is None and "home.json" in ed["sources"]["missing"] and all(not audit(a) for a in [ed["lead"]] + ed["articles"]) and len(ed["interviews"]) == 2, (ids, why))
    with tempfile.TemporaryDirectory() as tmp:
        ed = build(tmp, os.path.join(tmp, "web"), "2026-11-10", None, with_git=False)
        t("an empty newsroom: no lead, no articles, every story listed as skipped; still a valid edition (the page then shows its demo)", ed["lead"] is None and ed["articles"] == [] and len(ed["skipped"]) == 10 and ed["quiz"] == [] and ed["interviews"] == [])
    fx = fixture()
    t("the demo fixture: labelled demo and 'not real', a full edition (lead + 9), deterministic, with a 'new apps' story", fx["demo"] is True and "not real" in fx["note"] and fx["edition"]["demo"] is True and len(fx["edition"]["articles"]) == 9
      and dump(fx) == dump(fixture()) and fx["edition"]["articles"][-1]["id"] == "new-apps" and fx["edition"]["number"] == 7, len(fx["edition"]["articles"]))
    bad = res.count(False)
    print(f"\n{len(res) - bad}/{len(res)} passed")
    return 1 if bad else 0


def check(out_dir, root, web):
    cur = read_json(os.path.join(out_dir, "edition.json"))
    if not isinstance(cur, dict) or not isinstance(cur.get("date"), str):
        return False
    now = build(root, web, cur["date"], load_prev(out_dir, cur["date"]), with_git=False, demo=bool(cur.get("demo")))
    return stable(cur) == stable(now)


def check_edit(out_dir, root, web):
    p = os.path.join(out_dir, "edition.json")
    cur = read_json(p)
    cur["lead"]["headline"] += " (edited)"
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(dump(cur))
    return check(out_dir, root, web)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--web", default=WEB, help="the site folder to read and to write herald/ into (default: tools/web_public; the site build passes the built site)")
    ap.add_argument("--root", default=ROOT, help="the repo (handoff/, research/writeups/)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    out = os.path.join(a.web, "herald")
    fx_path = os.path.join(WEB, "herald", "fixture.json")
    if a.check:
        ok = check(out, a.root, a.web) and (a.web != WEB or read_text(fx_path) == dump(fixture()))
        print("herald: edition.json is up to date" if ok else "herald: edition.json is STALE (run python tools/herald_build.py --date <its date>)")
        return 0 if ok else 1
    date = a.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        print("herald: --date must be YYYY-MM-DD")
        return 2
    ed = build(a.root, a.web, date, load_prev(out, date))
    days = write(out, ed)
    if a.web == WEB:
        with open(fx_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump(fixture()))
    n = (1 if ed["lead"] else 0) + len(ed["articles"])
    print(f"herald: edition {ed['number']} for {date}: {n} stories ({', '.join(([ed['lead']['id']] if ed['lead'] else []) + [x['id'] for x in ed['articles']])}); {len(ed['skipped'])} not written; {len(days)} editions kept")
    for s_ in ed["skipped"]:
        print(f"  not written: {s_['article']}: {s_['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
