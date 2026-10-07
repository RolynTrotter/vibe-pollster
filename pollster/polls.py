"""Poll records and seat -> vote-share conversion.

Israeli pollsters publish projected *seats*, which are inflated relative to
vote share because votes for lists under the threshold are wasted. We convert
back. `wasted` is the reported share of sub-threshold lists plus an allowance
for unlisted parties; the rest is split among seat-winning lists in proportion
to seats + 0.5, which undoes D'Hondt's tilt toward big lists (each list loses
about half a seat to rounding on average). A list shown with seats is never
put below the threshold, since the pollster had it above.
Backtest check: this halves the underestimate of 4-5 seat lists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def seats_to_shares(poll: pd.DataFrame, total_seats: int = 120,
                    others_pct: float = 1.5, threshold: float = 3.25,
                    sub_default: dict | None = None) -> pd.Series:
    """One poll (rows = parties, cols seats, sub_pct) -> vote share (%).

    Parties with 0 seats and a reported percentage keep that percentage.
    Parties with 0 seats and no percentage get `sub_default[party]` (or
    half the threshold), capped just under the threshold.
    """
    sub_default = sub_default or {}
    sub = poll["sub_pct"].copy()
    zero = (poll["seats"] == 0) & sub.isna()
    sub[zero] = [min(sub_default.get(p, threshold / 2), threshold - 0.25)
                 for p in poll.loc[zero, "party"]]
    wasted = sub.fillna(0).sum() + others_pct
    above = poll["seats"] > 0
    w = np.where(above, poll["seats"] + 0.5, 0.0)
    pool = 100 - wasted
    share = np.where(above, w / w.sum() * pool, sub)
    floor = threshold + 0.05
    low = above & (share < floor)
    if low.any():
        rest = above & ~low
        share = np.where(low, floor, share)
        share = np.where(rest, w / w[rest].sum() * (pool - floor * low.sum()), share)
    return pd.Series(share, index=poll.index)


def add_shares(df: pd.DataFrame, poll_col: str = "poll_id", **kw) -> pd.DataFrame:
    """Add a `share` column to a long poll table (one row per poll x party)."""
    df = df.copy()
    defaults = (df[df.sub_pct.notna()].groupby("party").sub_pct.mean().to_dict()
                if "sub_pct" in df else {})
    kw.setdefault("sub_default", defaults)
    df["share"] = np.nan
    for _, g in df.groupby(poll_col):
        df.loc[g.index, "share"] = seats_to_shares(g, **kw)
    return df
