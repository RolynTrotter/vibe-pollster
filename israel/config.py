"""Israel 2026 configuration: parties, blocs, error families, agreements."""
from __future__ import annotations

ELECTION_DATE = "2026-10-27"
THRESHOLD = 3.25
SEATS = 120
# Ballot structure was fixed once lists were submitted (Unity dropped out 4 Sep,
# Reservists/Zionist Home split 5 Sep). Polls before this used other line-ups.
WINDOW_START = "2026-09-05"

LABELS = {
    "likud": "Likud",
    "yashar": "Yashar (Eisenkot)",
    "together": "Together (Bennett–Lapid)",
    "dems": "The Democrats",
    "yb": "Yisrael Beytenu",
    "joint_list": "Joint List",
    "otzma": "Otzma Yehudit",
    "shas": "Shas",
    "utj": "United Torah Judaism",
    "rzp": "Religious Zionism–Zehut",
    "raam": "Ra'am",
    "amcha": "Amcha Yisrael (Winter)",
    "blue_white": "Blue and White",
    "reservists": "Reservists–Economic (Hendel)",
}
PARTIES = list(LABELS)

# MEF column title -> key
MEF_COLUMNS = {
    "Likud": "likud", "Yashar": "yashar", "Together": "together",
    "The Democrats": "dems", "Yisrael Beytenu": "yb",
    "Joint List (Hadash, Ta'al, Balad)": "joint_list", "Otzma Yehudit": "otzma",
    "Shas": "shas", "United Torah Judaism": "utj",
    "Religious Zionism with Zehut": "rzp", "Ra'am": "raam",
    "Amcha Yisrael": "amcha", "Blue and White": "blue_white",
    "Reservists and Economic Party": "reservists",
}

# Political blocs (for coalition arithmetic)
GOV = ["likud", "otzma", "shas", "utj", "rzp"]             # 37th government
OPP = ["yashar", "together", "dems", "yb", "reservists", "blue_white"]
ARAB = ["joint_list", "raam"]
SWING = ["amcha"]                                           # stance uncertain
HAREDI = ["shas", "utj"]

# Error-correlation families: which parties' polling errors move together.
#   N = nationalist right, H = haredi, A = Arab, O = Zionist opposition
FAMILY = {p: "N" for p in ["likud", "otzma", "rzp", "amcha"]}
FAMILY.update({p: "H" for p in HAREDI})
FAMILY.update({p: "A" for p in ARAB})
FAMILY.update({p: "O" for p in OPP})

DEBUT = {"yashar", "together", "amcha", "reservists"}  # new lists poll less reliably

# Surplus-vote agreements. Wikipedia lists the first three as signed; Likud-RZP
# was reported signed on 6 Oct; Shas-UTJ have paired in every recent election.
# Deadline is 16 Oct.
SURPLUS_PAIRS = [("together", "yb"), ("yashar", "dems"), ("joint_list", "raam"),
                 ("likud", "rzp")]
ASSUMED_PAIRS = [("shas", "utj")]

# Unlisted micro-parties: always wasted. 38 lists filed; 2022 non-listed share ~1.5%.
OTHERS_PCT = 1.5

# Pollster names in the MEF archive -> canonical house; house -> methodological
# family (houses sharing methods share one vote in the consensus average).
POLLSTER_CANON = {
    "LRI+P4A": "Lazar", "Lazar": "Lazar",
    "Midgam R&C": "Midgam (Ch12)",
    "Midgam Project": "Midgam Project (Ch13)", "MP+TM+SN+A": "Midgam Project (Ch13)",
    "Maagar Mochot": "Maagar Mochot", "MM+SN": "Maagar Mochot",
    "Kantar": "Kantar",
    "Direct Polls": "Direct Polls",
    "Filber": "Channel 14 (Filber)", "SF+ND": "Channel 14 (Filber)",
    "Filber, NEXT DATA": "Channel 14 (Filber)",
    "Yossi Tatika": "Yossi Tatika", "TrendZone": "TrendZone",
}
POLLSTER_FAMILY = {"Direct Polls": "DP/Ch14", "Channel 14 (Filber)": "DP/Ch14"}
