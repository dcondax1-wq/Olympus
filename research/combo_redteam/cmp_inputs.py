import json, collections
W='/home/user/wt-combored/'
d=json.load(open(W+'research/lab/combo_account_trades.json'))
rows=[dict(zip(d['cols'],r)) for r in d['rows']]
def anat(b):
    a=json.load(open(W+f'research/anatomy/trades_{b}.json'))
    return [dict(zip(a['cols'],r)) for r in a['rows']]
for s,b in (('Z','lit'),('A','atlas')):
    C=[r for r in rows if r['s']==s]
    A=[r for r in anat(b) if r['day']>='2021-11-01' and r['day']<='2026-10-16']
    kc={(r['day'],r['et'],r['d']):r for r in C}
    ka={(r['day'],r['entry_t'],r['dir']):r for r in A}
    both=set(kc)&set(ka)
    print(s, 'combo',len(C),'anat',len(A),'both',len(both),'combo only',len(set(kc)-set(ka)),'anat only',len(set(ka)-set(kc)))
    # compare R and exit time
    dr=[];dx=0;dexit=0
    for k in both:
        c,a=kc[k],ka[k]
        Rc=c['pts']/c['risk']
        dr.append(abs(Rc-a['r']))
        if c['xt']!=a['exit_t']: dx+=1
        if c['x']!=a['exit']: dexit+=1
    dr.sort()
    print('  |R diff| median',dr[len(dr)//2] if dr else None,'p95',dr[int(.95*len(dr))] if dr else None,'max',dr[-1] if dr else None,'exit_t diffs',dx,'exit kind diffs',dexit)
    big=[(k,kc[k]['pts']/kc[k]['risk'],ka[k]['r'],kc[k]['x'],ka[k]['exit']) for k in both if abs(kc[k]['pts']/kc[k]['risk']-ka[k]['r'])>0.1]
    print('  big R diffs',len(big), big[:8])
    oc=sorted(set(kc)-set(ka)); oa=sorted(set(ka)-set(kc))
    def span(k): return 'H1' if k[0]<'2026-07-01' and k[0]>='2026' else ('H2' if k[0]>='2026-07' else 'REF')
    print('  combo-only by span',collections.Counter(span(k) for k in oc),'anat-only by span',collections.Counter(span(k) for k in oa))
    print('  ex combo-only',[(k, kc[k]['src']) for k in oc[:5]]); print('  ex anat-only',[(k, ka[k].get('src') or ka[k].get('member')) for k in oa[:5]])
    # sum R by span
    for nm,X,f in (('combo',C,lambda r:r['pts']/r['risk']),('anat',A,lambda r:r['r'])):
        by=collections.defaultdict(list)
        for r in X: by['H1' if '2026-01-01'<=r['day']<='2026-06-30' else ('H2' if r['day']>='2026-07-01' else 'REF')].append(f(r))
        print('  ',nm,{k:(len(v),round(sum(v),1),round(sum(v)/len(v),3)) for k,v in sorted(by.items())})
# exits after 16:10 ET
import datetime as dt
from zoneinfo import ZoneInfo
ET=ZoneInfo('America/New_York')
late=collections.Counter(); latest={}
for r in rows:
    x=dt.datetime.fromtimestamp(r['xt'],ET); e=dt.datetime.fromtimestamp(r['et'],ET)
    if r['s']!='P' and (x.hour*60+x.minute>16*60+10 or x.date().isoformat()!=r['day']):
        late[r['s']]+=1
    latest[r['s']]=max(latest.get(r['s'],'00:00'), x.strftime('%H:%M') if x.date().isoformat()==r['day'] else 'nextday')
    if r['xt']<r['et']: print('exit before entry',r)
print('exits after 16:10 ET / other day (non-P):',late,'latest',latest)
