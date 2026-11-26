"""DP policy table from dp_tables.npz: $ risk as % of the room, by room left and $ still needed (start of the eval / 10 trades left).
    python -X utf8 research/evalsizer/table.py"""
import os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
P = {"mffu_builder_50k": (3000, 2000, 100, 50.0), "mffu_builder_25k": (1500, 1000, 100, 25.0), "mffu_rapid_eod_25k": (1500, 1000, 100, 25.0)}


def show(plan, k, A, n_list):
    tgt, mll, lock, step = P[plan]
    bs, fs = np.arange(-mll, tgt + step / 2, step), np.arange(-mll, lock + step / 2, step)
    out = []
    for n in n_list:
        n = min(n, A.shape[0] - 1)
        out.append(f"\n{plan} {k}: {n} LIT trades left; rows = profit now, cols = room to the floor; cell = % of room risked")
        rooms = [0.15, 0.3, 0.5, 0.75, 1.0, 1.5]
        out.append("profit\\room " + " ".join(f"{int(x * mll):>6d}" for x in rooms))
        for pf in (-0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 0.9):
            b = pf * tgt
            cells = []
            for x in rooms:
                room = x * mll
                fl = b - room
                ok = -mll - 1e-9 <= fl <= lock + 1e-9 and (room <= mll + 1e-9 or abs(fl - lock) < 1e-6 or fl <= lock)
                ok = ok and (room <= mll + 1e-9 or b - mll > lock)
                if not ok:
                    cells.append("     -")
                    continue
                fi, bi = int(round((fl + mll) / step)), int(round((b + mll) / step))
                cells.append(f"{100 * A[n, fi, bi] / room:5.0f}%")
            out.append(f"{int(b):>11d} " + " ".join(cells))
    return "\n".join(out)


if __name__ == "__main__":
    Z = np.load(os.path.join(HERE, "dp_tables.npz"))
    txt = []
    for key in Z.files:
        plan, k = key.rsplit("_", 1)
        A = Z[key]
        txt.append(show(plan, k, A, [A.shape[0] - 1, 10, 3]))
    s = "\n".join(txt)
    print(s)
    open(os.path.join(HERE, "dp_table.txt"), "w", encoding="utf-8").write(s)
