"""Build the 2015-2022 backtest: pre-election polls and official results.

Sources (gzipped snapshots in data/raw/backtest/): Wikipedia "Opinion polling for the
<year> Israeli legislative election" and "<year> Israeli legislative election"
pages. Outputs data/processed/backtest_polls.csv and backtest_results.csv.

Families: N = Netanyahu-aligned right, H = haredi, A = Arab, O = opposition,
S = uncommitted (Kulanu 2015, Yamina 2021). These match israel/config.py.
"""
from __future__ import annotations

import io
import re
from datetime import date

import numpy as np
import pandas as pd

from pollster.polls import add_shares

MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

# election id -> (file stem, table index, election date, column map, result map)
ELECTIONS = {
    "2015": dict(
        stem="2015", table=0, date=date(2015, 3, 17),
        cols={"Likud": "likud", "Yisrael Beiteinu": "yb", "Yesh Atid": "yesh_atid",
              "Labor": "zionist_union", "Jewish Home": "jewish_home", "Shas": "shas",
              "UTJ": "utj", "Meretz": "meretz", "Hadash [a]": "joint_list",
              "Yachad [b]": "yachad", "Kulanu": "kulanu"},
        results={"Likud": "likud", "Zionist Union": "zionist_union",
                 "Joint List": "joint_list", "Yesh Atid": "yesh_atid", "Kulanu": "kulanu",
                 "The Jewish Home": "jewish_home", "Shas": "shas",
                 "Yisrael Beiteinu": "yb", "United Torah Judaism": "utj",
                 "Meretz": "meretz", "Yachad": "yachad"},
        family={"likud": "N", "yb": "N", "jewish_home": "N", "yachad": "N",
                "shas": "H", "utj": "H", "joint_list": "A", "yesh_atid": "O",
                "zionist_union": "O", "meretz": "O", "kulanu": "S"}),
    "2019a": dict(
        stem="April_2019", table=2, date=date(2019, 4, 9),
        cols={"Likud": "likud", "Labor": "labor", "Blue\xa0& White": "blue_white",
              "Kulanu": "kulanu", "Ra'am –Balad": "raam_balad", "Shas": "shas",
              "UTJ": "utj", "URWP": "urwp", "Yisrael Beiteinu": "yb", "Meretz": "meretz",
              "Hadash –Ta'al": "hadash_taal", "New Right": "new_right",
              "Gesher": "gesher", "Zehut": "zehut"},
        results={"Likud": "likud", "Blue and White": "blue_white", "Shas": "shas",
                 "United Torah Judaism": "utj", "Hadash–Ta'al": "hadash_taal",
                 "Labor Party": "labor", "Yisrael Beiteinu": "yb",
                 "Union of Right-Wing Parties": "urwp", "Meretz": "meretz",
                 "Kulanu": "kulanu", "United Arab List–Balad": "raam_balad",
                 "New Right": "new_right", "Zehut": "zehut", "Gesher": "gesher"},
        family={"likud": "N", "kulanu": "N", "urwp": "N", "yb": "N", "new_right": "N",
                "zehut": "N", "shas": "H", "utj": "H", "raam_balad": "A",
                "hadash_taal": "A", "labor": "O", "blue_white": "O", "meretz": "O",
                "gesher": "O"}),
    "2019b": dict(
        stem="September_2019", table=1, date=date(2019, 9, 17),
        cols={"Likud": "likud", "Blue\xa0& White": "blue_white", "Joint List": "joint_list",
              "Shas": "shas", "UTJ": "utj", "Yamina": "yamina", "Labor- Gesher": "labor",
              "Yisrael Beiteinu": "yb", "Dem. Union": "dem_union",
              "Otzma Yehudit": "otzma"},
        results={"Blue and White": "blue_white", "Likud": "likud",
                 "Joint List": "joint_list", "Shas": "shas", "Yisrael Beiteinu": "yb",
                 "United Torah Judaism": "utj", "Yamina": "yamina",
                 "Labor–Gesher": "labor", "Democratic Union": "dem_union",
                 "Otzma Yehudit": "otzma"},
        family={"likud": "N", "yamina": "N", "otzma": "N", "shas": "H", "utj": "H",
                "joint_list": "A", "blue_white": "O", "labor": "O", "yb": "O",
                "dem_union": "O"}),
    "2020": dict(
        stem="2020", table=0, date=date(2020, 3, 2),
        cols={"Blue & White": "blue_white", "Likud": "likud", "Joint List": "joint_list",
              "Emet": "emet", "Shas": "shas", "Yisrael Beiteinu": "yb", "UTJ": "utj",
              "Yamina": "yamina", "Otzma": "otzma"},
        results={"Likud": "likud", "Blue and White": "blue_white",
                 "Joint List": "joint_list", "Shas": "shas",
                 "United Torah Judaism": "utj", "Labor-Gesher-Meretz": "emet",
                 "Yisrael Beiteinu": "yb", "Yamina": "yamina", "Otzma Yehudit": "otzma"},
        family={"likud": "N", "yamina": "N", "otzma": "N", "shas": "H", "utj": "H",
                "joint_list": "A", "blue_white": "O", "emet": "O", "yb": "O"}),
    "2021": dict(
        stem="2021", table=0, date=date(2021, 3, 23),
        cols={"Likud": "likud", "Yesh Atid": "yesh_atid", "Blue & White": "blue_white",
              "Joint List": "joint_list", "Shas": "shas", "UTJ": "utj",
              "Yisrael Beiteinu": "yb", "Meretz": "meretz", "Ra'am": "raam",
              "Yamina": "yamina", "New Hope": "new_hope", "Labor": "labor",
              "Religious Zionist[a]": "rzp", "New Economic": "new_economic"},
        results={"Likud": "likud", "Yesh Atid": "yesh_atid", "Shas": "shas",
                 "Blue and White": "blue_white", "Yamina": "yamina",
                 "Israeli Labor Party": "labor", "United Torah Judaism": "utj",
                 "Yisrael Beiteinu": "yb", "Religious Zionist Party": "rzp",
                 "Joint List": "joint_list", "New Hope": "new_hope", "Meretz": "meretz",
                 "Ra'am": "raam", "New Economic Party": "new_economic"},
        family={"likud": "N", "rzp": "N", "shas": "H", "utj": "H", "joint_list": "A",
                "raam": "A", "yesh_atid": "O", "blue_white": "O", "yb": "O",
                "meretz": "O", "new_hope": "O", "labor": "O", "new_economic": "O",
                "yamina": "S"}),
    "2022": dict(
        stem="2022", table=0, date=date(2022, 11, 1),
        cols={"Likud": "likud", "Yesh Atid": "yesh_atid", "National Unity": "national_unity",
              "Shas": "shas", "Jewish Home": "jewish_home", "Labor": "labor", "UTJ": "utj",
              "Yisrael Beiteinu": "yb", "RZP- OY": "rzp", "Hadash –Ta'al": "hadash_taal",
              "Meretz": "meretz", "Ra'am": "raam", "Balad": "balad"},
        results={"Likud": "likud", "Yesh Atid": "yesh_atid",
                 "Religious Zionism-Otzma Yehudit": "rzp", "National Unity": "national_unity",
                 "Shas": "shas", "United Torah Judaism": "utj", "Yisrael Beiteinu": "yb",
                 "Ra'am": "raam", "Hadash–Ta'al": "hadash_taal",
                 "Israeli Labor Party": "labor", "Meretz": "meretz", "Balad": "balad",
                 "The Jewish Home": "jewish_home"},
        family={"likud": "N", "rzp": "N", "jewish_home": "N", "shas": "H", "utj": "H",
                "hadash_taal": "A", "raam": "A", "balad": "A", "yesh_atid": "O",
                "national_unity": "O", "labor": "O", "yb": "O", "meretz": "O"}),
}

