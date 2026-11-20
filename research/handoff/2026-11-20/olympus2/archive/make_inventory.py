"""Build INVENTORY.md from the before / after scans (scan.py --out) + the verdicts below.
    python research/handoff/2026-11-20/olympus2/archive/make_inventory.py BEFORE.json AFTER.json"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, *[".."] * 5, "tools"))
import archive_banners as A  # noqa: E402

# id -> (data it shows, verdict, why).  Verdicts: KEEP-ARCHIVED (reachable, banner, fixed) / RETIRE? (proposal for the lead/owner) / VISIBLE (not archived)
V = {
    "agency": ("demo leads + owner's PC leads (local only)", "VISIBLE", "side income page; fixed the my_leads.json 404 on github.io"),
    "inbox": ("home.json alerts (live)", "VISIBLE", "alerts list; the kalshi.json 404 is the Kalshi feed not connected yet (Monday)"),
    "tyche": ("kalshi.json (not connected) -> demo wheel", "VISIBLE", "Kalshi door shortcut; demo until the Kalshi feed connects"),
    "pc": ("static PC connect page", "VISIBLE", "PC helper downloads; fine"),
    "apollo": ("odeon trades to Oct 28", "KEEP-ARCHIVED", "weekly review view the journal lacks; data age now shown"),
    "epilogue": ("home.json week (live)", "KEEP-ARCHIVED", "Sunday review; Journal covers most"),
    "kratos": ("odeon trades to Oct 28", "KEEP-ARCHIVED", "discipline score; data age now shown"),
    "nemesis": ("odeon trades to Oct 28 + live balance", "KEEP-ARCHIVED", "loss review; data age now shown"),
    "nike": ("odeon trades to Oct 28", "RETIRE?", "trophy hall, 44 animations; no money use"),
    "ares": ("home.json account (live)", "KEEP-ARCHIVED", "GO/WAIT/HALT sizing; no longer downloads 8.8 MB on open"),
    "kairos": ("clock + odeon trades", "RETIRE?", "session clock; NQ + Planner show the window"),
    "chronos": ("odeon trades to Oct 28 ('2026-10 so far')", "RETIRE?", "day replay; duplicate of Odeon/NQ, data 23 days old"),
    "oracle": ("live NQ price (LAST SEEN shown)", "KEEP-ARCHIVED", "market radar with its own age; heavy"),
    "odeon": ("trades to Oct 28", "KEEP-ARCHIVED", "3D replay; its trades.json feeds Trading/Journal/Kronos/NQ: folder must stay"),
    "why": ("why.json research to Oct 16", "KEEP-ARCHIVED", "owner's win/loss study; Trading reads why.json"),
    "delphi": ("home.json (live) briefing", "RETIRE?", "go/no-go duplicate of Helios"),
    "forum": ("Pantheon read Nov 3 + live eval", "KEEP-ARCHIVED", "morning ritual; now labels the 17-day-old market read as old"),
    "pythia": ("events.json Nov 10 (calendar ahead)", "KEEP-ARCHIVED", "events.json feeds Helios/Planner/Jarvis/Hub: folder must stay"),
    "pantheon": ("pantheon.json Nov 3 (17 d old)", "KEEP-ARCHIVED", "builder stopped Nov 3 (lead/DATA team: rerun or retire); feeds Forum/Cities"),
    "pheme": ("stats.json Nov 10, bars to Oct 16", "RETIRE?", "releases word-on-street; low value, old"),
    "labyrinth": ("odeon trades + live room", "KEEP-ARCHIVED", "pass odds by size; Pnyx sizes but has no odds"),
    "moirai": ("simulation (labelled)", "KEEP-ARCHIVED", "eval Monte Carlo; Fates covers"),
    "plutus": ("roadmap.json Nov 4 (16 d old)", "RETIRE?", "duplicate of Hera; roadmap.json feeds Hera/Demeter/Ledger: folder must stay; 8.8 MB fixed"),
    "argo": ("home.json payouts (none yet)", "RETIRE?", "goals as islands; Hera covers"),
    "mint": ("money/index.json (labelled example)", "RETIRE?", "duplicate of Business"),
    "mintcity": ("money/index.json (labelled example)", "RETIRE?", "3D marble city of Mint; gimmick"),
    "harmonia": ("money/index.json estimate", "RETIRE?", "duplicate of Business"),
    "arbiter": ("demo spreads (labelled)", "RETIRE?", "off-strategy paper lab"),
    "hermes": ("demo 'Wrapped' (labelled)", "RETIRE?", "fun story; no decision value"),
    "stoa": ("home.json (live)", "RETIRE?", "duplicate of Compass"),
    "hestia": ("home.json (live)", "RETIRE?", "duplicate of Compass"),
    "argus": ("home.json + checks (live)", "KEEP-ARCHIVED", "what-to-fix list; dev-facing but real"),
    "herald": ("edition Nov 11", "RETIRE?", "daily paper of who built what; dev-facing, old"),
    "symposium": ("demo AI workers", "RETIRE?", "gimmick, 4 MB on open"),
    "ergasterion": ("demo AI workers", "RETIRE?", "dev-facing; queue.json read by Jarvis/Polis: folder must stay"),
    "mind": ("demo vault (labelled)", "RETIRE?", "3D brain demo; Jarvis has the memory"),
    "bridge": ("jobs.json (static)", "RETIRE?", "ChatGPT link jobs; niche"),
    "athena": ("200 strategy notes (static)", "KEEP-ARCHIVED", "learning library; Clio covers research"),
    "lyceum": ("quiz (static)", "RETIRE?", "duplicates Athena"),
    "archive": ("index.json today", "KEEP-ARCHIVED", "searchable test library; read by Cities/Colosseum"),
    "observatory": ("data health (demo parts)", "RETIRE?", "lab page"),
    "tree": ("research search snapshot", "KEEP-ARCHIVED", "strategy tree research (Clio links)"),
    "prometheus": ("forge.json Nov 17", "KEEP-ARCHIVED", "strategy forge research"),
    "hephaestus": ("data.json Nov 4", "KEEP-ARCHIVED", "tune dials research"),
    "pinakes": ("catalog.json today", "KEEP-ARCHIVED", "table catalogue (dev)"),
    "colosseum": ("extra.json Nov 15", "KEEP-ARCHIVED", "strategies fight (research)"),
    "arena": ("XP demo", "RETIRE?", "gamification"),
    "gallery": ("3D shapes demo", "RETIRE?", "showcase page, no data"),
    "polis": ("home.json + people (live)", "RETIRE?", "3D app city; Atlas is the directory"),
    "atlascity": ("home.json (live)", "RETIRE?", "duplicate of Atlas; no door lists it"),
}


def main():
    before = {r["id"]: r for r in json.load(open(sys.argv[1]))}
    after = {r["id"]: r for r in json.load(open(sys.argv[2]))} if len(sys.argv) > 2 else {}
    rows = ["| app | live version (banner link) | data it shows (age) | errors / 404 before -> after | KB on open before -> after | verdict | why |",
            "|---|---|---|---|---|---|---|"]
    for i in sorted(V):
        b, a = before.get(i, {}), after.get(i, {})
        target = A.MAP.get(i, ("-", "-", None))
        eb = len(b.get("errors", [])) + len(b.get("console", [])) + len(b.get("bad", []))
        ea = len(a.get("errors", [])) + len(a.get("console", [])) + len(a.get("bad", [])) if a else "?"
        bad = ", ".join(sorted(set(x.split(":", 1)[1].split("?")[0] for x in b.get("bad", []))))
        rows.append(f"| `{i}` | {target[1] if i in A.MAP else '(not archived)'} | {V[i][0]} | {eb}{' (' + bad + ')' if bad else ''} -> {ea} "
                    f"| {b.get('kb', '?')} -> {a.get('kb', '?')} | {V[i][1]} | {V[i][2]} |")
    n = {k: sum(1 for v in V.values() if v[1] == k) for k in ("VISIBLE", "KEEP-ARCHIVED", "RETIRE?")}
    head = (f"# Archive team inventory (day-archive 2026-11-20)\n\n{len(V)} app folders owned by the archive team. Scan: 390x844 mobile Chromium, our code, "
            "data files from the live site (dcondax1-wq.github.io), 2.5 s after load (`scan.py`). KB = bytes the page pulled on open (JS, CSS, data, images).\n"
            f"Verdicts: VISIBLE {n['VISIBLE']} (not archived), KEEP-ARCHIVED {n['KEEP-ARCHIVED']} (reachable from the Archive fold, banner + fixes), "
            f"RETIRE? {n['RETIRE?']} (proposal: drop from doors and search; the folder and URL stay, banner points to the live app; LEAD_WIRES.md).\n"
            "Page errors: 0 before and after on every page. Sideways scroll: 0 px everywhere. Left 404s: kalshi.json (the Kalshi feed, not connected "
            "until Monday: by design); agency/my_leads.json shows here because this scan is not on github.io (on the site it is no longer asked); "
            "pc's favicon is fixed after the scan. Ares 'before' KB is low because the scan's 6 s abort cut its 8.8 MB data.json short; on a phone it was ~10 MB.\n\n")
    open(os.path.join(HERE, "INVENTORY.md"), "w").write(head + "\n".join(rows) + "\n")
    print("INVENTORY.md", len(rows) - 2, "rows")


main()
