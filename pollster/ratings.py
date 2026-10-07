"""Pollster ratings from past elections, after FiveThirtyEight's 2024 method.

Per poll (final `max_days` before each election):
  error  = RMS over parties of (poll - result), in seats
  bias   = (poll - result) summed over a chosen bloc, in seats
Excess error = error minus the error expected for a poll that many days out
(fitted across all polls). Each poll's excess error/bias is blended with its
value *relative to other houses in the same election*, giving more weight to
the relative measure when more houses polled that race (controls for hard
races). House scores are time-weighted means (older elections count less)
shrunk toward zero by n / (n + n_shrink). POLLSCORE combines predictive error
and |predictive bias| (bias scaled to a per-party level); lower is better.
Quality weight for averages follows Silver's "pollster-induced error":
weight ~ 1 / (base_error + POLLSCORE)^2, normalised so an unrated house = 1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def poll_errors(polls: pd.DataFrame, results: pd.DataFrame, bloc_families=("N", "H"),
                max_days: int = 21, seats: int = 120) -> pd.DataFrame:
    res = results.set_index(["election", "party"]).pct
    P = polls[polls.days_out <= max_days].copy()
    P["result"] = [res.get((e, p), np.nan) for e, p in zip(P.election, P.party)]
    P = P.dropna(subset=["result"])
    P["err"] = (P.share - P.result) * seats / 100
    g = P.groupby(["election", "poll_id", "pollster", "days_out"])
    out = g.apply(lambda x: pd.Series({
        "error": np.sqrt(np.mean(x.err ** 2)),
        "bias": x.loc[x.family.isin(bloc_families), "err"].sum(),
        "n_parties": len(x)}), include_groups=False).reset_index()
    return out


def rate(polls: pd.DataFrame, results: pd.DataFrame, election_years: dict,
         now_year: float, n_shrink: float = 10.0, annual_decay: float = 0.14,
         bias_scale: float = np.sqrt(5), base_error: float | None = None):
    E = poll_errors(polls, results)
    # expected error by time to election
    X = np.column_stack([np.ones(len(E)), np.sqrt(E.days_out)])
    coef = np.linalg.lstsq(X, E.error, rcond=None)[0]
    E["excess_error"] = E.error - X @ coef
    E["excess_bias"] = E.bias
    for col in ["excess_error", "excess_bias"]:
        others = E.groupby("election")[col].transform("sum")
        cnt = E.groupby("election")[col].transform("count")
        own_sum = E.groupby(["election", "pollster"])[col].transform("sum")
        own_cnt = E.groupby(["election", "pollster"])[col].transform("count")
        mean_others = (others - own_sum) / (cnt - own_cnt).clip(lower=1)
        k = E.groupby("election").pollster.transform("nunique")
        w_rel = (k - 1) / (k + 1)
        E[col.replace("excess", "adj")] = (1 - w_rel) * E[col] + w_rel * (E[col] - mean_others)
    E["tw"] = (1 - annual_decay) ** (now_year - E.election.map(election_years))
    field_bloc_rms = float(np.sqrt(np.average(E.bias ** 2, weights=E.tw)))
    rows = []
    for h, g in E.groupby("pollster"):
        n = g.tw.sum()
        err = np.average(g.adj_error, weights=g.tw)
        bias = np.average(g.adj_bias, weights=g.tw)
        bloc_rms = np.sqrt(np.average(g.bias ** 2, weights=g.tw))
        shrink = n / (n + n_shrink)
        rows.append(dict(pollster=h, polls=len(g), elections=g.election.nunique(),
                         n_time_weighted=n, adj_error=err, adj_bias=bias,
                         pred_error=err * shrink, pred_bias=bias * shrink,
                         raw_error=g.error.mean(), raw_bias=g.bias.mean(),
                         bloc_rms=bloc_rms,
                         pred_bloc_rms=shrink * bloc_rms + (1 - shrink) * field_bloc_rms))
    R = pd.DataFrame(rows)
    R["pollscore"] = (R.pred_error + R.pred_bias.abs() / bias_scale) / 2
    if base_error is None:
        base_error = float(E.error.mean())
    # party-level quality (538-style) and bloc-level quality (what decides
    # Israeli elections: how close a house gets on the Netanyahu bloc)
    R["quality"] = (base_error / (base_error + R.pollscore)) ** 2
    R["bloc_quality"] = (field_bloc_rms / R.pred_bloc_rms) ** 2
    R.attrs["field_bloc_rms"] = field_bloc_rms
    return R.sort_values("pollscore").reset_index(drop=True), E, base_error
