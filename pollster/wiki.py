"""Generic parsers for Wikipedia election pages.

Two page types:
  * "Opinion polling for the <year> <country> election": one or more tables
    with a date column, a pollster column, optional sample size, and one
    column per party holding percentages (or seats).
  * "<year> <country> election": a results table with party names, votes,
    vote share and seats.
Party columns/rows are matched to canonical party keys with per-country alias
lists (exact match on the first header level, or on the party name).
"""
from __future__ import annotations

import gzip
import io
import os
import re
from datetime import date

import numpy as np
import pandas as pd

MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
MONTHS.update({m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], 1)})
MONTHS["sept"] = 9


def read_html(path: str) -> str:
    if os.path.exists(path):
        return open(path, encoding="utf8").read()
    return gzip.open(path + ".gz", "rt", encoding="utf8").read()


def read_tables(path: str) -> list[pd.DataFrame]:
    h = read_html(path)
    h = re.sub(r'(colspan|rowspan)="(\d+)[^"]*"', r'\1="\2"', h)
    h = re.sub(r"<sup[^>]*>.*?</sup>", "", h, flags=re.S)          # footnote markers
    h = re.sub(r'<span[^>]*display:\s*none[^>]*>.*?</span>', "", h, flags=re.S)  # hidden sort keys
    return pd.read_html(io.StringIO(h))


def flat(col) -> list[str]:
    parts = col if isinstance(col, tuple) else (col,)
    out = []
    for p in parts:
        p = re.sub(r"\[.*?\]", "", str(p)).replace("\xa0", " ").strip()
        if p and not p.startswith("Unnamed") and p not in out:
            out.append(p)
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9äöüåæøéè]+", "", str(s).lower())


