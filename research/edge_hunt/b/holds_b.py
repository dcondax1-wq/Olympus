import pickle, json
import numpy as np
from feat import *
import e2_new_strats as E2
P = pickle.load(open("/tmp/claude-0/-home-user/985fb1ba-d48a-5b61-8251-6d2f2f33af8c/scratchpad/trades_b.pkl", "rb"))
B = DS.D()
holds = ['T_orb_far_eod|gex_p50_high', 'T_orb_far_r2|gex_p50_high', 'T_orb_mid_r2|gex_p33_high', 'T_orb_far_eod|ts_p33_high', 'T_orb_far_r2|ts_p33_high', 'T_orb_far_eod|all']
lit = DS.lit_daily()
for h in holds:
    T = P["cells"][h]
    print(h)
    for sp in ("H1", "H2", "2025", "2021-24", "2021-25"):
        s = DS.stats(T, sp)
        print("  ", sp, {k: s.get(k) for k in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "t")})
    print("   corr", DS.corr(T, "2026", lit), DS.corr(T, "2021-25", lit))
