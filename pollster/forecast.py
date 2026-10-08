"""General-purpose forecast for any national list-PR election.

python -m pollster.forecast SPEC.json POLLS.csv [--run-date YYYY-MM-DD] [--n 20000]

SPEC.json:
  {"country": "Atlantis", "date": "2027-05-02", "seats": 150, "threshold": 5,
   "method": "dhondt" | "sainte_lague" | "modified_sainte_lague" | "hare",
   "first_divisor": 1.2, "exempt": [], "pairs": [],
   "parties": ["a", "b", ...], "family": {"a": "L", "b": "R", ...},
   "debut": [], "coalitions": {"A+B": ["a", "b"]}, "labels": {"a": "Party A"}}
POLLS.csv: date, pollster, n, party, share  (share in %; one row per poll x party)

Error sizes come from the cross-country backtest (data/processed/multi/pooled_errors.json)
with the country's own scale if it was in the backtest; otherwise from the pooled fit,
which held up as well on countries it had never seen (see output/multi_scorecard.json).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from pollster.pipeline import ErrorParams, average_polls, raw_average, simulate


def load_errors(path="data/processed/multi/pooled_errors.json") -> ErrorParams:
    d = json.load(open(path))
    return ErrorParams(**d)


def forecast(spec: dict, polls: pd.DataFrame, run_date: str, n: int = 20000, seed: int = 1):
    polls = polls.copy()
    polls["date"] = pd.to_datetime(polls.date).dt.date.astype(str)
    if "poll_id" not in polls:
        polls["poll_id"] = polls.groupby(["date", "pollster"]).ngroup()
    if "n" not in polls:
        polls["n"] = np.nan
    polls = polls[polls.date <= run_date]
    days_left = (pd.Timestamp(spec["date"]) - pd.Timestamp(run_date)).days
    mu, se, fa = average_polls(polls, run_date, spec["parties"])
    ep = load_errors()
    sim = simulate(spec, mu, se, ep, days_left=max(days_left, 0), n=n, seed=seed)
    ps, S, V = sim["parties"], sim["seats"], sim["shares"]
    lab = spec.get("labels", {})
    largest = np.argmax(V, axis=1)
    out = dict(run_date=run_date, days_left=days_left, n_polls=int(polls.poll_id.nunique()),
               houses=sorted(polls.pollster.unique()), parties={}, coalitions={},
               error_scale=ep.country_scale.get(spec["country"], 1.0))
    for i, p in enumerate(ps):
        out["parties"][p] = dict(
            label=lab.get(p, p), avg=round(float(mu[spec["parties"].index(p)]), 2),
            vote_p10=round(float(np.quantile(V[:, i], .1)), 2), vote_p90=round(float(np.quantile(V[:, i], .9)), 2),
            seats_median=float(np.median(S[:, i])), seats_p10=float(np.quantile(S[:, i], .1)),
            seats_p90=float(np.quantile(S[:, i], .9)), p_in=round(float((S[:, i] > 0).mean()), 3),
            p_largest=round(float((largest == i).mean()), 3),
            house_effects={h: round(v, 2) for h, v in fa[p].house.items()} if p in fa else {})
    for name, members in spec.get("coalitions", {}).items():
        idx = [ps.index(m) for m in members if m in ps]
        tot = S[:, idx].sum(1)
        out["coalitions"][name] = dict(p_majority=round(float((tot > spec["seats"] / 2).mean()), 3),
                                       median=float(np.median(tot)), p10=float(np.quantile(tot, .1)),
                                       p90=float(np.quantile(tot, .9)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("polls")
    ap.add_argument("--run-date", default=None)
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    polls = pd.read_csv(a.polls)
    run_date = a.run_date or str(pd.to_datetime(polls.date).max().date())
    res = forecast(spec, polls, run_date, a.n)
    print(f"{spec['country']} {spec['date']}: {res['n_polls']} polls, {res['days_left']} days out")
    for p, r in sorted(res["parties"].items(), key=lambda kv: -kv[1]["avg"]):
        print(f"  {r['label'][:28]:28s} {r['avg']:5.1f}%  seats {r['seats_median']:4.0f} "
              f"({r['seats_p10']:.0f}-{r['seats_p90']:.0f})  in {r['p_in']:.0%}  first {r['p_largest']:.0%}")
    for c, r in res["coalitions"].items():
        print(f"  {c:30s} majority {r['p_majority']:.0%}  median {r['median']:.0f} ({r['p10']:.0f}-{r['p90']:.0f})")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
