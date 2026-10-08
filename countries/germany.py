"""Germany, Bundestag. Polls report national party-list vote %; CDU and CSU poll jointly.

Seats: Sainte-Lague among parties with >=5% of list votes, or with >=3 constituency
wins (Grundmandatsklausel). Before 2025 overhang/levelling seats made the Bundestag
larger than its 598 nominal seats; comparisons use seat *shares*.
"""
COUNTRY = "Germany"
ALIASES = {
    "union": ["Union", "CDU/CSU", "CDU", "Christian Democratic Union", "Christian Social Union", "CSU"],
    "spd": ["SPD", "Social Democratic Party", "Social Democratic Party of Germany"],
    "afd": ["AfD", "Alternative for Germany"],
    "fdp": ["FDP", "Free Democratic Party"],
    "linke": ["Linke", "Die Linke", "The Left", "Left"],
    "gruene": ["Grüne", "Greens", "Alliance 90/The Greens", "Alliance 90/the Greens", "B90/Grüne"],
    "bsw": ["BSW", "Sahra Wagenknecht Alliance", "Sahra Wagenknecht Alliance – Reason and Justice",
            "Sahra Wagenknecht Alliance – For Reason and Justice"],
    "fw": ["FW", "Free Voters"],
    "piraten": ["Piraten", "Pirate Party Germany", "Pirate Party"],
}
FAMILY = {"union": "R", "fdp": "R", "afd": "R", "fw": "R", "spd": "L", "gruene": "L",
          "linke": "L", "bsw": "X", "piraten": "X"}
_base = dict(seats=598, threshold=5.0, method="sainte_lague", poll_unit="pct", others_pct=None,
             majority=None, wiki="German_federal")
ELECTIONS = {
    "2013": dict(_base, date="2013-09-22", parties=["union", "spd", "fdp", "linke", "gruene", "piraten", "afd"],
                 coalitions={"Union+FDP": ["union", "fdp"], "SPD+Greens": ["spd", "gruene"],
                             "SPD+Greens+Left": ["spd", "gruene", "linke"], "Union+SPD": ["union", "spd"]}),
    "2017": dict(_base, date="2017-09-24", parties=["union", "spd", "linke", "gruene", "fdp", "afd"],
                 coalitions={"Union+FDP": ["union", "fdp"], "Union+FDP+Greens": ["union", "fdp", "gruene"],
                             "SPD+Greens+Left": ["spd", "gruene", "linke"], "Union+SPD": ["union", "spd"]}),
    "2021": dict(_base, date="2021-09-26", parties=["union", "spd", "afd", "fdp", "linke", "gruene", "fw"],
                 exempt=["linke"], seats_total=736,  # Left held 5 constituencies in 2017; expected to keep >=3. SSW won 1 seat.
                 coalitions={"SPD+Greens+FDP": ["spd", "gruene", "fdp"], "Union+Greens+FDP": ["union", "gruene", "fdp"],
                             "SPD+Greens+Left": ["spd", "gruene", "linke"], "Union+SPD": ["union", "spd"]}),
    "2025": dict(_base, date="2025-02-23", seats=630, parties=["union", "afd", "spd", "gruene", "linke", "bsw", "fdp", "fw"],
                 coalitions={"Union+SPD": ["union", "spd"], "Union+Greens": ["union", "gruene"],
                             "Union+SPD+Greens": ["union", "spd", "gruene"]}),
}
