"""Best-first branch-and-bound search over condition combinations (pure numpy; knows nothing about markets).

Input: one value per trade (x, $ per micro) and a bool matrix of conditions (which trades each condition keeps), with
the feature each condition belongs to. A node is a set of conditions (each feature at most once); its trades are the
trades every condition keeps.

  score(S)  = (mean(S) - mean(root)) * n / (n + k)     mean excess over the root, shrunk toward 0 for small n
  bound(S)  = max over m in [min_n, n] of (mean of the m best values in S - mean(root)) * m / (m + k)

Any descendant D of S is a subset of S with |D| = m >= min_n, and no m-subset has a higher mean than the m best values,
so bound(S) >= score(D) for every descendant: a node whose bound is not above the best score found so far can never
lead to a better rule, and is CUT. Nodes are expanded best score first, up to `max_expand` expansions per tree.

Node status: EXPANDED (children generated), CUT (bound cannot beat the best), LEAF (at max depth), OPEN (the expansion
budget ran out before it was looked at). Children with fewer than min_n trades, children that drop no trade, and
condition sets already in the tree are not nodes.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np

OPEN, EXPANDED, CUT, LEAF = 0, 1, 2, 3
STATUS_NAMES = ("open", "expanded", "cut", "leaf")
EPS = 1e-9


@dataclass(frozen=True)
class SearchConfig:
    min_n: int = 60              # trades a rule needs in the training data
    shrink_k: float = 30.0       # score shrink: n / (n + k)
    max_depth: int = 5
    max_expand: int = 4000       # node expansions per tree (most trees finish below it: the search is then exhaustive)


@dataclass
class Tree:
    """A searched tree, nodes in creation order (node 0 = the root)."""
    parent: list = field(default_factory=list)
    cond: list = field(default_factory=list)          # the condition this node adds (-1 for the root)
    depth: list = field(default_factory=list)
    n: list = field(default_factory=list)
    mean: list = field(default_factory=list)          # raw mean value of the node's trades
    score: list = field(default_factory=list)
    bound: list = field(default_factory=list)
    status: list = field(default_factory=list)
    best: int = 0
    root_mean: float = 0.0
    counts: dict = field(default_factory=dict)        # too_small, no_op, duplicate

    def __len__(self):
        return len(self.parent)

    def path(self, node: int) -> list[int]:
        """Node ids from the root to `node`."""
        out = [node]
        while self.parent[out[-1]] >= 0:
            out.append(self.parent[out[-1]])
        return out[::-1]

    def conds_of(self, node: int) -> list[int]:
        """The conditions on the way to `node`, in the order the search added them."""
        return [self.cond[i] for i in self.path(node)[1:]]

    def stats(self) -> dict:
        """Headline numbers: nodes (without the root), how they ended, the CUT share, the best and the root's bound."""
        st = np.array(self.status[1:], dtype=int)
        nodes = len(st)
        out = {name: int((st == code).sum()) for code, name in enumerate(STATUS_NAMES)}
        out.update(nodes=nodes, cut_pct=round(100 * out["cut"] / nodes, 1) if nodes else 0.0,
                   best=float(self.score[self.best]), bound=float(self.bound[0]), best_depth=int(self.depth[self.best]),
                   **self.counts)
        return out


def scores_and_bounds(xs_desc: np.ndarray, masks: np.ndarray, root_mean: float, min_n: int, k: float):
    """For each row of `masks` (trades in the order of xs_desc, highest value first): n, mean, score and bound.
    Rows with n < min_n get score / bound -inf."""
    masks = np.atleast_2d(masks)
    cnt = np.cumsum(masks, axis=1)
    tot = np.cumsum(np.where(masks, xs_desc, 0.0), axis=1)
    n = cnt[:, -1] if masks.shape[1] else np.zeros(len(masks), dtype=int)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(n > 0, tot[:, -1] / np.maximum(n, 1), np.nan) if masks.shape[1] else np.full(len(masks), np.nan)
        score = np.where(n >= min_n, (mean - root_mean) * n / (n + k), -np.inf)
        top = np.where(cnt >= min_n, (tot / np.maximum(cnt, 1) - root_mean) * cnt / (cnt + k), -np.inf)
    bound = top.max(axis=1) if masks.shape[1] else np.full(len(masks), -np.inf)
    return n, mean, score, bound


