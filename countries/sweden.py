"""Sweden, Riksdag (349 seats). Polls report vote %.

Seats: modified Sainte-Lague nationally among parties with >=4% (first divisor 1.4
until 2014, 1.2 from 2018). The real allocation adds constituency seats, but the
adjustment seats make the national result proportional, which this reproduces.
"""
COUNTRY = "Sweden"
ALIASES = {
    "s": ["S", "Swedish Social Democratic Party", "Social Democrats"],
    "m": ["M", "Moderate Party", "Moderates"],
    "sd": ["SD", "Sd", "Sweden Democrats"],
    "mp": ["MP", "Mp", "Green Party"],
    "c": ["C", "Centre Party"],
    "v": ["V", "Left Party"],
    "l": ["L", "Fp", "FP", "Liberals", "Liberal People's Party"],
    "kd": ["KD", "Kd", "Christian Democrats"],
    "fi": ["Fi", "FI", "Feminist Initiative"],
}
_base = dict(seats=349, threshold=4.0, method="modified_sainte_lague", first_divisor=1.2,
             poll_unit="pct", others_pct=None, majority=175, wiki="Swedish_general")
ELECTIONS = {
    "2014": dict(_base, date="2014-09-14", first_divisor=1.4,
                 parties=["s", "m", "sd", "mp", "c", "v", "l", "kd", "fi"],
                 family={"s": "L", "v": "L", "mp": "L", "fi": "L", "m": "R", "c": "R", "l": "R", "kd": "R", "sd": "X"},
                 coalitions={"Red-greens (S+V+MP)": ["s", "v", "mp"], "Alliance (M+C+L+KD)": ["m", "c", "l", "kd"]}),
    "2018": dict(_base, date="2018-09-09", parties=["s", "m", "sd", "mp", "c", "v", "l", "kd", "fi"],
                 family={"s": "L", "v": "L", "mp": "L", "fi": "L", "m": "R", "c": "R", "l": "R", "kd": "R", "sd": "X"},
                 coalitions={"Red-greens (S+V+MP)": ["s", "v", "mp"], "Alliance (M+C+L+KD)": ["m", "c", "l", "kd"],
                             "Alliance+SD": ["m", "c", "l", "kd", "sd"]}),
    "2022": dict(_base, date="2022-09-11", parties=["s", "m", "sd", "c", "v", "kd", "l", "mp"],
                 family={"s": "L", "v": "L", "mp": "L", "c": "L", "m": "R", "kd": "R", "l": "R", "sd": "R"},
                 coalitions={"Right (M+KD+L+SD)": ["m", "kd", "l", "sd"], "Left (S+V+MP+C)": ["s", "v", "mp", "c"]}),
}
FAMILY = {}
