"""Country-agnostic forecasting pipeline.

Inputs, for any election:
  polls    long table: election_uid, poll_id, date, days_out, pollster, n, party, share (%)
  spec     dict: date, parties, family {party: 'L'|'R'|other}, seats, threshold, method,
           first_divisor, exempt, pairs, coalitions {name: [parties]}
  errors   an ErrorParams fitted on *other* elections (see calibrate_pool)
Output: simulated vote shares and seats, and summaries (party ranges, largest-party
odds, coalition majorities, threshold odds).

Error model (vote-share points):
  party noise   var = a + b * share + c * share * days_out + e * days_out   (scaled per country)
  camp swing    x ~ N(0, s_bloc^2 + k * days_out): moves x points from L to R
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pollster.average import AvgParams, fit_average
from pollster.systems import system_from_spec
from pollster.weights import poll_weights

DEFAULT_PARAMS = AvgParams(bandwidth=12.0, half_life=7.0, degree=1, mix=0.8)


@dataclass
class ErrorParams:
    a: float
    b: float
    c: float
    s_bloc: float
    k_bloc: float
    country_scale: dict = field(default_factory=dict)
    debut_mult: float = 1.5
    e: float = 0.0                  # extra variance per day, independent of size

    def party_sd(self, share, days, scale=1.0, debut=None):
        v = self.a + self.b * share + self.c * share * days + self.e * days
        sd = np.sqrt(np.clip(v, 1e-4, None)) * scale
        if debut is not None:
            sd = sd * np.where(debut, self.debut_mult, 1.0)
        return sd


def average_polls(polls: pd.DataFrame, run_date: str, parties: list[str],
                  params: AvgParams = DEFAULT_PARAMS, quality: dict | None = None):
    """House-adjusted average (consensus anchor: every house counts equally)."""
    one = polls.drop_duplicates("poll_id").copy()
    one["w"] = poll_weights(one, quality).values
    p = polls.merge(one[["poll_id", "w"]], on="poll_id")
    anchor = {h: 1.0 for h in p.pollster.unique()}
    fa = fit_average(p, run_date, anchor, params, parties=[x for x in parties if x in set(p.party)])
    mu = np.array([fa[x].level if x in fa else np.nan for x in parties])
    se = np.array([fa[x].se if x in fa else np.nan for x in parties])
    return mu, se, fa


def raw_average(polls: pd.DataFrame, run_date: str, parties: list[str], window: int = 7):
    """Plain mean of polls published in the `window` days up to run_date."""
    d = pd.Timestamp(run_date)
    t = pd.to_datetime(polls.date)
    w = polls[(t <= d) & (t > d - pd.Timedelta(days=window))]
    if w.poll_id.nunique() < 2:            # widen until there are a few polls
        w = polls[t <= d].sort_values("date").groupby("party").tail(5)
    m = w.groupby("party").share.mean()
    return np.array([m.get(x, np.nan) for x in parties])


def errors_for_election(polls, results, spec, uid, horizons=(0, 7, 14, 21, 28),
                        params=DEFAULT_PARAMS):
    """Error of the consensus average at several horizons (vote-share points)."""
    rows = []
    res = results.set_index("party").pct
    for d in horizons:
        cut = (pd.Timestamp(spec["date"]) - pd.Timedelta(days=d)).date().isoformat()
        past = polls[polls.date <= cut]
        if past.poll_id.nunique() < 4:
            continue
        mu, se, _ = average_polls(past, cut, spec["parties"], params)
        for p, m in zip(spec["parties"], mu):
            if np.isnan(m) or p not in res:
                continue
            rows.append(dict(uid=uid, country=spec["country"], days_out=d, party=p,
                             family=spec["family"].get(p, "X"), avg=m, result=res[p], err=m - res[p]))
    return rows


def calibrate_pool(E: pd.DataFrame, shrink_k: float = 2.0) -> ErrorParams:
    """Fit error parameters on a pooled error table (rows from many elections)."""
    E = E.copy()
    # camp swing per election-horizon: x = (err_R - err_L)/2
    D = E.groupby(["uid", "days_out"]).apply(lambda g: pd.Series({
        "x": (g.loc[g.family == "R", "err"].sum() - g.loc[g.family == "L", "err"].sum()) / 2,
        "R": g.loc[g.family == "R", "result"].sum(), "L": g.loc[g.family == "L", "result"].sum()}),
        include_groups=False).reset_index()
    v = D.groupby("days_out").x.apply(lambda s: np.mean(np.square(s)))
    s_bloc = float(np.sqrt(v.get(0, v.iloc[0])))
    k_bloc = float(max(np.polyfit(v.index.values, v.values, 1)[0], 0.0)) if len(v) > 1 else 0.0
    # party residuals after removing the camp swing (spread in proportion to share)
    E = E.merge(D, on=["uid", "days_out"])
    adj = np.where(E.family == "R", E.x * E.result / E.R.clip(lower=1e-6),
                   np.where(E.family == "L", -E.x * E.result / E.L.clip(lower=1e-6), 0.0))
    E["resid"] = E.err - adj
    X = np.column_stack([np.ones(len(E)), E.result, E.result * E.days_out])
    a, b, c = np.linalg.lstsq(X, E.resid ** 2, rcond=None)[0]
    a, b, c = max(a, 0.01), max(b, 0.0), max(c, 0.0)
    ep = ErrorParams(a=float(a), b=float(b), c=float(c), s_bloc=s_bloc, k_bloc=k_bloc)
    # country scale: RMS standardized residual at election day, shrunk toward 1
    E0 = E[E.days_out == 0].copy()
    E0["z"] = E0.resid / ep.party_sd(E0.result.values, 0)
    for cty, g in E0.groupby("country"):
        n_el = g.uid.nunique()
        s2 = float(np.mean(g.z ** 2))
        ep.country_scale[cty] = float(np.sqrt((n_el * s2 + shrink_k * 1.0) / (n_el + shrink_k)))
    return ep


def simulate(spec: dict, mu, se, ep: ErrorParams, days_left: int, n: int = 20000, seed: int = 0,
             others_pct: float | None = None):
    rng = np.random.default_rng(seed)
    parties = spec["parties"]
    ok = ~np.isnan(mu)
    parties = [p for p, o in zip(parties, ok) if o]
    mu, se = np.asarray(mu)[ok], np.asarray(se)[ok]
    P = len(parties)
    scale = ep.country_scale.get(spec["country"], 1.0)
    debut = np.array([p in spec.get("debut", []) for p in parties])
    psd = ep.party_sd(mu, days_left, scale, debut)
    s = mu + rng.standard_normal((n, P)) * np.sqrt(se ** 2 + psd ** 2)
    s = np.clip(s, 0.01, None)
    fam = np.array([spec["family"].get(p, "X") for p in parties])
    R_, L_ = fam == "R", fam == "L"
    if R_.any() and L_.any():
        sig = np.sqrt(ep.s_bloc ** 2 + ep.k_bloc * days_left) * scale
        x = sig * rng.standard_normal(n)
        s = s + x[:, None] * (R_ * s / (s * R_).sum(1, keepdims=True) - L_ * s / (s * L_).sum(1, keepdims=True))
        s = np.clip(s, 0.01, None)
    if others_pct is None:
        others_pct = max(100 - mu.sum(), 0.5)
    tot = s.sum(1, keepdims=True) + others_pct
    s = s / tot * 100
    oth = np.full((n, 1), others_pct) / tot * 100
    sysm = system_from_spec(spec)
    seats = sysm.allocate_many(np.hstack([s, oth]), parties + ["others"])[:, :P]
    return dict(parties=parties, shares=s, seats=seats)


def point_seats(spec, shares: np.ndarray, parties: list[str]):
    """Seats from a single vote-share vector (e.g. a raw poll average)."""
    ok = ~np.isnan(shares)
    sh = np.where(ok, shares, 0.0)
    oth = max(100 - sh.sum(), 0.5)
    return system_from_spec(spec).allocate(np.append(sh, oth), parties + ["others"])[:-1]


def jw_prior(path="data/processed/multi/jw_prior.json") -> ErrorParams:
    """Global prior from Jennings & Wlezien's 45-country poll-error data: total
    party error (camp swing included, so s_bloc = 0). For countries with no history."""
    import json
    p = json.load(open(path))
    return ErrorParams(a=p["a"], b=p["b"], c=p["c"], e=p["e"], s_bloc=0.0, k_bloc=0.0)
