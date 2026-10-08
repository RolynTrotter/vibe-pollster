"""Cross-country leave-one-election-out backtest of the general pipeline.

python -m countries.backtest [--n 10000]
-> output/multi_backtest.json, data/processed/multi/errors.csv

For each of the ~23 elections (Germany, Netherlands, Sweden, Denmark, New Zealand,
Israel), the error model is fitted on every OTHER election (all countries), with a
per-country error scale learned from that country's other elections only. The
held-out election is then forecast from its polls as of 20 days out and as of the
final polls, and compared with the result and with a plain average of recent polls.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

from countries import COUNTRIES, load
from pollster.pipeline import (calibrate_pool, errors_for_election, average_polls, point_seats,
                               raw_average, simulate, jw_prior)

DEBUT = {("Germany", "2013"): ["afd"], ("Germany", "2025"): ["bsw"],
         ("Netherlands", "2017"): ["denk", "fvd"], ("Netherlands", "2021"): ["ja21", "volt", "bij1", "bbb"],
         ("Netherlands", "2023"): ["nsc"], ("Denmark", "2019"): ["d", "e", "p"],
         ("Denmark", "2022"): ["m", "ae", "q"], ("New Zealand", "2017"): ["top"]}


def israel_specs():
    from israel.backtest_data import ELECTIONS
    fam_map = {"N": "R", "H": "R", "O": "L", "A": "X", "S": "X"}
    out = {}
    for eid, e in ELECTIONS.items():
        fam = {p: fam_map[f] for p, f in e["family"].items()}
        gov = [p for p, f in e["family"].items() if f in ("N", "H")]
        out[eid] = dict(country="Israel", date=e["date"].isoformat(), parties=list(e["family"]),
                        family=fam, seats=120, threshold=3.25, method="dhondt", pairs=e["pairs"],
                        debut=e["debut"], coalitions={"Netanyahu bloc": gov})
    return out


def load_all():
    P = pd.read_csv("data/processed/multi/polls.csv", dtype={"election": str})
    R = pd.read_csv("data/processed/multi/results.csv", dtype={"election": str})
    specs = {}
    for c in COUNTRIES:
        C = load(c)
        for eid, e in C.ELECTIONS.items():
            fam = e.get("family") or C.FAMILY
            specs[f"{C.COUNTRY} {eid}"] = dict(e, country=C.COUNTRY, family=fam,
                                              debut=DEBUT.get((C.COUNTRY, eid), []))
    P["uid"] = P.country + " " + P.election
    R["uid"] = R.country + " " + R.election
    # Israel
    IP = pd.read_csv("data/processed/backtest_polls.csv")
    IR = pd.read_csv("data/processed/backtest_results.csv")
    IP["country"], IP["uid"], IP["n"] = "Israel", "Israel " + IP.election, np.nan
    IR["country"], IR["uid"] = "Israel", "Israel " + IR.election
    IR["seats_total"] = 120
    for eid, s in israel_specs().items():
        specs[f"Israel {eid}"] = s
    cols = ["uid", "country", "poll_id", "date", "days_out", "pollster", "n", "party", "share"]
    P = pd.concat([P[cols], IP[cols]])
    R = pd.concat([R[["uid", "country", "party", "pct", "seats", "seats_total"]],
                   IR[["uid", "country", "party", "pct", "seats", "seats_total"]]])
    return P, R, specs


def evaluate(uid, spec, P, R, ep, d, n, use_raw=False):
    polls = P[P.uid == uid]
    res = R[R.uid == uid].set_index("party")
    cut = (pd.Timestamp(spec["date"]) - pd.Timedelta(days=d)).date().isoformat()
    past = polls[polls.date <= cut]
    parties = spec["parties"]
    mu, se, _ = average_polls(past, cut, parties)
    if use_raw:            # naive baseline: plain recent average, no house effects
        mu, se = raw_average(past, cut, parties), np.zeros(len(parties))
    sim = simulate(spec, mu, se, ep, days_left=d, n=n, seed=7)
    ps = sim["parties"]
    S, V = sim["seats"], sim["shares"]
    raw = raw_average(past, cut, parties)
    raw_ok = np.array([raw[parties.index(p)] for p in ps])
    raw_seats = point_seats(spec, raw_ok, ps)
    model_point = point_seats(spec, np.array([mu[parties.index(p)] for p in ps]), ps)
    tot_actual = res.seats.sum() if "seats_total" not in spec else spec["seats_total"]
    scale = spec["seats"] / (res.seats_total.iloc[0] if "seats_total" in res else tot_actual)
    rows = []
    for i, p in enumerate(ps):
        if p not in res.index:
            continue
        a_pct, a_seat = float(res.pct[p]), float(res.seats[p]) * scale
        rows.append(dict(party=p, actual_pct=a_pct, actual_seats=a_seat,
                         mean_pct=float(V[:, i].mean()), p10_pct=float(np.quantile(V[:, i], .1)),
                         p90_pct=float(np.quantile(V[:, i], .9)), raw_pct=float(raw_ok[i]),
                         mean_seats=float(S[:, i].mean()), p10_seats=float(np.quantile(S[:, i], .1)),
                         p90_seats=float(np.quantile(S[:, i], .9)), raw_seats=int(raw_seats[i]),
                         point_seats=int(model_point[i]), seats_nominal=spec["seats"],
                         p_in=float((S[:, i] > 0).mean()), passed=bool(res.seats[p] > 0)))
    # largest party (by votes)
    act_largest = res.loc[[p for p in ps if p in res.index], "pct"].idxmax()
    largest = np.argmax(V, axis=1)
    p_largest = {p: float((largest == i).mean()) for i, p in enumerate(ps)}
    raw_largest = ps[int(np.nanargmax(raw_ok))]
    # coalitions / blocs: seat majority
    coal = []
    for name, members in spec.get("coalitions", {}).items():
        idx = [ps.index(m) for m in members if m in ps]
        if not idx:
            continue
        tot = S[:, idx].sum(1)
        act = sum(float(res.seats[m]) * scale for m in members if m in res.index)
        coal.append(dict(name=name, p_majority=float((tot > spec["seats"] / 2).mean()),
                         raw_majority=bool(sum(raw_seats[i] for i in idx) > spec["seats"] / 2),
                         actual_majority=bool(act > spec["seats"] / 2), mean=float(tot.mean()),
                         p10=float(np.quantile(tot, .1)), p90=float(np.quantile(tot, .9)), actual=act))
    return dict(uid=uid, country=spec["country"], days_out=d, threshold=spec["threshold"], n_polls=int(past.poll_id.nunique()),
                n_houses=int(past.pollster.nunique()), parties=rows, p_largest=p_largest,
                actual_largest=act_largest, raw_largest=raw_largest, coalitions=coal)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    a = ap.parse_args()
    P, R, specs = load_all()
    os.makedirs("data/processed/multi", exist_ok=True)
    rows = []
    for uid, spec in specs.items():
        rows += errors_for_election(P[P.uid == uid], R[R.uid == uid], spec, uid)
    E = pd.DataFrame(rows)
    E.to_csv("data/processed/multi/errors.csv", index=False)
    pooled = calibrate_pool(E)
    json.dump(pooled.__dict__, open("data/processed/multi/pooled_errors.json", "w"), indent=1)
    print("pooled error params:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in pooled.__dict__.items() if k != "country_scale"})
    print("country scales:", {k: round(v, 2) for k, v in pooled.country_scale.items()})
    out = []
    jw = jw_prior()
    for uid, spec in specs.items():
        cty = spec["country"]
        modes = {
            # full model: error parameters from every other election, own-country scale
            "model": (calibrate_pool(E[E.uid != uid]), False),
            # new-country test: nothing from this country's past elections
            "unseen_country": (calibrate_pool(E[E.country != cty]), False),
            # global prior only (45-country data), our house-adjusted average
            "global_prior": (jw, False),
            # naive: plain average of recent polls + global prior error
            "naive": (jw, True),
        }
        for d in [20, 0]:
            for mode, (ep, use_raw) in modes.items():
                r = evaluate(uid, spec, P, R, ep, d, a.n, use_raw=use_raw)
                r["mode"] = mode
                out.append(r)
                if mode == "model":
                    df = pd.DataFrame(r["parties"])
                    print(f"{uid:17s} d={d:2d} polls={r['n_polls']:3d} vote MAE {(df.mean_pct - df.actual_pct).abs().mean():.2f} "
                          f"raw {(df.raw_pct - df.actual_pct).abs().mean():.2f} | largest {r['actual_largest']} "
                          f"p={r['p_largest'].get(r['actual_largest'], 0):.2f}")
    json.dump(dict(pooled=pooled.__dict__, results=out), open("output/multi_backtest.json", "w"), indent=1)


if __name__ == "__main__":
    main()
