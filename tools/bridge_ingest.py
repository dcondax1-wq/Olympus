"""Bridge ingest: ChatGPT's deliveries (handoff/inbox/<id>/) checked, summarised and prepared for building in. READ-ONLY on the inbox.

    python tools/bridge_ingest.py            report: every delivered job, each file approved or rejected with the reason
    python tools/bridge_ingest.py --apply    also copy the approved images to tools/web_public/olympus/assets/<id>/ with a manifest
    python tools/bridge_ingest.py --handback "Bridge: <job id> done"    what the owner's hand-back line means: the job checked, in one plain paragraph

What it does, for every job folder that has a DONE.md:
  validate   only png / webp / svg / json / md / txt / js, size caps per type, a file-count and total-size cap, plain names, no symlinks,
             no hidden files, no folders deeper than 3; images must really be PNG / WebP (magic bytes, sane size in pixels); JSON must parse;
             text files are scanned for secret-like strings (tokens, keys, private keys, long key=value secrets); a .js file is rejected if it
             can reach the network, evaluate text as code, load more code or write markup; an .svg is rejected if it holds a script, an event
             handler, javascript:, a foreignObject, an external reference or an entity.
  prepare    approved images (png / webp / svg) are copied to olympus/assets/<id>/ with a manifest.json (name, size, sha256, pixels); a text
             preview of the approved md / txt / json / js is written for the Bridge page (never as markup: the page uses textContent).
NOTHING delivered is ever executed, imported, evaluated or opened by a program: files are read as bytes and text only. Claude still reviews
a delivery before building it in; this only makes the first look safe and quick.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX = os.path.join(ROOT, "handoff", "inbox")
ASSETS = os.path.join(ROOT, "tools", "web_public", "olympus", "assets")
KB, MB = 1024, 1024 * 1024
CAPS = {".png": 5 * MB, ".webp": 5 * MB, ".svg": 200 * KB, ".json": 1 * MB, ".md": 200 * KB, ".txt": 200 * KB, ".js": 100 * KB}
IMAGE_EXT = (".png", ".webp", ".svg")
TEXT_EXT = (".md", ".txt", ".json", ".js", ".svg")
MAX_FILES, MAX_JOB_BYTES, MAX_DEPTH, MAX_PIXELS = 80, 40 * MB, 3, 8192
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ +()-]{0,79}$")
PREVIEW = 3000

SECRETS = [
    (r"gh[pousr]_[A-Za-z0-9]{30,}", "a GitHub token"), (r"github_pat_[A-Za-z0-9_]{20,}", "a GitHub token"),
    (r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}", "an API key (sk-...)"), (r"\bAKIA[0-9A-Z]{16}\b", "an AWS key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"), (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "a Telegram bot token"), (r"\bAIza[0-9A-Za-z_-]{35}\b", "a Google API key"),
    (r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "a JWT"),
    (r"(?i)\b(?:api[_-]?key|secret|token|passwd|password|private[_-]?key)\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-/+=]{20,}", "a key / secret / token value"),
]
JS_BAD = [
    (r"\bfetch\s*\(", "fetch()"), (r"\bXMLHttpRequest\b", "XMLHttpRequest"), (r"\bWebSocket\b", "WebSocket"), (r"\bEventSource\b", "EventSource"),
    (r"\bsendBeacon\b", "sendBeacon"), (r"\beval\s*\(", "eval()"), (r"\bnew\s+Function\b|\bFunction\s*\(", "Function()"), (r"\bimport\s*\(", "dynamic import()"),
    (r"\bimportScripts\b", "importScripts"), (r"\bdocument\.write", "document.write"), (r"\.innerHTML\s*=|\binsertAdjacentHTML\b|\bouterHTML\s*=", "writes markup"),
    (r"\bsetTimeout\s*\(\s*[\"'`]|\bsetInterval\s*\(\s*[\"'`]", "a timer that runs text"), (r"\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b|\bdocument\.cookie\b", "storage / cookies"),
    (r"\bimport\s+[^;]*\bfrom\s+[\"']https?:|\bimport\s+[\"']https?:", "imports from a URL"), (r"https?://", "a web address"), (r"\bchild_process\b|\brequire\s*\(", "node modules"),
]
SVG_BAD = [
    (r"<\s*script\b", "a <script>"), (r"\son[a-z]+\s*=", "an event handler"), (r"javascript\s*:", "javascript:"), (r"<\s*foreignObject\b", "a foreignObject"),
    (r"<!ENTITY|<!DOCTYPE[^>]*\[", "an entity / DTD"), (r"(?:href|src)\s*=\s*[\"']\s*(?:https?:|//|data:text/html)", "an external reference"),
    (r"url\(\s*[\"']?\s*https?:", "an external url()"), (r"<\s*(?:iframe|embed|object|link|meta)\b", "an embedded document"), (r"<\s*use\b[^>]*href\s*=\s*[\"'][^#\"']", "a <use> of another file"),
    (r"@import", "an @import"),
]
MD_BAD = [(r"<\s*script\b", "a <script>"), (r"javascript\s*:", "javascript:"), (r"<\s*(?:iframe|object|embed)\b", "an embedded document")]


def plain_reason(reason: str) -> str:
    """ONE plain sentence (8th-grade words) for a rejected file, from the technical reason: what the owner reads on the Bridge page."""
    r = (reason or "").strip()
    low = r.lower()
    if low.startswith("file type"):
        return "This kind of file is not allowed here (only png, webp, svg, json, md, txt and small js files are)."
    if low.startswith("too big"):
        m = re.search(r"\((\d+) KB, limit (\d+) KB\)", r)
        return f"It is too big ({m.group(1)} KB; the limit for this kind of file is {m.group(2)} KB)." if m else "It is too big."
    if low.startswith("the job is over"):
        return "The whole job is too big, so the extra files were left out."
    if low == "empty file":
        return "The file is empty."
    if low.startswith("not a real") or low == "not an svg":
        return "It says it is a picture, but it is not a real picture."
    if low.startswith("image size"):
        return "The picture is much too large."
    if low.startswith("not utf-8") or low.startswith("binary data"):
        return "It is not plain readable text."
    if low.startswith("looks like"):
        return "It looks like it holds a secret key or password, so I kept it out."
    if low.startswith("not valid json"):
        return "The data file is broken, so it cannot be read."
    if low.startswith("script uses"):
        what = low[len("script uses "):]
        if what in ("eval()", "function()", "a timer that runs text"):
            return "It is a small program that can run hidden code, so I did not use it."
        if what in ("writes markup", "document.write"):
            return "It is a small program that changes the page in an unsafe way, so I did not use it."
        if what.startswith("storage"):
            return "It is a small program that saves things on your phone, so I did not use it."
        if what == "node modules":
            return "It is a small program that uses computer tools it should not, so I did not use it."
        return "It is a small program that can reach the internet or load more code, so I did not use it."
    if low.startswith("svg holds") or low.startswith("text holds"):
        return "It has a hidden program or link inside, so I did not use it."
    if "odd characters" in low:
        return "The file name has odd characters (use letters, numbers, dashes and dots)."
    if low == "a symlink":
        return "It is a shortcut to another file, which is not allowed."
    if low == "a hidden file":
        return "Hidden files are not allowed."
    if low.startswith("unreadable"):
        return "I could not read this file."
    return "It did not pass the safety check, so I did not use it."


def _first(patterns, text):
    for pat, why in patterns:
        if re.search(pat, text):
            return why
    return None


def png_size(b):
    if len(b) < 24 or b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", b[16:24])


def webp_size(b):
    if len(b) < 30 or b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        return None
    t = b[12:16]
    try:
        if t == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if t == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return 1 + (v & 0x3FFF), 1 + ((v >> 14) & 0x3FFF)
        if t == b"VP8 ":
            return struct.unpack("<HH", b[26:30])[0] & 0x3FFF, struct.unpack("<HH", b[26:30])[1] & 0x3FFF
    except Exception:
        return (0, 0)
    return (0, 0)


def validate_bytes(name: str, data: bytes):
    """-> (ok, reason, meta). name is the file name (the extension decides the rules). Pure: no file access."""
    ext = os.path.splitext(name)[1].lower()
    base = os.path.basename(name)
    if base in ("DONE.md", "QUESTION.md"):
        ext = ".md"
    if ext not in CAPS:
        return False, f"file type {ext or '(none)'} is not allowed", {}
    if len(data) > CAPS[ext]:
        return False, f"too big ({len(data) // KB} KB, limit {CAPS[ext] // KB} KB)", {}
    if not len(data):
        return False, "empty file", {}
    meta = {"kind": ext[1:], "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if ext in (".png", ".webp"):
        dims = png_size(data) if ext == ".png" else webp_size(data)
        if dims is None:
            return False, f"not a real {ext[1:].upper()} image", {}
        if dims[0] > MAX_PIXELS or dims[1] > MAX_PIXELS or (ext == ".png" and (dims[0] < 1 or dims[1] < 1)):
            return False, f"image size {dims[0]}x{dims[1]} is out of range (max {MAX_PIXELS} px)", {}
        meta["w"], meta["h"] = dims
        return True, "", meta
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False, "not UTF-8 text", {}
    if "\x00" in text:
        return False, "binary data in a text file", {}
    why = _first(SECRETS, text)
    if why:
        return False, f"looks like {why}", {}
    if ext == ".json":
        try:
            json.loads(text)
        except Exception as e:
            return False, f"not valid JSON ({str(e)[:40]})", {}
    elif ext == ".js":
        why = _first(JS_BAD, text)  # comments are scanned too: stricter on purpose
        if why:
            return False, f"script uses {why}", {}
    elif ext == ".svg":
        if "<svg" not in text[:2000].lower():
            return False, "not an SVG", {}
        why = _first(SVG_BAD, text)
        if why:
            return False, f"SVG holds {why}", {}
    elif ext in (".md", ".txt"):
        why = _first(MD_BAD, text)
        if why:
            return False, f"text holds {why}", {}
    return True, "", meta


def scan_job(path: str, job_id: str | None = None) -> dict:
    """One job folder -> { id, state, files: [{name, ok, reason, ...meta}], approved, rejected, folder_issue } (reads files, never runs them)."""
    jid = job_id or os.path.basename(path.rstrip("/\\"))
    res = {"id": jid, "state": "in progress", "files": [], "approved": 0, "rejected": 0, "issues": []}
    entries = []
    total = 0
    for dp, dns, fns in os.walk(path, followlinks=False):
        depth = os.path.relpath(dp, path).count(os.sep) + (0 if dp == path else 1)
        if depth >= MAX_DEPTH:
            dns[:] = []
            res["issues"].append(f"folders deeper than {MAX_DEPTH} are ignored")
        for dn in list(dns):
            if os.path.islink(os.path.join(dp, dn)):
                dns.remove(dn)
                res["issues"].append(f"symlinked folder {dn} ignored")
        for fn in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, fn), path).replace(os.sep, "/")
            entries.append(rel)
    names = {e for e in entries}
    res["state"] = "done" if "DONE.md" in names else ("question" if "QUESTION.md" in names else "in progress")
    if len(entries) > MAX_FILES:
        res["issues"].append(f"{len(entries)} files (limit {MAX_FILES}): the first {MAX_FILES} are checked")
    for rel in entries[:MAX_FILES]:
        full = os.path.join(path, rel)
        base = os.path.basename(rel)
        row = {"name": rel, "ok": False, "reason": ""}
        if base == ".gitkeep":
            continue
        if os.path.islink(full):
            row["reason"] = "a symlink"
        elif base.startswith("."):
            row["reason"] = "a hidden file"
        elif not all(NAME_RE.match(part) for part in rel.split("/")):
            row["reason"] = "the file name has odd characters"
        else:
            try:
                size = os.path.getsize(full)
                total += size
                ext = os.path.splitext(base)[1].lower()
                if base in ("DONE.md", "QUESTION.md"):
                    ext = ".md"
                if ext in CAPS and size > CAPS[ext]:
                    row["reason"] = f"too big ({size // KB} KB, limit {CAPS[ext] // KB} KB)"
                elif total > MAX_JOB_BYTES:
                    row["reason"] = f"the job is over {MAX_JOB_BYTES // MB} MB in total"
                else:
                    with open(full, "rb") as fh:
                        data = fh.read(CAPS.get(ext, 0) + 1)
                    ok, why, meta = validate_bytes(base, data)
                    row.update(meta)
                    row["ok"], row["reason"] = ok, why
            except OSError as e:
                row["reason"] = f"unreadable ({e.__class__.__name__})"
        res["files"].append(row)
    for row in res["files"]:
        if not row["ok"]:
            row["plain"] = plain_reason(row["reason"])
    res["approved"] = sum(1 for f in res["files"] if f["ok"] and f["name"] not in ("DONE.md", "QUESTION.md"))
    res["rejected"] = sum(1 for f in res["files"] if not f["ok"])
    return res


def scan(inbox: str = INBOX) -> dict:
    """Every job folder of the inbox -> { id: scan_job(...) }. Never raises."""
    out = {}
    try:
        for d in sorted(os.listdir(inbox)):
            p = os.path.join(inbox, d)
            if os.path.isdir(p) and not os.path.islink(p) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", d):
                out[d] = scan_job(p, d)
    except OSError:
        pass
    return out


def preview(inbox: str, job: dict, limit: int = PREVIEW) -> list:
    """Text previews of a job's approved md / txt / json / js (and DONE.md), as plain strings for textContent."""
    out = []
    for f in job["files"]:
        if not f["ok"] or os.path.splitext(f["name"])[1].lower() not in (".md", ".txt", ".json", ".js"):
            continue
        try:
            with open(os.path.join(inbox, job["id"], f["name"]), "r", encoding="utf-8") as fh:
                t = fh.read(limit + 1)
        except OSError:
            continue
        out.append({"name": f["name"], "kind": f["kind"], "text": t[:limit], "truncated": len(t) > limit, "size": f["size"]})
    return out


