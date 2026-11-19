import sys, json
sys.path.insert(0,'/home/user/wt-combored'); sys.path.insert(0,'/home/user/wt-combored/tools'); sys.path.insert(0,'/home/user/wt-combored/tools/money')
import combo_account as C
from engine import account_b as EAB
for a in ('b50','b25'):
    P=C.plan(a)
    c=EAB.sizing_cfg(P['a_spec'])
    print(a,'ATLAS eval cfg', {k:v for k,v in c.items() if not isinstance(v,dict) and 'note' not in k}, json.dumps(c.get('two_week')), json.dumps(c.get('guard')), json.dumps(c.get('safe_eval'))[:300])
    f=EAB.funded_cfg(P['a_spec_f'])
    print(a,'ATLAS funded cfg', json.dumps(f.get('funded')), json.dumps(f.get('acct')))
    print(a, 'a_spec keys', {k:v for k,v in P['a_spec'].items() if k!='rules'})
