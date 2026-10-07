"""Calibrate a correlated forecast-error model from past elections.

Polls miss in groups. We decompose each past election's polling-average error
into
  bloc swing    x: votes moving between the governing bloc (N+H) and the
                   opposition (O): N+H gets +x, O gets -x
  family shocks:  extra error for the haredi (H) and Arab (A) families
  party noise:    what's left, with variance a + b * size
and measure how the bloc error grows with days to the election (drift).
All quantities are in seats (vote share x 1.2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def average_errors(avgs: dict, results: pd.DataFrame, family: dict, seats=120):
    """avgs: {(election, days_out): {party: level %}} -> long error table."""
    res = results.set_index(["election", "party"]).pct
    rows = []
    for (e, d), lv in avgs.items():
        for p, v in lv.items():
            if (e, p) in res.index:
                rows.append(dict(election=e, days_out=d, party=p, avg=v,
                                 result=res[(e, p)], family=family[e][p],
                                 err=(v - res[(e, p)]) * seats / 100))
    return pd.DataFrame(rows)


def decompose(E: pd.DataFrame) -> pd.DataFrame:
    g = E.groupby(["election", "days_out"])
    out = g.apply(lambda x: pd.Series({
        "N": x.loc[x.family == "N", "err"].sum(),
        "H": x.loc[x.family == "H", "err"].sum(),
        "A": x.loc[x.family == "A", "err"].sum(),
        "O": x.loc[x.family == "O", "err"].sum(),
        "S": x.loc[x.family == "S", "err"].sum(),
    }), include_groups=False).reset_index()
    out["bloc_swing"] = (out.N + out.H - out.O) / 2
    out["N_only"] = (out.N - out.O) / 2
    return out


def calibrate(E: pd.DataFrame) -> dict:
    D = decompose(E)
    D0 = D[D.days_out == 0]
    rms = lambda s: float(np.sqrt(np.mean(np.square(s))))
    # party residuals after removing family totals spread by size
    E0 = E[E.days_out == 0].copy()
    fam_tot = E0.groupby(["election", "family"]).err.transform("sum")
    fam_size = E0.groupby(["election", "family"]).result.transform("sum")
    E0["resid"] = E0.err - fam_tot * E0.result / fam_size
    size = E0.result * 1.2
    X = np.column_stack([np.ones(len(E0)), size])
    a, b = np.linalg.lstsq(X, E0.resid ** 2, rcond=None)[0]
    a, b = max(a, 0.05), max(b, 0.0)
    # drift: growth of bloc-swing variance with days out
    v = D.groupby("days_out").bloc_swing.apply(lambda s: np.mean(np.square(s)))
    slope = np.polyfit(v.index.values, v.values, 1)[0] if len(v) > 1 else 0.0
    return dict(
        sigma_bloc=rms(D0.bloc_swing), bloc_bias=float(D0.bloc_swing.mean()),
        nat_bias=float(D0.N_only.mean()),
        sigma_haredi=float(D0.H.std(ddof=1)), haredi_bias=float(D0.H.mean()),
        sigma_arab=rms(D0.A), arab_bias=float(D0.A.mean()),
        party_a=float(a), party_b=float(b),
        drift_var_per_day=float(max(slope, 0.0)),
        by_election=D0.set_index("election")[["bloc_swing", "N_only", "H", "A", "O"]].round(2).to_dict(),
        bloc_by_days=v.round(3).to_dict(),
    )