SURPLUS_2022 = [("likud", "rzp"), ("yesh_atid", "national_unity"), ("shas", "utj"),
                ("labor", "meretz"), ("hadash_taal", "raam")]


def canon_pollster(firm: str, publisher: str = "") -> str | None:
    s = f"{firm} {publisher}"
    rules = [("Panel Project HaMidgam", "Midgam Project (Ch13)"),
             ("Midgam", "Midgam (Ch12)"), ("Panels", "Lazar"), ("Lazar", "Lazar"),
             ("KANTAR", "Kantar"), ("Kantar", "Kantar"), ("TNS", "Kantar"),
             ("Fuchs", "Fuchs (Ch13)"), ("Maagar Mo", "Maagar Mochot"),
             ("Direct Polls", "Direct Polls"), ("Smith", "Smith"), ("Dialog", "Dialog"),
             ("Teleseker", "Teleseker"), ("Geocartography", "Geocartography"),
             ("Shvakim", "Shvakim Panorama"), ("Miskar", "Miskar"),
             ("Statnet", "Statnet"), ("Channel 2", "Midgam (Ch12)"),
             ("Channel 10", "Dialog"), ("Channel 1", "Teleseker")]
    for k, v in rules:
        if k in s:
            return v
    return None


def parse_date(s: str, edate: date) -> date | None:
    m = re.findall(r"(\d{1,2})\s+([A-Z][a-z]{2})(?:\s+(\d{2,4}))?", str(s))
    if not m:
        return None
    d, mon, yr = m[-1]
    if mon not in MONTHS:
        return None
    y = int(yr) + (2000 if yr and len(yr) == 2 else 0) if yr else edate.year
    if not yr and MONTHS[mon] > edate.month + 1:   # e.g. Dec polls for a Mar election
        y -= 1
    return date(y, MONTHS[mon], int(d))


