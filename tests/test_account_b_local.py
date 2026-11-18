"""ATLAS's account on the PC lives in data/account_b.json, not in the tracked second_model.json (engine/account_b.py,
owner 2026-10-25 "unblock updates": the PC's armed block in second_model.json blocked every auto-update).

    python -X utf8 -m tests.test_account_b_local

  1. migration (real git, temp repos only): an older version's block in second_model.json moves to data/account_b.json
     and the tracked file goes back to HEAD byte for byte; twice = nothing; a CRLF-rewritten file; other local edits kept;
     a local file that is already there wins; no git = copied only; files staged by hand are not touched.
  2. same trading after the move: ATLAS's spec (account, plan, strategies, sizing, armed), its adapter config (account,
     arming, order-file tag), LiveBot's account_b block, the routes on LIT's account, START BOT's route check, the launch
     checklist and the AI watch's rule snapshot are identical before and after; LIT's own account and routes unchanged.
Never touches the real second_model.json or data/.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import account_b as AB  # noqa: E402
from engine import second  # noqa: E402

RESULTS = []
LIT, ATLAS = "MFFUEVBLD000006016", "MFFUEVBLD000006017"
BLOCK = {"account": ATLAS, "plan": "builder25k", "eval_start": "2026-10-26",
         "strategies": ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"], "sizing": "need", "armed": True}


def check(name, ok, info=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(info)[:300]})" if info and not ok else ""), flush=True)


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True).stdout.strip()


def repo(tmp, name):
    """A temp git repo holding the shipped second_model.json (account_b null) + one code file, committed."""
    d = os.path.join(tmp, name)
    os.makedirs(os.path.join(d, "engine"))
    shutil.copy(os.path.join(ROOT, "second_model.json"), os.path.join(d, "second_model.json"))
    with open(os.path.join(d, "engine", "x.py"), "w") as fh:
        fh.write("v1\n")
    for a in (("init", "-q", "-b", "main"), ("config", "user.email", "t@t"), ("config", "user.name", "t"),
              ("config", "core.autocrlf", "false"), ("add", "."), ("commit", "-qm", "base")):
        git(d, *a)
    return d


def raw(p):
    with open(p, "rb") as fh:
        return fh.read()


def migration(tmp):
    print("1. migration", flush=True)
    shipped = raw(os.path.join(ROOT, "second_model.json"))
    check("the shipped second_model.json has account_b null (the PC's account is local)",
          json.loads(shipped).get("account_b") is None)
    d = repo(tmp, "a")
    p = os.path.join(d, "second_model.json")
    AB._set_tracked_block(p, BLOCK)                  # what the old set_account_b / launch prep / arm_b wrote
    before = AB.raw_cfg(p)
    dirty = git(d, "status", "--porcelain")
    r = AB.migrate_local(root=d)
    check("a. the block moves to data/account_b.json, second_model.json back to HEAD byte for byte, clean tree",
          dirty and r["status"] == "migrated" and before == BLOCK and AB.read_local(p) == (True, BLOCK)
          and raw(p) == shipped and not git(d, "status", "--porcelain", "--untracked-files=no"), (dirty, r))
    check("a. data/account_b.json is gitignored in this repo's .gitignore (never committed)",
          "data/account_b.json" in open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read().splitlines())
    r2 = AB.migrate_local(root=d)
    check("b. run again: nothing to do, the local block unchanged", r2["status"] == "clean" and AB.raw_cfg(p) == BLOCK, r2)

    d = repo(tmp, "c")
    p = os.path.join(d, "second_model.json")
    AB._set_tracked_block(p, BLOCK)
    txt = open(p, encoding="utf-8").read()
    with open(p, "w", encoding="utf-8", newline="\r\n") as fh:      # Windows text mode rewrote every line ending
        fh.write(txt)
    r = AB.migrate_local(root=d)
    check("c. a whole file rewritten with CRLF line endings: moved and restored all the same",
          r["status"] == "migrated" and raw(p) == shipped and AB.raw_cfg(p) == BLOCK, r)

    d = repo(tmp, "d")
    p = os.path.join(d, "second_model.json")
    c = json.load(open(p, encoding="utf-8"))
    c["strategies"]["ema_lon_vix"]["route"] = True                   # another local edit next to the block
    c["account_b"] = BLOCK
    json.dump(c, open(p, "w", encoding="utf-8"), indent=1)
    r = AB.migrate_local(root=d)
    c2 = json.load(open(p, encoding="utf-8"))
    check("d. other local edits are kept: only account_b goes back to HEAD's null, the block is in the local file",
          r["status"] == "migrated" and c2["account_b"] is None and c2["strategies"]["ema_lon_vix"]["route"] is True
          and AB.raw_cfg(p) == BLOCK, r)

    d = repo(tmp, "e")
    p = os.path.join(d, "second_model.json")
    newer = {**BLOCK, "eval_start": "2026-11-02"}
    AB.write_local(newer, p)
    AB._set_tracked_block(p, BLOCK)                                  # a stale copy in the tracked file
    r = AB.migrate_local(root=d)
    check("e. a local file that is already there wins (it is what the bot reads); the tracked copy is dropped",
          r["status"] == "migrated" and AB.raw_cfg(p) == newer and raw(p) == shipped, r)

    d = repo(tmp, "f")
    p = os.path.join(d, "second_model.json")
    AB._set_tracked_block(p, BLOCK)
    tr = raw(p)
    r = AB.migrate_local(root=d, git=lambda *a: (127, "FileNotFoundError: git"))
    check("f. no git: the block is copied to the local file, second_model.json left as it is, reads are the same",
          r["status"] == "no_git" and r.get("copied") and raw(p) == tr and AB.raw_cfg(p) == BLOCK, r)

    d = repo(tmp, "g")
    p = os.path.join(d, "second_model.json")
    with open(os.path.join(d, "engine", "x.py"), "w") as fh:
        fh.write("v2 from main\n")
    git(d, "add", "engine/x.py")                                     # checked out from main by hand (staged)
    AB._set_tracked_block(p, BLOCK)
    r = AB.migrate_local(root=d)
    st = git(d, "status", "--porcelain", "--untracked-files=no")
    check("g. a file staged by hand (the clock fix checked out from main) is not touched by the move",
          r["status"] == "migrated" and st == "M  engine/x.py" and open(os.path.join(d, "engine", "x.py")).read() == "v2 from main\n"
          and AB.raw_cfg(p) == BLOCK, (r, st))

    d = repo(tmp, "h")
    p = os.path.join(d, "second_model.json")
    os.makedirs(os.path.join(d, "data"), exist_ok=True)
    with open(AB.local_path(p), "w") as fh:
        fh.write("{broken")
    AB._set_tracked_block(p, BLOCK)
    seen = AB.raw_cfg(p)
    r = AB.migrate_local(root=d)
    check("h. an unreadable local file is not trusted: the tracked block counts, the move rewrites the local file",
          seen == BLOCK and r["status"] == "migrated" and AB.read_local(p) == (True, BLOCK) and raw(p) == shipped, r)


def snapshot(p, d):
    """Everything that decides where ATLAS and LIT trade, read the way the bot reads it."""
    from engine import go, launch_check, ai_watch
    from engine import live
    keep = (second.CFG_PATH, go.SECOND_PATH)
    try:
        second.CFG_PATH, go.SECOND_PATH = p, p
        ab = AB.raw_cfg()
        spec = AB.normalize(ab, second.load_cfg(), lit_account=LIT)
        bot = SimpleNamespace(cfg={"adapter": "ninjatrader", "nt_account": LIT, "armed": True, "confirm": "x", "sym": "NQ"},
                              state_path=os.path.join(d, "live_state.json"), clock=lambda: 1792980000, _log=lambda *a, **k: None)
        acc = AB.AccountB(bot, spec, state_path=os.path.join(d, "live_state_acctb.json"))
        acfg = acc.adapter_cfg()
        lb = live.LiveBot()
        lb.cfg = {"adapter": "ninjatrader", "nt_account": LIT}
        blk = lb._account_b_block()
        lb.acct_b = SimpleNamespace(spec=spec)
        _, routed_lit = lb._second_cfg()
        state = {"running": True, "cfg": {"nt_account": LIT, "adapter": "ninjatrader", "accounts": []}}
        lc = launch_check.facts(SimpleNamespace(acct_b=object(), cfg={"nt_account": LIT, "adapter": "ninjatrader"}, health={}),
                                now=1792980000, sim_path=os.path.join(d, "sim.json"), second_path=p,
                                allow_path=os.path.join(d, "allow.json"), anchor_path=os.path.join(d, "anchor.json"))
        rules = ai_watch.rules_snapshot(None).get("second", {}).get("account_b")
        return {"block": ab, "spec": {k: spec.get(k) for k in ("account", "plan", "preset", "strategies", "keys", "sizing", "armed",
                                                               "eval_start", "label", "problem")},
                "kind": acc.kind(), "adapter": {k: acfg.get(k) for k in ("adapter", "nt_account", "armed", "nt_file_tag")},
                "confirm_set": bool(acfg.get("confirm")), "livebot_block": blk, "lit_routed": routed_lit,
                "lit_account": bot.cfg["nt_account"], "verify": go.verify_routes(LIT, ATLAS, state=state),
                "launch_b": (lc or {}).get("b") if isinstance(lc, dict) else None, "ai_rules": rules,
                "second_cfg": second.load_cfg().get("account_b")}
    finally:
        second.CFG_PATH, go.SECOND_PATH = keep


def same_trading(tmp):
    print("2. same trading after the move", flush=True)
    from engine import ai_watch
    d = repo(tmp, "t")
    p = os.path.join(d, "second_model.json")
    AB._set_tracked_block(p, BLOCK)                  # the PC tonight: the armed block in the tracked file
    keep_root = ai_watch.ROOT
    ai_watch.ROOT = d                                # the AI watch's rule snapshot reads this repo's files
    try:
        before = snapshot(p, d)
        r = AB.migrate_local(root=d)
        after = snapshot(p, d)
    finally:
        ai_watch.ROOT = keep_root
    check("ATLAS before the move: the 25K, builder25k, EMA + MACD + S/R, need size, armed, LIVE, no problem",
          before["spec"]["account"] == ATLAS and before["spec"]["plan"] == "builder25k" and before["spec"]["armed"] is True
          and before["spec"]["keys"] == BLOCK["strategies"] and before["spec"]["problem"] is None and before["kind"] == "LIVE",
          before["spec"])
    check("the move happened", r["status"] == "migrated" and not git(d, "status", "--porcelain", "--untracked-files=no"), r)
    for k in ("block", "spec", "kind", "adapter", "confirm_set", "livebot_block", "lit_routed", "lit_account", "verify",
              "launch_b", "ai_rules", "second_cfg"):
        check(f"identical after the move: {k}", before[k] == after[k], (before[k], after[k]))
    check("ATLAS's adapter: its own 25K, armed, its own order-file tag (never LIT's account)",
          after["adapter"] == {"adapter": "ninjatrader", "nt_account": ATLAS, "armed": True, "nt_file_tag": "acctb_"}
          and after["confirm_set"], after["adapter"])
    check("LIT unaffected: its account is the 50K, nothing of ATLAS routed on it, START BOT's route check passes",
          after["lit_account"] == LIT and after["lit_routed"] == [] and after["verify"] == [], after["verify"])
    check("the launch checklist still sees ATLAS set up and armed on the 25K",
          (after["launch_b"] or {}).get("account") == ATLAS and (after["launch_b"] or {}).get("armed") is True
          and after["ai_rules"] == BLOCK and after["livebot_block"] == BLOCK,
          after["launch_b"])


def main():
    real = {p: raw(os.path.join(ROOT, p)) if os.path.exists(os.path.join(ROOT, p)) else None
            for p in ("second_model.json", os.path.join("data", "account_b.json"))}
    tmp = tempfile.mkdtemp(prefix="le_ablocal_")
    try:
        migration(tmp)
        same_trading(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    now = {p: raw(os.path.join(ROOT, p)) if os.path.exists(os.path.join(ROOT, p)) else None for p in real}
    check("the real second_model.json and data/account_b.json did not change", now == real)
    print(f"account_b local: {sum(RESULTS)}/{len(RESULTS)} {'ALL PASS' if all(RESULTS) else 'FAILED'}")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
