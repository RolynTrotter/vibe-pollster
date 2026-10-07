"""Parse the Middle East Forum 2026 poll archive into a long CSV.

Usage: python -m israel.scrape_meforum data/raw/polls/meforum_polls_YYYY-MM-DD.html
Refresh the snapshot with:
  curl -sSL https://israelvote.meforum.org/polls/ -o data/raw/polls/meforum_polls_$(date +%F).html

Each cell is either seats (integer), "(x.x%)" = the party's vote share in a
poll where it fell under the threshold, or "." = not polled.
"""
from __future__ import annotations

import html as htmllib
import re
import sys

import pandas as pd

from israel.config import MEF_COLUMNS, POLLSTER_CANON


def parse(path: str) -> pd.DataFrame:
    h = open(path, encoding="utf8").read()
    head = re.search(r"<thead>(.*?)</thead>", h, re.S).group(1)
    titles = []
    for attrs, text in re.findall(r"<th([^>]*)>([^<]*)</th>", head):
        t = re.search(r'title="([^"]*)"', attrs)
        titles.append(htmllib.unescape(t.group(1) if t else text))
    body = re.search(r"<tbody>(.*?)</tbody>", h, re.S).group(1)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        rec = dict(zip(titles, cells))
        rows.append(rec)
    out = []
    for i, r in enumerate(rows):
        firm = r["Pollster"]
        n = pd.to_numeric(r.get("n", ""), errors="coerce")
        for col, key in MEF_COLUMNS.items():
            v = r.get(col, ".")
            seats = pct = None
            if v in (".", "", "–", "-"):
                continue
            m = re.match(r"\(([\d.]+)%\)", v)
            if m:
                seats, pct = 0, float(m.group(1))
            else:
                seats = int(v)
            out.append(dict(row=i, date=r["Fieldwork"], firm=firm,
                            pollster=POLLSTER_CANON.get(firm, firm),
                            publisher=r["Published By"], n=n, party=key,
                            seats=seats, sub_pct=pct))
    df = pd.DataFrame(out)
    # The archive lists some polls twice under two firm names (e.g. Lazar and
    # LRI+P4A). Drop exact duplicates of (date, house, all numbers).
    sig = (df.sort_values("party").groupby("row")
           .apply(lambda g: (g.date.iat[0], g.pollster.iat[0],
                             tuple(zip(g.party, g.seats, g.sub_pct.fillna(-1)))),
                  include_groups=False))
    keep = sig[~sig.duplicated()].index
    df = df[df.row.isin(keep)].copy()
    df["poll_id"] = df.groupby("row").ngroup()
    return df.drop(columns="row")


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else "data/processed/polls_2026.csv"
    d = parse(src)
    d.to_csv(dst, index=False)
    print(f"{d.poll_id.nunique()} polls, {d.pollster.nunique()} houses, "
          f"{d.date.min()} .. {d.date.max()} -> {dst}")
    print(d.groupby("pollster").poll_id.nunique().sort_values(ascending=False))
