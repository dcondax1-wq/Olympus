"""IG POST: publish today's planned post to the owner's OWN Instagram professional account with the official Graph API.
DRY RUN BY DEFAULT: without --live it only prints what it would do and never opens a network connection.

    python -m money_machines.ig_post --plan money_machines/plans/local_growth_30d.json                    # dry run: what is due today
    python -m money_machines.ig_post --plan ... --date 2026-11-20                                         # dry run for another day
    python -m money_machines.ig_post --plan ... --image-base-url https://<you>.github.io/ig/ --live        # really post (needs a token)
    python -m money_machines.ig_post --check-token --live                                                 # which account the token is for
    python -m money_machines.ig_post --refresh-token --live                                               # long-lived tokens last 60 days

The token is the owner's and stays OUT of the repo: environment variables IG_ACCESS_TOKEN + IG_USER_ID, or a private JSON file
({"access_token": "...", "ig_user_id": "...", "api": "instagram"}) at --token-file / ~/.config/olympus/instagram.json. A token file
inside this repository is refused. The token is never printed.

What the API needs (Meta docs, searched 2026-11-14): an Instagram professional (Business or Creator) account, an app with the
instagram_business_content_publish permission (Instagram Login) or instagram_content_publish (Facebook Login); for your own
account the app's Standard Access is enough while you have a role on the app. Images must be JPEG on a PUBLIC https address at
the moment of posting (Instagram downloads them), 4:5 to 1.91:1. Two steps: create a media container, then publish it.

Limits we keep: the API allows 100 posts per rolling 24 h (Meta's pages also say 50; we read content_publishing_limit before each
post and stop well below either); our own cap is --max-per-day (default 1, never above 25) counted in a local ledger
(money_machines/out/ig_ledger.json, gitignored) that also stops the same day being posted twice; 30 s between publishes; any
rate-limit error stops the run for the day. No likes, follows, comments or DMs: posting only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get("MONEY_MACHINES_OUT") or os.path.join(HERE, "out")
LEDGER = os.path.join(OUT, "ig_ledger.json")
DEFAULT_TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".config", "olympus", "instagram.json")
HOSTS = {"instagram": "https://graph.instagram.com", "facebook": "https://graph.facebook.com"}
GRAPH_VERSION = "v23.0"
HARD_CAP_24H = 25              # our ceiling, whatever --max-per-day says
API_CAP_ASSUMED = 50           # the smaller of Meta's two published numbers (50 / 100), used when the API does not say
RATE_CODES = {4, 17, 32, 613}  # Graph API rate-limit error codes: stop for the day
GAP_S = 30


class Refused(Exception):
    """The run must stop: no token, a token file in the repo, the cap is reached, a rate limit, or an API error."""


# ------------------------------------------------------------------------------------------------ token (only in --live)
def inside_repo(path: str) -> bool:
    p = os.path.realpath(path)
    return p == os.path.realpath(ROOT) or p.startswith(os.path.realpath(ROOT) + os.sep)


def load_token(token_file: str | None = None, env=None) -> dict:
    env = os.environ if env is None else env
    if env.get("IG_ACCESS_TOKEN") and env.get("IG_USER_ID"):
        return {"access_token": env["IG_ACCESS_TOKEN"], "ig_user_id": env["IG_USER_ID"], "api": env.get("IG_API", "instagram"), "source": "env"}
    path = token_file or DEFAULT_TOKEN_FILE
    if inside_repo(path):
        raise Refused(f"refused: the token file {path} is inside the repository; keep it outside (default {DEFAULT_TOKEN_FILE})")
    if not os.path.exists(path):
        raise Refused("no token: set IG_ACCESS_TOKEN and IG_USER_ID, or put a private token file at " + path)
    with open(path, encoding="utf-8") as fh:
        t = json.load(fh)
    if not t.get("access_token") or not t.get("ig_user_id"):
        raise Refused(f"the token file {path} needs access_token and ig_user_id")
    t.setdefault("api", "instagram")
    t["source"] = path
    return t


def masked(tok: str) -> str:
    return (tok[:4] + "..." + tok[-2:]) if tok and len(tok) > 10 else "***"


# ------------------------------------------------------------------------------------------------ the one network function
def _call(method: str, url: str, params: dict) -> dict:
    """The only place that talks to the network. Never reached in a dry run."""
    import urllib.error
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode(), method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("User-Agent", "olympus-ig-post/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode() or "{}")
        except ValueError:
            return {"error": {"message": f"HTTP {e.code}", "code": e.code}}


def api(tok: dict, method: str, path: str, **params) -> dict:
    base = HOSTS.get(tok.get("api", "instagram"), HOSTS["instagram"])
    r = _call(method, f"{base}/{GRAPH_VERSION}/{path.lstrip('/')}", dict(params, access_token=tok["access_token"]))
    err = (r or {}).get("error")
    if err:
        code = err.get("code")
        msg = str(err.get("message", "error")).replace(tok["access_token"], "***")
        if code in RATE_CODES or err.get("error_subcode") == 2207042:
            raise Refused(f"rate limit from Instagram (code {code}): stopping for today. {msg}")
        raise Refused(f"Instagram API error (code {code}): {msg}")
    return r


# ------------------------------------------------------------------------------------------------ plan + ledger
def load_ledger(path: str = LEDGER) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) and isinstance(d.get("posts"), list) else {"v": 1, "posts": []}
    except (OSError, ValueError):
        return {"v": 1, "posts": []}


def save_ledger(led: dict, path: str = LEDGER) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(led, fh, indent=1)
    os.replace(tmp, path)


def posted_last_24h(led: dict, account: str, now: float) -> int:
    return sum(1 for p in led["posts"] if p.get("account") == account and now - float(p.get("t", 0)) < 86400)


def already_posted(led: dict, account: str, day: int) -> bool:
    return any(p.get("account") == account and p.get("day") == day for p in led["posts"])


def due_posts(plan: dict, date: str) -> list:
    return [p for p in plan["posts"] if p["date"] == date]


def image_url(base: str, post: dict) -> str:
    return base.rstrip("/") + "/" + os.path.basename(post["image"])


# ------------------------------------------------------------------------------------------------ the run
def run(plan: dict, date: str, live: bool = False, base_url: str = "", max_per_day: int = 1, token_file: str | None = None,
        ledger_path: str = LEDGER, now: float | None = None, sleep=time.sleep, env=None, log=print) -> dict:
    """Returns {"mode", "planned": [...], "posted": [...], "stopped": reason or ""}. Dry run never loads the token or the network."""
    now = time.time() if now is None else now
    cap = max(0, min(int(max_per_day), HARD_CAP_24H))
    account = plan["account"]
    led = load_ledger(ledger_path)
    todo = [p for p in due_posts(plan, date) if not already_posted(led, account, p["day"])]
    res = {"mode": "live" if live else "dry-run", "account": account, "date": date, "planned": [], "posted": [], "stopped": ""}
    room = cap - posted_last_24h(led, account, now)
    for p in todo:
        item = {"day": p["day"], "image_url": image_url(base_url or "<image-base-url>", p), "caption_chars": len(p["caption"]),
                "hashtags": len(p["hashtags"])}
        res["planned"].append(item)
    if not todo:
        res["stopped"] = "nothing due (or already posted)"
    if not live:
        for it in res["planned"]:
            log(f"[dry run] would post {account} day {it['day']}: {it['image_url']} ({it['caption_chars']} chars, {it['hashtags']} hashtags)")
        log("[dry run] nothing was sent. Add --live and a token to post.")
        return res
    if not base_url.startswith("https://"):
        raise Refused("--image-base-url must be a public https address where the JPEG images are already online")
    tok = load_token(token_file, env)
    log(f"token from {tok['source']} ({masked(tok['access_token'])}), account id {tok['ig_user_id']}")
    for i, p in enumerate(todo):
        if room <= 0:
            res["stopped"] = f"our cap of {cap} post(s) per 24 h is reached"
            break
        lim = api(tok, "GET", f"{tok['ig_user_id']}/content_publishing_limit", fields="quota_usage,config")
        row = (lim.get("data") or [{}])[0]
        used = int(row.get("quota_usage") or 0)
        total = int((row.get("config") or {}).get("quota_total") or API_CAP_ASSUMED)
        if used >= min(total, API_CAP_ASSUMED) - 2:
            res["stopped"] = f"Instagram's publishing limit is nearly used ({used} of {total} in 24 h)"
            break
        if i:
            sleep(GAP_S)
        c = api(tok, "POST", f"{tok['ig_user_id']}/media", image_url=image_url(base_url, p), caption=p["caption"])
        cid = c.get("id")
        if not cid:
            raise Refused(f"no container id for day {p['day']}: {c}")
        for _ in range(10):                                  # images are usually ready at once; wait up to ~30 s
            st = api(tok, "GET", cid, fields="status_code")
            if st.get("status_code") in ("FINISHED", None):
                break
            if st.get("status_code") in ("ERROR", "EXPIRED"):
                raise Refused(f"Instagram could not use the image for day {p['day']} (status {st.get('status_code')}): is the URL public JPEG?")
            sleep(3)
        pub = api(tok, "POST", f"{tok['ig_user_id']}/media_publish", creation_id=cid)
        led["posts"].append({"account": account, "day": p["day"], "date": p["date"], "container": cid, "media_id": pub.get("id"), "t": now})
        save_ledger(led, ledger_path)
        res["posted"].append({"day": p["day"], "media_id": pub.get("id")})
        room -= 1
        log(f"posted {account} day {p['day']} -> media {pub.get('id')}")
    return res


def refresh_token(token_file: str | None = None, env=None) -> str:
    tok = load_token(token_file, env)
    if tok.get("api", "instagram") != "instagram":
        raise Refused("refresh here is for Instagram Login tokens; Facebook Login tokens are refreshed in the Meta developer tools")
    r = _call("GET", HOSTS["instagram"] + "/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": tok["access_token"]})
    if not r.get("access_token"):
        raise Refused(f"refresh failed: {str(r.get('error', r))[:200]}")
    if tok["source"] == "env":
        return "refreshed; update IG_ACCESS_TOKEN yourself (the new token is not printed)"
    with open(tok["source"], encoding="utf-8") as fh:
        data = json.load(fh)
    data["access_token"] = r["access_token"]
    data["refreshed"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(tok["source"], "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    return f"refreshed, valid about {int(r.get('expires_in', 0)) // 86400} more days (saved in {tok['source']})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.ig_post", description="Post today's planned image (dry run by default).")
    ap.add_argument("--plan", help="a plan file from content_plan.py (money_machines/plans/<account>_30d.json)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="which plan day to post (YYYY-MM-DD, default today)")
    ap.add_argument("--image-base-url", default="", help="public https folder where dayNN.jpg are online (needed with --live)")
    ap.add_argument("--max-per-day", type=int, default=1, help=f"our own cap per rolling 24 h (default 1, at most {HARD_CAP_24H})")
    ap.add_argument("--token-file", help=f"private token file outside the repo (default {DEFAULT_TOKEN_FILE})")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--live", action="store_true", help="really talk to Instagram (needs the token)")
    ap.add_argument("--check-token", action="store_true")
    ap.add_argument("--refresh-token", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.check_token or a.refresh_token:
            if not a.live:
                print("[dry run] add --live to contact Instagram (nothing was sent)")
                return 0
            if a.refresh_token:
                print(refresh_token(a.token_file))
            else:
                tok = load_token(a.token_file)
                me = api(tok, "GET", "me", fields="user_id,username,account_type" if tok.get("api") == "instagram" else "id,username")
                print(f"token OK for @{me.get('username')} ({me.get('account_type', 'professional')})")
            return 0
        if not a.plan:
            ap.error("--plan is needed")
        with open(a.plan, encoding="utf-8") as fh:
            plan = json.load(fh)
        r = run(plan, a.date, live=a.live, base_url=a.image_base_url, max_per_day=a.max_per_day, token_file=a.token_file, ledger_path=a.ledger)
        if r["stopped"]:
            print("stopped: " + r["stopped"])
        return 0
    except Refused as e:
        print(str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
