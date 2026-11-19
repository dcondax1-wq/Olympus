import json, collections
W='/home/user/wt-combored/'
d=json.load(open(W+'research/lab/combo_account_trades.json'))
rows=[dict(zip(d['cols'],r)) for r in d['rows']]
def sp(day): return 'H1' if '2026-01-01'<=day<='2026-06-30' else ('H2' if day>='2026-07-01' else 'REF')
by=collections.defaultdict(list)
for r in rows: by[r['day']].append(r)
# self-overlap and per day counts
for s in 'ZA':
    ov=0; mx=collections.Counter()
    for day,ts in by.items():
        X=sorted([t for t in ts if t['s']==s], key=lambda t:t['et'])
        mx[len(X)]+=1
        for a,b in zip(X,X[1:]):
            if b['et']<a['xt']: ov+=1
    print(s,'self-overlaps',ov,'trades/day hist',sorted(mx.items()))
# first-in Z+A: count skipped by reason per span, and opposite vs same side
cnt=collections.Counter(); Rlost=collections.defaultdict(float)
for day,ts in sorted(by.items()):
    X=sorted([t for t in ts if t['s'] in 'ZA'], key=lambda t:(t['et'],0 if t['s']=='Z' else 1))
    busy=-1; cur=None
    for t in X:
        if t['et']<busy:
            k=(sp(day), t['s']+' skipped (other='+cur['s']+')', 'same' if t['d']==cur['d'] else 'opp')
            cnt[k]+=1; Rlost[k]+=t['pts']/t['risk']
            continue
        busy=t['xt']; cur=t
for k in sorted(cnt): print(k, cnt[k], 'R of skipped', round(Rlost[k],1))
# sm values of Z
print('Z size_mult', collections.Counter((sp(r['day']),r['sm']) for r in rows if r['s']=='Z'))
# stop trades pts/risk
import statistics
for s in 'ZA':
    v=[r['pts']/r['risk'] for r in rows if r['s']==s and str(r['x']).lower()=='stop']
    print(s,'stop R min/median/max', round(min(v),3), round(statistics.median(v),3), round(max(v),3), len(v))
    v=[(r['pts']+r['risk'])/0.25 for r in rows if r['s']==s and str(r['x']).lower()=='stop']
    print(s,'stop slippage ticks median', statistics.median(v), 'min', min(v), 'max', max(v))
