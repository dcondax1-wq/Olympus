"""Act on the two sign-stable discoveries: London H/L raids hurt; the 1H discount/premium check hurts (yet is weighted +2)."""
from multiprocessing import Pool

from study_be import run

SEGS = [("NQ fut 2026", "NQ", None, None), ("CFD Q4 2023", "NQX", None, "2023-12-31"), ("CFD Q1 2024", "NQX", "2024-01-01", "2024-12-31"),
        ("CFD Q4 2025", "NQX", "2025-01-01", "2025-12-31")]
V = [("current", {}),
     ("grade: pd weight 0", {"g_pd": 0}), ("grade: pd weight 1", {"g_pd": 1}), ("grade: pd flipped (-2)", {"g_pd": -2}),
     ("grade: London -1", {"g_london": 1}), ("grade: London -2", {"g_london": 2}), ("skip London raids", {"skip_london": True}),
     ("pd 0 + London -2", {"g_pd": 0, "g_london": 2}), ("pd 0 + skip London", {"g_pd": 0, "skip_london": True}),
     ("score: w_pd 0", {"w_pd": 0}), ("score: w_pd 0 + pd 0 + London -2", {"w_pd": 0, "g_pd": 0, "g_london": 2}),
     ("pd flipped + skip London", {"g_pd": -2, "skip_london": True})]

if __name__ == "__main__":
    import study_be
    study_be.SEGS[:] = SEGS
    with Pool(12) as pool:
        out = pool.map(run, V)
    print(f"{'variant':34s} | " + " | ".join(f"{l:44s}" for l, *_ in SEGS))
    for n, o in out:
        print(f"{n:34s} | " + " | ".join(f"{x:44s}" for x in o))
