"""Per-poll weights, following FiveThirtyEight's published polling-average rules.

* sample size: weight proportional to sqrt(n), n capped at 5,000; missing n is
  imputed with the house median, then the overall median
* frequency: a house's polls within a 14-day window share one poll's weight
  (two polls -> 0.5 each, three -> 1/3 each)
* house quality: a multiplier from pollster ratings (see ratings.py)
* house family: houses that share a methodology can be made to share weight
Recency is handled by the trend estimator (average.py), not here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sample_size_weight(n: pd.Series, house: pd.Series, cap: int = 5000) -> pd.Series:
    n = n.astype(float).copy()
    n = n.fillna(n.groupby(house).transform("median")).fillna(n.median()).fillna(600)
    n = n.clip(upper=cap)
    return np.sqrt(n / n.median())


def frequency_weight(dates: pd.Series, house: pd.Series, window: int = 14) -> pd.Series:
    d = pd.to_datetime(dates)
    out = pd.Series(1.0, index=dates.index)
    for _, idx in house.groupby(house).groups.items():
        dd = d.loc[idx]
        for i in idx:
            k = ((dd - d.loc[i]).abs().dt.days < window / 2 + 0.5).sum()
            out.loc[i] = 1.0 / max(k, 1)
    return out


def poll_weights(polls: pd.DataFrame, house_quality: dict | None = None,
                 cap: int = 5000, window: int = 14) -> pd.Series:
    """Weight per poll (one row per poll; needs columns date, pollster, n)."""
    w = sample_size_weight(polls["n"], polls["pollster"], cap)
    w = w * frequency_weight(polls["date"], polls["pollster"], window)
    if house_quality:
        w = w * polls["pollster"].map(house_quality).fillna(1.0)
    return w
