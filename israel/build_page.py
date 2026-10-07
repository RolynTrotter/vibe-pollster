"""Inject model output into site/template.html -> output/knesset_2026.html."""
import json

import pandas as pd

F = json.load(open("output/forecast.json"))
D = json.load(open("output/dynamics.json"))

data = dict(
    meta={k: F["meta"][k] for k in ["run_date", "election", "days_left", "n_sims", "n_polls",
                                    "window_start", "latest_poll", "houses", "polls_per_house",
                                    "labels", "gov", "opp", "arab", "swing", "family", "debut",
                                    "pairs", "assumed_pairs", "others_pct", "house_family"]},
    model=F["model"],
    results=F["results"],
    averages={k: {p: dict(level=v["level"], se=v["se"]) for p, v in a.items()} for k, a in F["averages"].items()},
    house=F["averages"]["consensus"],
    weights=F["weights"],
    ratings=F["ratings"],
    house_misses=(lambda E: dict(
        elections=sorted(E.election.unique().tolist()),
        field=E.groupby("election").bias.mean().round(1).to_dict(),
        house={h: g.groupby("election").bias.mean().round(1).to_dict()
               for h, g in E.groupby("pollster") if g.election.nunique() >= 3}))(
        pd.read_csv("data/processed/backtest_poll_errors.csv")),
    calibration={k: v for k, v in F["meta"]["calibration"].items()
                 if k in ["sigma_bloc", "bloc_bias", "sigma_haredi", "haredi_bias", "sigma_arab", "party_bias",
                          "arab_bias", "drift_var_per_day", "by_election", "avg_params"]},
    polls=[dict(date=p["date"], pollster=p["pollster"], n=p["n"], seats=p["seats"]) for p in F["polls"]],
    composition=F["composition"],
    dynamics=dict(n=D["n"], baseline=D["baseline"], scenarios=D["scenarios"], results=D["results"],
                  grid=D["grid"], sweep=D["sweep"]),
)
import numpy as np

BT = json.load(open("output/backtest.json"))
rows = [dict(e=r["election"], d=r["days_out"], mean=round(r["bloc"]["mean"], 1), p10=int(r["bloc"]["p10"]),
             p90=int(r["bloc"]["p90"]), actual=r["bloc"]["actual"], raw=round(r["bloc"]["naive"], 1),
             p61=round(r["bloc"]["p61"], 3)) for r in BT]


def summ(d):
    rs = [r for r in BT if r["days_out"] == d]
    parts = [p for r in rs for p in r["parties"]]
    hit = [r["bloc"]["actual"] >= 61 for r in rs]
    return dict(
        bloc_err=float(np.mean([abs(r["bloc"]["mean"] - r["bloc"]["actual"]) for r in rs])),
        bloc_err_raw=float(np.mean([abs(r["bloc"]["naive"] - r["bloc"]["actual"]) for r in rs])),
        brier=float(np.mean([(r["bloc"]["p61"] - h) ** 2 for r, h in zip(rs, hit)])),
        brier_raw=float(np.mean([((r["bloc"]["naive"] >= 61) - h) ** 2 for r, h in zip(rs, hit)])),
        party_mae=float(np.mean([abs(p["point"] - p["actual"]) for p in parts])),
        party_mae_raw=float(np.mean([abs(p["poll_seats"] - p["actual"]) for p in parts])),
        bloc_cover=float(np.mean([r["bloc"]["p10"] <= r["bloc"]["actual"] <= r["bloc"]["p90"] for r in rs])))


data["backtest"] = dict(rows=rows, summary=dict(final=summ(0), d20=summ(20)))
html = open("site/template.html").read().replace("/*__DATA__*/{}", json.dumps(data, separators=(",", ":")))
open("output/knesset_2026.html", "w").write(html)
print(f"wrote output/knesset_2026.html ({len(html)/1024:.0f} KB)")
