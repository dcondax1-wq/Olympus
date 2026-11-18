"""PC publisher: the NQ reporting chain without GitHub (owner 2026-11-10). Runs ON THE MAIN PC every 15 minutes
(Task Scheduler, PUBLISH_NQ.bat), stdlib only on top of the repo's own tools.

  1. state   the cloud monitor's own code (tools/cloud_monitor.run) with the PC's own bars: the heartbeat the bot writes to
             logs/pc_hb/ (engine/nogithub.py) instead of the heartbeat branch. Runs in a child process with a time limit.
  2. site    tools/build_web_dashboard.py -> <work>/site (the last good site is kept when a step fails).
  3. publish a PROVIDER sends the site out:
               folder   copy to any folder (an iCloud Drive / OneDrive / Dropbox synced folder); only changed files
               netlify  Netlify's free deploy API. Token + site id from a LOCAL file outside the repo
                        (%USERPROFILE%\\.olympus\\netlify.json), never printed, never committed. Default method "digest"
                        (sends only the files that changed, the site is ~280 MB of mostly unchanging research); method "zip"
                        (the whole site zipped with the files at the zip root, Content-Type application/zip) is the fallback.
               scp      your own Linux server over ssh (Oracle VM + Caddy / nginx): only changed files, no deploy limits
               cloudflare  Cloudflare Pages (free, no badge; docs/HOSTING.md), OFF unless publish.json says "provider":
                        "cloudflare". Cloudflare's own `npx wrangler pages deploy` (Node.js on the PC) to the production
                        branch "main". The key ONLY from the PC's environment variable CLOUDFLARE_API_TOKEN (never a file, never
                        the repo, never printed); account id from CLOUDFLARE_ACCOUNT_ID or publish.json "cf_account_id".
               none     build only
What leaves this PC (2026-11-15): the LITE set, the one the owner's Netlify Drop zip carried: the built site without the 5 heavy
folders (charts/ trade pictures, replays/ trade charts, writeups/ the research reader, datacity/ the 3D city, mind/ the vault),
and never a private file (tools/site_privacy.private_file, by name and by JSON content: household, day, inbox, agency, health,
cards, keys ...; the build's own last step, site_privacy.scrub, already masks ids / emails / names / ages in what stays). The PC's
own copy (data/pc_publish/site, served to your devices over Tailscale by engine/live_site.py) keeps everything.
publish.json "site_set": "full" sends the heavy folders too. The hash, the deploy budget and the six lines count what is sent.
Unchanged content (sha256 of what is sent) is not uploaded again. Every failure is soft: it is logged, the last good site
stays up, the exit code is 0 unless --strict. Nothing here touches the trading bot, live_model*.json or any order.

  python tools/pc_publish.py                 one full run (state, site, publish) and a six-line status
  python tools/pc_publish.py --status        only print the six lines of the last run
  python tools/pc_publish.py --setup folder --folder "C:\\Users\\me\\iCloudDrive\\olympus"     write publish.json
  python tools/pc_publish.py --setup netlify --site-id <id> --token-stdin                      write netlify.json (token not echoed)
  python tools/pc_publish.py --setup netlify --site-name <name> --token-stdin    the same, the site id looked up with the key
                             (Netlify API GET /sites?name=, else every page of the account's sites: its name, *.netlify.app
                             address or own domain). Exit 0 saved, 2 no key / no site given, 3 the key was refused, 4 no such
                             site on that account, 5 Netlify not reachable. The key is never printed, logged or put in a URL.
  python tools/pc_publish.py --setup cloudflare --cf-project <name> [--cf-account <id>]     publish.json for Cloudflare Pages
  python tools/pc_publish.py --dry-run       build, hash and say what would be sent; sends nothing
Config (all outside the repo, in %USERPROFILE%\\.olympus\\ or $OLYMPUS_HOME): publish.json {"provider", "folder", "method",
"min_interval_min", "site_set"}, netlify.json {"site_id", "token", "site_name", "site_url"}. Local files: data/pc_publish/
(last.json, publish_log.jsonl, site/, dash/).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import nogithub  # noqa: E402

WORK_DEFAULT = os.path.join(ROOT, "data", "pc_publish")
NETLIFY_API = "https://api.netlify.com/api/v1"
MONITOR_TIMEOUT_S = 900
BUILD_TIMEOUT_S = 600
HTTP_TIMEOUT_S = 120
LOG_KEEP = 500
LOCK_STALE_S = 25 * 60
UA = "olympus-pc-publish/1"
# Netlify's new free plan: 300 credits a month and every production deploy costs 15 = about 20 deploys a month (checked
# 2026-11-10, netlify.com/pricing); at zero the site pauses. Older accounts have no such cap. The guard keeps 2 in reserve.
DEPLOYS_PER_MONTH_DEFAULT = 18
# Cloudflare Pages free: 500 builds a month (developers.cloudflare.com/pages/platform/limits, checked 2026-11-18); a direct
# upload is counted as one to be safe, 50 kept in reserve = 15 a day. The wrangler version is pinned (released 2026-11-02).
CF_DEPLOYS_PER_MONTH_DEFAULT = 450
CF_WRANGLER = "wrangler@4.156.2"
CF_BRANCH = "main"
CF_PROJECT_RX = re.compile(r"^[a-z0-9][a-z0-9-]{0,56}$")
CF_TIMEOUT_S = 1800
CF_MAX_FILE, CF_MAX_FILES = 25 * 1024 * 1024, 20000
SECRET_KEYS = ("token", "access_token", "authorization", "password", "secret")
# the heavy folders the owner's Netlify Drop zip left out (the upload was too big); they stay on the PC (and its Tailscale link)
LITE_EXCLUDE = ("charts/", "replays/", "writeups/", "datacity/", "mind/")
# the folders of the Tailscale link's PRIVATE routes (engine/live_site.py: /site/day/, /site/me/): never sent, whatever lands there
PRIVATE_DIRS = ("day/", "me/")
SETUP_OK, SETUP_INPUT, SETUP_REFUSED, SETUP_NO_SITE, SETUP_UNREACHABLE = 0, 2, 3, 4, 5       # --setup netlify exit codes


# ------------------------------------------------------------------------------------------------ small helpers
def now_s() -> int:
    return int(time.time())


def redact(text, secrets=()) -> str:
    """Never let a token reach a log line, the console or last.json."""
    s = str(text)
    for sec in secrets:
        if sec and len(str(sec)) >= 6:
            s = s.replace(str(sec), "<token>")
    import re
    s = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}", r"\1<token>", s)
    s = re.sub(r"(?i)((?:access_)?token[\"'=:\s]+)[A-Za-z0-9._~+/=-]{12,}", r"\1<token>", s)
    return s


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    try:
        os.replace(tmp, path)
    except OSError:
        shutil.copyfile(tmp, path)


def ago(t, now=None) -> str:
    if not t:
        return "never"
    d = max(0, int((now or now_s()) - int(t)))
    if d < 90:
        return f"{d} s ago"
    if d < 5400:
        return f"{d // 60} min ago"
    if d < 172800:
        return f"{d // 3600} h ago"
    return f"{d // 86400} days ago"


def size_h(n) -> str:
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return "?"


# ------------------------------------------------------------------------------------------------ config (outside the repo)
def config_dir(env=None) -> str:
    return nogithub.olympus_dir(env)


def _default_kalshi_file(d: str):
    """No setting needed: a kalshi.json the VM's kit left in <config dir>/kalshi_feed/ (folder provider, synced or copied) is used."""
    f = os.path.join(d, "kalshi_feed", "kalshi.json")
    return f if os.path.exists(f) else None