def search(x: np.ndarray, cond_masks: np.ndarray, cond_feature: np.ndarray, cfg: SearchConfig = SearchConfig()) -> Tree:
    """Grow the tree for one root. x: value per trade; cond_masks: (C x n) bool; cond_feature: (C,) feature of each."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(-x, kind="stable")
    xs = x[order]
    cm = np.asarray(cond_masks, dtype=bool)[:, order]
    cf = np.asarray(cond_feature, dtype=int)
    root_mean = float(x.mean()) if len(x) else 0.0
    t = Tree(root_mean=root_mean, counts={"too_small": 0, "no_op": 0, "duplicate": 0})
    all_rows = np.ones((1, len(x)), dtype=bool)
    n0, _, _, b0 = scores_and_bounds(xs, all_rows, root_mean, cfg.min_n, cfg.shrink_k)
    _add(t, -1, -1, 0, int(n0[0]), root_mean, 0.0, float(b0[0]))
    masks = {0: all_rows[0]}
    feats_used = {0: frozenset()}
    seen = {frozenset()}
    heap = [(-0.0, 0)]
    expansions = 0
    while heap and expansions < cfg.max_expand:
        _, node = heapq.heappop(heap)
        if t.bound[node] <= t.score[t.best] + EPS:
            t.status[node] = CUT
            masks.pop(node, None)
            continue
        if t.depth[node] >= cfg.max_depth:
            t.status[node] = LEAF
            masks.pop(node, None)
            continue
        expansions += 1
        t.status[node] = EXPANDED
        parent_mask = masks.pop(node)
        used = feats_used[node]
        allowed = np.array([c for c in range(len(cf)) if cf[c] not in used], dtype=int)
        if not len(allowed):
            continue
        child = cm[allowed] & parent_mask
        n, mean, score, bound = scores_and_bounds(xs, child, root_mean, cfg.min_n, cfg.shrink_k)
        mine = set(t.conds_of(node))
        for i, c in enumerate(allowed):
            if n[i] < cfg.min_n:
                t.counts["too_small"] += 1
                continue
            if n[i] == t.n[node]:
                t.counts["no_op"] += 1
                continue
            key = frozenset(mine | {int(c)})
            if key in seen:
                t.counts["duplicate"] += 1
                continue
            seen.add(key)
            cid = _add(t, node, int(c), t.depth[node] + 1, int(n[i]), float(mean[i]), float(score[i]), float(bound[i]))
            if score[i] > t.score[t.best] + EPS:
                t.best = cid
            if bound[i] <= t.score[t.best] + EPS:
                t.status[cid] = CUT
                continue
            masks[cid] = child[i]
            feats_used[cid] = used | {int(cf[c])}
            heapq.heappush(heap, (-float(score[i]), cid))
    for _, node in heap:                     # the budget ran out: what could still beat the best stays OPEN
        if t.bound[node] <= t.score[t.best] + EPS:
            t.status[node] = CUT
        elif t.depth[node] >= cfg.max_depth:
            t.status[node] = LEAF
    return t


def _add(t: Tree, parent: int, cond: int, depth: int, n: int, mean: float, score: float, bound: float) -> int:
    t.parent.append(parent); t.cond.append(cond); t.depth.append(depth); t.n.append(n)
    t.mean.append(mean); t.score.append(score); t.bound.append(bound); t.status.append(OPEN)
    return len(t.parent) - 1


def subset_mean(x: np.ndarray, cond_masks: np.ndarray, conds: list[int]) -> tuple[int, float]:
    """n and mean of the trades every condition in `conds` keeps (for test-period checks of a found rule)."""
    keep = np.ones(len(x), dtype=bool)
    for c in conds:
        keep &= cond_masks[c]
    n = int(keep.sum())
    return n, (float(np.asarray(x)[keep].mean()) if n else float("nan"))
