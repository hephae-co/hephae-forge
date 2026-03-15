"""Chain / franchise detection — static name list for instant disqualification."""

from __future__ import annotations

import re

# Normalized chain names (lowercase, no punctuation)
CHAIN_NAMES: set[str] = {
    # Fast food
    "mcdonalds", "burger king", "wendys", "taco bell", "kfc",
    "chick fil a", "chickfila", "popeyes", "arbys", "sonic",
    "jack in the box", "carls jr", "hardees", "white castle",
    "five guys", "in n out", "shake shack", "whataburger",
    "del taco", "el pollo loco", "raising canes", "wingstop",
    "churchs chicken", "panda express",
    "zaxbys", "culvers", "rallys", "checkers",
    # Pizza chains
    "dominos", "pizza hut", "papa johns", "little caesars",
    "papa murphys", "marcos pizza", "jets pizza",
    # Coffee / bakery chains
    "starbucks", "dunkin", "dunkin donuts", "tim hortons",
    "caribou coffee", "peets coffee", "dutch bros",
    "krispy kreme", "cinnabon", "auntie annes",
    # Casual dining chains
    "applebees", "chilis", "olive garden", "red lobster",
    "outback steakhouse", "texas roadhouse", "cracker barrel",
    "ihop", "dennys", "waffle house", "perkins",
    "bob evans", "golden corral", "ruby tuesday",
    "tgi fridays", "buffalo wild wings", "hooters",
    "red robin", "cheesecake factory", "longhorn steakhouse",
    "cheddars", "bjs restaurant",
    # Sub / sandwich chains
    "subway", "jimmy johns", "jersey mikes", "firehouse subs",
    "potbelly", "quiznos", "jasons deli",
    "schlotzskys", "mcalisters deli", "which wich",
    # Mexican chains
    "chipotle", "qdoba", "moes southwest grill",
    # Asian chains
    "pf changs", "benihana",
    # Frozen treats
    "dairy queen", "baskin robbins", "cold stone",
    "marble slab", "yogurtland", "tcby", "jamba juice", "jamba",
    "smoothie king",
    # Banks
    "chase", "wells fargo", "bank of america", "citibank",
    "td bank", "capital one", "pnc", "us bank",
    "truist", "citizens bank", "fifth third bank",
    "regions bank", "key bank", "m&t bank", "huntington bank",
    # Retail chains
    "walmart", "target", "costco", "dollar tree", "dollar general",
    "family dollar", "big lots", "five below", "marshalls",
    "tj maxx", "ross", "burlington", "kohls", "jcpenney",
    "macys", "nordstrom",
    # Pharmacy / convenience
    "cvs", "walgreens", "rite aid", "7 eleven", "7-eleven",
    "wawa", "sheetz", "circle k", "speedway",
    # Hardware / home
    "home depot", "lowes", "ace hardware", "menards",
    "bed bath beyond", "pier 1",
    # Electronics / tech
    "best buy", "gamestop", "apple store",
    # Gym / fitness chains
    "planet fitness", "anytime fitness", "la fitness",
    "orangetheory", "equinox", "lifetime fitness",
    "24 hour fitness", "golds gym", "crunch fitness",
    "snap fitness", "youfit",
    # Auto chains
    "jiffy lube", "valvoline", "meineke", "midas",
    "pep boys", "autozone", "oreilly", "advance auto parts",
    "firestone", "goodyear",
    # Grocery
    "kroger", "safeway", "albertsons", "publix", "aldi",
    "trader joes", "whole foods", "food lion", "stop and shop",
    "giant", "wegmans", "sprouts",
    # Hotel chains
    "marriott", "hilton", "holiday inn", "best western",
    "hampton inn", "courtyard", "fairfield inn",
    # Gas stations
    "shell", "bp", "exxon", "mobil", "chevron", "sunoco",
    "marathon", "phillips 66", "conoco",
    # Pet
    "petco", "petsmart",
    # Shipping
    "ups store", "fedex office",
}

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]")


def _normalize(name: str) -> str:
    return _NORMALIZE_RE.sub("", name.lower()).strip()


def is_chain(business_name: str) -> bool:
    """Return True if the business name matches a known chain/franchise."""
    norm = _normalize(business_name)
    # Exact match
    if norm in CHAIN_NAMES:
        return True
    # Check if any chain name is a prefix or the full normalized name contains the chain
    for chain in CHAIN_NAMES:
        if norm == chain or norm.startswith(chain + " ") or norm.endswith(" " + chain):
            return True
    return False