def load_config(env=None, cdir: str | None = None) -> dict:
    """{"provider", "folder", "method", "min_interval_min", "netlify": {"site_id", "token"}, "dir"}. Never raises."""
    d = cdir or config_dir(env)
    pub = read_json(os.path.join(d, "publish.json"), {}) or {}
    net = read_json(os.path.join(d, "netlify.json"), {}) or {}
    prov = str(pub.get("provider") or "").lower()
    if not prov:
        prov = "netlify" if (net.get("token") and net.get("site_id")) else "none"
    return {"provider": prov, "folder": pub.get("folder"), "method": str(pub.get("method") or "digest").lower(),
            "min_interval_min": float(pub.get("min_interval_min") or 0), "dir": d,
            "kalshi_file": pub.get("kalshi_file") or _default_kalshi_file(d), "kalshi_feed_url": pub.get("kalshi_feed_url"),
            "scp_target": pub.get("scp_target"), "scp_dir": pub.get("scp_dir"), "scp_key": pub.get("scp_key"),
            "scp_port": pub.get("scp_port"), "scp_url": pub.get("scp_url"),
            "max_deploys_per_month": int(pub.get("max_deploys_per_month") or DEPLOYS_PER_MONTH_DEFAULT),
            "site_set": str(pub.get("site_set") or "lite").lower(),
            "cf_project": str(pub.get("cf_project") or "").strip().lower(), "cf_account_id": str(pub.get("cf_account_id") or "").strip(),
            "cf_url": pub.get("cf_url"),
            "cf_max_deploys_per_month": int(pub.get("cf_max_deploys_per_month") or CF_DEPLOYS_PER_MONTH_DEFAULT),
            "netlify": {"site_id": str(net.get("site_id") or net.get("siteId") or "").strip(),
                        "token": str(net.get("token") or net.get("access_token") or "").strip()}}


def inside_repo(path: str) -> bool:
    try:
        a, b = os.path.realpath(path), os.path.realpath(ROOT)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------------ the site tree
def site_files(site: str) -> dict:
    """{relative posix path: sha1 hex} of every file under site (what the digest deploy needs)."""
    out = {}
    for r, _d, fs in os.walk(site):
        for n in fs:
            p = os.path.join(r, n)
            rel = os.path.relpath(p, site).replace(os.sep, "/")
            h = hashlib.sha1()
            with open(p, "rb") as fh:
                for blk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(blk)
            out[rel] = h.hexdigest()
    return out


