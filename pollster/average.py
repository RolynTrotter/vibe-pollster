"""Polling average with house effects, after FiveThirtyEight's 2023 method.

For each party:
  share_i = trend(t_i) + house_effect[h_i] + noise_i
* trend: a blend of a Gaussian-kernel local polynomial (degree 0 or 1) and an
  exponentially weighted moving average; the blend leans on the kernel fit
  when there are many recent polls
* house effects: Bayesian-shrunk mean residual per house, normal prior N(0, prior_sd^2)
* anchoring: house effects are constrained so that an *anchor-weighted* mean
  of them is zero. The anchor weights say whose polls define "no lean":
  every house equally (consensus) or houses weighted by track record.
Hyperparameters are tuned on past elections by how well the average at day t
predicts house-adjusted polls published in the next 14 days.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class AvgParams:
    bandwidth: float = 7.0      # days, Gaussian kernel sd
    half_life: float = 7.0      # days, EWMA
    degree: int = 0             # local polynomial degree
    mix: float = 0.5            # max weight on kernel fit (scaled by poll density)
    prior_sd: float = 2.5       # house-effect prior sd, vote-share points
    tau: float = 0.6            # non-sampling poll noise sd, points
    iters: int = 12


def _kernel_fit(t, y, w, t_eval, bw, degree):
    out = np.empty(len(t_eval))
    for j, te in enumerate(t_eval):
        k = w * np.exp(-0.5 * ((t - te) / bw) ** 2) * (t <= te + 0.5)
        if k.sum() <= 0:
            out[j] = np.nan
            continue
        if degree == 0 or (k > 1e-3 * k.max()).sum() < 4:
            out[j] = np.sum(k * y) / k.sum()
        else:
            X = np.column_stack([np.ones_like(t), t - te])
            A = X.T @ (k[:, None] * X)
            if np.linalg.cond(A) > 1e8:
                out[j] = np.sum(k * y) / k.sum()
            else:
                out[j] = np.linalg.solve(A, X.T @ (k * y))[0]
    return out


def _ewma(t, y, w, t_eval, half_life):
    out = np.empty(len(t_eval))
    for j, te in enumerate(t_eval):
        m = t <= te + 0.5
        k = w[m] * 0.5 ** ((te - t[m]) / half_life)
        out[j] = np.sum(k * y[m]) / k.sum() if k.sum() > 0 else np.nan
    return out


def trend(t, y, w, t_eval, p: AvgParams):
    kf = _kernel_fit(t, y, w, t_eval, p.bandwidth, p.degree)
    ew = _ewma(t, y, w, t_eval, p.half_life)
    # density: effective number of polls in the last 2 bandwidths
    dens = np.array([(w * (t <= te) * (t > te - 2 * p.bandwidth)).sum() for te in t_eval])
    a = p.mix * dens / (dens + 4.0)
    return a * kf + (1 - a) * ew


@dataclass
class PartyAverage:
    level: float
    se: float
    house: dict
    curve: pd.Series


def fit_party(df: pd.DataFrame, run_t: float, anchor: dict, p: AvgParams,
              eval_t=None) -> PartyAverage:
    """df columns: t (days, float), house, share, n, w (poll weight)."""
    t = df["t"].to_numpy(float)
    y = df["share"].to_numpy(float)
    w = df["w"].to_numpy(float)
    hs = df["house"].to_numpy()
    n = (df["n"] if "n" in df else pd.Series(600.0, index=df.index)).fillna(600).to_numpy(float)
    houses = sorted(set(hs))
    var_i = np.clip(y, 0.3, 99) * (100 - np.clip(y, 0.3, 99)) / n + p.tau ** 2
    h = {k: 0.0 for k in houses}
    a = np.array([anchor.get(k, 0.0) for k in houses])
    if a.sum() <= 0:
        a = np.ones(len(houses))
    a = a / a.sum()
    for _ in range(p.iters):
        adj = y - np.array([h[k] for k in hs])
        mu_i = trend(t, adj, w, t, p)
        r = y - mu_i
        est = {}
        for k in houses:
            m = hs == k
            prec = (1 / var_i[m]).sum()
            est[k] = (r[m] / var_i[m]).sum() / (prec + 1 / p.prior_sd ** 2)
        c = sum(ai * est[k] for ai, k in zip(a, houses))
        h = {k: est[k] - c for k in houses}
    adj = y - np.array([h[k] for k in hs])
    te = np.atleast_1d(run_t) if eval_t is None else np.asarray(eval_t, float)
    curve = trend(t, adj, w, te, p)
    level = trend(t, adj, w, np.array([run_t]), p)[0]
    # sampling uncertainty of the level (house-effect uncertainty is part of
    # the calibrated forecast error, not added here)
    k = w * 0.5 ** ((run_t - t) / max(p.half_life, p.bandwidth))
    se = np.sqrt(np.sum(k ** 2 * var_i) / k.sum() ** 2)
    return PartyAverage(level, se, h, pd.Series(curve, index=te))


def fit_average(polls: pd.DataFrame, run_date: str, anchor: dict,
                p: AvgParams = AvgParams(), parties=None, eval_dates=None):
    """polls: long table with date, pollster, party, share, n, w."""
    d0 = pd.Timestamp(run_date)
    df = polls.copy()
    df["t"] = (pd.to_datetime(df["date"]) - d0).dt.days.astype(float)
    df = df[df.t <= 0]
    df["house"] = df["pollster"]
    parties = parties or sorted(df.party.unique())
    et = None if eval_dates is None else \
        (pd.to_datetime(pd.Series(eval_dates)) - d0).dt.days.to_numpy(float)
    out = {}
    for party in parties:
        g = df[df.party == party].dropna(subset=["share"])
        if g.empty:
            continue
        out[party] = fit_party(g, 0.0, anchor, p, et)
    return out


def tune(backtest_polls: pd.DataFrame, election_dates: dict, weight_fn,
         grid: list[AvgParams], cutoffs=(35, 28, 21, 14), horizon=14, verbose=False):
    """Pick hyperparameters by out-of-sample prediction of future polls.

    For each past election and cutoff (days before the vote), fit the average
    on polls published up to the cutoff, then score it against house-adjusted
    polls published in the following `horizon` days. Returns (best, scores).
    """
    scores = []
    for p in grid:
        errs = []
        for eid, edate in election_dates.items():
            B = backtest_polls[backtest_polls.election == eid].copy()
            B["w"] = weight_fn(B)
            anchor = {h: 1.0 for h in B.pollster.unique()}
            for c in cutoffs:
                cut = pd.Timestamp(edate) - pd.Timedelta(days=c)
                past = B[pd.to_datetime(B.date) <= cut]
                fut = B[(pd.to_datetime(B.date) > cut) &
                        (pd.to_datetime(B.date) <= cut + pd.Timedelta(days=horizon))]
                if past.poll_id.nunique() < 6 or fut.empty:
                    continue
                avg = fit_average(past, cut.date().isoformat(), anchor, p,
                                  parties=sorted(fut.party.unique()))
                for _, r in fut.iterrows():
                    pa = avg.get(r.party)
                    if pa is None:
                        continue
                    pred = pa.level + pa.house.get(r.pollster, 0.0)
                    errs.append(abs(pred - r.share))
        scores.append((float(np.mean(errs)) if errs else np.inf, p))
        if verbose:
            print(f"MAE {scores[-1][0]:.3f}  {p}")
    scores.sort(key=lambda x: x[0])
    return scores[0][1], scores
