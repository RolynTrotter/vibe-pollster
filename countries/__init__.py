"""Country configurations for the general-purpose forecaster.

Each module defines ALIASES (party key -> names used in poll headers and
results tables), PARTY (key -> name, family) and ELECTIONS (id -> spec).
Families: 'L' and 'R' are the two camps whose relative standing polls can
miss together; anything else ('C', 'X', or group codes) only gets
party-level noise. Specs give the seat rules used in that election.
"""
from importlib import import_module

COUNTRIES = ["germany", "netherlands", "sweden", "denmark", "new_zealand"]


def load(name):
    return import_module(f"countries.{name}")
