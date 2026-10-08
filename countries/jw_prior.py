"""Fit a global poll-error prior from Jennings & Wlezien (2018), "Election polling
errors across time and space", Nature Human Behaviour (Harvard Dataverse
doi:10.7910/DVN/8421DX): poll-of-polls vs result for 314 elections in 45 countries.

Uses legislative elections since 1990, days 0-45 before the vote, one error per
party per election per horizon band, and fits
    E[err^2] = a + b*share + c*share*days + e*days.
python -m countries.jw_prior /path/to/LONG_MI_NATURE_20180111.tab
"""
import json
import sys

import numpy as np
import pandas as pd


def main(path):
    J = pd.read_csv(path, sep="\t", usecols=["country", "election", "electionyr", "daysbeforeED",
                                              "poll_", "vote_", "partyid", "electionid"])
    J = J.dropna(subset=["poll_", "vote_"])
    J["eid"] = J.country + " " + J.electionid.astype(str)
    L = J[(J.election == "Legislative") & (J.electionyr >= 1990) & (J.daysbeforeED <= 45)].copy()
    L["err"] = L.poll_ - L.vote_
    L["band"] = pd.cut(L.daysbeforeED, [-1, 3, 10, 25, 45], labels=[0, 7, 18, 35]).astype(int)
    g = L.groupby(["eid", "partyid", "band"]).agg(err=("err", "mean"), vote=("vote_", "first"),
                                                   country=("country", "first")).reset_index()
    X = np.column_stack([np.ones(len(g)), g.vote, g.vote * g.band, g.band])
    a, b, c, e = np.linalg.lstsq(X, g.err ** 2, rcond=None)[0]
    out = dict(a=float(max(a, 0.05)), b=float(max(b, 0)), c=float(max(c, 0)), e=float(max(e, 0)),
               n_obs=int(len(g)), n_elections=int(g.eid.nunique()), n_countries=int(g.country.nunique()),
               mae_by_band={int(k): float(v) for k, v in g.groupby("band").err.apply(lambda s: s.abs().mean()).items()},
               source="Jennings & Wlezien 2018, doi:10.7910/DVN/8421DX")
    json.dump(out, open("data/processed/multi/jw_prior.json", "w"), indent=1)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
