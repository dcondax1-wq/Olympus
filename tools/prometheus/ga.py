"""The PROMETHEUS genetic algorithm: pure, seeded, deterministic, with every creature's lineage kept.

A genome is a tuple of grid indices (tools/prometheus/genome.py); `sizes[i]` is the number of grid points of gene i.
  generation 0   the live genome + `n_spark` mutants of it (heavy mutation) + random genomes
  each next one  `elite` best creatures survive as they are; the rest are children: tournament selection (k), uniform
                 crossover (rate `cx`), then each gene mutates with probability `pm` by +/- 1..3 grid steps (clamped)
The evaluate callable returns (fitness, metrics) for a genome; it is called once per creature (cache it outside).
Same seed + same evaluate = the same history, creature for creature.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Creature:
    id: int
    gen: int
    genome: tuple
    parents: tuple = ()          # creature ids (1 = mutant / elite, 2 = crossover child, 0 = generation 0)
    mutated: tuple = ()          # gene indices changed by mutation
    origin: str = "random"       # live | spark | random | elite | child
    fit: float = 0.0
    metrics: dict = field(default_factory=dict)


@dataclass
class GAConfig:
    pop: int = 24
    gens: int = 20
    elite: int = 2
    k: int = 3
    cx: float = 0.9
    pm: float = 0.12
    n_spark: int = 11
    seed: int = 7


def _mutate(rng, g, sizes, pm, force=False):
    g = list(g)
    hit = []
    for i, n in enumerate(sizes):
        if rng.random() < pm:
            step = rng.choice((1, 1, 1, 2, 2, 3)) * rng.choice((-1, 1))
            v = max(0, min(n - 1, g[i] + step))
            if v != g[i]:
                g[i] = v
                hit.append(i)
    if force and not hit:                       # a spark always changes at least one gene
        i = rng.randrange(len(sizes))
        v = g[i] + (1 if g[i] < sizes[i] - 1 else -1)
        g[i] = v
        hit.append(i)
    return tuple(g), tuple(hit)


def evolve(evaluate, sizes, base, cfg: GAConfig = GAConfig(), on_gen=None):
    """Run the GA. Returns the list of generations (each a list of Creature, best first)."""
    rng = random.Random(cfg.seed)
    sizes = tuple(int(n) for n in sizes)
    nid = [0]

    def make(gen, genome, parents=(), mutated=(), origin="child"):
        assert len(genome) == len(sizes) and all(0 <= v < n for v, n in zip(genome, sizes)), genome
        c = Creature(nid[0], gen, tuple(int(v) for v in genome), tuple(parents), tuple(mutated), origin)
        nid[0] += 1
        c.fit, c.metrics = evaluate(c.genome)
        return c

    pop = [make(0, tuple(base), origin="live")]
    for _ in range(min(cfg.n_spark, cfg.pop - 1)):
        g, hit = _mutate(rng, base, sizes, 0.35, force=True)
        pop.append(make(0, g, (), hit, "spark"))
    while len(pop) < cfg.pop:
        pop.append(make(0, tuple(rng.randrange(n) for n in sizes), origin="random"))
    pop.sort(key=lambda c: (-c.fit, c.id))
    history = [pop]
    if on_gen:
        on_gen(0, pop)

    def pick(P):
        best = None
        for _ in range(cfg.k):
            c = P[rng.randrange(len(P))]
            if best is None or c.fit > best.fit or (c.fit == best.fit and c.id < best.id):
                best = c
        return best

    for gen in range(1, cfg.gens):
        prev = history[-1]
        nxt = [make(gen, c.genome, (c.id,), (), "elite") for c in prev[:cfg.elite]]
        while len(nxt) < cfg.pop:
            a = pick(prev)
            if rng.random() < cfg.cx:
                b = pick(prev)
                child = tuple(x if rng.random() < 0.5 else y for x, y in zip(a.genome, b.genome))
                parents = (a.id, b.id) if a.id != b.id else (a.id,)
            else:
                child, parents = a.genome, (a.id,)
            child, hit = _mutate(rng, child, sizes, cfg.pm)
            nxt.append(make(gen, child, parents, hit, "child"))
        nxt.sort(key=lambda c: (-c.fit, c.id))
        history.append(nxt)
        if on_gen:
            on_gen(gen, nxt)
    return history


def all_creatures(history):
    return [c for gen in history for c in gen]


def champion(history):
    """The fittest creature ever made (the earliest one on a tie)."""
    return min(all_creatures(history), key=lambda c: (-c.fit, c.id))


def lineage(history, cid):
    """The champion's family tree as a list of creature ids from it back to generation 0 (first parent at each step, the
    fitter parent of a crossover), plus every ancestor id (both sides) for the trail."""
    by = {c.id: c for c in all_creatures(history)}
    line, seen, todo = [], set(), [cid]
    cur = cid
    while cur is not None:
        line.append(cur)
        ps = by[cur].parents
        cur = max(ps, key=lambda p: (by[p].fit, -p)) if ps else None
    while todo:
        x = todo.pop()
        if x in seen:
            continue
        seen.add(x)
        todo.extend(by[x].parents)
    return line, sorted(seen)


def hall_of_fame(history, n=10):
    """The n fittest distinct genomes (the first creature that carried each)."""
    seen, out = set(), []
    for c in sorted(all_creatures(history), key=lambda c: (-c.fit, c.id)):
        if c.genome in seen:
            continue
        seen.add(c.genome)
        out.append(c)
        if len(out) == n:
            break
    return out