def deliveries(inbox: str = INBOX, results: dict | None = None) -> dict:
    """The Bridge page's Deliveries data: per job with a DONE.md -> images, text previews, the DONE line, rejects."""
    results = scan(inbox) if results is None else results
    jobs = {}
    for jid, r in results.items():
        if r["state"] != "done":
            continue
        texts = preview(inbox, r)
        done = next((t["text"] for t in texts if t["name"] == "DONE.md"), "")
        jobs[jid] = {"state": "done", "approved": r["approved"], "rejected": r["rejected"], "issues": r["issues"],
                     "images": [{"name": f["name"], "kind": f["kind"], "w": f.get("w"), "h": f.get("h"), "size": f["size"]} for f in r["files"] if f["ok"] and f["name"].lower().endswith(IMAGE_EXT)],
                     "text": [t for t in texts if t["name"] != "DONE.md"][:12], "done": done.strip()[:600],
                     "rejects": [{"name": f["name"], "reason": f["reason"], "plain": f.get("plain") or plain_reason(f["reason"])} for f in r["files"] if not f["ok"]]}
    return {"v": 1, "jobs": jobs}


def apply_assets(inbox: str = INBOX, assets: str = ASSETS, results: dict | None = None) -> dict:
    """Copy each DONE job's approved images to assets/<id>/ with a manifest.json; a root index.json lists the jobs. Returns {id: n files}.
    Only copies bytes (shutil.copyfile); nothing is opened as code."""
    results = scan(inbox) if results is None else results
    done = {}
    os.makedirs(assets, exist_ok=True)
    for jid, r in results.items():
        if r["state"] != "done":
            continue
        imgs = [f for f in r["files"] if f["ok"] and f["name"].lower().endswith(IMAGE_EXT) and "/" not in f["name"]]
        dst = os.path.join(assets, jid)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        if not imgs:
            continue
        os.makedirs(dst)
        for f in imgs:
            shutil.copyfile(os.path.join(inbox, jid, f["name"]), os.path.join(dst, f["name"]))
        man = {"v": 1, "id": jid, "files": [{k: f[k] for k in ("name", "kind", "size", "sha256", "w", "h") if k in f} for f in imgs],
               "rejected": [{"name": f["name"], "reason": f["reason"]} for f in r["files"] if not f["ok"]]}
        with open(os.path.join(dst, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh, indent=1)
            fh.write("\n")
        done[jid] = len(imgs)
    with open(os.path.join(assets, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "jobs": done}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return done


def copy_for_site(out_dir: str, inbox: str = INBOX, results: dict | None = None, budget: int = 30 * MB) -> int:
    """Copy approved images of DONE jobs into <out_dir>/<id>/ for the Bridge page's thumbnails (a size budget for the whole site). -> files copied."""
    results = scan(inbox) if results is None else results
    n, used = 0, 0
    for jid, r in results.items():
        if r["state"] != "done":
            continue
        for f in r["files"]:
            if f["ok"] and f["name"].lower().endswith(IMAGE_EXT) and "/" not in f["name"] and used + f["size"] <= budget:
                os.makedirs(os.path.join(out_dir, jid), exist_ok=True)
                shutil.copyfile(os.path.join(inbox, jid, f["name"]), os.path.join(out_dir, jid, f["name"]))
                used += f["size"]
                n += 1
    return n


def stray(inbox: str = INBOX) -> list:
    """Things in the inbox that are not a job folder, each as ONE plain sentence (they are skipped, never read): a file at the top, a folder whose name is not
    lowercase letters / numbers / dashes. The owner's most likely slip is a folder named 'Money-Risk-Budget' or a file dropped outside a job folder."""
    out = []
    try:
        for d in sorted(os.listdir(inbox)):
            p = os.path.join(inbox, d)
            if d in ("README.md", ".gitkeep"):
                continue
            if os.path.islink(p):
                out.append(f"'{d[:40]}' is a shortcut, so it was skipped.")
            elif os.path.isdir(p) and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", d):
                out.append(f"The folder '{d[:40]}' was skipped: a job folder is named with lowercase letters, numbers and dashes, like the job id.")
            elif not os.path.isdir(p):
                out.append(f"The file '{d[:40]}' was skipped: files belong inside a folder named after the job.")
    except OSError:
        pass
    return out


def report(results: dict, inbox: str | None = None) -> str:
    lines = []
    for jid, r in results.items():
        lines.append(f"{jid}: {r['state']}, {r['approved']} approved, {r['rejected']} rejected")
        if r["state"] == "in progress":
            lines.append("    ChatGPT has not added DONE.md yet, so it is not finished.")
        for f in r["files"]:
            if not f["ok"]:
                lines.append(f"    REJECTED {f['name']}: {f.get('plain') or plain_reason(f['reason'])} [{f['reason']}]")
        for i in r["issues"]:
            lines.append(f"    note: {i}")
    lines += ["note: " + x for x in stray(inbox or INBOX)]
    return "\n".join(lines) or "the inbox is empty"


HANDBACK_RE = re.compile(r"\bbridge\s*:\s*([A-Za-z0-9][A-Za-z0-9-]{0,60})\s+(done|question)\b", re.I)


def parse_handback(text: str):
    """The owner's hand-back line, 'Bridge: <job id> done' (or 'question') -> (id, kind), or None. Capital letters, extra spaces, a full stop and a longer
    message around it are fine. The id is only letters, numbers and dashes, so it can never name a path."""
    m = HANDBACK_RE.search(str(text or "")[:2000])
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower()


def handback(text: str, inbox: str = INBOX) -> dict:
    """What Claude does with 'Bridge: <id> done': find the job's folder, check it, say it in ONE plain paragraph. Read-only. -> {ok, id, kind, sentence, job}"""
    pr = parse_handback(text)
    if not pr:
        return {"ok": False, "id": None, "kind": None, "job": None, "sentence": "I did not understand that. The message should look like: Bridge: money-risk-budget done"}
    jid, kind = pr
    p = os.path.join(inbox, jid)
    if not os.path.isdir(p) or os.path.islink(p):
        return {"ok": False, "id": jid, "kind": kind, "job": None, "sentence": f"I cannot find a folder called {jid} in the inbox. ChatGPT may not have saved its files yet."}
    job = scan_job(p, jid)
    if kind == "question" or job["state"] == "question":
        sentence = f"{jid}: ChatGPT has a question for you. Open QUESTION.md in that folder and answer it."
    elif job["state"] != "done":
        sentence = f"{jid}: ChatGPT has not added DONE.md yet, so it is not finished. Ask ChatGPT to finish and add it."
    else:
        bad = sorted((f for f in job["files"] if not f["ok"]), key=lambda f: (0 if f["reason"].startswith(("script uses", "looks like", "svg holds", "text holds")) else 1, f["name"]))   # the unsafe ones first
        sentence = f"{jid}: ChatGPT is done. {job['approved']} file{'s' if job['approved'] != 1 else ''} passed the safety check" + (f" and {len(bad)} {'was' if len(bad) == 1 else 'were'} not used." if bad else ".")
        if bad:
            sentence += " " + " ".join(f"{f['name']}: {f.get('plain') or plain_reason(f['reason'])}" for f in bad[:3])
    return {"ok": job["state"] == "done" and kind == "done", "id": jid, "kind": kind, "job": job, "sentence": sentence}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    inbox = INBOX
    if "--inbox" in argv:
        inbox = argv[argv.index("--inbox") + 1]
    if "--handback" in argv:
        print(handback(argv[argv.index("--handback") + 1], inbox)["sentence"])
        return 0
    res = scan(inbox)
    print(report(res, inbox))
    if "--apply" in argv:
        done = apply_assets(inbox, ASSETS if "--assets" not in argv else argv[argv.index("--assets") + 1], res)
        print("copied images for:", ", ".join(f"{k} ({v})" for k, v in done.items()) or "nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
