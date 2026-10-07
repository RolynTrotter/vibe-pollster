"""What could change the result? Scenario sweeps on top of the forecast.

python -m israel.dynamics [--n 10000]
Writes output/dynamics.json. Every scenario reuses the same random draws as
the baseline (common random numbers), so differences are due to the scenario,
not simulation noise.

Turnout scenarios are relative to the polls' implied baseline, which we take
to be the 2022 turnout pattern (Arab turnout 53%; see segments.py). Party
"stay home" scenarios remove that share of a party's supporters entirely.
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from israel import config as C
from israel.forecast import build_model, run
from pollster.simulate import Scenario

AR0 = 0.53  # Arab turnout in 2022 (official 53.2%; ballot-box estimate 53.0%)
OPP_CORE = ["yashar", "together", "dems", "yb"]


def scenarios(ctx):
    mu = dict(zip(C.PARTIES, ctx["mu"]["consensus"]))
    gov_tot = sum(mu[p] for p in C.GOV)
    opp_tot = sum(mu[p] for p in C.OPP)
    # Fly & Vote: >33,000 expats registered; assume 25,000 vote, 75% opposition.
    exp_share = 25000 / 4.9e6 * 100
    expats = {p: exp_share * 0.75 * mu[p] / opp_tot for p in C.OPP}
    expats.update({p: exp_share * 0.25 * mu[p] / gov_tot for p in C.GOV})
    S = [
        ("turnout", "arab_45", "Arab turnout falls to 45%",
         "2021 level (44.6%), when the Joint List split", Scenario(seg_mult={"arab": 0.45 / AR0})),
        ("turnout", "arab_60", "Arab turnout rises to 60%",
         "Between 2019b (59%) and 2020 (65%)", Scenario(seg_mult={"arab": 0.60 / AR0})),
        ("turnout", "arab_67", "Arab turnout 67%",
         "KAS survey (May 2026): ~67% if a united Joint List runs", Scenario(seg_mult={"arab": 0.67 / AR0})),
        ("turnout", "haredi_up", "Haredi turnout +8%",
         "Draft-law fight mobilises haredi voters", Scenario(seg_mult={"haredi": 1.08})),
        ("turnout", "haredi_down", "Haredi turnout −8%",
         "Haredi voters disaffected with both camps", Scenario(seg_mult={"haredi": 0.92})),
        ("turnout", "likud_home10", "10% of Likud supporters stay home",
         "IDI: 43% of right-wing Jews say voting makes no difference (vs 15% on the left)",
         Scenario(party_mult={"likud": 0.90})),
        ("turnout", "right_home5", "5% of all right-bloc supporters stay home",
         "A general enthusiasm gap on the right", Scenario(party_mult={p: 0.95 for p in C.GOV + C.SWING})),
        ("turnout", "opp_home7", "7% of opposition supporters stay home",
         "Complacency, or a 'nothing changes' mood in the centre", Scenario(party_mult={p: 0.93 for p in C.OPP})),
        ("turnout", "expats", "Fly & Vote expats: 25,000 votes, 75% opposition",
         ">33,000 expats registered to fly home to vote", Scenario(extra_votes=expats)),
        ("strategy", "gevalt", "Gevalt: 30% of RZP and Amcha voters switch to Likud",
         "The 2015 pattern: small right lists bled to Likud in the final week",
         Scenario(transfers=[("rzp", "likud", 0.30), ("amcha", "likud", 0.30)])),
        ("strategy", "amcha_out", "Amcha Yisrael drops out (votes 70% Likud, 30% Otzma)",
         "It is polling on the threshold", Scenario(transfers=[("amcha", "likud", 0.7), ("amcha", "otzma", 0.3)])),
        ("strategy", "reservists_out", "Reservists drop out (votes to Yashar/Together)",
         "Hendel's list is polling on the threshold",
         Scenario(transfers=[("reservists", "yashar", 0.5), ("reservists", "together", 0.5)])),
        ("strategy", "bw_out", "Gantz's Blue and White drops out (votes to Yashar)",
         "Polling ~1%: a wasted-vote list", Scenario(transfers=[("blue_white", "yashar", 1.0)])),
        ("polls", "shy_right", "Polls miss like 2015: 3 seats toward the right",
         "Largest Netanyahu-bloc miss in the backtest", Scenario(bloc_shift=3.0)),
        ("polls", "miss_left", "Polls miss 3 seats toward the opposition",
         "The 2019b-style miss in the other direction", Scenario(bloc_shift=-3.0)),
        ("polls", "no_shas_fix", "No Shas correction",
         "Assume Shas is polled accurately this time", None),
        ("polls", "ch14", "Channel 14 and Direct Polls are right",
         "Anchor the average to the DP/Channel 14 family", None),
        ("polls", "mainstream", "Only the mainstream pollsters are right",
         "Drop Channel 14 and Direct Polls from the anchor", None),
    ]
    return S


KEYS = ["gov61", "gov_amcha61", "opp61", "opp_amcha61", "opp_raam61", "opp_arab61",
        "opp_haredi61", "deadlock"]


def summarise(summ):
    out = {k: summ["paths"][k] for k in KEYS}
    out.update({f"seats_{b}": summ["blocs"][b]["mean"] for b in ["gov", "opp", "arab", "amcha", "haredi"]})
    out.update({f"in_{p}": summ["party"][p]["p_in"] for p in ["rzp", "raam", "amcha", "reservists", "joint_list"]})
    out["likud_largest"] = summ["party"]["likud"]["p_largest"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default="2026-10-07")
    ap.add_argument("--n", type=int, default=10000)
    a = ap.parse_args()
    ctx = build_model(a.run_date)
    base, _ = run(ctx, "consensus", n=a.n)
    res = {"baseline": summarise(base)}
    meta = []
    for group, key, label, why, sc in scenarios(ctx):
        if key == "ch14":
            summ, _ = run(ctx, "ch14_world", n=a.n)
        elif key == "mainstream":
            summ, _ = run(ctx, "mainstream", n=a.n)
        elif key == "no_shas_fix":
            import copy
            e = copy.deepcopy(ctx["err"]); e.party_shift = {}
            summ, _ = run(ctx, "consensus", n=a.n, err=e)
        else:
            summ, _ = run(ctx, "consensus", scenario=sc, n=a.n)
        res[key] = summarise(summ)
        meta.append(dict(group=group, key=key, label=label, why=why))
        b, r = res["baseline"], res[key]
        print(f"{label:58s} gov+A {r['gov_amcha61']:.2f} ({r['gov_amcha61']-b['gov_amcha61']:+.2f})  "
              f"opp {r['opp61']:.2f} ({r['opp61']-b['opp61']:+.2f})  "
              f"gov {r['seats_gov']:.1f} opp {r['seats_opp']:.1f} arab {r['seats_arab']:.1f}")

    # grids: Arab turnout x bloc swing; Likud stay-home sweep
    arab = [0.40, 0.45, 0.50, 0.53, 0.56, 0.60, 0.65, 0.70]
    swing = [-4, -3, -2, -1, 0, 1, 2, 3, 4]
    grid = {"arab": arab, "swing": swing, "gov_amcha61": [], "opp61": [], "opp_amcha61": [], "deadlock": []}
    for t in arab:
        rows = {k: [] for k in ["gov_amcha61", "opp61", "opp_amcha61", "deadlock"]}
        for s in swing:
            summ, _ = run(ctx, "consensus", Scenario(seg_mult={"arab": t / AR0}, bloc_shift=s), n=4000)
            for k in rows:
                rows[k].append(summ["paths"][k])
        for k in rows:
            grid[k].append(rows[k])
    sweep = {"swing": [], "gov_amcha61": [], "gov61": [], "opp61": []}
    for s in np.arange(-6, 9.5, 0.5):
        summ, _ = run(ctx, "consensus", Scenario(bloc_shift=float(s)), n=4000)
        sweep["swing"].append(float(s))
        for k in ["gov_amcha61", "gov61", "opp61"]:
            sweep[k].append(summ["paths"][k])
    json.dump(dict(n=a.n, baseline=res["baseline"], scenarios=meta, results=res, grid=grid,
                   sweep=sweep), open("output/dynamics.json", "w"), indent=1)
    print("wrote output/dynamics.json")


if __name__ == "__main__":
    main()
