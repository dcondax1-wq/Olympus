import sys, json
sys.path.insert(0,'/home/user/wt-combored'); sys.path.insert(0,'/home/user/wt-combored/tools'); sys.path.insert(0,'/home/user/wt-combored/tools/money')
import combo_account as C
for a in ('b50','b25','r25'):
    P=C.plan(a)
    print(a,'E',json.dumps(P['E']))
    print(a,'F',json.dumps(P['F']))
    print(a,'z_eval keys', {k:P['z_eval'][k] for k in P['z_eval'] if not isinstance(P['z_eval'][k],dict)}, json.dumps(P['z_eval'].get('two_week'))[:600])
    print(a,'z_funded', json.dumps(P['z_funded'])[:600])
    print(a,'a_spec rules', json.dumps(P['a_spec'].get('rules'))[:600])
    print(a,'acct_f', P['acct_f'])
    print()
