"""
Ground truth for integration test businesses.

5 real NE-corridor businesses with known facts for assertion.
Each TestBusiness contains only publicly verifiable information
used to validate discovery results are NOT hallucinated.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GroundTruth:
    id: str
    name: str
    query: str  # what we pass to LocatorAgent
    city: str
    state: str
    biz_type: str

    # Known facts for validation
    expected_name_fragment: str  # substring expected in resolved name
    expected_url_fragment: str  # substring expected in officialUrl
    expected_lat: float  # approximate center
    expected_lng: float
    coord_tolerance: float = 0.15  # degrees (~10mi)

    # Social media presence (which platforms they're known to be on)
    expected_social_platforms: list[str] = field(default_factory=list)

    # Whether we expect a phone number, menu, etc.
    expect_phone: bool = True
    expect_menu: bool = False
    is_restaurant: bool = True
    expect_yelp: bool = True  # most businesses have Yelp pages


BUSINESSES: list[GroundTruth] = [
    GroundTruth(
        id="bosphorus",
        name="The Bosphorus",
        query="The Bosphorus Turkish restaurant Nutley NJ",
        city="Nutley",
        state="NJ",
        biz_type="Turkish restaurant",
        expected_name_fragment="Bosphorus",
        expected_url_fragment="bosphorus",
        expected_lat=40.822,
        expected_lng=-74.159,
        expected_social_platforms=["instagram", "facebook"],
        expect_phone=True,
        expect_menu=True,
        is_restaurant=True,
    ),
    GroundTruth(
        id="nom-wah",
        name="Nom Wah Tea Parlor",
        query="Nom Wah Tea Parlor dim sum New York NY",
        city="New York",
        state="NY",
        biz_type="Dim sum restaurant",
        expected_name_fragment="Nom Wah",
        expected_url_fragment="nomwah",
        expected_lat=40.714,
        expected_lng=-73.998,
        expected_social_platforms=["instagram"],
        expect_phone=True,
        expect_menu=True,
        is_restaurant=True,
    ),
    GroundTruth(
        id="bens-chili-bowl",
        name="Ben's Chili Bowl",
        query="Ben's Chili Bowl Washington DC",
        city="Washington",
        state="DC",
        biz_type="Historic restaurant",
        expected_name_fragment="Ben",
        expected_url_fragment="benschilibowl",
        expected_lat=38.917,
        expected_lng=-77.036,
        expected_social_platforms=["instagram", "facebook"],
        expect_phone=True,
        expect_menu=True,
        is_restaurant=True,
    ),
    GroundTruth(
        id="mikes-pastry",
        name="Mike's Pastry",
        query="Mike's Pastry Boston MA",
        city="Boston",
        state="MA",
        biz_type="Italian bakery",
        expected_name_fragment="Mike",
        expected_url_fragment="mikespastry",
        expected_lat=42.363,
        expected_lng=-71.056,
        expected_social_platforms=["instagram"],
        expect_phone=True,
        expect_menu=False,
        is_restaurant=False,
    ),
    GroundTruth(
        id="strand-bookstore",
        name="Strand Bookstore",
        query="Strand Bookstore New York NY",
        city="New York",
        state="NY",
        biz_type="Independent bookstore",
        expected_name_fragment="Strand",
        expected_url_fragment="strand",
        expected_lat=40.733,
        expected_lng=-73.991,
        expected_social_platforms=["instagram"],
        expect_phone=True,
        expect_menu=False,
        is_restaurant=False,
    ),
]

# Quick lookup by ID
BUSINESS_MAP: dict[str, GroundTruth] = {b.id: b for b in BUSINESSES}
