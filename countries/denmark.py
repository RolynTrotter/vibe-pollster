"""Denmark, Folketing. 175 seats in Denmark proper (+4 from the Faroes and Greenland,
not modelled). Polls report vote %. Seats: largest remainder (Hare) nationally
among parties with >=2%; bloc majority shown for the 175 mainland seats (88)."""
COUNTRY = "Denmark"
ALIASES = {
    "a": ["A", "Social Democrats", "Social Democratic Party"],
    "v": ["V", "Venstre", "Liberal Party"],
    "o": ["O", "Danish People's Party"],
    "b": ["B", "Danish Social Liberal Party", "Social Liberals", "Social Liberal Party"],
    "f": ["F", "Socialist People's Party", "Green Left"],
    "oe": ["Ø", "Red–Green Alliance", "Red-Green Alliance"],
    "c": ["C", "Conservative People's Party", "Conservatives"],
    "aa": ["Å", "The Alternative", "Alternative"],
    "d": ["D", "New Right", "Nye Borgerlige"],
    "i": ["I", "Liberal Alliance"],
    "k": ["K", "Christian Democrats"],
    "m": ["M", "Moderates", "The Moderates"],
    "ae": ["Æ", "Denmark Democrats"],
    "p": ["P", "Stram Kurs", "Hard Line"],
    "e": ["E", "Klaus Riskær Pedersen"],
    "q": ["Q", "Independent Greens", "Frie Grønne"],
}
FAMILY = {"a": "L", "b": "L", "f": "L", "oe": "L", "aa": "L", "q": "L",
          "v": "R", "o": "R", "c": "R", "i": "R", "d": "R", "k": "R", "ae": "R", "p": "R", "e": "X", "m": "X"}
_base = dict(seats=175, threshold=2.0, method="hare", poll_unit="pct", others_pct=None, majority=88,
             wiki="Danish_general")
ELECTIONS = {
    "2015": dict(_base, date="2015-06-18", parties=["v", "a", "o", "b", "f", "oe", "i", "c", "k", "aa"],
                 coalitions={"Red bloc": ["a", "b", "f", "oe", "aa"], "Blue bloc": ["v", "o", "i", "c", "k"]}),
    "2019": dict(_base, date="2019-06-05", parties=["a", "o", "v", "oe", "i", "aa", "b", "f", "c", "k", "d", "e", "p"],
                 coalitions={"Red bloc": ["a", "b", "f", "oe", "aa"], "Blue bloc": ["v", "o", "i", "c", "k", "d", "p"]}),
    "2022": dict(_base, date="2022-11-01", parties=["a", "v", "o", "b", "f", "oe", "c", "aa", "d", "i", "k", "m", "q", "ae"],
                 coalitions={"Red bloc": ["a", "b", "f", "oe", "aa", "q"], "Blue bloc": ["v", "o", "c", "d", "i", "k", "ae"],
                             "Red bloc + Moderates": ["a", "b", "f", "oe", "aa", "q", "m"]}),
}
