import json, os
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")))
def line(r):
    out = [f"{r['name'][:40]:40s} tgt={r.get('tgt')}"]
    for sp in ("2026H1", "2026H2", "2021-25"):
        s = r["spans"].get(sp)
        if not s: out.append(f"{sp}: -"); continue
        out.append(f"{sp[-4:]}: ev{s['events']} n{s['trades']} {s['win_pct']}% PF{s['pf']} ${s['net']} ({s['per_month']}/mo) DD{s['max_dd']} p{s.get('perm_p')}")
    return " | ".join(out)
for k in ("standalone", "tod", "pension"):
    print("==", k)
    for r in d[k]:
        if "spans" in r: print(line(r), "WIN" if all(r["spans"].get(x) and r["spans"][x]["net"] > 0 for x in ("2026H1","2026H2","2021-25")) else "")
        else: print(r)
print("== dial")
for r in d["dial"]:
    s = r["spans"]
    print(f"{r['name']:28s}", " | ".join(f"{k[-4:]}: d${s[k]['delta']} p{s[k]['perm_p']} nd{s[k]['window_days']} 2wk {s[k]['eval_2wk']['pass_pct']}/{s[k]['eval_2wk']['fail_pct']} vs {s[k]['eval_2wk_base']['pass_pct']}/{s[k]['eval_2wk_base']['fail_pct']}" for k in s))
