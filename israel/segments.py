"""Who votes for whom: a segment x party composition of the Israeli electorate.

Built from the 2022 official results by ballot box (CEC expb.csv), then carried
forward to the 2026 party system and fitted to the current poll average.

Segments (ballot-box classification, documented assumptions):
  arab      boxes where Hadash-Ta'al + Ra'am + Balad >= 50% of valid votes,
            plus Arab-party votes anywhere else (mixed cities, double envelopes)
  druze     boxes in Druze localities below that 50% line
  haredi    boxes where UTJ + Shas >= 65%, plus an allowance for haredim who
            vote in mixed boxes: 80% of UTJ and 25% of Shas votes elsewhere
  dati      national-religious core: boxes where RZP-Otzma >= 35%
  jewish    everyone else (incl. soldiers' and other double-envelope votes)

The box rule misses segment members who live in mixed areas and includes some
non-members in segment boxes; it is an ecological approximation good enough
to translate "X% more Arab turnout" into votes by party.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pollster.turnout import ipf

L22 = {"מחל": "likud", "פה": "yesh_atid", "ט": "rzp_oy", "כן": "national_unity",
       "שס": "shas", "ג": "utj", "ל": "yb", "עם": "raam", "ום": "hadash_taal",
       "אמת": "labor", "מרצ": "meretz", "ד": "balad", "ב": "jewish_home"}
ARAB22 = ["hadash_taal", "raam", "balad"]
DRUZE = ["דאלית אלכרמל", "עספיא", "בית גן", "ירכא", "חורפיש", "כסראסמיע", "גולס",
         "יאנוחגת", "סאגור", "עין אלאסד", "פקיעין בוקייעה", "מסעדה", "מגדל שמס",
         "בוקעאתא", "עין קנייא", "מגאר", "ראמה", "אבו סנאן"]
SEGMENTS = ["arab", "druze", "haredi", "dati", "jewish"]

# 2026 party <- 2022 parents (weights). Only used as a *seed* for each party's
# segment profile; the fitted matrix matches 2026 poll shares exactly.
SEED_2026 = {
    "likud": {"likud": 1},
    "otzma": {"rzp_oy": 1}, "rzp": {"rzp_oy": 0.8, "jewish_home": 0.2},
    "shas": {"shas": 1}, "utj": {"utj": 1},
    "yb": {"yb": 1}, "raam": {"raam": 1}, "joint_list": {"hadash_taal": 0.6, "balad": 0.4},
    "dems": {"labor": 0.55, "meretz": 0.45},
    "together": {"yesh_atid": 0.6, "likud": 0.2, "jewish_home": 0.2},
    "yashar": {"national_unity": 0.5, "yesh_atid": 0.4, "likud": 0.1},
    "blue_white": {"national_unity": 1},
    "reservists": {"national_unity": 0.5, "likud": 0.5},
    "amcha": {"likud": 0.6, "rzp_oy": 0.4},
}


def classify_2022(path="data/raw/cec/expb25.csv") -> tuple[pd.DataFrame, pd.DataFrame]:
    b = pd.read_csv(path, encoding="utf-8-sig")
    v = b[list(L22)].rename(columns=L22).astype(float)
    valid = b["כשרים"].astype(float)
    other = valid - v.sum(axis=1)
    v["others"] = other.clip(lower=0)
    arab_sh = v[ARAB22].sum(axis=1) / valid.clip(lower=1)
    har_sh = (v.utj + v.shas) / valid.clip(lower=1)
    rz_sh = v.rzp_oy / valid.clip(lower=1)
    town = b["שם ישוב"].str.strip()
    seg = np.select(
        [arab_sh >= 0.5, town.isin(DRUZE), har_sh >= 0.65, rz_sh >= 0.35],
        ["arab", "druze", "haredi", "dati"], "jewish")
    seg = pd.Series(seg, index=b.index)
    # votes[s, party]
    M = v.groupby(seg).sum().reindex(SEGMENTS).fillna(0)
    # dispersed-member corrections
    for s in ["druze", "haredi", "dati", "jewish"]:
        for p in ARAB22:
            M.loc["arab", p] += M.loc[s, p]
            M.loc[s, p] = 0
    for p, f in [("utj", 0.8), ("shas", 0.25)]:
        for s in ["dati", "jewish"]:
            moved = M.loc[s, p] * f
            M.loc["haredi", p] += moved
            M.loc[s, p] -= moved
    # turnout by segment (geographic boxes only; double envelopes have no roll)
    geo = b["סמל ישוב"] < 9000
    elig = b.loc[geo, "בזב"].groupby(seg[geo]).sum()
    voted = b.loc[geo, "מצביעים"].groupby(seg[geo]).sum()
    T = pd.DataFrame({"eligible": elig, "voted": voted}).reindex(SEGMENTS)
    T["turnout_boxes"] = T.voted / T.eligible
    return M, T


def composition_2026(M22: pd.DataFrame, shares: dict[str, float],
                     others_pct: float = 1.5) -> pd.DataFrame:
    """Fit a segment x 2026-party vote matrix (percent of all valid votes).

    Columns sum to the 2026 poll shares; rows sum to each segment's 2022 share
    of the vote (i.e. baseline = 2022-like turnout pattern).
    """
    prof22 = M22.div(M22.sum(axis=0), axis=1)          # segment profile of each 2022 party
    seed = pd.DataFrame(0.0, index=SEGMENTS, columns=list(shares) + ["others"])
    for p in shares:
        for parent, w in SEED_2026[p].items():
            seed[p] += w * prof22[parent]
    seed["others"] = prof22["others"]
    # Arab parties stay (almost) entirely in the Arab segment; never zero a cell
    # that could plausibly be non-zero.
    seed = seed.clip(lower=1e-6)
    col = pd.Series(shares, dtype=float)
    col["others"] = others_pct
    col = col / col.sum() * 100
    row = M22.sum(axis=1) / M22.values.sum() * 100
    fitted = ipf(seed * col, row.values, col.values)
    return pd.DataFrame(fitted, index=SEGMENTS, columns=seed.columns)


if __name__ == "__main__":
    M, T = classify_2022()
    M.to_csv("data/processed/segments_votes_2022.csv")
    T.to_csv("data/processed/segments_turnout_2022.csv")
    share = M.sum(axis=1) / M.values.sum()
    print("segment share of 2022 valid votes:\n", share.round(3))
    print(T.round(3))
    prof = M.div(M.sum(axis=0), axis=1)
    print("\nshare of each 2022 party's vote by segment:\n", prof.round(2).T)
    print("\nvote split within each segment:\n", M.div(M.sum(axis=1), axis=0).round(2))
