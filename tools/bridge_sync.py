"""Refresh the AUTO block of handoff/SYNC.md: latest commits, inbox contents, open ChatGPT branches.
Run from the repo root: python tools/bridge_sync.py   (writes only SYNC.md and tools/web_public/bridge/status.json)."""
import pathlib, subprocess, datetime, json, re, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
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


def job_ids():
    """The job ids on the Bridge page (the cards)."""
    try:
        return re.findall(r"\{ id: '([a-z0-9-]+)', t:", (PAGE / "index.html").read_text(encoding="utf-8"))
    except Exception:
        return []


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
    return {"v": 1, "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "t": int(time.time()),
            "jobs": jobs, "counts": {"total": len(ids) or len(jobs), "done": done,
                                      "question": sum(1 for j in jobs.values() if j["state"] == "question"),
                                      "in_progress": sum(1 for j in jobs.values() if j["state"] == "in progress"),
                                      "files": sum(j["files"] for j in jobs.values())},
            "commits": commits}


def card(st):
    """The Jarvis status-contract card (docs/JARVIS_APPS.md) for the Bridge app from status()."""
    c = st.get("counts", {})
    done, total, q = c.get("done", 0), c.get("total", 0), c.get("question", 0)
    level, label = ("warn", "ChatGPT has a question") if q else (("ok", "Link is live") if done else ("off", "Nothing delivered yet"))
    return {"v": 1, "name": "Bridge", "status": {"level": level, "label": label},
            "kpis": [{"label": "Delivered", "value": f"{done}/{total}"}, {"label": "Files", "value": str(c.get("files", 0))}],
            "lines": [f"ChatGPT link: {done} of {total} jobs delivered"] + ([f"{q} question{'s' if q != 1 else ''} waiting for you"] if q else []),
            "t": st.get("t", int(time.time())), "theme": "#06040d"}


def publish(out):
    """Write bridge/status.json and bridge/jarvis.json into the site folder `out` (called by build_web_dashboard.py)."""
    st = status()
    d = pathlib.Path(out) / "bridge"
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps(st, separators=(",", ":")), encoding="utf-8")
    (d / "jarvis.json").write_text(json.dumps(card(st), separators=(",", ":")), encoding="utf-8")
    return f"{st['counts']['done']}/{st['counts']['total']} jobs delivered"


def main():
    PAGE.mkdir(parents=True, exist_ok=True)
    (PAGE / "status.json").write_text(json.dumps(status(), indent=1) + "\n", encoding="utf-8")
    t = SYNC.read_text(encoding="utf-8")
    a, b = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"
    i, j = t.index(a) + len(a), t.index(b)
    SYNC.write_text(t[:i] + "\n" + build() + "\n" + t[j:], encoding="utf-8")
    print("SYNC.md refreshed")


if __name__ == "__main__":
    main()
