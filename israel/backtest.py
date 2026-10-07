"""Leave-one-election-out backtest: how close would the model have been?

For each election 2015-2022, everything that is learned from data (pollster
ratings, the error model, the haredi correction) is re-learned from the
OTHER five elections only. The withheld election's polls are then averaged
as of N days before the vote (0 = final polls, 20 = where we are now in 2026)
and 20,000 elections are simulated under that election's real rules
(3.25% threshold, its actual surplus-vote agreements).

The averaging hyperparameters were tuned once on all six elections; the
tuning surface is flat (MAE 0.544-0.58), so this leaks very little.

python -m israel.backtest  ->  output/backtest.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from israel.backtest_data import ELECTIONS
from israel.calibrate import NOW, YEARS, weight_fn
from pollster.average import AvgParams, fit_average
from pollster.errors import calibrate
from pollster.ratings import rate
from pollster.simulate import ErrorModel, family_seat_sensitivity, simulate
from pollster.systems import ListPR

SEG = ["arab", "haredi", "rest"]


def profile_for(parties, family):
    """A simple segment profile (columns: parties + others), 2022 ballot-box shares."""
    cols = []
    for p in parties + ["others"]:
        f = family.get(p, "X")
        if f == "A":
            cols.append([1.0, 0.0, 0.0])
        elif p == "utj":
            cols.append([0.0, 0.94, 0.06])
        elif p == "shas":
            cols.append([0.01, 0.45, 0.54])
        elif p == "others":
            cols.append([0.05, 0.01, 0.94])
        else:
            cols.append([0.01, 0.01, 0.98])
    return np.array(cols).T


def run_one(eid, days_out, P, R, E, params, n=20000):
    e = ELECTIONS[eid]
    train = [k for k in ELECTIONS if k != eid]
    ratings, _, _ = rate(P[P.election.isin(train)], R[R.election.isin(train)], YEARS, NOW)
    cal = calibrate(E[E.election.isin(train)])
    quality = dict(zip(ratings.pollster, ratings.quality))

    B = P[P.election == eid].copy()
    cut = (pd.Timestamp(e["date"]) - pd.Timedelta(days=days_out)).date().isoformat()
    B = B[B.date <= cut]
    B["w"] = weight_fn(B, quality)
    anchor = {h: 1.0 for h in B.pollster.unique()}
    avg = fit_average(B, cut, anchor, params)
    parties = [p for p in avg if p in set(R[R.election == eid].party)]
    mu = np.array([avg[p].level for p in parties])
    se = np.array([avg[p].se for p in parties])
    fam = e["family"]
    prof = profile_for(parties, fam)
    sysm = ListPR(120, 3.25, e["pairs"])
    har = [p for p in parties if fam[p] == "H"]
    arab = [p for p in parties if fam[p] == "A"]
    sens_h = family_seat_sensitivity(parties, mu, har, SEG, prof, "haredi", sysm)
    sens_a = family_seat_sensitivity(parties, mu, arab, SEG, prof, "arab", sysm) if arab else 1.0
    err = ErrorModel(sigma_bloc=cal["sigma_bloc"], drift_var_per_day=cal["drift_var_per_day"],
                     party_a=cal["party_a"], party_b=cal["party_b"],
                     seg_sigma={"haredi": cal["sigma_haredi"] / sens_h, "arab": cal["sigma_arab"] / sens_a},
                     party_shift={"shas": -cal["party_bias"]["shas"]["mean"] / 1.2})
    out = simulate(parties, mu, se, fam, debut=e["debut"], segments=SEG, profile=prof, err=err,
                   days_left=days_out, others_pct=1.5, system=sysm, n=n, seed=11)
    S = out["seats"]
    # point forecast: allocate the (corrected) average itself, like a pollster's projection
    mu_pt = mu.copy()
    for p, d in err.party_shift.items():
        if p in parties:
            mu_pt[parties.index(p)] += d
    point = sysm.allocate(np.append(mu_pt, 1.5), parties + ["others"])[:-1]
    actual = R[R.election == eid].set_index("party")
    rows = []
    for i, p in enumerate(parties):
        x = S[:, i]
        rows.append(dict(party=p, family=fam[p], actual=int(actual.seats[p]),
                         median=float(np.median(x)), mean=float(x.mean()),
                         p10=float(np.quantile(x, .1)), p90=float(np.quantile(x, .9)),
                         p_in=float((x > 0).mean()), point=int(point[i]), poll_seats=None))
    # naive baseline: plain mean of published seat projections in the final week before cutoff
    last = B[B.days_out <= days_out + 7]
    naive = last.groupby("party").seats.mean()
    for r in rows:
        r["poll_seats"] = float(naive.get(r["party"], np.nan))
    gov = [i for i, p in enumerate(parties) if fam[p] in ("N", "H")]
    g = S[:, gov].sum(1)
    gov_actual = int(sum(actual.seats[parties[i]] for i in gov))
    return dict(
        election=eid, days_out=days_out, n_polls=int(B.poll_id.nunique()), parties=rows,
        bloc=dict(actual=gov_actual, mean=float(g.mean()), p10=float(np.quantile(g, .1)),
                  p90=float(np.quantile(g, .9)), p61=float((g >= 61).mean()),
                  naive=float(sum(naive.get(parties[i], 0) for i in gov)),
                  pct_rank=float((g < gov_actual).mean() + 0.5 * (g == gov_actual).mean()),
                  point=int(sum(point[i] for i in gov))),
        trained_on=train, shas_fix=float(-cal["party_bias"]["shas"]["mean"]), sigma_bloc=cal["sigma_bloc"],
    )


def main():
    P = pd.read_csv("data/processed/backtest_polls.csv")
    R = pd.read_csv("data/processed/backtest_results.csv")
    E = pd.read_csv("data/processed/backtest_errors.csv")
    params = AvgParams(**json.load(open("data/processed/calibration.json"))["avg_params"])

    # sanity: the allocator reproduces every official result with that year's agreements
    for eid, e in ELECTIONS.items():
        r = R[R.election == eid]
        got = ListPR(120, 3.25, e["pairs"]).allocate(r.pct.values, r.party.tolist())
        assert (got == r.seats.values).all(), (eid, dict(zip(r.party, got)))
    print("allocator reproduces all six official results")

    res = []
    for d in [0, 20]:
        for eid in ELECTIONS:
            r = run_one(eid, d, P, R, E, params)
            res.append(r)
            df = pd.DataFrame(r["parties"])
            mae = (df.point - df.actual).abs().mean()
            mae_n = (df.poll_seats - df.actual).abs().mean()
            cover = ((df.actual >= df.p10) & (df.actual <= df.p90)).mean()
            b = r["bloc"]
            print(f"{eid:6s} d={d:2d} polls={r['n_polls']:3d}  party MAE model {mae:.2f} vs raw polls {mae_n:.2f}"
                  f"  80%-cover {cover:.0%}  brier(in) {((df.p_in - (df.actual > 0)) ** 2).mean():.3f}  bloc pt {b['point']} mean {b['mean']:.1f} [{b['p10']:.0f}-{b['p90']:.0f}] actual {b['actual']}"
                  f" (raw polls {b['naive']:.1f})  P(>=61) {b['p61']:.2f}")
    json.dump(res, open("output/backtest.json", "w"), indent=1)


if __name__ == "__main__":
    main()
