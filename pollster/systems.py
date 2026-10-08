"""Electoral systems: turn vote totals into seats.

National list PR with a legal threshold: D'Hondt (Israel's Bader-Ofer, the
Netherlands), Sainte-Lague (Germany, New Zealand), modified Sainte-Lague
(Sweden), Hare largest remainder (Denmark), plus pairwise surplus-vote
(apparentment) agreements and threshold exemptions (Germany's three-seat
rule, New Zealand electorates). District systems (FPTP etc.) are not here yet.
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


def highest_averages(votes: np.ndarray, seats: int, method: str = "sainte_lague",
                     first_divisor: float = 1.0) -> np.ndarray:
    """Divisor methods: 'dhondt' (1,2,3..), 'sainte_lague' (1,3,5..), or
    'modified_sainte_lague' (first divisor `first_divisor`, e.g. 1.2 or 1.4, then 3,5..).
    Starts near the quota and adds seats by highest average (exact for divisor methods)."""
    votes = np.asarray(votes, dtype=float)
    out = np.zeros(len(votes), dtype=int)
    if seats <= 0 or votes.sum() <= 0:
        return out
    if method == "dhondt":
        return dhondt(votes, seats)
    q = votes.sum() / seats
    out = np.maximum(np.floor(votes / q).astype(int) - 1, 0)
    fd = first_divisor if method == "modified_sainte_lague" else 1.0
    while out.sum() < seats:
        div = np.where(out == 0, fd, 2 * out + 1)
        out[np.argmax(np.where(votes > 0, votes / div, -1))] += 1
    while out.sum() > seats:            # cannot happen from the lower start; kept for safety
        out[np.argmin(np.where(out > 0, votes / (2 * out - 1), np.inf))] -= 1
    return out


def sainte_lague(votes: np.ndarray, seats: int) -> np.ndarray:
    return highest_averages(votes, seats, "sainte_lague")


def hare(votes: np.ndarray, seats: int) -> np.ndarray:
    """Largest remainder with the Hare quota."""
    votes = np.asarray(votes, dtype=float)
    out = np.zeros(len(votes), dtype=int)
    if seats <= 0 or votes.sum() <= 0:
        return out
    q = votes / votes.sum() * seats
    out = np.floor(q).astype(int)
    rem = q - out
    for i in np.argsort(-rem)[: seats - out.sum()]:
        out[i] += 1
    return out


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
    method: str = "dhondt"          # dhondt | sainte_lague | modified_sainte_lague | hare
    first_divisor: float = 1.0      # for modified_sainte_lague
    exempt: list[str] = field(default_factory=list)  # lists that qualify regardless of threshold

    def _div(self, v, s):
        if self.method == "dhondt":
            return dhondt(v, s)
        if self.method == "hare":
            return hare(v, s)
        return highest_averages(v, s, self.method, self.first_divisor)

    def allocate(self, votes, names: list[str]) -> np.ndarray:
        votes = np.asarray(votes, dtype=float)
        passed = votes >= self.threshold / 100 * votes.sum()
        for e in self.exempt:
            if e in names:
                passed[names.index(e)] = True
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


def system_from_spec(spec: dict) -> ListPR:
    return ListPR(seats=spec["seats"], threshold=spec["threshold"], pairs=spec.get("pairs", []),
                  method=spec["method"], first_divisor=spec.get("first_divisor", 1.0),
                  exempt=spec.get("exempt", []))
