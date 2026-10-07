"""Turnout layer: translate group-level turnout changes into party shares.

A composition matrix V[s, p] gives baseline votes (as % of all valid votes)
cast by segment s for party p. Polls tell us column totals (party shares);
census/results data tell us roughly who votes for whom. A turnout scenario
multiplies rows (segment turnout) and/or columns (a party's supporters
staying home) and renormalises.
"""
from __future__ import annotations

import numpy as np


def ipf(seed, row_targets, col_targets, iters: int = 500, tol: float = 1e-10):
    """Iterative proportional fitting of a non-negative matrix to margins."""
    X = np.asarray(seed, dtype=float).copy()
    r = np.asarray(row_targets, dtype=float)
    c = np.asarray(col_targets, dtype=float)
    c = c / c.sum() * r.sum()
    for _ in range(iters):
        X *= (r / X.sum(axis=1).clip(1e-300))[:, None]
        X *= (c / X.sum(axis=0).clip(1e-300))[None, :]
        if np.abs(X.sum(axis=1) - r).max() < tol:
            break
    return X


def profile(V: np.ndarray) -> np.ndarray:
    """Column-normalised composition: share of each party's vote from each segment."""
    V = np.asarray(V, dtype=float)
    return V / V.sum(axis=0, keepdims=True).clip(1e-300)


def apply_turnout(shares, prof, seg_mult=None, party_mult=None):
    """New vote shares (%) after turnout changes.

    shares: (..., P) baseline party shares; prof: (S, P) composition profile
    (columns sum to 1); seg_mult: (..., S) multipliers on each segment's turnout;
    party_mult: (..., P) multipliers on each party's own supporters (e.g. 0.9 =
    10% of its would-be voters stay home). Leading dims broadcast (draws).
    """
    shares = np.asarray(shares, dtype=float)
    S, P = prof.shape
    V = shares[..., None, :] * prof                       # (..., S, P)
    if seg_mult is not None:
        V = V * np.asarray(seg_mult, dtype=float)[..., :, None]
    if party_mult is not None:
        V = V * np.asarray(party_mult, dtype=float)[..., None, :]
    out = V.sum(axis=-2)
    return out / out.sum(axis=-1, keepdims=True) * 100