def parse_date(s, ref: date) -> date | None:
    """Last date in a fieldwork string. Handles '20–21 Sep 2017', '02.07.2021',
    '30 Aug–2 Sep 2021', 'Sep 3–5, 2020', '2021-09-01'."""
    s = str(s).replace("\xa0", " ")
    m = re.findall(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m[-1]); return date(y, mo, d)
    m = re.findall(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", s)
    if m:
        d, mo, y = m[-1]; y = int(y) + (2000 if len(y) == 2 else 0)
        return date(y, int(mo), int(d))
    yr = re.findall(r"(\d{4})", s)
    y = int(yr[-1]) if yr else None
    toks = re.findall(r"(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\s+(\d{1,2})", s)
    best = None
    for d1, m1, m2, d2 in toks:
        mon, day = (m1, d1) if m1 else (m2, d2)
        if mon.lower() in MONTHS:
            best = (MONTHS[mon.lower()], int(day))
    if best is None:
        return None
    if y is None:
        y = ref.year if best[0] <= ref.month + 1 else ref.year - 1
    try:
        return date(y, best[0], best[1])
    except ValueError:
        return None


def num(v):
    s = str(v).replace(",", ".").replace("\xa0", " ").strip()
    m = re.match(r"^[<~]?\s*(\d+(?:\.\d+)?)\s*%?$", s)
    return float(m.group(1)) if m else None


def match_key(header: list[str], aliases: dict[str, list[str]]) -> str | None:
    for h in header:
        n = norm(h)
        for k, al in aliases.items():
            if any(norm(a) == n for a in al):
                return k
    return None


def parse_polls(path: str, aliases: dict, election: date, max_days: int = 120,
                min_parties: int = 3) -> pd.DataFrame:
    """All polls on the page within `max_days` before the election (long format)."""
    rows = []
    for ti, t in enumerate(read_tables(path)):
        heads = [flat(c) for c in t.columns]
        lab = [" ".join(h).lower() for h in heads]
        dcol = next((i for i, l in enumerate(lab) if re.search(r"date|fieldwork|conducted|released", l)), None)
        fcol = next((i for i, l in enumerate(lab) if re.search(r"poll(ing)? (firm|source|company)|pollster|institute|polling firm|^firm|organisation|organization|^poll$", l)), None)
        if dcol is None or fcol is None:
            continue
        ncol = next((i for i, l in enumerate(lab) if re.search(r"sample", l)), None)
        pcols = {}
        for i, h in enumerate(heads):
            k = match_key(h, aliases)
            if k and k not in pcols.values():
                pcols[i] = k
        if len(pcols) < min_parties:
            continue
        for ri in range(len(t)):
            r = t.iloc[ri]
            firm = re.sub(r"\[.*?\]", "", str(r.iloc[fcol])).strip()
            if not firm or firm == "nan" or re.search(r"election|result|exit", firm, re.I):
                continue
            d = parse_date(r.iloc[dcol], election)
            if d is None or d >= election or (election - d).days > max_days:
                continue
            vals = {k: num(r.iloc[i]) for i, k in pcols.items()}
            got = {k: v for k, v in vals.items() if v is not None}
            if len(got) < min_parties:
                continue
            n = num(str(r.iloc[ncol]).replace(" ", "").replace(",", "").replace(".", "")) if ncol is not None else None
            for k, v in got.items():
                rows.append(dict(table=ti, row=ri, date=d.isoformat(), days_out=(election - d).days,
                                 firm=firm, n=n, party=k, value=v))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Pages also carry regional, state or electorate polls in separate tables with
    # the same party columns. Keep the national table: the one with the most polls
    # in the window (ties -> earliest on the page).
    cnt = df.groupby("table").apply(lambda g: g[["row"]].drop_duplicates().shape[0], include_groups=False)
    main = cnt[cnt == cnt.max()].index.min()
    df = df[df.table == main].copy()
    df["firm"] = df.firm.str.replace(r"\s*Archived.*$", "", regex=True).str.strip()
    # one row per (date, firm, values): drop duplicates across tables
    df["poll_key"] = df.groupby(["table", "row"]).ngroup()
    sig = df.sort_values("party").groupby("poll_key").apply(
        lambda g: (g.date.iat[0], g.firm.iat[0], tuple(zip(g.party, g.value))), include_groups=False)
    keep = sig[~sig.duplicated()].index
    return df[df.poll_key.isin(keep)].drop(columns=["table", "row"])


def parse_results(path: str, aliases: dict, prefer: str | None = None) -> pd.DataFrame:
    """Results table -> party, votes, pct, seats (for aliased parties) + total valid votes.

    Picks the table that has numeric Votes, % and Seats columns and matches the
    most aliased parties. `prefer` picks among columns, e.g. 'party' for list votes.
    """
    best = None
    for t in read_tables(path):
        if all(re.fullmatch(r"\d+", str(c)) for c in t.columns) and len(t) > 2:
            # header stored in the body: use rows down to the one containing 'Votes'
            hit = [i for i in range(min(5, len(t))) if any(str(x).strip() == "Votes" for x in t.iloc[i])]
            if not hit:
                continue
            k = hit[0]
            t = t.copy()
            t.columns = pd.MultiIndex.from_arrays([[str(x) for x in t.iloc[i]] for i in range(k + 1)])
            t = t.iloc[k + 1:]
        heads = [flat(c) for c in t.columns]
        lab = [" | ".join(h).lower() for h in heads]

        def pick(pat, avoid=r"result|\+|−|–|change|swing|constituency|electorate"):
            cands = [i for i, l in enumerate(lab) if re.search(pat, l) and not re.search(avoid, l)]
            if prefer:
                pc = [i for i in cands if prefer in lab[i]]
                cands = pc or cands
            return cands[0] if cands else None
        vcol, pcol = pick(r"votes"), pick(r"%")
        scol = pick(r"total seats|seats \| total") or pick(r"seats")
        if vcol is None or pcol is None or scol is None:
            continue
        name_cols = [i for i, l in enumerate(lab) if "party" in l or "name" in l or l == ""] or [0, 1]
        recs, total = {}, None
        for ri in range(len(t)):
            r = t.iloc[ri]
            names = [str(r.iloc[i]) for i in name_cols]
            if any(re.match(r"^\s*total", n, re.I) for n in names):
                v = num(str(r.iloc[vcol]).replace(",", "").replace(" ", "").replace(".", ""))
                total = total or v
                if recs:
                    break                      # later sections (e.g. Faroe Islands) are separate
                continue
            k = None
            for n in names:
                k = match_key([n], aliases) or match_key([re.sub(r"\s*\(.*?\)", "", n)], aliases)
                if k:
                    break
            if not k:
                continue
            v = num(str(r.iloc[vcol]).replace(",", "").replace(" ", "").replace(".", ""))
            p = num(r.iloc[pcol])
            s = num(r.iloc[scol])
            if v is None or p is None:
                continue
            if k in recs:              # e.g. CDU and CSU rows both map to 'union'
                if names[-1] in recs[k]["_names"]:
                    continue
                recs[k]["votes"] += v; recs[k]["pct"] += p; recs[k]["seats"] += int(s or 0)
                recs[k]["_names"].append(names[-1])
                continue
            recs[k] = dict(party=k, votes=v, pct=p, seats=int(s) if s is not None else 0, _names=[names[-1]])
        if not recs:
            continue
        score = len(recs)
        if best is None or score > best[0]:
            best = (score, pd.DataFrame(recs.values()).drop(columns="_names"), total)
    if best is None:
        return pd.DataFrame()
    df, total = best[1], best[2]
    df.attrs["total_votes"] = total
    return df
