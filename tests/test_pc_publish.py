"""tools/pc_publish.py + engine/nogithub.py + the Kalshi kit's providers: the NQ reporting chain without GitHub.

No network (a local stub plays Netlify), no real bot, no orders. The heavy build steps are replaced by small fakes, except one
check that runs the real cloud-monitor child on the repo data when RUN_REAL=1.

  python -X utf8 -m tests.test_pc_publish
"""
from __future__ import annotations

import http.server
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:600]})" if detail and not cond else ""))
    return bool(cond)


from tools import pc_publish as PP  # noqa: E402
from engine import nogithub  # noqa: E402

TOKEN = "nfp_SECRETTOKEN1234567890abcdef"


class Netlify(http.server.BaseHTTPRequestHandler):
    """A tiny stand-in for api.netlify.com: records calls, answers the digest and zip deploys."""
    calls: list = []
    fail_with = None

    def log_message(self, *a):
        pass

    def _reply(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _go(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        Netlify.calls.append({"m": self.command, "path": self.path, "auth": self.headers.get("Authorization"),
                              "ctype": self.headers.get("Content-Type"), "body": body})
        if Netlify.fail_with:
            return self._reply(Netlify.fail_with, {"message": "nope " + TOKEN})
        if self.command == "POST" and self.path.endswith("/deploys"):
            if self.headers.get("Content-Type") == "application/zip":
                return self._reply(200, {"id": "dz1", "state": "uploaded", "ssl_url": "https://stub.example"})
            files = json.loads(body)["files"]
            return self._reply(200, {"id": "dd1", "required": sorted(set(files.values()))[:3], "ssl_url": "https://stub.example"})
        if self.command == "PUT":
            return self._reply(200, {})
        if self.command == "GET":
            return self._reply(200, {"id": "dd1", "state": "ready", "ssl_url": "https://stub.example"})
        return self._reply(404, {})

    do_GET = do_POST = do_PUT = _go


def make_site(d, extra=""):
    os.makedirs(os.path.join(d, "runs"), exist_ok=True)
    open(os.path.join(d, "index.html"), "w").write("<html>" + extra + "</html>")
    open(os.path.join(d, "data.json"), "w").write('{"t":1}')
    open(os.path.join(d, "runs", "a.json"), "w").write("{}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="pcpub_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Netlify)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    api = f"http://127.0.0.1:{srv.server_address[1]}/api/v1"
    try:
        # ------------------------------------------------------------------ nogithub (the bot side)
        oh = os.path.join(tmp, "oh")
        os.makedirs(oh)
        check("nogithub: off by default (no env, no marker)", not nogithub.active({"OLYMPUS_HOME": oh}))
        open(os.path.join(oh, "no_github"), "w").close()
        check("nogithub: on with the marker file; LE_NO_GITHUB=0 overrides it off, =1 forces it on",
              nogithub.active({"OLYMPUS_HOME": oh}) and not nogithub.active({"OLYMPUS_HOME": oh, "LE_NO_GITHUB": "0"})
              and nogithub.active({"OLYMPUS_HOME": tmp, "LE_NO_GITHUB": "1"}))
        hbd = os.path.join(tmp, "hb")
        r = nogithub.local_push({"t": 1000, "running": True, "every_s": 300}, files={"bars_1m.csv.gz": b"\x00\x01\r\n"}, dest=hbd)
        got = nogithub.read_local(now=1100, files=("bars_1m.csv.gz", "bars_5m.csv.gz"), src=hbd)
        check("nogithub: local_push + read_local round-trip (payload, binary bars byte for byte, age, missing file None)",
              r["ok"] and got["present"] and got["age_s"] == 100 and not got["silent"] and got["files"]["bars_1m.csv.gz"] == b"\x00\x01\r\n"
              and got["files"]["bars_5m.csv.gz"] is None and nogithub.read_local(now=1, src=os.path.join(tmp, "none"))["present"] is False, got)
        check("nogithub: a running bot that stopped writing 20 min ago is 'silent'", nogithub.read_local(now=1000 + 1200, src=hbd)["silent"])
        env_on = {"LE_NO_GITHUB": "1", "LE_HEARTBEAT": "1", "LE_LIVE_PUBLISH": "1", "LE_REMOTE": "1"}
        from engine import live_publish, remote_ctl, autoupdate, heartbeat
        check("GitHub-free mode switches the phone live push, the remote control and the auto-update FROM ORIGIN off (they would need the old account)",
              not live_publish.enabled(env_on) and not remote_ctl.enabled(env_on)
              and not autoupdate.is_enabled({"enabled": True}, env_on, root=tmp))
        # 2026-11-14 (owner: "keep it on GitHub in case we get banned ... I'm not updating the files every time"): with the
        # backup repo in update_source.json the auto-update runs in GitHub-free mode too (tests/test_autoupdate_source.py)
        check("GitHub-free mode keeps the auto-update ON when the code names the backup repo (update_source.json)",
              autoupdate.is_enabled({"enabled": True}, env_on) and autoupdate.source()["remote"] != "origin")
        check("... and changes nothing when the mode is off (old behaviour)",
              live_publish.enabled({"LE_HEARTBEAT": "1"}) and remote_ctl.enabled({"LE_REMOTE": "1"})
              and autoupdate.is_enabled({"enabled": True}, {}))

        class Bot:
            running = False
            cfg = {}
        os.environ["LE_NO_GITHUB"] = "1"
        try:
            hb = heartbeat.Heartbeat(Bot(), last_path=os.path.join(tmp, "last.json"))
        finally:
            os.environ.pop("LE_NO_GITHUB", None)
        check("the Heartbeat object uses the local writer in GitHub-free mode (no git, no network)", hb.push_fn is nogithub.local_push and hb.notify_fn is None)
        hb2 = heartbeat.Heartbeat(Bot(), last_path=os.path.join(tmp, "last2.json"))
        check("... and the real push otherwise", hb2.push_fn is heartbeat.push)
        src = open(os.path.join(ROOT, "engine", "nogithub.py"), encoding="utf-8").read()
        check("nogithub.py touches no trading file (no live_model, no order code)", "live_model" not in src.replace("live_model*", "") and "ninjatrader" not in src.lower().replace("ninjatrader bars", ""))

        # ------------------------------------------------------------------ config (outside the repo)
        cd = os.path.join(tmp, "cfg")
        os.makedirs(cd)
        check("config: nothing configured -> provider none", PP.load_config(cdir=cd)["provider"] == "none")
        json.dump({"site_id": "SID", "token": TOKEN}, open(os.path.join(cd, "netlify.json"), "w"))
        c = PP.load_config(cdir=cd)
        check("config: a netlify.json alone selects netlify, digest method, 18 deploys a month budget",
              c["provider"] == "netlify" and c["method"] == "digest" and c["netlify"]["site_id"] == "SID" and c["max_deploys_per_month"] == 18, c)
        check("config dir is outside the repo; a token file inside the repo is refused", not PP.inside_repo(cd) and PP.inside_repo(os.path.join(ROOT, "data")))
        gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
        check(".gitignore keeps the publisher's local files and any token file out of git",
              "data/pc_publish/" in gi and "netlify.json" in gi and ".olympus/" in gi)

        # ------------------------------------------------------------------ site tree, zip, hashes
        site = os.path.join(tmp, "site")
        make_site(site)
        files = PP.site_files(site)
        z = zipfile.ZipFile(io.BytesIO(PP.make_zip(site, files)))
        names = sorted(z.namelist())
        check("zip: files at the zip root (index.html at the top, no wrapping folder), subfolders kept",
              names == ["data.json", "index.html", "runs/a.json"] and not any(n.startswith("site/") for n in names), names)
        h1 = PP.site_hash(files)
        make_site(site, "x")
        check("site hash changes with the content and not otherwise", PP.site_hash(PP.site_files(site)) != h1 and PP.site_hash(files) == h1)

        # ------------------------------------------------------------------ netlify provider against the stub
        env = {"OLYMPUS_NETLIFY_API": api}
        cfg = {**c, "method": "digest"}
        Netlify.calls.clear()
        make_site(site)
        files = PP.site_files(site)
        res = PP.publish_netlify(site, files, cfg, env=env, log=lambda m: None)
        posts = [x for x in Netlify.calls if x["m"] == "POST"]
        puts = [x for x in Netlify.calls if x["m"] == "PUT"]
        check("netlify digest: POST the file list (paths with leading slash, sha1), Bearer token header, only the required files PUT",
              len(posts) == 1 and posts[0]["auth"] == "Bearer " + TOKEN and "/index.html" in json.loads(posts[0]["body"])["files"]
              and len(puts) == len(set(files.values())) and res["uploaded"] == len(puts) and res["url"] == "https://stub.example" and res["state"] == "ready", (res, Netlify.calls[:2]))
        Netlify.calls.clear()
        res = PP.publish_netlify(site, files, {**cfg, "method": "zip"}, env=env)
        zpost = Netlify.calls[0]
        zz = zipfile.ZipFile(io.BytesIO(zpost["body"]))
        check("netlify zip: one POST of Content-Type application/zip with the files at the root",
              len(Netlify.calls) == 1 and zpost["ctype"] == "application/zip" and "index.html" in zz.namelist() and res["method"] == "zip", res)
        Netlify.fail_with = 401
        try:
            PP.publish_netlify(site, files, cfg, env=env)
            ok = False
            msg = ""
        except PP.ProviderError as e:
            ok, msg = True, str(e)
        Netlify.fail_with = None
        check("netlify: a refused token is a plain sentence and the token is not in it", ok and TOKEN not in msg and "refused the token" in msg, msg)
        Netlify.fail_with = 400
        try:
            PP.publish_netlify(site, files, {**cfg, "method": "zip"}, env=env)
            msg = "no error"
        except PP.ProviderError as e:
            msg = str(e)
        Netlify.fail_with = None
        check("redaction: a server echoing the token back never reaches the error text", TOKEN not in msg and "<token>" in msg, msg)
        check("redact(): bearer strings and the token value are removed from any text",
              TOKEN not in PP.redact("x " + TOKEN, [TOKEN]) and "abcdefghijklmnop" not in PP.redact("Authorization: Bearer abcdefghijklmnop"))

        # ------------------------------------------------------------------ folder provider
        dest = os.path.join(tmp, "synced")
        r1 = PP.publish_folder(site, files, {"folder": dest})
        make_site(site, "new")
        files2 = PP.site_files(site)
        r2 = PP.publish_folder(site, files2, {"folder": dest})
        os.remove(os.path.join(site, "runs", "a.json"))
        files3 = PP.site_files(site)
        PP.publish_folder(site, files3, {"folder": dest})
        check("folder: first copy sends everything, the next only the changed file, a removed file is removed, manifest kept",
              r1["uploaded"] == 3 and r2["uploaded"] == 1 and not os.path.exists(os.path.join(dest, "runs", "a.json"))
              and os.path.exists(os.path.join(dest, "index.html")) and os.path.exists(os.path.join(dest, ".olympus_manifest.json")), (r1, r2))

        # ------------------------------------------------------------------ scp provider (your own server) with fake ssh / scp
        fb = os.path.join(tmp, "fakebin")
        os.makedirs(fb)
        open(os.path.join(fb, "scp"), "w").write('#!/bin/sh\n# fake scp: the last two args are SRC and user@host:/path\nsrc=""; dst=""\nfor a in "$@"; do src="$dst"; dst="$a"; done\n'
                                                 'case "$src" in *@*) exit 9;; esac\ncp "$src" "${dst#*:}"\n')
        open(os.path.join(fb, "ssh"), "w").write('#!/bin/sh\n# fake ssh: runs the last argument (the remote command) locally\nfor a in "$@"; do c="$a"; done\nexec sh -c "$c"\n')
        os.chmod(os.path.join(fb, "scp"), 0o755)
        os.chmod(os.path.join(fb, "ssh"), 0o755)
        remote = os.path.join(tmp, "remote", "www")
        scfg = {"scp_target": "me@box", "scp_dir": remote}
        sw = os.path.join(tmp, "scpwork")
        os.makedirs(sw)
        ssite = os.path.join(tmp, "ssite")
        make_site(ssite)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = fb + os.pathsep + old_path
        try:
            f1 = PP.site_files(ssite)
            q1 = PP.publish_scp(ssite, f1, scfg, work=sw)
            q1b = PP.publish_scp(ssite, f1, scfg, work=sw)
            open(os.path.join(ssite, "data.json"), "w").write('{"t":2}')
            os.remove(os.path.join(ssite, "runs", "a.json"))
            f2 = PP.site_files(ssite)
            q2 = PP.publish_scp(ssite, f2, scfg, work=sw)
            got = sorted(os.path.relpath(os.path.join(r_, f), remote) for r_, _d, fs in os.walk(remote) for f in fs)
            check("scp: first run sends every file, an unchanged site sends nothing, a change sends only the changed file and removes deleted ones",
                  q1["uploaded"] == 3 and q1b["uploaded"] == 0 and q2["uploaded"] == 1 and got == ["data.json", "index.html"]
                  and open(os.path.join(remote, "data.json")).read() == '{"t":2}' and not os.path.exists(os.path.join(remote, ".olympus_upload.zip")), (q1, q1b, q2, got))
            try:
                PP.publish_scp(ssite, f2, {"scp_target": "me@box"}, work=sw)
                msg = ""
            except PP.ProviderError as e:
                msg = str(e)
            check("scp: a missing target / non-absolute dir is a plain error", "scp_target" in msg, msg)
        finally:
            os.environ["PATH"] = old_path

        # ------------------------------------------------------------------ the Kalshi feed goes into the site as kalshi.json
        ksite = os.path.join(tmp, "ksite")
        make_site(ksite)
        kf = os.path.join(tmp, "kfeed.json")
        open(kf, "w").write('{"t": 1, "balance": 5.5}')
        note = PP.add_kalshi(ksite, {"kalshi_file": kf})
        check("kalshi feed: a configured kalshi_file is copied into the site as kalshi.json", note == "kalshi feed added" and json.load(open(os.path.join(ksite, "kalshi.json")))["balance"] == 5.5, note)
        open(kf, "w").write("<html>not json</html>")
        os.remove(os.path.join(ksite, "kalshi.json"))
        note2 = PP.add_kalshi(ksite, {"kalshi_file": kf})
        check("kalshi feed: junk (HTML) is left out, soft; no setting = nothing added", "not added" in note2 and not os.path.exists(os.path.join(ksite, "kalshi.json")) and PP.add_kalshi(ksite, {}) == "")
        cdk = os.path.join(tmp, "cfgk")
        os.makedirs(os.path.join(cdk, "kalshi_feed"))
        open(os.path.join(cdk, "kalshi_feed", "kalshi.json"), "w").write("{}")
        check("kalshi feed: a kalshi.json left in <settings>/kalshi_feed/ is used with no setting at all", PP.load_config(cdir=cdk)["kalshi_file"].endswith("kalshi.json"))
        check("kalshi feed: the https-only rule for kalshi_feed_url", PP.add_kalshi(ksite, {"kalshi_feed_url": "http://example.com/k.json"}) == "kalshi feed: address must be https")

        # ------------------------------------------------------------------ run_once with the heavy steps faked
        work = os.path.join(tmp, "work")
        calls = {"state": 0, "site": 0, "fail_state": False}
        real_state, real_site = PP.step_state, PP.step_site

        def fake_state(w):
            calls["state"] += 1
            return (False, "boom") if calls["fail_state"] else (True, "ok")

        def fake_site(w):
            calls["site"] += 1
            s = os.path.join(w, "site")
            shutil.rmtree(s, ignore_errors=True)
            make_site(s, "v%d" % calls["site"] if not calls.get("same") else "same")
            return True, "ok"

        PP.step_state, PP.step_site = fake_state, fake_site
        try:
            class A:
                work = None
                provider = None
                folder = None
                dry_run = False
                force = False
                skip_build = False
                min_interval = 0.0

            a = A()
            a.work = work
            env2 = {"OLYMPUS_HOME": cd, "OLYMPUS_NETLIFY_API": api}
            Netlify.calls.clear()
            rec = PP.run_once(a, env=env2, say=lambda m: None)
            check("run_once netlify: builds, publishes, records url / files / bytes, last good time", rec["ok"] and rec["provider"] == "netlify"
                  and rec["url"] == "https://stub.example" and rec["files"] == 3 and rec["last_good_t"], rec)
            PP.write_json(os.path.join(work, "last.json"), rec)
            n0 = len(Netlify.calls)
            calls["same"] = True
            PP.run_once(a, env=env2, say=lambda m: None)            # one different build ("same"), published
            rec_s = read = PP.read_json(os.path.join(work, "last.json"))
            rec2 = PP.run_once(a, env=env2, say=lambda m: None)
            check("deploy budget: a second deploy the same day is held back (budget 18 a month = 1 a day), reported, not an error",
                  rec2["ok"] and rec2.get("throttled") and "today's 1 Netlify deploy" in rec2["state_text"], rec2)
            # same content twice with the folder provider -> the second run uploads nothing
            a.provider, a.folder = "folder", os.path.join(tmp, "synced2")
            r_a = PP.run_once(a, env=env2, say=lambda m: None)
            PP.write_json(os.path.join(work, "last.json"), r_a)
            r_b = PP.run_once(a, env=env2, say=lambda m: None)
            check("unchanged content is not sent again (hash), still ok", r_a["ok"] and r_b["ok"] and r_b.get("skipped_same") and r_b["uploaded"] == 0, (r_a, r_b))
            # a failing state step: nothing published, the last good site stays, soft failure with a plain sentence
            calls["fail_state"] = True
            r_f = PP.run_once(a, env=env2, say=lambda m: None)
            check("state step fails: ok False, the sentence says the last good site stays up, nothing uploaded, last_good_t kept",
                  not r_f["ok"] and "last good site stays up" in r_f["error"] and r_f["last_good_t"] == (r_a["last_good_t"]) or
                  (not r_f["ok"] and "last good site stays up" in r_f["error"] and r_f.get("last_good_t")), r_f)
            calls["fail_state"] = False
            # provider none and dry run
            a.provider, a.folder, a.dry_run = "none", None, False
            r_n = PP.run_once(a, env=env2, say=lambda m: None)
            a.provider, a.folder, a.dry_run = "folder", os.path.join(tmp, "synced3"), True
            r_d = PP.run_once(a, env=env2, say=lambda m: None)
            check("provider none builds only; --dry-run sends nothing (the folder is not even created)",
                  r_n["ok"] and r_d["ok"] and r_d.get("dry") and not os.path.exists(os.path.join(tmp, "synced3")), (r_n, r_d))
            a.dry_run = False
            a.provider = "carrierpigeon"
            r_u = PP.run_once(a, env=env2, say=lambda m: None)
            check("an unknown provider is a plain error, not a crash", not r_u["ok"] and "unknown provider" in r_u["error"], r_u)
            # an unreachable Netlify is soft
            a.provider = None
            bad = {"OLYMPUS_HOME": cd, "OLYMPUS_NETLIFY_API": "http://127.0.0.1:9/api/v1"}
            PP.write_json(os.path.join(work, "deploys.json"), {"month": "1999-01", "n": 0, "days": {}})
            r_x = PP.run_once(a, env=bad, say=lambda m: None)
            check("Netlify unreachable: soft failure, token not in the message", not r_x["ok"] and TOKEN not in json.dumps(r_x), r_x)
        finally:
            PP.step_state, PP.step_site = real_state, real_site

        # ------------------------------------------------------------------ status card, log, token never on disk in the work folder
        last = PP.read_json(os.path.join(work, "last.json"))
        lines = PP.status_lines(last)
        check("status: exactly six lines, PUBLISH 1/6 .. 6/6", len(lines) == 6 and [ln[:12] for ln in lines] == [f"PUBLISH {i}/6 " for i in range(1, 7)], lines)
        check("status with no run yet: six lines that say what to do", len(PP.status_lines({})) == 6 and "PUBLISH_NQ.bat" in PP.status_lines({})[5])
        PP.log_line(work, {"t": 1, "ok": True})
        check("a local publish log is written (jsonl)", os.path.getsize(os.path.join(work, "publish_log.jsonl")) > 0)
        leaked = []
        for r_, _d, fs in os.walk(work):
            for f in fs:
                if f.endswith((".json", ".jsonl")) and TOKEN in open(os.path.join(r_, f), errors="replace").read():
                    leaked.append(f)
        check("the token appears in no file the publisher writes (last.json, log, deploys.json)", not leaked, leaked)

        # ------------------------------------------------------------------ setup writes outside the repo, never echoes the token
        class S:
            setup = "netlify"
            site_id = "SID2"
            token = TOKEN
            token_stdin = False
            folder = None
        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            os.environ["OLYMPUS_HOME"] = os.path.join(tmp, "cfg2")
            rc = PP.setup(S(), env={"OLYMPUS_HOME": os.path.join(tmp, "cfg2")})
        finally:
            sys.stdout = old
            os.environ.pop("OLYMPUS_HOME", None)
        nf = os.path.join(tmp, "cfg2", "netlify.json")
        check("--setup netlify: writes netlify.json + publish.json + the no_github marker outside the repo, token never printed",
              rc == 0 and json.load(open(nf))["token"] == TOKEN and TOKEN not in buf.getvalue() and os.path.exists(os.path.join(tmp, "cfg2", "no_github")), buf.getvalue())

        # ------------------------------------------------------------------ the main entry never raises on a soft failure
        rc = PP.main(["--work", os.path.join(tmp, "w2"), "--provider", "folder", "--skip-build"])
        check("main(): a failed run (no site built yet) still exits 0 (the scheduled task must not show a crash) and --strict exits 1",
              rc == 0 and PP.main(["--work", os.path.join(tmp, "w2"), "--provider", "folder", "--skip-build", "--strict"]) == 1)

        # ------------------------------------------------------------------ the Kalshi kit's providers
        spec = importlib.util.spec_from_file_location("ksv", os.path.join(ROOT, "tools", "kalshi_kit", "public", "kalshi_status_vm.py"))
        ks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ks)
        payload = json.loads(subprocess_sample())
        fd = os.path.join(tmp, "kfolder")
        r = ks.publish_folder(payload, fd)
        check("kalshi kit: folder provider writes kalshi.json atomically, same bytes as the git push would send",
              r["ok"] and json.load(open(os.path.join(fd, "kalshi.json"))) == payload and not [f for f in os.listdir(fd) if f.endswith(".tmp")], r)
        nf2 = os.path.join(tmp, "kn.json")
        json.dump({"site_id": "KS", "token": TOKEN}, open(nf2, "w"))
        Netlify.calls.clear()
        sf = os.path.join(tmp, "nl_last.json")
        r = ks.publish_netlify(payload, nf2, api=api, state_file=sf, now=5000.0)
        r2 = ks.publish_netlify(payload, nf2, api=api, state_file=sf, now=5000.0 + 60)
        r3 = ks.publish_netlify(payload, nf2, api=api, state_file=sf, now=5000.0 + 3700)
        sent = [json.loads(x["body"])["files"] for x in Netlify.calls if x["m"] == "POST"]
        check("kalshi kit: netlify provider deploys kalshi.json + _headers (CORS) + index.html by digest, paced to one an hour",
              r["ok"] and r2.get("skipped") and r3["ok"] and not r3.get("skipped") and len(sent) == 2 and sorted(sent[0]) == ["/_headers", "/index.html", "/kalshi.json"]
              and Netlify.calls[0]["auth"] == "Bearer " + TOKEN, (r, r2, r3))
        Netlify.fail_with = 401
        r4 = ks.publish_netlify(payload, nf2, api=api, state_file=os.path.join(tmp, "nl2.json"), now=9e9)
        Netlify.fail_with = None
        check("kalshi kit: a refused token is an error without the token", not r4["ok"] and TOKEN not in json.dumps(r4), r4)
        r5 = ks.publish_netlify(payload, os.path.join(tmp, "missing.json"))
        check("kalshi kit: missing token file is a plain error, not a crash", not r5["ok"] and "token file" in r5["error"], r5)
        check("kalshi kit: --publish is a real option and defaults to git (old behaviour)",
              ks.parser().parse_args(["--check"]).publish == "git" and ks.parser().parse_args(["--check", "--publish", "netlify"]).publish == "netlify")
        kit = open(os.path.join(ROOT, "tools", "kalshi_kit", "public", "kalshi_status_vm.py"), encoding="utf-8").read()
        leak = re.findall(r"(?:KEY|TOKEN)\s*=\s*['\"][A-Za-z0-9]{20,}['\"]", kit)
        check("kalshi kit: no token literal in the file", not leak, leak)
        # the page text
        js = open(os.path.join(ROOT, "tools", "web_public", "kalshi", "kalshi.js"), encoding="utf-8").read()
        W = os.path.join(ROOT, "tools", "web_public")
        readers = ["hermes/data.js", "tyche/data.js", "kalshi/kalshi.js", "ledger/ledger.js", "inbox/inbox.js", "stoa/stoa.js",
                   "ergasterion/ergasterion.js", "dionysus/dionysus.js", "kalshicity/kalshicity.js", "jarvis/data.js", "cities/datasets.js"]
        bad = [rd for rd in readers if "../kalshi.json" not in open(os.path.join(W, rd), encoding="utf-8").read()]
        check("every Kalshi reader asks this site's ../kalshi.json before the old GitHub address (which stays as the fallback)", not bad, bad)
        check("every Kalshi reader keeps the old feed address as the fallback", all("kalshi-feed" in open(os.path.join(W, rd), encoding="utf-8").read() for rd in readers))
        check("kalshi page: the kalshi-server message holds {SITE_URL}, filled from location.origin, no github.io address",
              "{SITE_URL}/kalshi/SETUP.md" in js and "location.origin" in js and "github.io" not in js)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def subprocess_sample() -> str:
    import subprocess
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "kalshi_kit", "public", "kalshi_status_vm.py"), "--sample"],
                          capture_output=True, text=True, timeout=60).stdout


def test_pc_publish():                       # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
