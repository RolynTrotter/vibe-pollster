"""Seat rules reproduce official results across countries (where no overhang distorts them)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from countries import load  # noqa: E402
from pollster.systems import system_from_spec  # noqa: E402

CASES = [("sweden", "2018"), ("sweden", "2022"), ("denmark", "2015"), ("denmark", "2019"),
         ("new_zealand", "2017"), ("netherlands", "2021"), ("germany", "2017")]


def test_official_seats():
    R = pd.read_csv(ROOT / "data/processed/multi/results.csv", dtype={"election": str})
    for c, eid in CASES:
        C = load(c)
        e = C.ELECTIONS[eid]
        r = R[(R.country == C.COUNTRY) & (R.election == eid)]
        v = np.append(r.pct.values, 100 - r.pct.sum())
        got = system_from_spec(e).allocate(v, r.party.tolist() + ["others"])[:-1]
        scaled = r.seats.values * e["seats"] / e.get("seats_total", r.seats.sum())
        assert np.abs(got - scaled).max() <= 1.0, (c, eid, dict(zip(r.party, got)), dict(zip(r.party, scaled.round(1))))


if __name__ == "__main__":
    test_official_seats()
    print("ok: seat rules match official results (within 1 seat after scaling)")
