"""Calibrate the Israeli model on 2015-2022: tune the average, rate pollsters,
measure how the average missed, and fit the error model.

python -m israel.calibrate [--retune]
Writes data/processed/{tuning.csv, pollster_ratings.csv, backtest_errors.csv,
calibration.json}.
"""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict

import pandas as pd

from israel.backtest_data import ELECTIONS
from pollster.average import AvgParams, fit_average, tune
from pollster.errors import average_errors, calibrate
from pollster.ratings import rate
from pollster.weights import poll_weights

ED = {k: v["date"].isoformat() for k, v in ELECTIONS.items()}
YEARS = {k: v["date"].year + v["date"].timetuple().tm_yday / 365 for k, v in ELECTIONS.items()}
NOW = 2026 + 300 / 365


def weight_fn(B: pd.DataFrame, quality=None) -> pd.Series:
    one = B.drop_duplicates("poll_id").copy()
    if "n" not in one:
        one["n"] = float("nan")
    w = poll_weights(one, quality)
    return B.poll_id.map(dict(zip(one.poll_id, w)))


def main(retune: bool = False):
    P = pd.read_csv("data/processed/backtest_polls.csv")
    R = pd.read_csv("data/processed/backtest_results.csv")

    # 1. hyperparameters
    if retune:
        grid = [AvgParams(bandwidth=b, half_life=h, degree=d, mix=m)
                for b, h, d, m in itertools.product([4, 7, 12, 20], [4, 7, 14, 28], [0, 1], [0.0, 0.8])]
        best, scores = tune(P, ED, weight_fn, grid)
        pd.DataFrame([dict(mae=s, **asdict(p)) for s, p in scores]).to_csv(
            "data/processed/tuning.csv", index=False)
    T = pd.read_csv("data/processed/tuning.csv").sort_values("mae")
    # The surface is flat (MAE 0.544-0.58 across the grid). Among near-ties
    # (within 0.002) prefer the smoothest: longest EWMA half-life, then the
    # median bandwidth, so a single fresh poll can't swing the average.
    top = T[T.mae <= T.mae.min() + 0.002]
    top = top[top.half_life == top.half_life.max()]
    row = top.iloc[(top.bandwidth - top.bandwidth.median()).abs().argsort().iloc[0]]
    params = AvgParams(bandwidth=float(row.bandwidth), half_life=float(row.half_life),
                       degree=int(row.degree), mix=float(row["mix"]))
    print("average params:", params, f"(MAE {row.mae:.3f}; grid range {T.mae.min():.3f}-{T.mae.max():.3f})")

    # 2. pollster ratings
    ratings, poll_err, base = rate(P, R, YEARS, NOW)
    ratings.to_csv("data/processed/pollster_ratings.csv", index=False)
    poll_err.to_csv("data/processed/backtest_poll_errors.csv", index=False)

    # 3. how the (consensus) average missed, at several horizons
    avgs = {}
    for eid, edate in ED.items():
        B = P[P.election == eid].copy()
        B["w"] = weight_fn(B)
        anchor = {h: 1.0 for h in B.pollster.unique()}
        for d in [0, 7, 14, 21, 28]:
            cut = (pd.Timestamp(edate) - pd.Timedelta(days=d)).date().isoformat()
            past = B[B.date <= cut]
            if past.poll_id.nunique() < 5:
                continue
            fa = fit_average(past, cut, anchor, params)
            avgs[(eid, d)] = {k: v.level for k, v in fa.items()}
    fam = {k: v["family"] for k, v in ELECTIONS.items()}
    E = average_errors(avgs, R, fam)
    E.to_csv("data/processed/backtest_errors.csv", index=False)
    cal = calibrate(E)
    cal["avg_params"] = asdict(params)
    cal["field_bloc_rms_polls"] = ratings.attrs["field_bloc_rms"]
    cal["base_party_error"] = base
    json.dump(cal, open("data/processed/calibration.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in cal.items() if not isinstance(v, dict)}, indent=1))
    print(pd.DataFrame(cal["by_election"]))


if __name__ == "__main__":
    main(retune="--retune" in sys.argv)
