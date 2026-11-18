"""tools/pc_publish.py provider "cloudflare" (Cloudflare Pages, no badge; docs/HOSTING.md). OFF by default.

No network: a fake `npx` (OLYMPUS_NPX) plays Cloudflare's wrangler and records what it was asked. The key only ever comes from
the CLOUDFLARE_API_TOKEN environment variable and must never reach the command line, a file, a log or last.json.

  python -X utf8 -m tests.test_pc_publish_cloudflare
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:600]})" if detail and not cond else ""))
    return bool(cond)


from tools import pc_publish as PP  # noqa: E402

TOKEN = "cfut_SECRETCLOUDFLAREKEY1234567890abcd"
ACCT = "0123456789abcdef0123456789abcdef"

FAKE = r'''#!{py}
import json, os, sys
log = os.environ["FAKE_NPX_LOG"]
mode = os.environ.get("FAKE_NPX_MODE", "ok")
rows = [json.loads(l) for l in open(log)] if os.path.exists(log) else []
stage = sys.argv[sys.argv.index("deploy") + 1] if "deploy" in sys.argv else None
rec = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "token_env": os.environ.get("CLOUDFLARE_API_TOKEN"),
       "acct_env": os.environ.get("CLOUDFLARE_ACCOUNT_ID"), "ci": os.environ.get("CI"),
       "stage": sorted(os.path.relpath(os.path.join(r, f), stage).replace(os.sep, "/") for r, _d, fs in os.walk(stage) for f in fs) if stage else None}}
open(log, "a").write(json.dumps(rec) + "\n")
deploys = [r for r in rows if "deploy" in r["argv"]]
if mode == "auth":
    print("Authentication error [code: 10000] for key " + os.environ.get("CLOUDFLARE_API_TOKEN", ""), file=sys.stderr); sys.exit(1)
if mode == "noproj" and "deploy" in sys.argv and not deploys:
    print("Project not found. The specified project name does not match any of your existing projects. [code: 8000007]", file=sys.stderr); sys.exit(1)
if "create" in sys.argv:
    print("Successfully created the 'olympus-dash' project."); sys.exit(0)
print("Uploaded 3 files (2 already uploaded)\nDeployment complete! Take a peek over at https://a1b2c3d4.olympus-dash.pages.dev")
'''


def make_site(d, files):
    for rel, txt in files.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(txt)


def calls(log):
    return [json.loads(l) for l in open(log)] if os.path.exists(log) else []


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="cfpub_")
    try:
        npx = os.path.join(tmp, "npx")
        with open(npx, "w") as fh:
            fh.write(FAKE.format(py=sys.executable))
        os.chmod(npx, os.stat(npx).st_mode | stat.S_IEXEC)
        log = os.path.join(tmp, "npx_log.jsonl")
        cd = os.path.join(tmp, "cfg")
        os.makedirs(cd)

        # 1. off by default
        cfg0 = PP.load_config({"OLYMPUS_HOME": cd})
        with open(os.path.join(cd, "netlify.json"), "w") as fh:
            json.dump({"site_id": "abc12345", "token": "x" * 20}, fh)
        cfg1 = PP.load_config({"OLYMPUS_HOME": cd, "CLOUDFLARE_API_TOKEN": TOKEN})
        os.remove(os.path.join(cd, "netlify.json"))
        check("1. OFF by default: no settings = provider none; a Netlify file (even with the Cloudflare key set) stays Netlify",
              cfg0["provider"] == "none" and cfg1["provider"] == "netlify", (cfg0["provider"], cfg1["provider"]))

        # 2. setup writes publish.json, never the key
        os.environ["OLYMPUS_HOME"] = cd
        try:
            rc_bad = PP.main(["--setup", "cloudflare", "--cf-project", "Bad Name!"])
            rc_bad2 = PP.main(["--setup", "cloudflare", "--cf-project", "olympus-dash", "--cf-account", "nope"])
            rc_ok = PP.main(["--setup", "cloudflare", "--cf-project", "olympus-dash", "--cf-account", ACCT])
        finally:
            os.environ.pop("OLYMPUS_HOME", None)
        pub = json.load(open(os.path.join(cd, "publish.json")))
        raw = open(os.path.join(cd, "publish.json")).read()
        check("2. --setup cloudflare: bad name / bad account id refused (exit 2); good one saved: provider, project, account, NO key",
              rc_bad == 2 and rc_bad2 == 2 and rc_ok == 0 and pub.get("provider") == "cloudflare" and pub.get("cf_project") == "olympus-dash"
              and pub.get("cf_account_id") == ACCT and "token" not in raw.lower() and TOKEN not in raw, (rc_bad, rc_bad2, rc_ok, pub))
        cfg = PP.load_config({"OLYMPUS_HOME": cd})
        check("2b. load_config reads the Cloudflare settings and its own budget (450 a month = 15 a day)",
              cfg["provider"] == "cloudflare" and cfg["cf_project"] == "olympus-dash" and cfg["cf_max_deploys_per_month"] == 450, cfg)

        site = os.path.join(tmp, "site")
        make_site(site, {"index.html": "<h1>hi</h1>", "data.json": "{}", "a/b.js": "1", "old.txt": "x"})
        files = PP.site_files(site)
        work = os.path.join(tmp, "work")
        base_env = {"OLYMPUS_NPX": npx, "FAKE_NPX_LOG": log, "PATH": os.environ.get("PATH", "")}

        # 3. missing key / Node / project are plain errors
        errs = []
        for env, c in ((dict(base_env), cfg), ({**base_env, "CLOUDFLARE_API_TOKEN": TOKEN, "OLYMPUS_NPX": ""}, cfg),
                       ({**base_env, "CLOUDFLARE_API_TOKEN": TOKEN}, {**cfg, "cf_project": ""})):
            if not env.get("OLYMPUS_NPX"):
                env.pop("OLYMPUS_NPX")
                env["PATH"] = tmp + "/nothing"
            try:
                PP.publish_cloudflare(site, files, c, env=env, log=lambda m: None, work=work)
                errs.append("no error")
            except PP.ProviderError as e:
                errs.append(str(e))
        check("3. no key -> names CLOUDFLARE_API_TOKEN; no Node -> the free winget line; no project -> the setup line; nothing ran",
              "CLOUDFLARE_API_TOKEN" in errs[0] and "winget install OpenJS.NodeJS.LTS" in errs[1] and "--cf-project" in errs[2]
              and not calls(log), errs)

        # 4. a good deploy
        env = {**base_env, "CLOUDFLARE_API_TOKEN": TOKEN}
        res = PP.publish_cloudflare(site, files, cfg, env=env, log=lambda m: None, work=work)
        c = calls(log)
        a = c[0]["argv"] if c else []
        check("4. one wrangler call: the pinned version, pages deploy <stage> --project-name olympus-dash --branch main (PRODUCTION)",
              len(c) == 1 and a[:2] == ["--yes", PP.CF_WRANGLER] and a[2:4] == ["pages", "deploy"] and "--project-name" in a
              and a[a.index("--project-name") + 1] == "olympus-dash" and a[a.index("--branch") + 1] == "main" and "@" in PP.CF_WRANGLER
              and PP.CF_WRANGLER.split("@")[1].count(".") == 2, c)
        check("4b. the key travels only in the child's environment (never on the command line); account id + CI set",
              c and c[0]["token_env"] == TOKEN and TOKEN not in json.dumps(a) and c[0]["acct_env"] == ACCT and c[0]["ci"] == "true", c)
        check("4c. wrangler runs in an empty folder (no stray functions/), the stage holds exactly the send set, no manifest in it",
              c and os.path.realpath(c[0]["cwd"]) == os.path.realpath(os.path.join(work, "cf_run"))
              and c[0]["stage"] == sorted(files), c and c[0]["stage"])
        check("4d. result: the production address <project>.pages.dev, the deploy's own address kept apart, nothing secret",
              res["url"] == "https://olympus-dash.pages.dev" and res["deploy_url"] == "https://a1b2c3d4.olympus-dash.pages.dev"
              and res["uploaded"] == 4 and TOKEN not in json.dumps(res), res)

        # 5. incremental stage: a gone file is removed, unchanged ones not copied again
        os.remove(os.path.join(site, "old.txt"))
        files2 = PP.site_files(site)
        open(log, "w").close()
        res2 = PP.publish_cloudflare(site, files2, cfg, env=env, log=lambda m: None, work=work)
        c = calls(log)
        check("5. next deploy: the stage drops the gone file, copies 0 unchanged files", c and c[0]["stage"] == sorted(files2)
              and res2["uploaded"] == 0, (res2, c))

        # 6. no project yet: created once on the production branch main, then deployed
        open(log, "w").close()
        said = []
        PP.publish_cloudflare(site, files2, cfg, env={**env, "FAKE_NPX_MODE": "noproj"}, log=said.append, work=work)
        c = calls(log)
        kinds = [("create" if "create" in r["argv"] else "deploy") for r in c]
        cr = [r["argv"] for r in c if "create" in r["argv"]]
        check("6. project missing: deploy, create (--production-branch main), deploy again; said so in one line",
              kinds == ["deploy", "create", "deploy"] and cr and cr[0][cr[0].index("--production-branch") + 1] == "main" and said, (kinds, said))

        # 7. a refused key: plain error, the key never in it
        open(log, "w").close()
        try:
            PP.publish_cloudflare(site, files2, cfg, env={**env, "FAKE_NPX_MODE": "auth"}, log=lambda m: None, work=work)
            e7 = "no error"
        except PP.ProviderError as e:
            e7 = str(e)
        check("7. Cloudflare refuses the key -> 'refused the key', the key itself never in the message", "refused the key" in e7 and TOKEN not in e7, e7)

        # 8. run_once end to end: own budget file, Netlify's untouched, the 16th deploy of a day held back
        class A:
            provider = None
            folder = None
            dry_run = False
            force = True
            skip_build = True
            min_interval = 0.0

        aw = A()
        aw.work = os.path.join(tmp, "work8")
        make_site(os.path.join(aw.work, "site"), {"index.html": "<h1>x</h1>", "data.json": "{}"})
        renv = {**env, "OLYMPUS_HOME": cd}
        open(log, "w").close()
        recs = [PP.run_once(aw, env=renv, say=lambda m: None) for _ in range(16)]
        dj = json.load(open(os.path.join(aw.work, "deploys_cloudflare.json")))
        check("8. run_once cloudflare: ok, the production address recorded, 15 deploys a day then held back (not an error)",
              all(r["ok"] for r in recs) and recs[0]["provider"] == "cloudflare" and recs[0]["url"] == "https://olympus-dash.pages.dev"
              and dj["n"] == 15 and recs[-1].get("throttled") and "Cloudflare deploy" in recs[-1]["state_text"]
              and not os.path.exists(os.path.join(aw.work, "deploys.json")), (dj, recs[-1]))
        check("8b. the key is in no record and no file the publisher wrote",
              all(TOKEN not in json.dumps(r) for r in recs) and not any(TOKEN in open(os.path.join(r_, f), errors="ignore").read()
                                                                       for r_, _d, fs in os.walk(aw.work) for f in fs), "")
        src = open(os.path.join(ROOT, "tools", "pc_publish.py"), encoding="utf-8").read()
        check("9. the source reads the key only from the environment (no cloudflare.json, no token argument)",
              not re.search(r"[\"']cloudflare\.json", src) and 'env.get("CLOUDFLARE_API_TOKEN")' in src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_pc_publish_cloudflare():            # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
