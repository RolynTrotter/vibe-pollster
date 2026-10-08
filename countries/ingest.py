"""Parse every configured country's Wikipedia snapshots into standard tables.

python -m countries.ingest
-> data/processed/multi/polls.csv   country, election, poll_id, date, days_out, pollster, n, party, value, share
   data/processed/multi/results.csv country, election, party, votes, pct, seats, seats_total
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd

from countries import COUNTRIES, load
from pollster.polls import add_shares
from pollster.wiki import parse_polls, parse_results

RAW = "data/raw/wiki"
OUT = "data/processed/multi"


def ingest_country(name: str):
    C = load(name)
    P, R = [], []
    for eid, e in C.ELECTIONS.items():
        ed = date.fromisoformat(e["date"])
        stem = f"{e['wiki']}_{ed.year}"
        p = parse_polls(f"{RAW}/polls_{stem}.html", C.ALIASES, ed, max_days=120)
        r = parse_results(f"{RAW}/elec_{stem}.html", C.ALIASES, prefer=e.get("results_prefer", "party"))
        if p.empty or r.empty:
            print(f"!! {name} {eid}: polls {len(p)} results {len(r)}")
            continue
        p = p[p.party.isin(e["parties"])].copy()
        # typos on the page (e.g. '196' for 19.6): drop impossible cells
        cap = e["seats"] * 0.7 if e["poll_unit"] == "seats" else 75
        bad = p.value > cap
        if bad.any():
            print(f"   dropped {int(bad.sum())} impossible cells: {p.loc[bad, ['date', 'firm', 'party', 'value']].values.tolist()}")
        p = p[~bad]
        p["country"], p["election"] = C.COUNTRY, eid
        p["pollster"] = p.firm.str.replace(r"\s*\(.*?\)", "", regex=True).str.strip()
        p["poll_id"] = f"{name}_{eid}_" + p.poll_key.astype(str)
        if e["poll_unit"] == "seats":
            p["seats"] = p["value"]
            p["sub_pct"] = float("nan")
            p = add_shares(p, total_seats=e["seats"], others_pct=e.get("others_pct") or 1.0,
                           threshold=e["threshold"])
        else:
            p["share"] = p["value"]
        r["country"], r["election"] = C.COUNTRY, eid
        r["seats_total"] = int(r.seats.sum()) if "seats_total" not in e else e["seats_total"]
        P.append(p)
        R.append(r)
        fin = p[p.days_out <= 30]
        listed = r[r.party.isin(e["parties"])]
        print(f"{C.COUNTRY:12s} {eid}: {p.poll_id.nunique():4d} polls ({fin.poll_id.nunique()} in last 30d, "
              f"{fin.pollster.nunique()} houses); results {len(r)} parties, {listed.pct.sum():.1f}% of vote, "
              f"{r.seats.sum()} seats; missing in results: {sorted(set(e['parties']) - set(r.party))}")
    return pd.concat(P), pd.concat(R)


def main():
    os.makedirs(OUT, exist_ok=True)
    Ps, Rs = [], []
    for c in COUNTRIES:
        p, r = ingest_country(c)
        Ps.append(p)
        Rs.append(r)
    P = pd.concat(Ps)
    cols = ["country", "election", "poll_id", "date", "days_out", "pollster", "n", "party", "value", "share"]
    P[cols].to_csv(f"{OUT}/polls.csv", index=False)
    pd.concat(Rs)[["country", "election", "party", "votes", "pct", "seats", "seats_total"]].to_csv(
        f"{OUT}/results.csv", index=False)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
