#!/usr/bin/env python3
"""PEOPLE OF OLYMPUS builder: the roster people.json for the shared people kit (tools/web_public/olympus/people.js). READ ONLY, OFFLINE, stdlib only.

    python tools/people_build.py                        # repo -> tools/web_public/olympus/people.json
    python tools/people_build.py --out DIR/people.json  # the site build writes it into the built site folder (olympus/people.json)
    python tools/people_build.py --check                # exit 1 when people.json is not what this script writes now (git part ignored)
    python tools/people_build.py --selftest

Every real worker becomes one named person with a stable id (docs/PERSONA_API.md):
  * builder:<short>   the build agents of handoff/agents_now.json, joined with their git branch when git is there (never required, never part of --check)
  * scanner:<id>      the five money scanners (tools/money/<id>.py)
  * bot:lit|atlas|blitz|kalshi   the paper bots
  * mind              the Mind;  job:prometheus|hephaestus|cronos|queue   the nightly jobs and the task queue
  * keeper:<district> one keeper per app district (jarvis/districts.js)
  * champion:<run-id> the top adopted runs of the Archive (archive/index.json), plus two rejected runs that looked good ("fallen", for debates)
  * villagers[]       villager:<app-id>, one per app (olympus/apps-list.js); they speak for that app's own jarvis.json card
A person has a Greek name with its meaning, a one-line bio and a temperament (calm / blunt / curious / wry). The temperament only changes WORDING, never facts.
Nothing here is a trade and nothing is sent anywhere. `asof` is the newest date found in the sources (not the clock), so the file is reproducible.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "web_public", "olympus", "people.json")
TEMPERS = ("calm", "blunt", "curious", "wry")

# id, name, meaning, title, kind, area, app, temperament, sources, home (scene, place), bio
CAST = (
    ("scanner:chrysos", "Chrysanthe", "golden flower", "Prop-firm planner", "scanner", "money", "chrysos", "calm",
     ["../money/index.json", "../money/chrysos.json"], ("ergasterion", "chrysos"), "Counts what each eval account costs and what it could pay back. Estimates only."),
    ("scanner:mercury", "Hermolaos", "of the people of Hermes", "Deal finder", "scanner", "money", "mercury", "wry",
     ["../money/index.json", "../money/mercury.json"], ("ergasterion", "mercury"), "Watches prop-firm sales and discount codes so you never pay list price."),
    ("scanner:sibyl", "Manto", "the seer", "Prediction-market pick finder", "scanner", "money", "sibyl", "curious",
     ["../money/index.json", "../money/sibyl.json"], ("ergasterion", "sibyl"), "Reads public prediction markets and writes down paper picks, with what could go wrong."),
    ("scanner:oikos", "Pheidon", "the thrifty one", "Household savings finder", "scanner", "money", "oikos", "calm",
     ["../money/index.json", "../money/oikos.json"], ("ergasterion", "oikos"), "Looks for money the household already has and is not keeping."),
    ("scanner:arbiter", "Dikaios", "the fair one", "Price-gap checker", "scanner", "money", "arbiter", "blunt",
     ["../money/index.json", "../money/arbiter.json"], ("ergasterion", "arbiter"), "Checks price gaps after fees. Most gaps are not there once the costs are in."),
    ("bot:lit", "Phoibos", "the bright one", "The LIT bot (Zlarior 50K, paper)", "bot", "trading", "hestia", "calm",
     ["../home.json", "../odeon/trades.json"], ("ergasterion", "lit"), "Trades the LIT plan on NQ: one trade a day, the stop behind the sweep, size follows the stop."),
    ("bot:atlas", "Telamon", "the bearer", "The ATLAS bot (25K, paper)", "bot", "trading", "hestia", "blunt",
     ["../home.json"], ("ergasterion", "atlas"), "Carries the second NQ strategy on the 25K account. Paper only."),
    ("bot:blitz", "Asterope", "lightning", "The BLITZ bot (25K, paper)", "bot", "trading", "hestia", "wry",
     ["../home.json"], ("ergasterion", "blitz"), "The quick third NQ strategy on its own 25K account. Paper only."),
    ("bot:kalshi", "Eutychos", "the fortunate", "The Kalshi bot (paper)", "bot", "money", "kalshi", "curious",
     ["../kalshi.json", "../kalshicity/learned.json"], ("ergasterion", "kalshi"), "Paper-trades prediction markets and keeps score of what it learned."),
    ("mind", "Metis", "wise counsel", "The Mind: nightly self-research", "mind", "research", "mind", "curious",
     ["../ergasterion/queue.json"], ("ergasterion", "mind"), "Thinks at night about recent trades and tests ideas. She only suggests; she never changes a rule."),
    ("job:prometheus", "Pyrrhos", "flame-coloured", "Prometheus: breeds LIT settings", "mind", "research", "prometheus", "blunt",
     ["../prometheus/forge.json", "../cronos/status.json"], ("ergasterion", "prometheus"), "Breeds LIT settings on Jan-Jun and checks them on Jul-Oct. Says so when nothing holds."),
    ("job:hephaestus", "Chalkeus", "the bronze-smith", "Hephaestus: stored LIT results", "mind", "research", "hephaestus", "calm",
     ["../hephaestus/data.json"], ("ergasterion", "hephaestus"), "Keeps the stored result of every LIT setting that was really run. Read-only."),
    ("job:cronos", "Horaios", "the timely one", "Cronos: the night clock", "mind", "research", "kronos", "blunt",
     ["../cronos/status.json"], ("ergasterion", "cronos"), "Runs the nightly jobs and tells you which ones failed or are late."),
    ("job:queue", "Kalamos", "the reed pen", "Scribe of the task queue", "mind", "factory", "ergasterion", "wry",
     ["../ergasterion/queue.json"], ("ergasterion", "queue"), "Keeps the list of open tasks and write-ups, and the ideas that were tested and rejected."),
    ("job:dev", "Epistates", "the overseer", "Foreman of the coding agents", "mind", "factory", "ergasterion", "calm",
     ["../ergasterion/builders.json"], ("ergasterion", "dev"), "Watches over the coding agents in the builders' camp: who is building what, and what was merged."),
)
KEEPERS = {"market": ("Agoraios", "of the marketplace", "calm"), "research": ("Zetes", "the seeker", "curious"), "money": ("Tamias", "the treasurer", "blunt"),
           "command": ("Hegemon", "the leader", "calm"), "life": ("Eirene", "peace", "wry")}
POOL_BUILDER = (("Daidalos", "the cunning worker"), ("Tekton", "the builder"), ("Ergane", "the worker"), ("Kallias", "beauty"), ("Ariston", "the best"), ("Philon", "the loving one"),
                ("Thalia", "the blooming one"), ("Myron", "sweet oil"), ("Nikias", "of victory"), ("Demetria", "of the earth"), ("Korinna", "the maiden"), ("Lysis", "the one who frees"),
                ("Phaidon", "the shining one"), ("Agathon", "the good one"), ("Timon", "honour"), ("Zoe", "life"), ("Kleio", "the one who tells"), ("Xenon", "the guest"),
                ("Melissa", "the honey bee"), ("Leandros", "lion of a man"), ("Iris", "the rainbow"), ("Doros", "the gift"), ("Euthymia", "good spirits"), ("Pelagia", "of the sea"))
POOL_CHAMP = (("Nikephoros", "bringer of victory"), ("Kallinikos", "fair victory"), ("Stephanos", "the crown"), ("Eunike", "good victory"), ("Andronikos", "victory of a man"),
              ("Berenike", "she who brings victory"), ("Nikandros", "man of victory"), ("Aristos", "the best"))
POOL_FALLEN = (("Ikaros", "who flew too high"), ("Phaethon", "who shone, then fell"), ("Niobe", "who boasted too soon"))
POOL_VILLAGER = ("Alexios", "Anthea", "Basileios", "Charis", "Damon", "Daphne", "Eleni", "Filippos", "Galene", "Hektor", "Ione", "Kyros", "Leda", "Linos", "Maia", "Nestor", "Olympia",
                 "Orestes", "Pallas", "Rhea", "Sophia", "Theron", "Thekla", "Xanthe", "Zenon", "Kosmas", "Phoebe", "Markos", "Agne", "Dion", "Hero", "Kyra", "Nike", "Petros", "Selene",
                 "Stavros", "Thais", "Tryphon", "Ourania", "Ploutos", "Kalliope", "Lykos", "Myrto", "Nikon", "Pyrrha", "Simon", "Timaios", "Chloe", "Evander", "Glauke", "Helene",
                 "Isidoros", "Kleon", "Lampros", "Melina", "Nikolaos", "Ophelia", "Pavlos", "Roxane", "Sotiris", "Theano", "Xenia", "Yannis", "Zosime", "Arion", "Briseis", "Korax", "Delia")


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_json(path):
    try:
        return json.loads(read(path))
    except ValueError:
        return None


def clean(text, n):
    t = re.sub(r"\s+", " ", re.sub(r"[`*<>]", "", str(text or ""))).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def seed_of(text):
    """FNV-1a 32 bit: the same number people-core.js computes from the id (face, voice, temperament)."""
    h = 2166136261
    for b in str(text).encode("utf-8"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def voice_of(seed):
    return {"pitch": round(0.8 + (seed % 51) / 100.0, 2), "rate": round(0.92 + ((seed >> 8) % 17) / 100.0, 2)}


def short_branch(branch):
    b = re.sub(r"^(worktree-agent-|claude/|chatgpt/|sprint/|agent-?)", "", str(branch or "").strip())
    b = re.sub(r"[^a-z0-9]+", "-", b.lower()).strip("-")
    return b[:8] or "agent"


def person(pid, name, meaning, title, kind, area, app, temper, sources, home, bio, **more):
    s = seed_of(pid)
    p = {"id": pid, "name": name, "meaning": meaning, "title": clean(title, 70), "kind": kind, "area": area, "app": app, "seed": s, "temperament": temper if temper in TEMPERS else TEMPERS[s % 4],
         "voice": voice_of(s), "sources": list(sources), "home": {"scene": home[0], "place": home[1]}, "bio": clean(bio, 170), "aliases": []}
    p.update(more)
    return p


def pick(pool, seed, used):
    for i in range(len(pool)):
        cand = pool[(seed + i) % len(pool)]
        nm = cand[0] if isinstance(cand, tuple) else cand
        if nm not in used:
            used.add(nm)
            return cand
    cand = pool[seed % len(pool)]
    nm = (cand[0] if isinstance(cand, tuple) else cand) + " " + "ΑΒΓΔΕΖΗΘ"[(seed >> 5) % 8]
    used.add(nm)
    return (nm, cand[1]) if isinstance(cand, tuple) else nm


def git_branches(root):
    """{branch: {t, s, n}} or {} when git is not there. Never raises."""
    try:
        out = subprocess.run(["git", "-C", root, "for-each-ref", "refs/heads", "--count=80", "--format=%(refname:short)|%(committerdate:unix)|%(subject)"], capture_output=True, text=True, timeout=15, check=True).stdout
    except Exception:  # noqa: BLE001 - git is never required
        return {}
    res = {}
    for ln in out.splitlines():
        a = ln.split("|", 2)
        if len(a) == 3 and a[1].isdigit():
            res[a[0]] = {"t": int(a[1]), "s": clean(a[2], 110)}
    return res


def builders(root, used, with_git=True):
    doc = read_json(os.path.join(root, "handoff", "agents_now.json")) or {}
    gb = git_branches(root) if with_git else {}
    rows, seen = [], set()
    for a in doc.get("agents") or []:
        if not isinstance(a, dict) or not a.get("branch"):
            continue
        short = short_branch(a["branch"])
        if short in seen:
            continue
        seen.add(short)
        pid = "builder:" + short
        nm, meaning = pick(POOL_BUILDER, seed_of(pid), used)
        job = clean(a.get("job"), 150)
        slug = re.sub(r"[^a-z0-9]+", "-", str(a.get("name", "")).lower()).strip("-")
        p = person(pid, nm, meaning, clean(a.get("name") or "Build agent", 40) + " builder", "builder", clean(a.get("area") or "build", 20), "ergasterion", "",
                   ["../ergasterion/builders.json", "../ergasterion/queue.json"], ("ergasterion", "dev"), job or "A build agent of this project.",
                   job=job, branch=str(a["branch"])[:60], agent=clean(a.get("name"), 40))
        p["aliases"] = [x for x in (str(a["branch"])[:60], "builder:" + slug if slug else "") if x]
        g = gb.get(a["branch"])
        if g:
            p["git"] = g
        rows.append(p)
    return rows, str(doc.get("asof") or "")[:10]


def districts(root):
    text = read(os.path.join(root, "tools", "web_public", "jarvis", "districts.js"))
    out = []
    for m in re.finditer(r"\{ id: '([a-z]+)', title: '([^']+)', colour: '(#[0-9a-fA-F]{6})'[^\n]*?ids: \[([^\]]*)\]", text):
        out.append({"id": m.group(1), "title": m.group(2), "colour": m.group(3), "ids": re.findall(r"'([a-z0-9_]+)'", m.group(4))})
    return out


def apps(root):
    text = read(os.path.join(root, "tools", "web_public", "olympus", "apps-list.js"))
    rows = []
    for m in re.finditer(r"^\s*(\{\"id\": .*\}),?\s*$", text, re.M):
        try:
            r = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("id"):
            rows.append(r)
    return rows


def metrics(cols, arr):
    if not isinstance(arr, list):
        return None
    d = {}
    for k, v in zip(cols, arr):
        if isinstance(v, (int, float)):
            d[k] = v
    return d or None


def champions(root, used, top=6, fallen=2):
    base = os.path.join(root, "tools", "web_public", "archive")
    idx = read_json(os.path.join(base, "index.json")) or {}
    cols, mcols = idx.get("cols") or [], idx.get("metric_cols") or []
    if not cols or "id" not in cols:
        return [], ""
    ix = {c: i for i, c in enumerate(cols)}
    verdicts = idx.get("verdicts") or ["adopted", "rejected", "open"]

    def row(r):
        g = lambda k: r[ix[k]] if k in ix and ix[k] < len(r) else None  # noqa: E731
        v = g("verdict")
        return {"id": str(g("id")), "title": clean(g("title"), 120), "family": clean(g("family"), 40), "verdict": verdicts[v] if isinstance(v, int) and v < len(verdicts) else "",
                "status": str(g("status") or ""), "built": str(g("built") or ""), "m26": metrics(mcols, g("m26")), "mold": metrics(mcols, g("mold")), "note": clean(g("note"), 200)}
    allrows = [row(r) for r in (idx.get("runs") or []) if isinstance(r, list)]
    for sh in idx.get("shards") or []:
        d = read_json(os.path.join(base, str(sh))) or {}
        allrows += [row(r) for r in (d.get("runs") or []) if isinstance(r, list)]
    net = lambda r: (r["m26"] or {}).get("net", -1e18)  # noqa: E731
    ok = [r for r in allrows if r["m26"] and "net" in r["m26"] and (r["m26"].get("n") or 0) >= 30]
    adopted = sorted([r for r in ok if r["verdict"] == "adopted"], key=lambda r: (-net(r), r["id"]))
    champs, fams = [], {}
    for r in adopted:                                   # at most two per family, so the hall is not six copies of one idea
        if fams.get(r["family"], 0) >= 2:
            continue
        fams[r["family"]] = fams.get(r["family"], 0) + 1
        champs.append(r)
        if len(champs) >= top:
            break
    rej = sorted([r for r in ok if r["verdict"] == "rejected" and (r["mold"] or {}).get("net") is not None], key=lambda r: (-net(r), r["id"]))[:fallen]
    out = []
    for r, is_f in [(c, False) for c in champs] + [(f, True) for f in rej]:
        pid = "champion:" + r["id"]
        nm, meaning = pick(POOL_FALLEN if is_f else POOL_CHAMP, seed_of(pid), used)
        title = ("Rejected idea: " if is_f else "Champion: ") + clean(r["title"], 52)
        bio = ("A run that looked good in 2026 and was still rejected. Ask why." if is_f else "An adopted run of the Archive. History, not a forecast.")
        p = person(pid, nm, meaning, title, "champion", "archive", "archive", "", ["../archive/index.json"], ("colosseum", r["id"]), bio,
                   fallen=is_f, run={k: r[k] for k in ("id", "title", "family", "verdict", "status", "built", "m26", "mold", "note")})
        p["aliases"] = [r["id"]]
        out.append(p)
    return out, str(idx.get("built") or "")[:10]


def build(root=ROOT, with_git=True):
    used = {c[1] for c in CAST} | {k[0] for k in KEEPERS.values()}
    people = [person(*c) for c in CAST]
    for p in people:
        tail = p["id"].split(":")[-1]
        p["aliases"] = [tail] if tail != p["id"] else []
    dts = districts(root)
    app_rows = apps(root)
    for d in dts:
        nm, meaning, temper = KEEPERS.get(d["id"], (None, None, ""))
        if not nm:
            nm, meaning = pick(POOL_BUILDER, seed_of("keeper:" + d["id"]), used)
        have = {a["id"] for a in app_rows}
        ids = [i for i in d["ids"] if i in have] or d["ids"]
        people.append(person("keeper:" + d["id"], nm, meaning, "Keeper of the " + d["title"] + " district", "keeper", d["id"], "atlas", temper,
                             ["../" + i + "/jarvis.json" for i in ids[:24]], ("hellas", d["id"]), "Looks after the " + str(len(ids)) + " apps of the " + d["title"] + " district and knows which ones need you.",
                             district={"id": d["id"], "title": d["title"], "colour": d["colour"], "apps": ids[:24]}))
    b, asof_b = builders(root, used, with_git)
    people += b
    c, asof_c = champions(root, used)
    people += c
    vused = set(used)
    villagers = []
    for a in app_rows:
        pid = "villager:" + a["id"]
        nm = pick(POOL_VILLAGER, seed_of(pid), vused)
        villagers.append({"id": pid, "name": nm, "title": "Lives in " + clean(a.get("name"), 30), "kind": "villager", "area": a.get("group", ""), "app": a["id"], "seed": seed_of(pid),
                          "temperament": TEMPERS[seed_of(pid) % 4], "voice": voice_of(seed_of(pid)), "sources": (["../" + a["path"] + "jarvis.json"] if a.get("live") and a.get("path") else []),
                          "home": {"scene": "athens", "place": a["id"]}, "bio": clean(a.get("purpose"), 120), "appName": clean(a.get("name"), 30)})
    asof = max([x for x in (asof_b, asof_c) if x] or [""])
    return {"v": 1, "asof": asof, "note": "The people of OLYMPUS: one named character per real worker. Built by tools/people_build.py from handoff/agents_now.json, the Archive, the app list and git (when present). "
            "A person only says what that worker's own files say. Nothing here is a trade.",
            "git": bool(any("git" in p for p in people)), "people": people, "villagers": villagers}


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def stable(text):
    try:
        d = json.loads(text)
    except ValueError:
        return None
    d.pop("git", None)
    for p in d.get("people") or []:
        p.pop("git", None)
    return d


def problems(doc):
    """The contract checks (also run by tests/test_people.py)."""
    bad, ids, names = [], set(), set()
    for p in (doc.get("people") or []) + (doc.get("villagers") or []):
        for k in ("id", "name", "title", "kind", "area", "app", "seed", "voice", "sources", "home"):
            if k not in p:
                bad.append(f"{p.get('id')}: no {k}")
        if p.get("id") in ids:
            bad.append(f"duplicate id {p.get('id')}")
        ids.add(p.get("id"))
        if p.get("kind") != "villager":
            if p.get("name") in names:
                bad.append(f"duplicate name {p.get('name')}")
            names.add(p.get("name"))
            if p.get("kind") not in ("builder", "scanner", "bot", "mind", "keeper", "champion"):
                bad.append(f"{p.get('id')}: kind {p.get('kind')}")
            if p.get("temperament") not in TEMPERS or not p.get("meaning") or not p.get("bio"):
                bad.append(f"{p.get('id')}: temperament / meaning / bio")
        if p.get("seed") != seed_of(p.get("id")):
            bad.append(f"{p.get('id')}: seed")
        if re.search(r"[<>]", json.dumps(p, ensure_ascii=False)):
            bad.append(f"{p.get('id')}: markup")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-git", action="store_true", help="build without reading git (what --check compares)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cur = build(with_git=not a.no_git)
    if a.check:
        if stable(read(a.out)) != stable(dump(cur)):
            print("people.json is out of date: run python tools/people_build.py")
            return 1
        print("people.json is current")
        return 0
    bad = problems(cur)
    if bad:
        print("people_build: " + "; ".join(bad[:6]))
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(dump(cur))
    kinds = {}
    for p in cur["people"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"wrote {a.out}: {len(cur['people'])} people ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}), {len(cur['villagers'])} villagers, git {'yes' if cur['git'] else 'no'}")
    return 0


def selftest():
    ok = []

    def ck(name, cond):
        ok.append(bool(cond))
        print(("[PASS] " if cond else "[FAIL] ") + name)
    ck("seed is FNV-1a 32 bit and stable", seed_of("bot:lit") == seed_of("bot:lit") and seed_of("") == 2166136261 and seed_of("a") == 0xE40C292C)
    ck("short branch names", short_branch("worktree-agent-a8fa04fb59e01df25") == "a8fa04fb" and short_branch("claude/Fix_Thing") == "fix-thin" and short_branch("") == "agent")
    ck("voice stays inside a natural range", all(0.8 <= voice_of(s)["pitch"] <= 1.3 and 0.92 <= voice_of(s)["rate"] <= 1.08 for s in (0, 1, 99, 2 ** 32 - 1)))
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "handoff"))
    os.makedirs(os.path.join(d, "tools", "web_public", "archive"))
    os.makedirs(os.path.join(d, "tools", "web_public", "jarvis"))
    os.makedirs(os.path.join(d, "tools", "web_public", "olympus"))
    with open(os.path.join(d, "handoff", "agents_now.json"), "w", encoding="utf-8") as fh:
        json.dump({"asof": "2026-11-11T01:00:00Z", "agents": [{"branch": "worktree-agent-abc123456789", "name": "Hellas", "job": "A world of cities", "area": "cities"},
                                                              {"branch": "worktree-agent-abc123456789", "name": "dup"}, {"name": "no branch"}]}, fh)
    with open(os.path.join(d, "tools", "web_public", "archive", "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-04", "cols": ["id", "title", "family", "strategy", "verdict", "status", "built", "periods", "m26", "mold", "writeup", "note"],
                   "metric_cols": ["n", "tpw", "pf", "net", "per_month", "p10", "f10"], "verdicts": ["adopted", "rejected", "open"], "shards": [],
                   "runs": [["r_good", "Good run", "LIT", 0, 0, "adopted", "26-10-01", 3, [100, 2.5, 3.0, 9000, 900, 20, 1], [500, 2.4, 1.2, 4000, 60, 5, 9], "w", "n"],
                            ["r_small", "Too few trades", "LIT", 0, 0, "adopted", "26-10-01", 3, [5, 0.1, 9.0, 99000, 900, 20, 1], None, "w", "n"],
                            ["r_bad", "Looked good", "LIT", 0, 1, "rejected", "26-10-01", 3, [90, 2.2, 2.0, 5000, 500, 10, 2], [400, 2, 0.9, -800, -13, 2, 12], "w", "n"]]}, fh)
    with open(os.path.join(d, "tools", "web_public", "jarvis", "districts.js"), "w", encoding="utf-8") as fh:
        fh.write("export const DISTRICTS = [\n  { id: 'market', title: 'Market', colour: '#c8a24a', tint: '#d9b25a', ids: ['hestia', 'oracle'] },\n];\n")
    with open(os.path.join(d, "tools", "web_public", "olympus", "apps-list.js"), "w", encoding="utf-8") as fh:
        fh.write('var rows = [\n  {"id": "hestia", "name": "Hestia", "group": "trading", "purpose": "Today at home", "path": "hestia/", "live": true},\n  {"id": "zenith", "name": "Zenith", "group": "trading", "purpose": "x", "path": "", "live": false}\n];\n')
    b = build(d, with_git=False)
    ids = [p["id"] for p in b["people"]]
    ck("roster: the fixed cast, one keeper, one builder (duplicates and branchless rows dropped), one champion and one fallen run",
       ids[:len(CAST)] == [c[0] for c in CAST] and "keeper:market" in ids and ids.count("builder:abc12345") == 1 and len([i for i in ids if i.startswith("builder:")]) == 1
       and "champion:r_good" in ids and "champion:r_bad" in ids and "champion:r_small" not in ids)
    fallen = next(p for p in b["people"] if p["id"] == "champion:r_bad")
    ck("a champion carries its run snapshot (2026 and 2021-25 numbers); a rejected one is marked fallen", fallen["fallen"] is True and fallen["run"]["mold"]["net"] == -800
       and next(p for p in b["people"] if p["id"] == "champion:r_good")["run"]["m26"]["per_month"] == 900)
    ck("villagers: one per app, sources only for apps with a status card", [v["id"] for v in b["villagers"]] == ["villager:hestia", "villager:zenith"] and b["villagers"][0]["sources"] == ["../hestia/jarvis.json"] and b["villagers"][1]["sources"] == [])
    ck("the contract holds: ids unique, names unique, kinds, seeds, temperaments, no markup", problems(b) == [] and problems(build(ROOT, with_git=False)) == [])
    ck("asof comes from the sources, not the clock; the build is reproducible", b["asof"] == "2026-11-11" and dump(b) == dump(build(d, with_git=False)))
    g = json.loads(dump(b))
    g["git"] = True
    g["people"][-1]["git"] = {"t": 1, "s": "x"}
    ck("--check ignores the git part", stable(dump(b)) == stable(dump(g)))
    ck("git never raises on a folder that is not a repo", git_branches(tempfile.mkdtemp()) == {})
    ck("an empty folder still gives the fixed cast (never blank)", len(build(tempfile.mkdtemp(), with_git=False)["people"]) == len(CAST))
    print("ALL PASS" if all(ok) else "SOME FAILED")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
