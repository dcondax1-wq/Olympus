"""Refresh the AUTO block of handoff/SYNC.md: latest commits, inbox contents, open ChatGPT branches.
Run from the repo root: python tools/bridge_sync.py   (writes only SYNC.md and tools/web_public/bridge/status.json)."""
import pathlib, subprocess, datetime, json, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SYNC = ROOT / "handoff" / "SYNC.md"
PAGE = ROOT / "tools" / "web_public" / "bridge"


def git(*a):
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def build():
    inbox = ROOT / "handoff" / "inbox"
    jobs = sorted(p.name for p in inbox.iterdir() if p.is_dir()) if inbox.exists() else []
    lines = ["_updated " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") + "_", "", "**Inbox (ChatGPT results):**"]
    for j in jobs:
        files = [f.name for f in (inbox / j).iterdir()]
        flag = "DONE" if "DONE.md" in files else ("QUESTION" if "QUESTION.md" in files else "in progress")
        lines.append(f"- {j}: {flag} ({len(files)} files)")
    if not jobs:
        lines.append("- empty")
    br = [b.strip() for b in git("branch", "-r").splitlines() if "chatgpt/" in b]
    lines += ["", "**Open ChatGPT branches:** " + (", ".join(br) if br else "none"), "", "**Latest Claude commits:**"]
    lines += ["- " + c for c in git("log", "-8", "--pretty=%h %s").splitlines()]
    return "\n".join(lines)


def _ingest():
    """tools/bridge_ingest.py (works from `python tools/bridge_sync.py` and from `from tools import bridge_sync`)."""
    try:
        from tools import bridge_ingest as m
    except ImportError:
        sys.path.insert(0, str(HERE))
        import bridge_ingest as m
    return m


def library():
    """The ready ChatGPT jobs (bridge/jobs.json, built by tools/bridge_jobs_build.py): a list of dicts, [] if missing."""
    try:
        d = json.loads((PAGE / "jobs.json").read_text(encoding="utf-8"))
        return [j for j in d.get("jobs", []) if isinstance(j, dict) and re.fullmatch(r"[a-z0-9-]+", str(j.get("id", "")))]
    except Exception:
        return []


def job_ids():
    """The job ids on the Bridge page: the cards plus the library."""
    try:
        cards = re.findall(r"\{ id: '([a-z0-9-]+)', t:", (PAGE / "index.html").read_text(encoding="utf-8"))
    except Exception:
        cards = []
    return cards + [j["id"] for j in library() if j["id"] not in cards]


def suggest(jobs, lib=None, today=None, cats=None, limit=5):
    """'What to ask ChatGPT next': a short list from static rules (no model, no network). `jobs` = status()['jobs'] ({id: {state, files}}).
    Rules, in order, each job once, at most `limit`:
      1 question   ChatGPT is waiting for an answer: answer first
      2 finish     a job ChatGPT started (in progress) and has not finished: nudge it
      3 first      nothing delivered yet: the easiest 5-minute job (the first win)
      4 week       the category of the week (rotates every ISO week): its two easiest jobs not yet asked
      5 gap        a category with no delivery yet: its easiest job
      6 quick      the shortest job not yet asked
    -> [{id, title, cat, minutes, difficulty, rule, why}]"""
    lib = library() if lib is None else lib
    today = today or datetime.date.today()
    if cats is None:
        try:
            cats = [c["id"] for c in json.loads((PAGE / "jobs.json").read_text(encoding="utf-8")).get("cats", [])]
        except Exception:
            cats = []
    cats = cats or sorted({j.get("cat", "") for j in lib})
    rank = {"easy": 0, "medium": 1, "hard": 2}
    by_id = {j["id"]: j for j in lib}
    state = lambda i: (jobs.get(i) or {}).get("state")  # noqa: E731
    asked = {i for i in by_id if state(i)}
    easy_first = lambda js: sorted(js, key=lambda j: (rank.get(j.get("difficulty"), 1), j.get("minutes", 99), j["id"]))  # noqa: E731
    out, seen = [], set()

    def add(j, rule, why):
        if j["id"] not in seen and len(out) < limit:
            seen.add(j["id"])
            out.append({"id": j["id"], "title": j.get("title", j["id"]), "cat": j.get("cat", ""), "minutes": j.get("minutes", 10),
                        "difficulty": j.get("difficulty", "medium"), "rule": rule, "why": why})

    for i in sorted(by_id):
        if state(i) == "question":
            add(by_id[i], "question", "ChatGPT asked you something: answer it first")
    for i in sorted(by_id):
        if state(i) == "in progress":
            add(by_id[i], "finish", "ChatGPT started this and has not sent DONE.md yet")
    if lib and not any(state(i) == "done" for i in by_id):
        add(easy_first([j for j in lib if j["id"] not in asked] or lib)[0], "first", "Nothing is delivered yet: start with the easiest win")
    if cats:
        wk = today.isocalendar()[1]
        cat = cats[wk % len(cats)]
        for j in easy_first([j for j in lib if j.get("cat") == cat and j["id"] not in asked])[:2]:
            add(j, "week", f"This week's category is {cat} (it changes every week)")
    for c in cats:
        mine = [j for j in lib if j.get("cat") == c]
        if mine and not any(state(j["id"]) == "done" for j in mine):
            free = easy_first([j for j in mine if j["id"] not in asked])
            if free:
                add(free[0], "gap", f"Nothing delivered yet in {c}")
    for j in sorted([j for j in lib if j["id"] not in asked], key=lambda j: (j.get("minutes", 99), j["id"])):
        add(j, "quick", "A short one: about %d min" % j.get("minutes", 10))
    return out


def status():
    """Live state for the Bridge page and Jarvis (bridge/status.json): per job done / question / in progress, file counts,
    updated time, the last 5 commits touching handoff/. Read-only; never raises."""
    inbox = ROOT / "handoff" / "inbox"
    jobs = {}
    try:
        if inbox.exists():
            for d in sorted(p for p in inbox.iterdir() if p.is_dir()):
                names = [f.name for f in d.rglob("*") if f.is_file()]
                state = "done" if "DONE.md" in names else ("question" if "QUESTION.md" in names else "in progress")
                files = len([n for n in names if n not in ("DONE.md", "QUESTION.md", ".gitkeep")])
                jobs[d.name] = {"state": state, "files": files}
    except Exception:
        pass
    commits = []
    for line in git("log", "-5", "--pretty=%h|%cs|%s", "--", "handoff").splitlines():
        h, _, rest = line.partition("|")
        day, _, subj = rest.partition("|")
        commits.append({"sha": h, "date": day, "subject": subj[:100]})
    ids = job_ids()
    done = sum(1 for j in jobs.values() if j["state"] == "done")
    dl = brief(deliveries())
    return {"v": 1, "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "t": int(time.time()),
            "jobs": jobs, "counts": {"total": len(ids) or len(jobs), "done": done,
                                      "question": sum(1 for j in jobs.values() if j["state"] == "question"),
                                      "in_progress": sum(1 for j in jobs.values() if j["state"] == "in progress"),
                                      "files": sum(j["files"] for j in jobs.values())},
            "commits": commits, "next": suggest(jobs), "deliveries": dl}


def brief(dl):
    """The small version of deliveries() that goes into status.json: counts, image names, text names, the DONE line (the text itself is in
    deliveries.json, loaded only when the Deliveries tab opens)."""
    return {i: {"approved": d.get("approved", 0), "rejected": d.get("rejected", 0), "images": [x["name"] for x in d.get("images", [])][:40],
                "texts": [x["name"] for x in d.get("text", [])], "done": (d.get("done") or "")[:200]}
            for i, d in (dl.get("jobs") or {}).items()}


def deliveries(inbox=None):
    """What ChatGPT delivered, checked by tools/bridge_ingest.py (read-only: nothing delivered is run): {v, jobs: {id: images, text, rejects ...}}.
    Never raises."""
    try:
        return _ingest().deliveries(str(inbox or (ROOT / "handoff" / "inbox")))
    except Exception:
        return {"v": 1, "jobs": {}}


def card(st):
    """The Jarvis status-contract card (docs/JARVIS_APPS.md) for the Bridge app from status()."""
    c = st.get("counts", {})
    done, total, q = c.get("done", 0), c.get("total", 0), c.get("question", 0)
    level, label = ("warn", "ChatGPT has a question") if q else (("ok", "Link is live") if done else ("off", "Nothing delivered yet"))
    return {"v": 1, "name": "Bridge", "status": {"level": level, "label": label},
            "kpis": [{"label": "Delivered", "value": f"{done}/{total}"}, {"label": "Files", "value": str(c.get("files", 0))}],
            "lines": [f"ChatGPT link: {done} of {total} jobs delivered"] + ([f"{q} question{'s' if q != 1 else ''} waiting for you"] if q else []),
            "t": st.get("t", int(time.time())), "theme": "#14110e"}


def publish(out):
    """Write bridge/status.json and bridge/jarvis.json into the site folder `out` (called by build_web_dashboard.py)."""
    st = status()
    d = pathlib.Path(out) / "bridge"
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps(st, separators=(",", ":")), encoding="utf-8")
    (d / "jarvis.json").write_text(json.dumps(card(st), separators=(",", ":")), encoding="utf-8")
    dl = deliveries()
    raw = json.dumps(dl, separators=(",", ":"))
    if len(raw) > 400_000:      # keep the site small: drop the long previews, keep names and counts
        for x in dl["jobs"].values():
            x["text"] = [{"name": t["name"], "kind": t["kind"], "text": t["text"][:400], "truncated": True, "size": t["size"]} for t in x["text"]][:4]
        raw = json.dumps(dl, separators=(",", ":"))
    (d / "deliveries.json").write_text(raw, encoding="utf-8")
    n = 0
    try:   # the Deliveries tab: the approved images of finished jobs next to the page (thumbnails), copied as bytes only
        n = _ingest().copy_for_site(str(d / "deliveries"), str(ROOT / "handoff" / "inbox"))
    except Exception:
        pass
    return f"{st['counts']['done']}/{st['counts']['total']} jobs delivered" + (f", {n} delivered images" if n else "")


def main():
    PAGE.mkdir(parents=True, exist_ok=True)
    (PAGE / "status.json").write_text(json.dumps(status(), indent=1) + "\n", encoding="utf-8")
    (PAGE / "deliveries.json").write_text(json.dumps(deliveries(), indent=1) + "\n", encoding="utf-8")
    t = SYNC.read_text(encoding="utf-8")
    a, b = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"
    i, j = t.index(a) + len(a), t.index(b)
    SYNC.write_text(t[:i] + "\n" + build() + "\n" + t[j:], encoding="utf-8")
    print("SYNC.md refreshed")


if __name__ == "__main__":
    main()
