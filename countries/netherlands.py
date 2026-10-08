"""Netherlands, Tweede Kamer. Polls report projected seats out of 150.

Seats: one national list, D'Hondt; a party needs one full quota (1/150 of votes).
List combinations were abolished from 2017 on.
"""
COUNTRY = "Netherlands"
ALIASES = {
    "vvd": ["VVD", "People's Party for Freedom and Democracy"],
    "pvv": ["PVV", "Party for Freedom"],
    "cda": ["CDA", "Christian Democratic Appeal"],
    "d66": ["D66", "Democrats 66"],
    "gl": ["GL", "GroenLinks"],
    "pvda": ["PvdA", "Labour Party"],
    "glpvda": ["GL–PvdA", "GL/PvdA", "GroenLinks–PvdA", "GL-PvdA", "PvdA–GL"],
    "sp": ["SP", "Socialist Party"],
    "cu": ["CU", "Christian Union"],
    "pvdd": ["PvdD", "Party for the Animals"],
    "plus50": ["50+", "50PLUS", "50Plus"],
    "sgp": ["SGP", "Reformed Political Party"],
    "denk": ["DENK", "Denk"],
    "fvd": ["FvD", "Forum for Democracy"],
    "ja21": ["JA21"],
    "volt": ["Volt", "Volt Netherlands"],
    "bij1": ["BIJ1"],
    "bbb": ["BBB", "Farmer–Citizen Movement", "Farmer-Citizen Movement"],
    "nsc": ["NSC", "New Social Contract"],
}
FAMILY = {"vvd": "R", "pvv": "R", "cda": "R", "fvd": "R", "ja21": "R", "sgp": "R", "bbb": "R", "nsc": "R",
          "d66": "L", "gl": "L", "pvda": "L", "glpvda": "L", "sp": "L", "pvdd": "L", "volt": "L", "bij1": "L",
          "denk": "L", "cu": "X", "plus50": "X"}
_base = dict(seats=150, threshold=100 / 150, method="dhondt", poll_unit="seats", others_pct=1.0,
             majority=76, wiki="Dutch_general")
_p17 = ["vvd", "pvda", "pvv", "sp", "cda", "d66", "cu", "gl", "sgp", "pvdd", "plus50"]
ELECTIONS = {
    "2017": dict(_base, date="2017-03-15", parties=_p17 + ["denk", "fvd"]),
    "2021": dict(_base, date="2021-03-17", parties=["vvd", "pvv", "cda", "d66", "gl", "sp", "pvda", "cu", "pvdd",
                                                    "plus50", "sgp", "denk", "fvd", "ja21", "volt", "bij1", "bbb"]),
    "2023": dict(_base, date="2023-11-22", parties=["vvd", "d66", "pvv", "cda", "sp", "glpvda", "fvd", "pvdd", "cu",
                                                    "volt", "ja21", "sgp", "denk", "plus50", "bbb", "bij1", "nsc"]),
    "2025": dict(_base, date="2025-10-29", parties=["pvv", "glpvda", "vvd", "nsc", "d66", "bbb", "cda", "sp", "denk",
                                                    "pvdd", "fvd", "sgp", "cu", "volt", "ja21", "plus50"]),
}
