"""Inject model output into site/template.html -> output/knesset_2026.html."""
import json

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
    calibration={k: v for k, v in F["meta"]["calibration"].items()
                 if k in ["sigma_bloc", "bloc_bias", "sigma_haredi", "haredi_bias", "sigma_arab",
                          "arab_bias", "drift_var_per_day", "by_election", "avg_params"]},
    polls=[dict(date=p["date"], pollster=p["pollster"], n=p["n"], seats=p["seats"]) for p in F["polls"]],
    composition=F["composition"],
    dynamics=dict(n=D["n"], baseline=D["baseline"], scenarios=D["scenarios"], results=D["results"],
                  grid=D["grid"], sweep=D["sweep"]),
)
html = open("site/template.html").read().replace("/*__DATA__*/{}", json.dumps(data, separators=(",", ":")))
open("output/knesset_2026.html", "w").write(html)
print(f"wrote output/knesset_2026.html ({len(html)/1024:.0f} KB)")
