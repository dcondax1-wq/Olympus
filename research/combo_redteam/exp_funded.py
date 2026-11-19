import sys, json
import numpy as np
sys.path.insert(0, '/tmp/claude-0/-home-user/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/rt')
import rt_sim as R
DZ, DZA = R.days_of({'Z'}), R.days_of({'Z', 'A'})
for sp in ('H1', 'H2', 'REF'):
    a, z = R.SPANS[sp]
    P = R.day_paths(a, z, 2000, seed=707)
    for nm, D in (('Z', DZ), ('Z+A', DZA)):
        first, lost, grad = [], 0, 0
        for seq in P:
            f = R.Funded(); fp = None
            for k, si in enumerate(seq):
                ev, x = f.step(D[si])
                if x and fp is None:
                    fp = k + 1
                if ev in ('lost', 'stuck', 'grad'):
                    lost += ev != 'grad'; grad += ev == 'grad'
                    break
            first.append(fp)
        n = len(P)
        print(sp, nm, 'first payout <=30 sessions', round(100 * sum(1 for x in first if x and x <= 30) / n, 1), '%',
              '| lost/stuck in 6 mo', round(100 * lost / n, 1), '% | 5 payouts in 6 mo', round(100 * grad / n, 1), '%', flush=True)
