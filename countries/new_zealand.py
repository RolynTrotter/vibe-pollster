"""New Zealand, House of Representatives (MMP, 120 nominal seats). Polls report party-vote %.

Seats: Sainte-Lague among parties with >=5% of the party vote or an electorate seat.
Electorate exemptions are those expected beforehand (ACT's Epsom since 2008;
Te Pati Maori's Waiariki, won 2020). Overhang seats are ignored (seat shares compared)."""
COUNTRY = "New Zealand"
ALIASES = {
    "nat": ["NAT", "National", "National Party", "New Zealand National Party"],
    "lab": ["LAB", "Labour", "Labour Party", "New Zealand Labour Party"],
    "grn": ["GRN", "Green", "Green Party", "Green Party of Aotearoa New Zealand"],
    "nzf": ["NZF", "New Zealand First", "NZ First"],
    "act": ["ACT", "ACT New Zealand", "ACT Party"],
    "mri": ["MRI", "TPM", "Māori Party", "Maori Party", "Te Pāti Māori"],
    "top": ["TOP", "The Opportunity Party", "The Opportunities Party", "Opportunity", "Opportunities"],
    "con": ["CON", "Conservative", "New Conservative", "NCP", "Conservative Party"],
}
FAMILY = {"lab": "L", "grn": "L", "mri": "L", "nat": "R", "act": "R", "con": "R", "nzf": "X", "top": "X"}
_base = dict(seats=120, threshold=5.0, method="sainte_lague", poll_unit="pct", others_pct=None,
             majority=61, wiki="New_Zealand_general")
ELECTIONS = {
    "2017": dict(_base, date="2017-09-23", parties=["nat", "lab", "grn", "nzf", "mri", "act", "top", "con"], exempt=["act"],
                 coalitions={"Labour+Greens": ["lab", "grn"], "National+ACT": ["nat", "act"],
                             "Labour+Greens+NZF": ["lab", "grn", "nzf"]}),
    "2020": dict(_base, date="2020-10-17", parties=["nat", "lab", "nzf", "grn", "act", "top", "mri", "con"], exempt=["act"],
                 coalitions={"Labour alone": ["lab"], "Labour+Greens": ["lab", "grn"], "National+ACT": ["nat", "act"]}),
    "2023": dict(_base, date="2023-10-14", parties=["lab", "nat", "grn", "act", "mri", "nzf", "top", "con"], exempt=["act", "mri"], seats_total=123,
                 coalitions={"National+ACT": ["nat", "act"], "National+ACT+NZF": ["nat", "act", "nzf"],
                             "Labour+Greens+TPM": ["lab", "grn", "mri"]}),
}
