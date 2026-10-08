"""Score the cross-country backtest: point accuracy and probability quality.

python -m countries.scorecard  -> output/multi_scorecard.json (+ printed tables)

Point accuracy: vote-share MAE (points) and seat MAE as % of the chamber, model
vs a plain average of the last week's polls. Probabilities: Brier scores for
(a) does a list clear the threshold, (b) which list comes first, (c) does a bloc
or coalition win a majority; the plain average is scored as a 0/1 forecast.
Calibration: do 80% ranges contain the result 80% of the time?
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd


def score(results):
    rows, events = [], []
    for r in results:
        mode = r.get("mode", "model")
        df = pd.DataFrame(r["parties"])
        seats = df.seats_nominal.iloc[0]
        rows.append(dict(
            uid=r["uid"], country=r["country"], d=r["days_out"], mode=mode, n_polls=r["n_polls"],
            vote_mae=(df.mean_pct - df.actual_pct).abs().mean(),
            vote_mae_raw=(df.raw_pct - df.actual_pct).abs().mean(),
            seat_mae=(df.point_seats - df.actual_seats).abs().mean() / seats * 100,
            seat_mae_raw=(df.raw_seats - df.actual_seats).abs().mean() / seats * 100,
            cover80=((df.actual_pct >= df.p10_pct) & (df.actual_pct <= df.p90_pct)).mean(),
            n_parties=len(df)))
        # threshold events: the same set for every variant - lists whose result or
        # plain poll average was within 2 points of the threshold
        th = r.get("threshold", 0)
        for _, p in df.iterrows():
            if abs(p.actual_pct - th) <= 2 or abs(p.raw_pct - th) <= 2:
                events.append(dict(uid=r["uid"], d=r["days_out"], mode=mode, kind="threshold", label=p.party,
                                   p=p.p_in, raw=float(p.raw_seats > 0), y=float(p.passed)))
        # largest party (multi-class Brier, summed over lists)
        pl = r["p_largest"]
        bs = sum((pl.get(k, 0) - (k == r["actual_largest"])) ** 2 for k in set(pl) | {r["actual_largest"]})
        bs_raw = sum(((k == r["raw_largest"]) - (k == r["actual_largest"])) ** 2 for k in set(pl) | {r["actual_largest"]})
        events.append(dict(uid=r["uid"], d=r["days_out"], mode=mode, kind="largest", label=r["actual_largest"],
                           p=pl.get(r["actual_largest"], 0.0), raw=float(r["raw_largest"] == r["actual_largest"]),
                           y=1.0, brier=bs, brier_raw=bs_raw))
        for c in r["coalitions"]:
            events.append(dict(uid=r["uid"], d=r["days_out"], mode=mode, kind="majority", label=c["name"],
                               p=c["p_majority"], raw=float(c["raw_majority"]), y=float(c["actual_majority"])))
    return pd.DataFrame(rows), pd.DataFrame(events)


def brier(ev):
    b = ((ev.p - ev.y) ** 2)
    b_raw = ((ev.raw - ev.y) ** 2)
    if "brier" in ev and ev.brier.notna().any():
        b = ev.brier.where(ev.brier.notna(), b)
        b_raw = ev.brier_raw.where(ev.brier_raw.notna(), b_raw)
    return float(b.mean()), float(b_raw.mean()), len(ev)


def main():
    B = json.load(open("output/multi_backtest.json"))
    S, EV = score(B["results"])
    pd.set_option("display.width", 200)
    out = {"modes": {}}
    cols = ["vote_mae", "vote_mae_raw", "seat_mae", "seat_mae_raw", "cover80"]
    for d in [20, 0]:
        print(f"\n=== {d} days out ===")
        s = S[(S.d == d) & (S["mode"] == "model")]
        by = s.groupby("country")[cols].mean()
        by.loc["All (equal per election)"] = s[cols].mean()
        print(by.round(2).to_string())
        summ = []
        for mode in ["model", "unseen_country", "global_prior", "naive"]:
            ev = EV[(EV.d == d) & (EV["mode"] == mode)]
            sm = S[(S.d == d) & (S["mode"] == mode)]
            row = dict(mode=mode, vote_mae=sm.vote_mae.mean(), cover80=sm.cover80.mean())
            for k in ["threshold", "largest", "majority"]:
                m, r, n = brier(ev[ev.kind == k])
                row[f"brier_{k}"] = m
                row[f"brier_{k}_plain"] = r
            # log score of the actual largest party
            lg = ev[ev.kind == "largest"]
            row["logscore_largest"] = float(np.log(lg.p.clip(lower=0.01)).mean())
            bin_ev = ev[ev.kind != "largest"].copy()
            bin_ev["bucket"] = pd.cut(bin_ev.p, [-0.01, .1, .3, .5, .7, .9, 1.0])
            rel = bin_ev.groupby("bucket", observed=True).agg(n=("y", "size"), p=("p", "mean"), hit=("y", "mean"))
            row["reliability"] = rel.reset_index().astype({"bucket": str}).round(3).to_dict(orient="records")
            summ.append(row)
        T = pd.DataFrame(summ).set_index("mode")
        print(T.drop(columns="reliability").round(3).to_string())
        print("reliability (model):")
        print(pd.DataFrame(summ[0]["reliability"]).to_string(index=False))
        out["modes"][str(d)] = dict(summary=T.drop(columns="reliability").round(4).reset_index().to_dict(orient="records"),
                                    reliability={r["mode"]: r["reliability"] for r in summ},
                                    by_country=by.round(3).reset_index().to_dict(orient="records"),
                                    elections=s.round(3).to_dict(orient="records"))
    out["events"] = EV[EV["mode"] == "model"].round(3).to_dict(orient="records")
    out["pooled"] = B["pooled"]
    json.dump(out, open("output/multi_scorecard.json", "w"), indent=1)


if __name__ == "__main__":
    main()
