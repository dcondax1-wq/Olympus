"""Multi-strategy books, step 4: markdown tables from research/books/{lanes_stats,accounts_h1,pvals,final}.json.
    python -X utf8 tools/books/report.py > research/books/tables.md
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "research", "books")
J = lambda n: json.load(open(os.path.join(OUT, n), encoding="utf-8"))
AN = {"b50": "Builder 50K", "b25": "Builder 25K", "r25": "Rapid EOD 25K", "r50": "Rapid EOD 50K"}
SP = (("H1", "Jan-Jun 2026 (pick)"), ("H2", "Jul-Oct 2026"), ("REF", "2021-25"))
KIND = {"money": "best $ (any lanes)", "five": "best 5+/wk (any lanes)", "fixed_money": "best $ (fixed lanes)",
        "fixed_five": "best 5+/wk (fixed lanes)", "under5": "best under 5/wk"}


def m(x):
    return "-" if x is None else (f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}")


def lanes_table():
    L = J("lanes_stats.json")
    print("| lane | trades/wk H1 | PF H1 / H2 / 21-25 | $/mo at $250 a trade H1 / H2 / 21-25 | max DD 21-25 |")
    print("|---|---:|---|---|---:|")
    for s, v in L["lanes"].items():
        print(f"| {s} {v['name']} | {v['H1']['tpw']} | {v['H1']['pf']} / {v['H2']['pf']} / {v['REF']['pf']} | "
              f"{m(v['H1']['per_month'])} / {m(v['H2']['per_month'])} / {m(v['REF']['per_month'])} | {m(v['REF']['max_dd'])} |")


def final_tables(fills="real"):
    F = J("final.json")
    A = J("accounts_h1.json")
    P = J("pvals.json")
    for acct in AN:
        print(f"\n### {AN[acct]} ({fills} fills)\n")
        print("| book | rule | period | trades/wk | win % | PF | net $/mo (6-mo slot, after fees) | 10th pct $/mo | lose 6 mo % | "
              "eval pass % (60 sess) / fail % | median days to pass | median sessions to 1st payout | max DD (trades, $250) |")
        print("|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|")
        tags = {}
        for k, p in A["picks"][acct].items():
            if p:
                tags.setdefault((p["book"], p["rule"]), []).append(KIND[k])
        for r in F["rows"]:
            if r["acct"] != acct or r["fills"] != fills:
                continue
            tag = ", ".join(tags.get((r["book"], r["rule"]), [])) or ("today's setup" if r["book"] == {"b50": "Z", "b25": "A"}.get(acct, "Z+A") else "reference")
            for sp, lab in SP:
                x = r[sp]
                pl = x["plain"]
                print(f"| {r['book']} ({tag}) | {r['rule']} | {lab} | {pl['tpw']} | {pl['win']} | {pl['pf']} | {m(x['net_m'])} | {m(x['p10_m'])} | "
                      f"{x['p_neg']} | {x['pass60']} / {x['fail60']} | {x['pass_med']} | {x['first_pay_med']} | {m(pl['max_dd'])} |")
    if fills == "real":
        print(f"\n### Multiple testing (N = {P['N']:,} things tried; Bonferroni needs p < {P['alpha']:.2e})\n")
        print("| account | pick | book | H1 gain vs today a day ($250 a trade) | t | p | Bonferroni | reality-check p |")
        print("|---|---|---|---:|---:|---:|:-:|---:|")
        for k, v in P["picks"].items():
            a, kind = k.split("|")
            print(f"| {AN[a]} | {KIND[kind]} | {v['book']} ({v['rule']}) | {m(v['gain_per_day'])} | {v['t']} | {v['p']:.2g} | "
                  f"{'pass' if v['bonferroni_pass'] else 'fail'} | {v['reality_check_p']} |")


if __name__ == "__main__":
    print("## Lanes alone (real fills)\n")
    lanes_table()
    print("\n## Books per account\n")
    final_tables("real")
    print("\n## Same rows at model fills (sensitivity)\n")
    final_tables("model")
