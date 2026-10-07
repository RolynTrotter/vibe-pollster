"""Electoral systems: turn vote totals into seats.

Currently implements highest-averages list PR (D'Hondt / Israel's Bader-Ofer)
with a legal threshold and pairwise surplus-vote (apparentment) agreements.
Add other systems here (Sainte-Lague, largest remainder, FPTP by district)
with the same signature: votes -> seats.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def dhondt(votes: np.ndarray, seats: int) -> np.ndarray:
    """D'Hondt allocation of `seats` among lists with `votes` (1-D).

    Bader-Ofer, Israel's method, is D'Hondt: start from the floor of the
    Hare-like quota then hand out remaining seats by highest average.
    """
    votes = np.asarray(votes, dtype=float)
    alloc = np.zeros(len(votes), dtype=int)
    if seats <= 0 or votes.sum() <= 0:
        return alloc
    q = votes.sum() / seats
    alloc = np.floor(votes / q).astype(int)
    while alloc.sum() < seats:
        alloc[np.argmax(votes / (alloc + 1))] += 1
    return alloc


def sainte_lague(votes: np.ndarray, seats: int) -> np.ndarray:
    votes = np.asarray(votes, dtype=float)
    alloc = np.zeros(len(votes), dtype=int)
    for _ in range(seats):
        alloc[np.argmax(votes / (2 * alloc + 1))] += 1
    return alloc


@dataclass
class ListPR:
    """National list PR with a threshold and surplus agreements.

    seats: total seats; threshold: percent of *all valid votes*;
    pairs: surplus-vote agreements as (a, b) list names. A pair only counts
    if both partners pass the threshold (Israeli rule).
    """
    seats: int = 120
    threshold: float = 3.25
    pairs: list[tuple[str, str]] = field(default_factory=list)
    method: str = "dhondt"

    def _div(self, v, s):
        return dhondt(v, s) if self.method == "dhondt" else sainte_lague(v, s)

    def allocate(self, votes, names: list[str]) -> np.ndarray:
        votes = np.asarray(votes, dtype=float)
        passed = votes >= self.threshold / 100 * votes.sum()
        v = np.where(passed, votes, 0.0)
        idx = {n: i for i, n in enumerate(names)}
        groups, used = [], set()
        for a, b in self.pairs:
            if a in idx and b in idx and passed[idx[a]] and passed[idx[b]] \
                    and idx[a] not in used and idx[b] not in used:
                groups.append([idx[a], idx[b]])
                used.update((idx[a], idx[b]))
        for i in range(len(names)):
            if passed[i] and i not in used:
                groups.append([i])
        gseats = self._div(np.array([v[g].sum() for g in groups]), self.seats)
        out = np.zeros(len(names), dtype=int)
        for g, s in zip(groups, gseats):
            if len(g) == 1:
                out[g[0]] = s
            else:
                out[g] = self._div(v[g], s)
        return out

    def allocate_many(self, votes: np.ndarray, names: list[str]) -> np.ndarray:
        """Row-wise allocation for an (n_draws, n_lists) array."""
        return np.vstack([self.allocate(row, names) for row in votes])
