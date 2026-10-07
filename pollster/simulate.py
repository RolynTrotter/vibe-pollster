"""Monte Carlo election simulation with correlated errors and a turnout layer.

Each draw:
 1. start from the polling average (+ its sampling error)
 2. add party-level noise, sd = sqrt(a + b * seats), wider for debut lists
 3. bloc swing: move x seats' worth of votes from the opposition family to the
    governing families (or back), x ~ N(shift, sigma_bloc(days_left))
 4. turnout: random multipliers on segment turnout (e.g. Arab, haredi voters)
    and any scenario multipliers on segments or on parties' own supporters,
    applied through the segment x party composition
 5. scenario vote transfers between parties (e.g. strategic voting)
 6. seats via the electoral system
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pollster.systems import ListPR
from pollster.turnout import apply_turnout


@dataclass
class ErrorModel:
    sigma_bloc: float          # seats, on election day
    drift_var_per_day: float   # seats^2 per day of campaign left
    party_a: float
    party_b: float
    debut_mult: float = 1.5
    seat_per_pct: float = 1.2
    seg_sigma: dict = field(default_factory=dict)   # segment -> sd of log turnout multiplier
    seg_mean: dict = field(default_factory=dict)    # segment -> mean log multiplier (bias correction)
    scale: float = 1.0                              # inflate/deflate all random error


@dataclass
class Scenario:
    name: str = "baseline"
    bloc_shift: float = 0.0                         # seats toward governing families
    seg_mult: dict = field(default_factory=dict)    # segment -> turnout multiplier
    party_mult: dict = field(default_factory=dict)  # party -> share of supporters who vote
    transfers: list = field(default_factory=list)   # (from, to, fraction of 'from' share)
    level_shift: dict = field(default_factory=dict) # party -> +/- vote share points
    extra_votes: dict = field(default_factory=dict) # party -> extra share points (e.g. expats)
    pairs: list | None = None                       # override surplus agreements
    no_error: bool = False


def simulate(parties: list[str], mu, se, family: dict, gov_fams=("N", "H"), opp_fams=("O",),
             debut=(), segments=None, profile=None, err: ErrorModel = None,
             days_left: int = 0, others_pct: float = 1.5, system: ListPR = None,
             scenario: Scenario = Scenario(), n: int = 20000, seed: int = 0):
    """Returns dict with 'seats' (n x P int) and 'shares' (n x P float)."""
    rng = np.random.default_rng(seed)
    P = len(parties)
    mu = np.asarray(mu, float).copy()
    se = np.asarray(se, float)
    for p, d in scenario.level_shift.items():
        mu[parties.index(p)] += d
    mu = np.clip(mu, 0.02, None)
    k = 1 / err.seat_per_pct
    sc = 0.0 if scenario.no_error else err.scale
    sizes = mu / k
    psd = np.sqrt(err.party_a + err.party_b * sizes) * k
    psd *= np.array([err.debut_mult if p in debut else 1.0 for p in parties])
    s = mu + sc * (rng.standard_normal((n, P)) * se + rng.standard_normal((n, P)) * psd)
    s = np.clip(s, 0.02, None)

    # bloc swing
    fam = np.array([family.get(p, "X") for p in parties])
    to = np.isin(fam, gov_fams)
    fr = np.isin(fam, opp_fams)
    sig = np.sqrt(err.sigma_bloc ** 2 + err.drift_var_per_day * days_left)
    x = (scenario.bloc_shift + sc * sig * rng.standard_normal(n)) * k
    s = s + x[:, None] * (to * s / (s * to).sum(1, keepdims=True)
                          - fr * s / (s * fr).sum(1, keepdims=True))
    s = np.clip(s, 0.02, None)

    # append unlisted 'others' (always wasted)
    s = np.column_stack([s, np.full(n, others_pct)])
    names = parties + ["others"]

    # turnout layer
    if profile is not None:
        S = len(segments)
        logm = np.zeros((n, S))
        for j, g in enumerate(segments):
            logm[:, j] = err.seg_mean.get(g, 0.0) + sc * err.seg_sigma.get(g, 0.0) * rng.standard_normal(n)
            logm[:, j] += np.log(scenario.seg_mult.get(g, 1.0))
        pm = np.ones(P + 1)
        for p, m in scenario.party_mult.items():
            pm[names.index(p)] = m
        tot0 = s.sum(1, keepdims=True)
        s = apply_turnout(s, profile, np.exp(logm), pm) / 100 * tot0

    for a, b, f in scenario.transfers:
        ia, ib = names.index(a), names.index(b)
        moved = s[:, ia] * f
        s[:, ia] -= moved
        s[:, ib] += moved
    for p, v in scenario.extra_votes.items():
        s[:, names.index(p)] += v
    s = s / s.sum(1, keepdims=True) * 100

    sysm = system
    if scenario.pairs is not None:
        sysm = ListPR(system.seats, system.threshold, scenario.pairs, system.method)
    seats = sysm.allocate_many(s, names)[:, :P]
    return dict(seats=seats, shares=s[:, :P], parties=parties)


def family_seat_sensitivity(parties, mu, family_members, segments, profile, segment,
                            system: ListPR, others_pct=1.5, eps=0.05):
    """d(vote-share seats of `family_members`)/d(log turnout of `segment`)."""
    j = segments.index(segment)
    base = np.append(np.asarray(mu, float), others_pct)
    idx = [parties.index(p) for p in family_members]
    def fam_share(m):
        mult = np.ones(len(segments)); mult[j] = np.exp(m)
        out = apply_turnout(base, profile, mult)
        return out[idx].sum() * 1.2
    return (fam_share(eps) - fam_share(-eps)) / (2 * eps)


def summarise(seats: np.ndarray, parties: list[str], blocs: dict, paths: dict):
    """blocs: name -> list of parties; paths: name -> (list of blocs/parties, min seats)."""
    col = {p: i for i, p in enumerate(parties)}
    n = len(seats)
    out = {"party": {}, "blocs": {}, "paths": {}}
    largest = np.argmax(seats + 1e-3 * np.arange(len(parties))[::-1], axis=1)
    for p, i in col.items():
        x = seats[:, i]
        out["party"][p] = dict(mean=float(x.mean()), p10=float(np.quantile(x, .1)),
                               p50=float(np.median(x)), p90=float(np.quantile(x, .9)),
                               p_in=float((x > 0).mean()), p_largest=float((largest == i).mean()))
    for b, members in blocs.items():
        tot = seats[:, [col[p] for p in members]].sum(1)
        out["blocs"][b] = dict(mean=float(tot.mean()), p10=float(np.quantile(tot, .1)),
                               p90=float(np.quantile(tot, .9)),
                               hist=np.bincount(tot, minlength=121)[:121].tolist())
    for name, (members, need) in paths.items():
        tot = seats[:, [col[p] for p in members]].sum(1)
        out["paths"][name] = float((tot >= need).mean())
    return out
