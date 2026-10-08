"""Build output/scorecard.html from the cross-country backtest."""
import json

import pandas as pd

B = json.load(open("output/multi_backtest.json"))
S = json.load(open("output/multi_scorecard.json"))
E = pd.read_csv("data/processed/multi/errors.csv")
JW = json.load(open("data/processed/multi/jw_prior.json"))

from countries import COUNTRIES, load

labels = {}
for c in COUNTRIES:
    C = load(c)
    for k, al in C.ALIASES.items():
        labels[f"{C.COUNTRY}|{k}"] = min([a for a in al if len(a) >= 3] or al, key=len)
labels.update({"Israel|likud": "Likud", "Israel|blue_white": "Blue and White", "Sweden|s": "Social Democrats",
               "Denmark|a": "Social Democrats", "New Zealand|nat": "National", "New Zealand|lab": "Labour"})

elections = []
res = [r for r in B["results"] if r["mode"] == "model"]
for uid in dict.fromkeys(r["uid"] for r in res):
    row = dict(uid=uid, country=uid.rsplit(" ", 1)[0], year=uid.rsplit(" ", 1)[1])
    for r in res:
        if r["uid"] != uid:
            continue
        df = pd.DataFrame(r["parties"])
        k = "d20" if r["days_out"] == 20 else "d0"
        row[k] = dict(n_polls=r["n_polls"], n_houses=r["n_houses"],
                      mae=round(float((df.mean_pct - df.actual_pct).abs().mean()), 2),
                      mae_raw=round(float((df.raw_pct - df.actual_pct).abs().mean()), 2),
                      cover=round(float(((df.actual_pct >= df.p10_pct) & (df.actual_pct <= df.p90_pct)).mean()), 2),
                      largest=r["actual_largest"], p_largest=round(r["p_largest"].get(r["actual_largest"], 0), 3),
                      raw_largest=r["raw_largest"],
                      worst=df.assign(e=df.mean_pct - df.actual_pct).sort_values("e", key=abs).iloc[-1][["party", "e"]].to_dict())
    elections.append(row)

data = dict(
    elections=elections,
    modes={d: S["modes"][d]["summary"] for d in S["modes"]},
    reliability={d: S["modes"][d]["reliability"]["model"] for d in S["modes"]},
    by_country={d: S["modes"][d]["by_country"] for d in S["modes"]},
    error_curve=dict(ours={int(k): round(float(v), 3) for k, v in E.groupby("days_out").err.apply(lambda s: s.abs().mean()).items()},
                     jw={int(k): round(v, 3) for k, v in JW["mae_by_band"].items()},
                     jw_n=dict(elections=JW["n_elections"], countries=JW["n_countries"])),
    pooled=S["pooled"],
    labels=labels,
)
html = open("site/scorecard_template.html").read().replace("/*__DATA__*/{}", json.dumps(data, separators=(",", ":")))
open("output/scorecard.html", "w").write(html)
print(f"wrote output/scorecard.html ({len(html)/1024:.0f} KB)")
