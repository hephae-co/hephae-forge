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


# ── Edge-case / adversarial businesses ─────────────────────────────────


@dataclass
class EdgeCaseBusiness:
    """A business with known challenges for the discovery pipeline."""

    id: str
    name: str
    address: str
    official_url: str  # may be empty, aggregator, or broken
    edge_type: str  # no_website | aggregator | broken_site | non_english | conflicting_info
    description: str  # what makes this case hard
    expect_discovery_abort: bool = False
    expect_social_links: bool = True  # should still find social even without site


EDGE_CASES: list[EdgeCaseBusiness] = [
    EdgeCaseBusiness(
        id="no-website-instagram-only",
        name="Cupily Coffeehouse",
        address="Nutley, NJ 07110",
        official_url="",
        edge_type="no_website",
        description="Instagram-only business, no website at all. Pipeline must skip Phase 1 (crawl) and still find social links via search.",
        expect_social_links=True,
    ),
    EdgeCaseBusiness(
        id="aggregator-site",
        name="Generic Test Restaurant",
        address="123 Main St, Anytown, NJ 07001",
        official_url="https://www.doordash.com/store/generic-test-restaurant",
        edge_type="aggregator",
        description="URL points to DoorDash (aggregator). EntityMatcher should detect AGGREGATOR and abort discovery.",
        expect_discovery_abort=True,
        expect_social_links=False,
    ),
    EdgeCaseBusiness(
        id="third-party-menu-site",
        name="Caffè Rosalba",
        address="Bloomfield, NJ 07003",
        official_url="",
        edge_type="no_website",
        description="Has a third-party menu site (res-menu.net) but not a real website. Pipeline should find it via search and still discover social links.",
        expect_social_links=True,
    ),
]

EDGE_CASE_MAP: dict[str, EdgeCaseBusiness] = {b.id: b for b in EDGE_CASES}


# ── Happy-path ground truth ──────────────────────────────────────────

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

# ── Grounded Pricing Benchmarks (Open Prices / Dotlas) ──────────────────

@dataclass
class PricingBenchmark:
    item_name: str
    expected_avg_price: float
    expected_low_price: float
    expected_high_price: float
    category: str

# Ground truth for specific item categories in NE corridor (NYC/NJ)
PRICING_GROUND_TRUTH: dict[str, list[PricingBenchmark]] = {
    "Pizza Shops": [
        PricingBenchmark("Plain Slice", 3.50, 2.50, 4.50, "Food"),
        PricingBenchmark("Large Plain Pie", 22.00, 18.00, 26.00, "Food"),
        PricingBenchmark("Soda (Can)", 2.00, 1.50, 2.50, "Beverage"),
    ],
    "Coffee Shops": [
        PricingBenchmark("Drip Coffee (Small)", 3.25, 2.75, 4.50, "Beverage"),
        PricingBenchmark("Latte (Small)", 5.25, 4.50, 6.50, "Beverage"),
        PricingBenchmark("Croissant", 4.50, 3.50, 5.50, "Food"),
    ],
}

# ── Yelp Grounded Businesses (Verified Entity Data) ───────────────────

YELP_GROUNDED_BUSINESSES: list[GroundTruth] = [
    GroundTruth(
        id="joes-pizza-nyc",
        name="Joe's Pizza",
        query="Joe's Pizza Greenwich Village NYC",
        city="New York",
        state="NY",
        biz_type="Pizza restaurant",
        expected_name_fragment="Joe",
        expected_url_fragment="joespizzanyc",
        expected_lat=40.730,
        expected_lng=-74.002,
        expected_social_platforms=["instagram", "facebook"],
        expect_menu=True,
    ),
    GroundTruth(
        id="katz-delicatessen",
        name="Katz's Delicatessen",
        query="Katz's Delicatessen Lower East Side NYC",
        city="New York",
        state="NY",
        biz_type="Kosher-style delicatessen",
        expected_name_fragment="Katz",
        expected_url_fragment="katzsdelicatessen",
        expected_lat=40.722,
        expected_lng=-73.987,
        expected_social_platforms=["instagram", "facebook", "twitter"],
        expect_menu=True,
    ),
]

# Quick lookup by ID
BUSINESS_MAP: dict[str, GroundTruth] = {b.id: b for b in BUSINESSES}
ALL_GROUNDED_BUSINESSES = BUSINESSES + YELP_GROUNDED_BUSINESSES