def site_hash(files: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(files):
        h.update(f"{k}\0{files[k]}\n".encode("utf-8"))
    return h.hexdigest()


def deploy_set(site: str, files: dict, cfg: dict) -> tuple[dict, dict]:
    """(the files that leave this PC, {"lite": n heavy files kept on the PC, "private": [paths kept out]}). The lite set (unless
    publish.json "site_set" is "full") and never a private file: tools/site_privacy.private_file by name, and by content for JSON.
    Fails closed: when the privacy check cannot run, nothing is sent (ProviderError)."""
    try:
        from tools import site_privacy
    except Exception as e:                             # never send a site that was not checked
        raise ProviderError(f"the privacy check could not run ({e.__class__.__name__}): nothing sent")
    lite = str(cfg.get("site_set") or "lite").lower() != "full"
    out, n_lite, private = {}, 0, []
    for rel, h in files.items():
        if lite and rel.startswith(LITE_EXCLUDE):
            n_lite += 1
            continue
        raw = None
        if rel.lower().endswith(".json"):
            try:
                with open(os.path.join(site, rel.replace("/", os.sep)), "rb") as fh:
                    raw = fh.read()
            except OSError:
                raw = None
        if rel.startswith(PRIVATE_DIRS) or site_privacy.private_file(rel, raw):
            private.append(rel)
            continue
        out[rel] = h
    return out, {"lite": n_lite, "private": sorted(private)}


def make_zip(site: str, files: dict) -> bytes:
    """The whole site as one zip with the files at the zip root (index.html at the top, no wrapping folder)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in sorted(files):
            z.write(os.path.join(site, rel.replace("/", os.sep)), rel)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ providers
class ProviderError(RuntimeError):
    pass


def _http(method, url, token, data=None, ctype=None, timeout=HTTP_TIMEOUT_S, tries=2):
    """-> (status, parsed json or text). Retries a network error / 5xx once. Raises ProviderError (already redacted)."""
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("User-Agent", UA)
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                try:
                    return r.status, json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    return r.status, raw.decode("utf-8", "replace")[:300]
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            last = f"HTTP {e.code} {body}".strip()
            if e.code in (401, 403):
                raise ProviderError(redact(f"Netlify refused the token (HTTP {e.code}): make a new one (docs/NQ_BOT_BACK.md step 2)", [token]))
            if e.code < 500 and e.code != 429:
                raise ProviderError(redact(last, [token]))
        except Exception as e:
            last = f"{e.__class__.__name__}: {e}"
        if i + 1 < tries:
            time.sleep(2 + 3 * i)
    raise ProviderError(redact(last or "network error", [token]))


def api_base(env=None) -> str:
    env = os.environ if env is None else env
    return (env.get("OLYMPUS_NETLIFY_API") or NETLIFY_API).rstrip("/")


def site_key(s) -> str:
    """'moonlit-scone-08afe5', 'moonlit-scone-08afe5.netlify.app' or 'https://moonlit-scone-08afe5.netlify.app/' -> the bare name
    (a custom domain stays a domain)."""
    s = str(s or "").strip().lower()
    s = re.sub(r"^[a-z]+://", "", s).split("/")[0].split("?")[0]
    return s[:-len(".netlify.app")] if s.endswith(".netlify.app") else s


SITE_ID_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,63}$")


def find_site(name: str, token: str, env=None) -> dict | None:
    """{"id", "name", "url"} of the site called `name` on the Netlify account the key belongs to, else None. Netlify's own filter
    first (GET /sites?name=), then every page of the account's sites; a site matches by its name, its *.netlify.app address, its
    own domain or an alias. Only these three fields are kept (never the rest of the account's data). Raises ProviderError
    (redacted: 'refused the token' for a 401 / 403)."""
    want = site_key(name)
    if not want:
        return None
    base = api_base(env)

    def keys(s):
        vals = [s.get(k) for k in ("name", "url", "ssl_url", "custom_domain")] + list(s.get("domain_aliases") or [])
        return {site_key(v) for v in vals if isinstance(v, str) and v}

    def pick(rows):
        for s in rows if isinstance(rows, list) else []:
            if isinstance(s, dict) and want in keys(s):
                sid = str(s.get("id") or s.get("site_id") or "")
                if SITE_ID_RX.match(sid):
                    return {"id": sid, "name": str(s.get("name") or want), "url": str(s.get("ssl_url") or s.get("url") or "")}
        return None

    _st, rows = _http("GET", f"{base}/sites?name={urllib.parse.quote(want)}&filter=all", token)
    hit = pick(rows)
    for page in range(1, 21):                          # up to 2,000 sites: the filter missed it (an own domain, an alias)
        if hit:
            break
        _st, rows = _http("GET", f"{base}/sites?filter=all&page={page}&per_page=100", token)
        hit = pick(rows)
        if not isinstance(rows, list) or len(rows) < 100:
            break
    return hit


def publish_netlify(site: str, files: dict, cfg: dict, env=None, log=print, **_k) -> dict:
    n = cfg.get("netlify") or {}
    token, sid = n.get("token"), n.get("site_id")
    if not token or not sid:
        raise ProviderError("no Netlify token / site id: " + os.path.join(cfg.get("dir") or "~/.olympus", "netlify.json") + " is missing")
    base = api_base(env)
    method = cfg.get("method") or "digest"
    if method == "digest":
        try:
            return _netlify_digest(site, files, base, sid, token, log)
        except ProviderError as e:
            if "refused the token" in str(e):
                raise
            log(f"[publish] digest deploy failed ({e}); trying the zip upload")
    return _netlify_zip(site, files, base, sid, token)


def _deploy_url(d) -> str | None:
    if isinstance(d, dict):
        return d.get("ssl_url") or d.get("deploy_ssl_url") or d.get("url")
    return None


def _netlify_zip(site, files, base, sid, token) -> dict:
    blob = make_zip(site, files)
    st, d = _http("POST", f"{base}/sites/{urllib.parse.quote(sid)}/deploys", token, data=blob, ctype="application/zip", timeout=600)
    if not isinstance(d, dict) or not d.get("id"):
        raise ProviderError(redact(f"Netlify zip deploy gave no deploy id ({st})", [token]))
    return {"url": _deploy_url(d), "deploy": d.get("id"), "bytes": len(blob), "uploaded": len(files), "method": "zip",
            "state": d.get("state")}


def _netlify_digest(site, files, base, sid, token, log) -> dict:
    body = json.dumps({"files": {"/" + k: v for k, v in files.items()}}).encode("utf-8")
    st, d = _http("POST", f"{base}/sites/{urllib.parse.quote(sid)}/deploys", token, data=body, ctype="application/json")
    if not isinstance(d, dict) or not d.get("id"):
        raise ProviderError(redact(f"Netlify gave no deploy id ({st})", [token]))
    did = d["id"]
    need = set(d.get("required") or [])
    by_hash: dict = {}
    for rel, h in files.items():
        by_hash.setdefault(h, rel)
    todo = [by_hash[h] for h in need if h in by_hash]
    sent = [0]

    def put(rel):
        with open(os.path.join(site, rel.replace("/", os.sep)), "rb") as fh:
            raw = fh.read()
        _http("PUT", f"{base}/deploys/{urllib.parse.quote(did)}/files/{urllib.parse.quote(rel)}", token, data=raw,
              ctype="application/octet-stream")
        sent[0] += len(raw)

    if todo:
        with cf.ThreadPoolExecutor(max_workers=6) as ex:
            for f in [ex.submit(put, r) for r in todo]:
                f.result()
    state = None
    for _ in range(30):                            # up to ~60 s for Netlify to publish what it got
        try:
            _s, cur = _http("GET", f"{base}/deploys/{urllib.parse.quote(did)}", token, tries=1)
        except ProviderError:
            cur = {}
        state = cur.get("state") if isinstance(cur, dict) else None
        if state in ("ready", "current"):
            d = cur
            break
        if state == "error":
            raise ProviderError(redact("Netlify deploy ended in error: " + str(cur.get("error_message") or ""), [token]))
        time.sleep(2)
    return {"url": _deploy_url(d), "deploy": did, "bytes": sent[0], "uploaded": len(todo), "method": "digest", "state": state}


def publish_folder(site: str, files: dict, cfg: dict, **_k) -> dict:
    dest = cfg.get("folder")
    if not dest:
        raise ProviderError('provider "folder" needs a folder: python tools/pc_publish.py --setup folder --folder <path>')
    sent, n = sync_dir(site, files, dest, os.path.join(dest, ".olympus_manifest.json"))
    return {"url": None, "bytes": sent, "uploaded": n, "method": "folder", "state": "copied"}


def sync_dir(site: str, files: dict, dest: str, mpath: str) -> tuple[int, int]:
    """Make dest hold exactly `files` (only changed files copied; files this wrote before and the site no longer has removed).
    The record of what dest holds is mpath. -> (bytes copied, files copied)."""
    os.makedirs(dest, exist_ok=True)
    old = read_json(mpath, {}) or {}
    sent = n = 0
    for rel, h in files.items():
        tgt = os.path.join(dest, rel.replace("/", os.sep))
        if old.get(rel) == h and os.path.exists(tgt):
            continue
        os.makedirs(os.path.dirname(tgt), exist_ok=True)
        tmp = tgt + ".olympus_tmp"
        shutil.copyfile(os.path.join(site, rel.replace("/", os.sep)), tmp)
        os.replace(tmp, tgt)
        sent += os.path.getsize(tgt)
        n += 1
    for rel in set(old) - set(files):                 # files this publisher wrote before and the new site no longer has
        try:
            os.remove(os.path.join(dest, rel.replace("/", os.sep)))
        except OSError:
            pass
    write_json(mpath, files)
    return sent, n


_REMOTE_UNPACK = (
    "import zipfile,os,sys\n"
    "zp,d=sys.argv[1],sys.argv[2]\n"
    "z=zipfile.ZipFile(zp)\n"
    "z.extractall(d)\n"
    "dl=os.path.join(d,'.olympus_delete.txt')\n"
    "if os.path.exists(dl):\n"
    "    for n in open(dl).read().split('\\n'):\n"
    "        p=os.path.normpath(os.path.join(d,n))\n"
    "        if n and p.startswith(os.path.normpath(d)+os.sep) and os.path.isfile(p): os.remove(p)\n"
    "    os.remove(dl)\n"
    "z.close(); os.remove(zp)\n")


def publish_scp(site: str, files: dict, cfg: dict, env=None, log=print, work: str | None = None, **_k) -> dict:
    """Your own server (the Oracle VM, any Linux box with ssh + python3 and a web server such as Caddy): only the changed files are
    zipped, sent with scp, and unpacked remotely with python3; files the site no longer has are removed. No deploy limits.
    publish.json: {"provider": "scp", "scp_target": "user@host", "scp_dir": "/var/www/olympus", "scp_key": "~/.ssh/id_x", "scp_port": 22}.
    The local record of what the server holds is <work>/scp_manifest.json (delete it to resend everything)."""
    import shlex
    tgt, rdir = cfg.get("scp_target"), cfg.get("scp_dir")
    if not tgt or not rdir or not str(rdir).startswith("/"):
        raise ProviderError('provider "scp" needs scp_target (user@host) and an absolute scp_dir in publish.json')
    if not shutil.which("scp") or not shutil.which("ssh"):
        raise ProviderError("scp / ssh not found (Windows 10+: Settings > Apps > Optional features > OpenSSH Client)")
    mpath = os.path.join(work or WORK_DEFAULT, "scp_manifest.json")
    old = read_json(mpath, {}) or {}
    changed = [k for k, h in files.items() if old.get(k) != h]
    gone = sorted(set(old) - set(files))
    if not changed and not gone:
        return {"url": None, "bytes": 0, "uploaded": 0, "method": "scp", "state": "unchanged"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for k in sorted(changed):
            z.write(os.path.join(site, k.replace("/", os.sep)), k)
        if gone:
            z.writestr(".olympus_delete.txt", "\n".join(gone))
    blob = buf.getvalue()
    key = os.path.expanduser(cfg["scp_key"]) if cfg.get("scp_key") else None
    base_opts = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=20"] + \
                (["-i", key, "-o", "IdentitiesOnly=yes"] if key else [])
    port = str(int(cfg["scp_port"])) if cfg.get("scp_port") else None
    tmp = os.path.join(work or WORK_DEFAULT, "upload.zip")
    with open(tmp, "wb") as fh:
        fh.write(blob)
    rzip = rdir.rstrip("/") + "/.olympus_upload.zip"
    try:
        r = subprocess.run(["ssh", *base_opts, *(["-p", port] if port else []), tgt, "mkdir -p " + shlex.quote(rdir)],
                           capture_output=True, timeout=120)
        if r.returncode:
            raise ProviderError("ssh failed: " + redact((r.stderr or b"").decode(errors="replace").strip()[-160:]))
        r = subprocess.run(["scp", "-q", *base_opts, *(["-P", port] if port else []), tmp, f"{tgt}:{rzip}"], capture_output=True, timeout=1800)
        if r.returncode:
            raise ProviderError("scp failed: " + redact((r.stderr or b"").decode(errors="replace").strip()[-160:]))
        cmd = "python3 -c " + shlex.quote(_REMOTE_UNPACK) + " " + shlex.quote(rzip) + " " + shlex.quote(rdir)
        r = subprocess.run(["ssh", *base_opts, *(["-p", port] if port else []), tgt, cmd], capture_output=True, timeout=600)
        if r.returncode:
            raise ProviderError("unpack on the server failed (is python3 installed there?): " + redact((r.stderr or b"").decode(errors="replace").strip()[-160:]))
    except subprocess.TimeoutExpired:
        raise ProviderError("the server did not answer in time")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    write_json(mpath, files)
    return {"url": cfg.get("scp_url"), "bytes": len(blob), "uploaded": len(changed), "method": "scp", "state": "sent"}


CF_NO_PROJECT_RX = re.compile(r"(?i)project not found|8000007|could not find project|does not exist")
CF_URL_RX = re.compile(r"https://[A-Za-z0-9.-]+\.pages\.dev\b")


def cf_settings(cfg: dict, env=None) -> dict:
    """{"token", "account", "project", "npx"} for Cloudflare Pages. The key only from the environment variable. Raises ProviderError."""
    env = os.environ if env is None else env
    token = str(env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account = str(env.get("CLOUDFLARE_ACCOUNT_ID") or cfg.get("cf_account_id") or "").strip()
    project = str(cfg.get("cf_project") or "").strip().lower()
    if not CF_PROJECT_RX.match(project):
        raise ProviderError('provider "cloudflare" needs a project name: python tools/pc_publish.py --setup cloudflare --cf-project <name>')
    if not token:
        raise ProviderError("no Cloudflare key: set the PC's environment variable CLOUDFLARE_API_TOKEN (docs/HOSTING.md step 2), "
                            "then restart the publisher")
    if not re.match(r"^[0-9a-fA-F]{32}$", account):
        raise ProviderError("no Cloudflare account id: set CLOUDFLARE_ACCOUNT_ID or publish.json cf_account_id (docs/HOSTING.md)")
    npx = env.get("OLYMPUS_NPX") or shutil.which("npx", path=env.get("PATH"))
    if not npx:
        raise ProviderError("Node.js not found (npx): install it free with  winget install OpenJS.NodeJS.LTS  then try again")
    return {"token": token, "account": account, "project": project, "npx": npx}


def publish_cloudflare(site: str, files: dict, cfg: dict, env=None, log=print, work: str | None = None, **_k) -> dict:
    """Cloudflare Pages through Cloudflare's own `wrangler pages deploy` (pinned version, via npx), to the PRODUCTION branch "main"
    (a deploy to another branch would only be a preview address). Only the send set goes: it is mirrored into <work>/cf_site
    (changed files copied, gone files removed) and wrangler uploads only what Cloudflare does not hold yet. The key travels in
    the child's environment, never on the command line, and every output line is redacted. A missing project is created once
    (production branch main) and the deploy is tried again."""
    env = os.environ if env is None else env
    c = cf_settings(cfg, env)
    big = [k for k in files if os.path.getsize(os.path.join(site, k.replace("/", os.sep))) > CF_MAX_FILE]
    if big or len(files) > CF_MAX_FILES:              # Cloudflare Pages free: 25 MiB a file, 20,000 files a site
        raise ProviderError(f"too big for Cloudflare Pages: {len(files)} files (max {CF_MAX_FILES})"
                            + (f", over 25 MiB: {', '.join(big[:3])}" if big else ""))
    w = work or WORK_DEFAULT
    stage, run_dir = os.path.join(w, "cf_site"), os.path.join(w, "cf_run")     # run_dir: empty, so no stray functions/ folder
    os.makedirs(run_dir, exist_ok=True)
    _bytes, n = sync_dir(site, files, stage, os.path.join(w, "cf_manifest.json"))
    child = {k: v for k, v in env.items() if k not in ("CLOUDFLARE_API_KEY", "CLOUDFLARE_EMAIL")}
    child.update(CLOUDFLARE_API_TOKEN=c["token"], CLOUDFLARE_ACCOUNT_ID=c["account"], CI="true", WRANGLER_SEND_METRICS="false",
                 NO_COLOR="1")
    secrets = [c["token"]]

    def wr(*args, timeout=CF_TIMEOUT_S):
        try:
            r = subprocess.run([c["npx"], "--yes", CF_WRANGLER, *args], cwd=run_dir, env=child, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ProviderError("Cloudflare did not finish in time; the last good site stays up")
        except OSError as e:
            raise ProviderError(redact(f"could not start npx ({e.__class__.__name__}: {e})", secrets))
        out = redact(((r.stdout or b"") + b"\n" + (r.stderr or b"")).decode("utf-8", "replace"), secrets)
        return r.returncode, out

    deploy = ("pages", "deploy", stage, "--project-name", c["project"], "--branch", CF_BRANCH, "--commit-dirty=true")
    rc, out = wr(*deploy)
    if rc and CF_NO_PROJECT_RX.search(out):
        log(f"[publish] Cloudflare has no project {c['project']} yet: creating it (production branch {CF_BRANCH})")
        rc2, out2 = wr("pages", "project", "create", c["project"], "--production-branch", CF_BRANCH, timeout=600)
        if rc2 and "already exists" not in out2.lower():
            raise ProviderError("Cloudflare would not create the project: " + out2.strip()[-200:])
        rc, out = wr(*deploy)
    if rc:
        if re.search(r"(?i)authentication|10000|unauthori[sz]ed|forbidden|invalid.*token", out):
            raise ProviderError("Cloudflare refused the key: make a new one with Cloudflare Pages: Edit (docs/HOSTING.md step 2)")
        raise ProviderError("Cloudflare deploy failed: " + out.strip()[-240:])
    seen = CF_URL_RX.findall(out)
    url = cfg.get("cf_url") or f"https://{c['project']}.pages.dev"
    return {"url": url, "deploy_url": seen[-1] if seen else None, "bytes": _bytes, "uploaded": n, "method": "wrangler",
            "state": "deployed"}


PROVIDERS = {"netlify": publish_netlify, "folder": publish_folder, "scp": publish_scp, "cloudflare": publish_cloudflare}
BUDGETED = {"netlify": ("Netlify", "max_deploys_per_month", DEPLOYS_PER_MONTH_DEFAULT, "deploys.json"),
            "cloudflare": ("Cloudflare", "cf_max_deploys_per_month", CF_DEPLOYS_PER_MONTH_DEFAULT, "deploys_cloudflare.json")}


# ------------------------------------------------------------------------------------------------ steps
def hb_from_last(now: float) -> dict:
    """No logs/pc_hb yet (the bot runs the old way): the heartbeat payload the bot keeps in logs/heartbeat_last.json plus the
    bars from the PC's own archive / NinjaTrader files. {"present": False} when neither exists."""
    last = read_json(os.path.join(ROOT, "logs", "heartbeat_last.json"), {}) or {}
    pl = last.get("payload")
    if not isinstance(pl, dict) or not pl.get("t"):
        return {"present": False, "reason": "no heartbeat file from the PC bot"}
    hb = dict(pl)
    try:
        from engine import pcbars
        hb["files"] = pcbars.PCBars(sym="NQ", root=pcbars.ARCHIVE_DIR).files(None, now=now)
        hb["bars"] = pcbars.PCBars.meta(hb["files"], None)
    except Exception:
        hb["files"] = {}
    age = max(0.0, now - float(hb.get("t") or 0))
    hb.update(present=True, age_s=int(age), silent=bool(hb.get("running")) and age > 900)
    return hb


def inner_monitor(out: str) -> int:
    """Child process: tools/cloud_monitor.run(out) with heartbeat.read answered from the PC's own files."""
    os.environ["LE_NO_GITHUB"] = "1"
    from engine import heartbeat

    def local_read(cwd=None, remote=None, branch=None, now=None, files=(), **_k):
        t = time.time() if now is None else now
        hb = nogithub.read_local(now=t, files=files)
        return hb if hb.get("present") else hb_from_last(t)

    heartbeat.read = local_read
    from tools import cloud_monitor
    cloud_monitor.run(out)
    return 0


def run_child(args, timeout, cwd=ROOT, env=None):
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    tail = (r.stdout or b"").decode("utf-8", "replace").strip().splitlines()[-3:] + \
           (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-4:]
    return r.returncode, " | ".join(x.strip() for x in tail if x.strip())[:400]


def step_state(work: str) -> tuple[bool, str]:
    dash = os.path.join(work, "dash")
    os.makedirs(dash, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LE_NO_GITHUB": "1"}
    try:
        rc, tail = run_child([sys.executable, "-X", "utf8", os.path.abspath(__file__), "--inner-monitor", dash], MONITOR_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return False, f"the state step ran longer than {MONITOR_TIMEOUT_S // 60} min"
    if rc:
        return False, "state step failed: " + tail
    return os.path.exists(os.path.join(dash, "state.json")), "ok" if os.path.exists(os.path.join(dash, "state.json")) else "no state.json"


def step_site(work: str) -> tuple[bool, str]:
    dash, nxt, site = os.path.join(work, "dash"), os.path.join(work, "site_next"), os.path.join(work, "site")
    shutil.rmtree(nxt, ignore_errors=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        rc, tail = run_child([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "build_web_dashboard.py"), "--state",
                              os.path.join(dash, "state.json"), "--chart", os.path.join(dash, "chart.png"), "--out", nxt],
                             BUILD_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return False, "the site build ran too long"
    if rc or not os.path.exists(os.path.join(nxt, "index.html")) or not os.path.exists(os.path.join(nxt, "data.json")):
        shutil.rmtree(nxt, ignore_errors=True)
        return False, "site build failed: " + tail
    shutil.rmtree(site, ignore_errors=True)           # the new site replaces the old only now it is complete
    os.replace(nxt, site)
    return True, "ok"


def deploy_budget(work: str, cfg: dict, now=None, provider: str = "netlify") -> tuple[bool, str, dict]:
    """(allowed, why, counts): Netlify / Cloudflare deploys are paced so the month's budget lasts: at most budget / 30 a day
    (min 1). Each provider has its own counter file and its own budget key."""
    import datetime as dt
    label, key, default, fname = BUDGETED.get(provider, BUDGETED["netlify"])
    t = dt.datetime.fromtimestamp(now or now_s())
    mk, dk = t.strftime("%Y-%m"), t.strftime("%Y-%m-%d")
    c = read_json(os.path.join(work, fname), {}) or {}
    if c.get("month") != mk:
        c = {"month": mk, "n": 0, "days": {}}
    c["file"] = fname
    budget = int(cfg.get(key) or default)
    per_day = max(1, budget // 30)
    if c["n"] >= budget:
        return False, f"{label} deploy budget used up for {mk} ({c['n']}/{budget}); next month, or raise {key} if your plan allows", c
    if c["days"].get(dk, 0) >= per_day:
        return False, f"today's {per_day} {label} deploy(s) already used (budget {budget} a month)", c
    return True, "ok", c


def deploy_count(work: str, c: dict, now=None):
    import datetime as dt
    dk = dt.datetime.fromtimestamp(now or now_s()).strftime("%Y-%m-%d")
    c["n"] = int(c.get("n") or 0) + 1
    c.setdefault("days", {})[dk] = int(c["days"].get(dk, 0)) + 1
    fname = c.pop("file", None) or "deploys.json"
    write_json(os.path.join(work, fname), c)


def add_kalshi(site: str, cfg: dict) -> str:
    """Optional: put the Kalshi bot's feed into the site as kalshi.json (publish.json "kalshi_file": a local file the VM's
    kalshi_status_vm.py --publish folder writes into a synced folder, or "kalshi_feed_url": an https address of the feed's own
    small site). Must be JSON under 300 KB. Soft: returns a short note, never raises."""
    try:
        raw = None
        if cfg.get("kalshi_file"):
            with open(os.path.expanduser(cfg["kalshi_file"]), "rb") as fh:
                raw = fh.read(300_001)
        elif cfg.get("kalshi_feed_url"):
            u = str(cfg["kalshi_feed_url"])
            if not u.startswith("https://") and not u.startswith("http://127.0.0.1"):
                return "kalshi feed: address must be https"
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20) as r:
                raw = r.read(300_001)
        if raw is None:
            return ""
        if len(raw) > 300_000 or not isinstance(json.loads(raw.decode("utf-8")), dict):
            return "kalshi feed: not a small JSON object, left out"
        with open(os.path.join(site, "kalshi.json"), "wb") as fh:
            fh.write(raw)
        return "kalshi feed added"
    except Exception as e:
        return "kalshi feed not added (" + e.__class__.__name__ + ")"


def acquire_lock(work: str):
    p = os.path.join(work, "lock.json")
    cur = read_json(p, None)
    if cur and now_s() - int(cur.get("t") or 0) < LOCK_STALE_S:
        return None
    write_json(p, {"t": now_s(), "pid": os.getpid()})
    return p


def log_line(work: str, rec: dict):
    try:
        p = os.path.join(work, "publish_log.jsonl")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":"), default=str) + "\n")
        with open(p, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > LOG_KEEP * 1.2:
            with open(p, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-LOG_KEEP:])
    except Exception:
        pass


def status_lines(last: dict, now=None) -> list[str]:
    """The six-line card (also read by scripts/pc_status.ps1 through --status)."""
    now = now or now_s()
    if not last:
        return ["PUBLISH 1/6 last run: never (run PUBLISH_NQ.bat)", "PUBLISH 2/6 provider: -", "PUBLISH 3/6 state: -", "PUBLISH 4/6 site: -",
                "PUBLISH 5/6 sent: -", "PUBLISH 6/6 next: double-click PUBLISH_NQ.bat once, then follow docs/NQ_BOT_BACK.md"]
    ok = last.get("ok")
    return [
        f"PUBLISH 1/6 last run: {ago(last.get('t'), now)} -> {'OK' if ok else 'FAILED'}"
        + (f"  (last good: {ago(last.get('last_good_t'), now)})" if not ok else ""),
        f"PUBLISH 2/6 provider: {last.get('provider')}" + (f" ({last.get('method')})" if last.get("method") and last.get("method") != last.get("provider") else "")
        + (f"  {last.get('url')}" if last.get("url") else ""),
        f"PUBLISH 3/6 state: {last.get('state_text') or '-'}",
        f"PUBLISH 4/6 site: {last.get('files', 0)} files, {size_h(last.get('site_bytes'))}, "
        + ("changed" if last.get("changed") else "unchanged") + f", built {ago(last.get('built_t'), now)}"
        + (f" (lite: {last.get('kept_lite')} heavy files stay on this PC)" if last.get("kept_lite") else ""),
        f"PUBLISH 5/6 sent: {size_h(last.get('bytes'))} in {last.get('uploaded', 0)} files" + (f", took {last.get('took_s')} s" if last.get("took_s") is not None else ""),
        "PUBLISH 6/6 " + ("next: nothing to do." if ok else f"problem: {last.get('error') or 'see data/pc_publish/publish_log.jsonl'}"),
    ]


def run_once(args, env=None, say=print) -> dict:
    env = os.environ if env is None else env
    work = args.work or WORK_DEFAULT
    os.makedirs(work, exist_ok=True)
    cfg = load_config(env)
    if args.provider:
        cfg["provider"] = args.provider
    if args.folder:
        cfg["folder"] = args.folder
    prev = read_json(os.path.join(work, "last.json"), {}) or {}
    t0 = time.time()
    secrets = [cfg["netlify"]["token"], str(env.get("CLOUDFLARE_API_TOKEN") or "")]
    rec = {"t": now_s(), "ok": False, "provider": cfg["provider"], "method": cfg["method"] if cfg["provider"] == "netlify" else None,
           "last_good_t": prev.get("last_good_t") or (prev.get("t") if prev.get("ok") else None)}
    lock = acquire_lock(work)
    if lock is None:
        rec.update(error="another publish is still running", skipped=True)
        return rec
    try:
        if cfg["provider"] not in ("none", *PROVIDERS):
            raise ProviderError(f"unknown provider '{cfg['provider']}' (folder, netlify, scp, cloudflare or none)")
        if cfg["provider"] == "netlify" and inside_repo(cfg["dir"]):
            raise ProviderError("the Netlify token file must live outside the repo")
        if (args.min_interval or cfg["min_interval_min"]) and not args.force and prev.get("ok") and \
                now_s() - int(prev.get("t") or 0) < 60 * float(args.min_interval or cfg["min_interval_min"]):
            rec.update(ok=True, skipped=True, state_text="skipped: published a moment ago", **{k: prev.get(k) for k in ("files", "site_bytes", "built_t", "url")})
            return rec
        if args.skip_build:
            ok_s, st_txt, ok_b, b_txt = True, "skipped (--skip-build)", True, "ok"
        else:
            ok_s, st_txt = step_state(work)
            ok_b, b_txt = (step_site(work) if ok_s else (False, "not built (state step failed)"))
        rec["state_text"] = st_txt if ok_s else ("FAILED: " + st_txt)
        site = os.path.join(work, "site")
        if not ok_s or not ok_b:
            raise ProviderError(redact(st_txt if not ok_s else b_txt, secrets) + "; the last good site stays up")
        note = add_kalshi(site, cfg)
        if note:
            rec["state_text"] += "; " + note
        if os.path.isfile(os.path.join(site, "kalshi.json")):      # the feed added after the build: the same privacy pass (docs/PRIVACY.md)
            from tools import site_privacy
            site_privacy.scrub(site, only=("kalshi.json",))
        files = site_files(site)
        if not files:
            raise ProviderError("the site folder is empty")
        files, kept = deploy_set(site, files, cfg)        # what leaves this PC: the lite set, never a private file
        if not files:
            raise ProviderError("nothing left to send after the lite / privacy pass")
        if kept["private"]:
            rec["state_text"] += f"; {len(kept['private'])} private file(s) kept out of the upload: " + ", ".join(kept["private"][:5])
        total = sum(os.path.getsize(os.path.join(site, k.replace("/", os.sep))) for k in files)
        sh = site_hash(files)
        rec.update(files=len(files), site_bytes=total, built_t=now_s(), site_hash=sh, changed=sh != prev.get("site_hash"),
                   kept_lite=kept["lite"], kept_private=len(kept["private"]))
        if cfg["provider"] == "none":
            rec.update(ok=True, state_text=rec["state_text"] + " (provider none: built only)")
            return rec
        if args.dry_run:
            rec.update(ok=True, state_text=f"dry run: would send {len(files)} files via {cfg['provider']} ({kept['lite']} heavy files stay "
                                           f"on this PC, {len(kept['private'])} private kept out)", dry=True)
            return rec
        if not rec["changed"] and prev.get("ok") and prev.get("provider") == cfg["provider"] and not args.force:
            rec.update(ok=True, uploaded=0, bytes=0, url=prev.get("url"), skipped_same=True)
            return rec
        counts = None
        if cfg["provider"] in BUDGETED:
            okb, why, counts = deploy_budget(work, cfg, provider=cfg["provider"])
            if not okb:                                  # kept for the next allowed run: the old hash stays, so it counts as changed
                rec.update(ok=True, uploaded=0, bytes=0, url=prev.get("url"), throttled=True, site_hash=prev.get("site_hash"),
                           state_text=rec["state_text"] + "; not sent: " + why)
                return rec
        res = PROVIDERS[cfg["provider"]](site, files, cfg, env=env, log=lambda m: say(redact(m, secrets)), work=work)
        if counts is not None:
            deploy_count(work, counts)
        rec.update(ok=True, url=res.get("url") or prev.get("url"), bytes=res.get("bytes"), uploaded=res.get("uploaded"),
                   method=res.get("method") or rec.get("method"), last_good_t=now_s())
        return rec
    except ProviderError as e:
        rec["error"] = redact(e, secrets)[:300]
        return rec
    except Exception as e:                             # never leave a crash trace with a token in it
        rec["error"] = redact(f"{e.__class__.__name__}: {e}", secrets)[:300]
        return rec
    finally:
        rec["took_s"] = int(time.time() - t0)
        try:
            os.remove(os.path.join(work, "lock.json"))
        except OSError:
            pass


def setup(args, env=None) -> int:
    d = config_dir(env)
    os.makedirs(d, exist_ok=True)
    pub = read_json(os.path.join(d, "publish.json"), {}) or {}
    if args.setup == "folder":
        if not args.folder:
            print("[FIX] add --folder <path to a synced folder>")
            return 2
        pub.update(provider="folder", folder=args.folder)
    elif args.setup == "scp":
        if not (args.scp_target and args.scp_dir):
            print("[FIX] needs --scp-target user@host and --scp-dir /absolute/folder/on/the/server")
            return 2
        pub.update(provider="scp", scp_target=args.scp_target, scp_dir=args.scp_dir)
        if args.scp_key:
            pub["scp_key"] = args.scp_key
        if args.scp_url:
            pub["scp_url"] = args.scp_url
    elif args.setup == "netlify":
        tok = sys.stdin.readline().strip() if args.token_stdin else (args.token or "")
        sid = str(getattr(args, "site_id", None) or "").strip()
        name = str(getattr(args, "site_name", None) or "").strip()
        if not tok or not (sid or name):
            print("[FIX] needs the key (--token-stdin, then paste it and press Enter) and --site-name <name> or --site-id <id>")
            return SETUP_INPUT
        extra = {}
        if not sid:                                   # the site id looked up with the key (it never goes into a URL or a log)
            try:
                hit = find_site(name, tok, env)
            except Exception as e:
                msg = redact(e, [tok])
                if "refused the token" in msg:
                    print("[FIX] Netlify refused that key: make a new one (app.netlify.com > your picture > User settings > Applications > "
                          "New access token > Generate). Nothing was saved.")
                    return SETUP_REFUSED
                print(f"[FIX] Netlify could not be reached ({msg[:160]}): check the internet. Nothing was saved.")
                return SETUP_UNREACHABLE
            if not hit:
                print(f"[FIX] The Netlify account of that key has no site called {site_key(name)}: make the key while signed in to the account "
                      "the site is on. Nothing was saved.")
                return SETUP_NO_SITE
            sid = hit["id"]
            extra = {"site_name": hit["name"], "site_url": hit["url"]}
        write_json(os.path.join(d, "netlify.json"), {"site_id": sid, "token": tok, **extra})
        try:
            os.chmod(os.path.join(d, "netlify.json"), 0o600)
        except OSError:
            pass
        pub.update(provider="netlify")
    elif args.setup == "cloudflare":                  # OFF until this is run; the key stays an environment variable
        proj = str(getattr(args, "cf_project", None) or "").strip().lower()
        acct = str(getattr(args, "cf_account", None) or "").strip()
        if not CF_PROJECT_RX.match(proj):
            print("[FIX] needs --cf-project <name>: lowercase letters, digits and dashes (it becomes <name>.pages.dev)")
            return SETUP_INPUT
        if acct and not re.match(r"^[0-9a-fA-F]{32}$", acct):
            print("[FIX] --cf-account is the 32-character account id (Cloudflare > Workers & Pages, right side)")
            return SETUP_INPUT
        pub.update(provider="cloudflare", cf_project=proj, **({"cf_account_id": acct} if acct else {}))
        env_ = os.environ if env is None else env
        if not env_.get("CLOUDFLARE_API_TOKEN"):
            print("[NOTE] the environment variable CLOUDFLARE_API_TOKEN is not set yet (docs/HOSTING.md step 2)")
    else:
        pub.update(provider="none")
    write_json(os.path.join(d, "publish.json"), pub)
    try:                                              # GitHub-free bot mode: the bot writes its heartbeat to logs/pc_hb/
        open(os.path.join(d, nogithub.MARKER), "w").close()
    except OSError:
        pass
    where = ""
    if args.setup == "cloudflare":
        where = f" Site: https://{pub['cf_project']}.pages.dev (after the first publish)."
    if args.setup == "netlify":
        where = f" Site: {extra.get('site_url') or extra.get('site_name') or 'id ' + sid}." if extra else f" Site id {sid}."
    print(f"[OK] publisher set to {args.setup}.{where} Config folder: {d} (outside the repo; the token is never shown)")
    return SETUP_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the NQ state + site on this PC and publish it (no GitHub).")
    ap.add_argument("--work", help="work folder (default data/pc_publish)")
    ap.add_argument("--provider", choices=["folder", "netlify", "scp", "cloudflare", "none"])
    ap.add_argument("--folder")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="publish even when nothing changed")
    ap.add_argument("--skip-build", action="store_true", help="publish the site already in <work>/site")
    ap.add_argument("--min-interval", type=float, default=0, help="skip when the last good publish is younger than N minutes")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when the run failed (default: always 0, a failure is only logged)")
    ap.add_argument("--setup", choices=["folder", "netlify", "scp", "cloudflare", "none"])
    ap.add_argument("--cf-project", help="--setup cloudflare: the Cloudflare Pages project name (<name>.pages.dev)")
    ap.add_argument("--cf-account", help="--setup cloudflare: the 32-character account id (or set CLOUDFLARE_ACCOUNT_ID)")
    ap.add_argument("--scp-target")
    ap.add_argument("--scp-dir")
    ap.add_argument("--scp-key")
    ap.add_argument("--scp-url")
    ap.add_argument("--site-id")
    ap.add_argument("--site-name", help="--setup netlify: the site's name (or its *.netlify.app address); its id is looked up with the key")
    ap.add_argument("--token")
    ap.add_argument("--token-stdin", action="store_true")
    ap.add_argument("--inner-monitor", metavar="OUT", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.inner_monitor:
        return inner_monitor(a.inner_monitor)
    if a.setup:
        return setup(a)
    work = a.work or WORK_DEFAULT
    if a.status:
        print("\n".join(status_lines(read_json(os.path.join(work, "last.json"), {}) or {})))
        return 0
    rec = run_once(a)
    if not rec.get("skipped") or rec.get("ok"):
        if not rec.get("skipped"):
            write_json(os.path.join(work, "last.json"), rec)
    log_line(work, {k: rec.get(k) for k in ("t", "ok", "provider", "method", "files", "bytes", "uploaded", "changed", "took_s", "error", "state_text", "url",
                                            "kept_lite", "kept_private")})
    print("\n".join(status_lines(rec)))
    return 1 if (a.strict and not rec.get("ok")) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:                         # the scheduled task must never show a crash for a soft failure
        print("PUBLISH failed softly:", redact(f"{e.__class__.__name__}: {e}"))
        sys.exit(0)
