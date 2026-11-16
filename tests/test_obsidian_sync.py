"""The Obsidian living sync (tools/obsidian_sync.py): a temp vault, fake PC files, no network, no real vault.

  a. one sync writes Index / Days / Trades / Pictures / Research / Business checklist / STATE under OLYMPUS/Sync only
  b. the day note: Zlarior + ATLAS drawdown left / today / balance, BLITZ hidden, both bots' total, trade links that resolve
  c. no secret, email or account id reaches the vault (scrub), and every [[link]] resolves to a note in the vault
  d. a second sync with the same inputs writes nothing; the owner's ticks and his own day notes survive a rewrite
  e. maybe_run: nothing without a vault, the 10-minute spacing, LE_PR_NO_NET never touches the real config
  f. the pc_report hook and the gitignored config

    python -X utf8 -m tests.test_obsidian_sync
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import obsidian_sync as OS  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def wj(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def wt(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="obs_sync_")
    try:
        vault = os.path.join(tmp, "Vault")
        os.makedirs(vault)
        wt(os.path.join(vault, "My own note.md"), "mine\n")
        now = 1794920400.0                                   # 2026-11-16 ~11:00 ET
        day = OS.today_et(now)
        t1 = now - 3600
        live = {"pc": {"t": now - 300}, "board": {
            "lit": {"room": 1145, "mll": 2000, "today_pnl": 212.5, "balance": 51145, "trades_today": 1, "status": "Watching NY window acct MFFU1234567"},
            "atlas": {"room": 822, "mll": 1000, "today_pnl": -40, "balance": 24822, "trades_today": 0, "status": "Flat"},
            "blitz": {"room": 900, "mll": 1000, "today_pnl": 55, "balance": 24900, "status": "paper"},
            "trades": [{"acct": "atlas", "entry_t": t1 + 600, "side": "short", "qty": 2, "entry": 21000, "stop": 21010, "exit": 20990, "usd": 40, "r": 1.0},
                       {"acct": "blitz", "entry_t": t1, "side": "long", "usd": 10}]}}
        wj(os.path.join(tmp, "live.json"), live)
        charts = os.path.join(tmp, "charts")
        wj(os.path.join(charts, "index.json"), {"strategies": {"lit": [{"tid": "t1", "entry_t": t1, "side": "long", "qty": 3, "entry": 21000.25,
                                                                         "stop": 20990, "target": 21080, "exit": 21071, "usd": 212.5, "r": 2.1, "exit_kind": "target"}],
                                                               "blitz": [{"tid": "b1", "entry_t": t1, "side": "long"}],
                                                               "lit_asia": [{"tid": "s1", "entry_t": t1 + 1800, "side": "long", "usd": 99}],
                                                               "ema_lon_vix": [{"tid": "a1", "entry_t": t1 + 630, "side": "short"}, {"tid": "a2", "entry_t": t1 + 2400, "side": "long"}]}})
        wt(os.path.join(charts, "lit", "t1.png"), "PNG" * 50)
        wt(os.path.join(charts, "ema_lon_vix", "a1.png"), "PNG" * 40)
        wt(os.path.join(charts, "ema_lon_vix", "a2.png"), "PNG" * 40)
        wt(os.path.join(tmp, "latest.md"), f"# Learning night {day}\n\nNo new edge. Contact me at owner@example.com, token: ghp_abcdefghijklmnopqrstuvwxyz123456\n")
        biz = os.path.join(tmp, "biz")
        wj(os.path.join(biz, "business.json"), {"kind": "business", "models": [{"id": "agency", "name": "Website agency", "next": "Fill agency/config.json",
                                                                                "first_dollar": ["Free Stripe account", "60 calls"], "real_usd_month": 0}],
                                                "week": [{"day": 1, "title": "Set up", "tasks": ["Make the accounts"]}]})
        wt(os.path.join(tmp, "STATE.md"), "# STATE\n\n| Zlarior | live |\nAccount 123456789 waiting.\n")
        kw = dict(live_path=os.path.join(tmp, "live.json"), charts=charts, learn=os.path.join(tmp, "latest.md"), biz=biz,
                  state=os.path.join(tmp, "STATE.md"), hide={"blitz"})
        r = OS.sync(vault, now, **kw)
        base = os.path.join(vault, "OLYMPUS", "Sync")
        files = sorted(os.path.relpath(os.path.join(d, f), vault) for d, _, fs in os.walk(vault) for f in fs)
        want = {"OLYMPUS/Sync/OLYMPUS Index.md", f"OLYMPUS/Sync/Days/Bots {day}.md", f"OLYMPUS/Sync/STATE.md", "OLYMPUS/Sync/Business checklist.md",
                f"OLYMPUS/Sync/Research/Learning {day}.md"}
        check("a. one sync writes the index, the day, research, business, STATE", r["ok"] and want <= {f.replace(os.sep, "/") for f in files}, files)
        check("a. only inside OLYMPUS/Sync (the owner's own note untouched)", all(f.startswith(os.path.join("OLYMPUS", "Sync")) or f == "My own note.md" for f in files)
              and open(os.path.join(vault, "My own note.md")).read() == "mine\n", files)
        tn = [f for f in files if os.sep + "Trades" + os.sep in f]
        check("a. a trade note per shown trade (Zlarior with its picture, ATLAS from the board), none for BLITZ", len(tn) == 2 and not any("BLITZ" in f for f in files)
              and os.path.isfile(os.path.join(base, "Pictures", f"{day} Zlarior {OS.et_of(t1).strftime('%H%M')}.png")), tn)
        hm_a = OS.et_of(t1 + 600).strftime('%H%M')
        an = open(os.path.join(base, "Trades", f"{day} ATLAS {hm_a}.md"), encoding="utf-8").read()
        bad_hm = (OS.et_of(t1 + 2400).strftime('%H%M'), OS.et_of(t1 + 1800).strftime('%H%M'))
        check("a. ATLAS's real trade gets the picture drawn for it; a paper shadow (LIT+Asia, an ATLAS member alone) gets no note",
              f"![[{day} ATLAS {hm_a}.png]]" in an and not any(h in f for f in tn for h in bad_hm), (an[-200:], tn))
        dn = open(os.path.join(base, "Days", f"Bots {day}.md"), encoding="utf-8").read()
        check("b. day note: Zlarior $1,145 of $2,000, ATLAS $822 of $1,000, today's $ and balances", "| Zlarior 50K | $1,145 of $2,000 | +$212 | $51,145 |" in dn
              and "| ATLAS 25K | $822 of $1,000 | -$40 | $24,822 |" in dn and "Both bots today: +$172" in dn, dn[:600])
        check("b. BLITZ hidden; data age says fresh", "BLITZ" not in dn and "fresh (5 min old)" in dn, dn[:300])
        allt = ""
        for f in files:
            if f.endswith(".md"):
                allt += open(os.path.join(vault, f), encoding="utf-8").read()
        check("c. no email, key, account id or long number in the vault", not re.search(r"@example\.com|ghp_|MFFU1234567|123456789", allt), re.findall(r"@example\.com|ghp_\w+|MFFU\d+|\d{9}", allt))
        names = {os.path.splitext(os.path.basename(f))[0] for f in files}
        links = set(re.findall(r"\[\[([^\]|#]+)", allt))
        bad = sorted(l for l in links if l not in names and not l.endswith(".png"))
        pics = {l[:-4] for l in links if l.endswith(".png")}
        check("c. every [[link]] resolves (notes and pictures)", not bad and all(os.path.isfile(os.path.join(base, "Pictures", p + ".png")) for p in pics), bad)
        r2 = OS.sync(vault, now, **kw)
        check("d. the same inputs again: nothing rewritten", r2["ok"] and r2["wrote"] == [], r2["wrote"])
        bp = os.path.join(base, "Business checklist.md")
        b = open(bp, encoding="utf-8").read().replace("- [ ] 60 calls", "- [x] 60 calls")
        wt(bp, b)
        dp = os.path.join(base, "Days", f"Bots {day}.md")
        wt(dp, open(dp, encoding="utf-8").read().replace("## How I feel / what I learned\n\n- ", "## How I feel / what I learned\n\n- calm, followed the plan"))
        live["board"]["lit"]["today_pnl"] = 300
        wj(os.path.join(tmp, "live.json"), live)
        OS.sync(vault, now + 900, **kw)
        b2, d2 = open(bp, encoding="utf-8").read(), open(dp, encoding="utf-8").read()
        check("d. the owner's tick survives; his day words survive; the numbers update", "- [x] 60 calls" in b2 and "- [ ] Free Stripe account" in b2
              and "calm, followed the plan" in d2 and "+$300" in d2, d2[-300:])
        # e. maybe_run
        cfgp = os.path.join(tmp, "cfg.json")
        check("e. no vault set: nothing", OS.maybe_run(now, say=lambda *_: None, env={}, cfg_path=cfgp) is None)
        wj(cfgp, {"vault": vault})
        say = []
        res = OS.maybe_run(now + 2000, say=say.append, env={}, cfg_path=cfgp)
        check("e. vault set: one sync, its time saved", res and res["ok"] and json.load(open(cfgp))["last"]["t"] == int(now + 2000), (res, say))
        check("e. 10-minute spacing", OS.maybe_run(now + 2100, say=say.append, env={}, cfg_path=cfgp) is None)
        check("e. LE_PR_NO_NET (the PC report's tests) never touches the real config", OS.maybe_run(now, say=say.append, env={"LE_PR_NO_NET": "1"}) is None)
        wj(cfgp, {"vault": os.path.join(tmp, "nope")})
        res = OS.maybe_run(now + 5000, say=say.append, env={}, cfg_path=cfgp)
        check("e. a missing vault folder is a soft skip", res and not res["ok"] and "not found" in res["why"], res)
        # f. wiring
        pr = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
        check("f. the PC report calls the sync (soft, after the learning hook)", "obsidian_sync" in pr and pr.index("obsidian_sync") > pr.index("learn_loop"))
        ig = subprocess.run(["git", "check-ignore", "-q", "data/obsidian_sync.json"], cwd=ROOT).returncode == 0
        check("f. data/obsidian_sync.json is gitignored", ig)
        src = open(os.path.join(ROOT, "tools", "obsidian_sync.py"), encoding="utf-8").read()
        check("f. no network, no broker / order import", not re.search(r"urllib|requests|socket|ninjatrader|engine\.live\b|place_order", src))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"obsidian sync: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
