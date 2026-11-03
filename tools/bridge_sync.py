"""Refresh the AUTO block of handoff/SYNC.md: latest commits, inbox contents, open ChatGPT branches.
Run from the repo root: python tools/bridge_sync.py   (read-only on everything except SYNC.md)."""
import pathlib, subprocess, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYNC = ROOT / "handoff" / "SYNC.md"


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


def main():
    t = SYNC.read_text(encoding="utf-8")
    a, b = "<!-- AUTO:BEGIN -->", "<!-- AUTO:END -->"
    i, j = t.index(a) + len(a), t.index(b)
    SYNC.write_text(t[:i] + "\n" + build() + "\n" + t[j:], encoding="utf-8")
    print("SYNC.md refreshed")


if __name__ == "__main__":
    main()
