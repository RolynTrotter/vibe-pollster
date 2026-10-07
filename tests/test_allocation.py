"""The seat allocator must reproduce the official 2022 Knesset result exactly."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from israel.backtest_data import SURPLUS_2022  # noqa: E402
from pollster.systems import ListPR, dhondt  # noqa: E402

OFFICIAL_2022 = {"likud": 32, "yesh_atid": 24, "rzp": 14, "national_unity": 12, "shas": 11,
                 "utj": 7, "yb": 6, "raam": 5, "hadash_taal": 5, "labor": 4,
                 "meretz": 0, "balad": 0, "jewish_home": 0}


def test_2022():
    R = pd.read_csv(Path(__file__).resolve().parents[1] / "data/processed/backtest_results.csv")
    R = R[R.election == "2022"]
    names = R.party.tolist()
    # 'others' carries the remaining valid votes (all far below threshold)
    votes = R.pct.values
    seats = ListPR(120, 3.25, SURPLUS_2022).allocate(votes, names)
    got = dict(zip(names, seats))
    for p, s in OFFICIAL_2022.items():
        assert got[p] == s, (p, got[p], s)
    assert sum(seats) == 120


def test_dhondt_small():
    assert dhondt([100, 80, 30], 5).tolist() == [3, 2, 0]


if __name__ == "__main__":
    test_2022()
    test_dhondt_small()
    print("ok: 2022 allocation matches the official result")
