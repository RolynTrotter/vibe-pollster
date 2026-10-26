"""Build polls_2026.csv from several MEF snapshots plus hand-entered polls.

The MEF archive sometimes lags the broadcasters by days and has dropped rows
it once listed (e.g. Channel 16 after its site went offline), so a single
snapshot is not enough near election day. This unions every snapshot given
(newer snapshots win on the same date+house+publisher), then appends polls
entered by hand from the publishers' own reports (wide CSV, one row per poll,
"(x.x%)" for a list under the threshold, with a source URL).

Usage:
  python -m israel.merge_polls --mef data/raw/polls/meforum_polls_2026-10-18.html \
      data/raw/polls/meforum_polls_2026-10-26.html \
      --manual data/raw/polls/hebrew_finals_2026-10-23.csv
"""
from __future__ import annotations

import argparse
import re

import pandas as pd

from israel.config import MEF_COLUMNS, POLLSTER_CANON
from israel.scrape_meforum import parse

PARTY_KEYS = list(MEF_COLUMNS.values())


def manual(path: str) -> pd.DataFrame:
    w = pd.read_csv(path, dtype=str)
    out = []
    for i, r in w.iterrows():
        firm = r["firm"]
        n = pd.to_numeric(r.get("n"), errors="coerce")
        for key in PARTY_KEYS:
            v = r.get(key)
            if v is None or pd.isna(v) or v in (".", ""):
                continue
            m = re.match(r"\(([\d.]+)%\)", v)
            seats, pct = (0, float(m.group(1))) if m else (int(v), None)
            out.append(dict(snap=999, row=i, date=r["date"], firm=firm,
                            pollster=POLLSTER_CANON.get(firm, firm),
                            publisher=r["publisher"], n=n, party=key,
                            seats=seats, sub_pct=pct))
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mef", nargs="+", required=True, help="MEF snapshots, oldest first")
    ap.add_argument("--manual", nargs="*", default=[])
    ap.add_argument("--out", default="data/processed/polls_2026.csv")
    a = ap.parse_args()

    frames = []
    for s, path in enumerate(a.mef):
        d = parse(path).rename(columns={"poll_id": "row"})
        d["snap"] = s
        frames.append(d)
    for path in a.manual:
        frames.append(manual(path))
    d = pd.concat(frames, ignore_index=True)
    key = ["date", "pollster", "publisher"]
    polls = d[key + ["snap", "row"]].drop_duplicates()
    # newest source wins for each date+house+publisher
    keep = polls.sort_values("snap").drop_duplicates(key, keep="last")[["snap", "row"]]
    d = d.merge(keep, on=["snap", "row"])
    d["poll_id"] = d.groupby(["snap", "row"]).ngroup()
    d = d.drop(columns=["snap", "row"]).sort_values(["date", "poll_id", "party"], ascending=[False, True, True])
    d.to_csv(a.out, index=False)
    print(f"{d.poll_id.nunique()} polls, {d.pollster.nunique()} houses, "
          f"{d.date.min()} .. {d.date.max()} -> {a.out}")
    print(d.groupby("pollster").agg(polls=("poll_id", "nunique"), last=("date", "max")))


if __name__ == "__main__":
    main()
