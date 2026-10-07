"""2026 Knesset forecast: average the polls, then simulate the election.

python -m israel.forecast [--run-date 2026-10-07] [--n 20000]
Writes output/forecast.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from israel import config as C
from israel.segments import SEGMENTS, classify_2022, composition_2026
from pollster.average import AvgParams, fit_average
from pollster.polls import add_shares
from pollster.simulate import ErrorModel, Scenario, family_seat_sensitivity, simulate, summarise
from pollster.systems import ListPR
from pollster.turnout import profile as col_profile
from pollster.weights import poll_weights

BLOCS = {"gov": C.GOV, "opp": C.OPP, "arab": C.ARAB, "amcha": C.SWING, "haredi": C.HAREDI}
PATHS = {
    "gov61": (C.GOV, 61),
    "gov_amcha61": (C.GOV + C.SWING, 61),
    "opp61": (C.OPP, 61),
    "opp_amcha61": (C.OPP + C.SWING, 61),
    "opp_raam61": (C.OPP + ["raam"], 61),
    "opp_arab61": (C.OPP + C.ARAB, 61),
    "opp_haredi61": (C.OPP + C.HAREDI, 61),   # an Eisenkot/Bennett deal with Shas+UTJ
    "opp_shas61": (C.OPP + ["shas"], 61),
}


def load_polls(run_date: str, start: str = C.WINDOW_START) -> pd.DataFrame:
    d = pd.read_csv("data/processed/polls_2026.csv")
    d = add_shares(d, total_seats=C.SEATS, others_pct=C.OTHERS_PCT, threshold=C.THRESHOLD)
    d = d[(d.date >= start) & (d.date <= run_date)].copy()
    return d


def house_tables(polls: pd.DataFrame):
    ratings = pd.read_csv("data/processed/pollster_ratings.csv").set_index("pollster")
    houses = sorted(polls.pollster.unique())
    fam = {h: C.POLLSTER_FAMILY.get(h, h) for h in houses}
    fsize = pd.Series(fam).value_counts()
    q = {h: float(ratings.quality.get(h, 1.0)) for h in houses}
    bq = {h: float(ratings.bloc_quality.get(h, 1.0)) for h in houses}
    anchors = {
        "consensus": {h: 1.0 / fsize[fam[h]] for h in houses},
        "track_record": {h: bq[h] / fsize[fam[h]] for h in houses},
        "ch14_world": {h: (1.0 if fam[h] == "DP/Ch14" else 0.0) for h in houses},
        "mainstream": {h: (0.0 if fam[h] == "DP/Ch14" else 1.0) for h in houses},
    }
    return anchors, q, bq, fam


def averages(polls, run_date, anchor, quality, params, eval_dates=None):
    one = polls.drop_duplicates("poll_id").copy()
    one["w"] = poll_weights(one, quality).values
    p = polls.merge(one[["poll_id", "w"]], on="poll_id")
    return fit_average(p, run_date, anchor, params, parties=C.PARTIES, eval_dates=eval_dates)


def build_model(run_date: str, n: int = 20000):
    cal = json.load(open("data/processed/calibration.json"))
    params = AvgParams(**cal["avg_params"])
    polls = load_polls(run_date)
    anchors, q, bq, fam = house_tables(polls)
    days = pd.date_range(C.WINDOW_START, run_date).strftime("%Y-%m-%d").tolist()
    avg = {k: averages(polls, run_date, a, q, params, eval_dates=days if k in ("consensus", "track_record") else None)
           for k, a in anchors.items()}
    mu = {k: np.array([v[p].level for p in C.PARTIES]) for k, v in avg.items()}
    se = {k: np.array([v[p].se for p in C.PARTIES]) for k, v in avg.items()}

    # composition (fitted to the consensus average)
    M22, T22 = classify_2022()
    V = composition_2026(M22, dict(zip(C.PARTIES, mu["consensus"])), C.OTHERS_PCT)
    prof = col_profile(V.values)
    names = C.PARTIES + ["others"]
    system = ListPR(C.SEATS, C.THRESHOLD, C.SURPLUS_PAIRS + C.ASSUMED_PAIRS)

    sens_h = family_seat_sensitivity(C.PARTIES, mu["consensus"], C.HAREDI, SEGMENTS, prof, "haredi", system)
    sens_a = family_seat_sensitivity(C.PARTIES, mu["consensus"], C.ARAB, SEGMENTS, prof, "arab", system)
    err = ErrorModel(
        sigma_bloc=cal["sigma_bloc"], drift_var_per_day=cal["drift_var_per_day"],
        party_a=cal["party_a"], party_b=cal["party_b"],
        seg_sigma={"haredi": cal["sigma_haredi"] / sens_h, "arab": cal["sigma_arab"] / sens_a},
        # Shas, not the haredi community as a whole, is what polls miss: Shas beat
        # its final average in 5 of 6 elections; UTJ's average was on target.
        party_shift={"shas": -cal["party_bias"]["shas"]["mean"] / 1.2},
    )
    days_left = (pd.Timestamp(C.ELECTION_DATE) - pd.Timestamp(run_date)).days
    ctx = dict(polls=polls, anchors=anchors, quality=q, bloc_quality=bq, fam=fam, avg=avg,
               mu=mu, se=se, V=V, prof=prof, T22=T22, M22=M22, system=system, err=err,
               days_left=days_left, cal=cal, params=params, days=days,
               sens={"haredi": sens_h, "arab": sens_a})
    return ctx


def run(ctx, anchor="consensus", scenario=Scenario(), n=20000, seed=20261027, err=None):
    out = simulate(C.PARTIES, ctx["mu"][anchor], ctx["se"][anchor], C.FAMILY, debut=C.DEBUT,
                   segments=SEGMENTS, profile=ctx["prof"], err=err or ctx["err"],
                   days_left=ctx["days_left"], others_pct=C.OTHERS_PCT, system=ctx["system"],
                   scenario=scenario, n=n, seed=seed)
    summ = summarise(out["seats"], C.PARTIES, BLOCS, PATHS)
    s = out["seats"]
    col = {p: i for i, p in enumerate(C.PARTIES)}
    tot = lambda ps: s[:, [col[p] for p in ps]].sum(1)
    g, o, am = tot(C.GOV), tot(C.OPP), tot(C.SWING)
    summ["paths"]["deadlock"] = float(((g + am < 61) & (o + am < 61)).mean())
    summ["share_mean"] = dict(zip(C.PARTIES, out["shares"].mean(0).round(3).tolist()))
    return summ, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default="2026-10-07")
    ap.add_argument("--n", type=int, default=20000)
    a = ap.parse_args()
    ctx = build_model(a.run_date, a.n)
    res = {}
    for k in ["consensus", "track_record", "ch14_world", "mainstream"]:
        summ, _ = run(ctx, k, n=a.n)
        res[k] = summ
        print(k, {p: round(v, 3) for p, v in summ["paths"].items()})
        print("  seats:", {p: round(v["mean"], 1) for p, v in summ["party"].items()})
    pol = ctx["polls"]
    meta = dict(
        run_date=a.run_date, election=C.ELECTION_DATE, days_left=ctx["days_left"], n_sims=a.n,
        n_polls=int(pol.poll_id.nunique()), window_start=C.WINDOW_START,
        latest_poll=pol.date.max(), houses=sorted(pol.pollster.unique()),
        polls_per_house=pol.drop_duplicates("poll_id").pollster.value_counts().to_dict(),
        labels=C.LABELS, gov=C.GOV, opp=C.OPP, arab=C.ARAB, swing=C.SWING, family=C.FAMILY,
        debut=sorted(C.DEBUT), pairs=C.SURPLUS_PAIRS, assumed_pairs=C.ASSUMED_PAIRS,
        others_pct=C.OTHERS_PCT, house_family=ctx["fam"],
        error_model=asdict(ctx["err"]), sensitivity=ctx["sens"],
        calibration={k: v for k, v in ctx["cal"].items()},
    )
    averages_out = {}
    for k, v in ctx["avg"].items():
        averages_out[k] = {p: dict(level=round(v[p].level, 3), se=round(v[p].se, 3),
                                   house={h: round(x, 3) for h, x in v[p].house.items()})
                           for p in C.PARTIES}
    curves = {k: {p: [round(x, 3) for x in ctx["avg"][k][p].curve.values] for p in C.PARTIES}
              for k in ["consensus", "track_record"]}
    one = pol.drop_duplicates("poll_id")
    poll_rows = []
    for pid, g in pol.groupby("poll_id"):
        r = g.iloc[0]
        poll_rows.append(dict(date=r.date, pollster=r.pollster, n=None if pd.isna(r.n) else int(r.n),
                              seats={p: int(x) for p, x in zip(g.party, g.seats)},
                              share={p: round(x, 2) for p, x in zip(g.party, g.share)}))
    V = ctx["V"]
    comp = dict(segments=SEGMENTS, matrix=V.round(3).to_dict(),
                turnout_2022=ctx["T22"].turnout_boxes.round(3).to_dict(),
                seg_share=(V.sum(axis=1) / V.values.sum()).round(4).to_dict())
    ratings = pd.read_csv("data/processed/pollster_ratings.csv")
    from israel.segments import SEGMENTS as SEG
    e = ctx["err"]
    model = dict(parties=C.PARTIES, segments=SEG, profile=np.round(ctx["prof"], 6).tolist(),
                 mu={k: np.round(v, 4).tolist() for k, v in ctx["mu"].items()},
                 se={k: np.round(v, 4).tolist() for k, v in ctx["se"].items()},
                 sigma_bloc=e.sigma_bloc, drift=e.drift_var_per_day, party_a=e.party_a,
                 party_b=e.party_b, debut_mult=e.debut_mult, seg_sigma=e.seg_sigma,
                 seg_mean=e.seg_mean, party_shift=e.party_shift, days_left=ctx["days_left"], others_pct=C.OTHERS_PCT,
                 threshold=C.THRESHOLD, seats=C.SEATS, pairs=C.SURPLUS_PAIRS,
                 assumed_pairs=C.ASSUMED_PAIRS, arab_turnout_base=0.53)
    json.dump(dict(meta=meta, model=model, results=res, averages=averages_out, curves=curves, days=ctx["days"],
                   polls=sorted(poll_rows, key=lambda x: x["date"]), composition=comp,
                   weights=dict(quality=ctx["quality"], bloc_quality=ctx["bloc_quality"],
                                anchors=ctx["anchors"]),
                   ratings=ratings.round(3).to_dict(orient="records")),
              open("output/forecast.json", "w"), indent=1, default=float)
    print("wrote output/forecast.json")


if __name__ == "__main__":
    main()