def num(v):
    """Seats from a cell: int seats, '(x%)' -> 0 seats with pct, else NaN."""
    s = str(v)
    m = re.match(r"\(([\d.]+)%\)", s)
    if m:
        return 0, float(m.group(1))
    m = re.match(r"^(\d+)", s)
    if m:
        return int(m.group(1)), None
    return None, None


def read_tables(path):
    import gzip
    import os
    h = (open(path, encoding="utf8").read() if os.path.exists(path)
         else gzip.open(path + ".gz", "rt", encoding="utf8").read())
    h = re.sub(r'(colspan|rowspan)="(\d+)[^"]*"', r'\1="\2"', h)
    return pd.read_html(io.StringIO(h))


def build(days_window: int = 45):
    polls, results = [], []
    for eid, e in ELECTIONS.items():
        t = read_tables(f"data/raw/backtest/polls_{e['stem']}.html")[e["table"]]
        t.columns = [c[0] if isinstance(c, tuple) else c for c in t.columns]
        firm_col = "Poll" if "Poll" in t.columns else "Polling firm"
        for _, r in t.iterrows():
            firm, pub = str(r[firm_col]), str(r.get("Publisher", ""))
            if re.search(r"exit|result|Election|silence|Seats|Outgoing|Pre-", firm + pub, re.I):
                continue
            d = parse_date(r["Date"], e["date"])
            house = canon_pollster(firm, pub)
            if d is None or house is None or d >= e["date"]:
                continue
            days = (e["date"] - d).days
            if days > days_window:
                continue
            rec = []
            for col, key in e["cols"].items():
                if col not in t.columns:
                    continue
                s, pct = num(r[col])
                if s is None:
                    continue
                rec.append(dict(party=key, seats=s, sub_pct=pct))
            if len(rec) < len(e["cols"]) - 3 or sum(x["seats"] for x in rec) not in range(115, 126):
                continue
            pid = f"{eid}_{len(polls)}"
            for x in rec:
                polls.append(dict(election=eid, poll_id=pid, date=d.isoformat(),
                                  days_out=days, pollster=house, family=e["family"][x["party"]],
                                  **x))
        # results
        for tab in read_tables(f"data/raw/backtest/elec_{e['stem']}.html"):
            cols = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in tab.columns]
            if "Votes" in cols and "%" in cols:
                tab.columns = cols
                break
        name_col = "Party.1"
        tot_valid = pd.to_numeric(tab.loc[tab[name_col] == "Total", "Votes"], errors="coerce").iloc[0]
        for _, r in tab.iterrows():
            key = e["results"].get(str(r[name_col]).strip())
            if key:
                v = float(r["Votes"])
                results.append(dict(election=eid, party=key, votes=v,
                                    pct=100 * v / tot_valid, seats=int(r["Seats"]),
                                    family=e["family"][key]))
        results.append(dict(election=eid, party="others", votes=np.nan,
                            pct=100 - sum(x["pct"] for x in results if x["election"] == eid),
                            seats=0, family="X"))
    P = pd.DataFrame(polls)
    # Seat totals vary when some cells are missing; normalise each poll to 120.
    P["seats"] = P["seats"].astype(float)
    P = add_shares(P, total_seats=120, others_pct=1.5)
    R = pd.DataFrame(results)
    return P, R


if __name__ == "__main__":
    P, R = build()
    P.to_csv("data/processed/backtest_polls.csv", index=False)
    R.to_csv("data/processed/backtest_results.csv", index=False)
    print(P.groupby("election").poll_id.nunique())
    print(P.groupby("pollster").poll_id.nunique().sort_values(ascending=False))
    print(R.pivot_table(index="party", columns="election", values="pct").round(2))
