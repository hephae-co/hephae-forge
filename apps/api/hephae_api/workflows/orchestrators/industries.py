"""Industry configurations for the weekly pulse pipeline.

Each IndustryConfig is a frozen dataclass — pure data, no methods, no framework magic.
Adding a new vertical = adding a new instance below and appending to _ALL.

The config drives:
  - Which BLS CPI series to fetch (national signals)
  - Which USDA commodities to query (food verticals only)
  - Which CPI labels to extract as named impact variables
  - Which playbooks to match against computed impact
  - What context to inject into LLM agent prompts
  - What persona the critique agent adopts
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IndustryConfig:
    """Static configuration for an industry vertical in the pulse pipeline."""

    id: str
    name: str
    aliases: frozenset[str]

    # BLS CPI series — {label: series_id}
    bls_series: dict[str, str] = field(default_factory=dict)

    # USDA commodity keys for food verticals (empty for non-food)
    usda_commodities: list[str] = field(default_factory=list)

    # Extra signal sources beyond the common set
    extra_signals: list[str] = field(default_factory=list)

    # Map CPI label substrings → pre-computed variable names
    track_labels: dict[str, str] = field(default_factory=dict)

    # Industry-specific playbooks (merged with common playbooks at runtime)
    playbooks: list[dict] = field(default_factory=list)

    # Prompt context injected into LLM agents
    economist_context: str = ""
    scout_context: str = ""
    synthesis_context: str = ""
    critique_persona: str = "local business owner with 15 years experience"
    social_search_terms: list[str] = field(default_factory=list)


# ── Restaurant ──────────────────────────────────────────────────

RESTAURANT = IndustryConfig(
    id="restaurant",
    name="Restaurants & Cafes",
    aliases=frozenset({
        "restaurants", "restaurant", "pizza", "pizzeria", "tacos", "taqueria",
        "seafood", "fish market", "cafe", "cafes", "deli", "delis", "diner",
        "bistro", "food truck", "ice cream", "gelato", "juice bar", "smoothie",
        "coffee shops", "coffee", "butcher", "grocery", "supermarket",
    }),
    bls_series={
        # Base food CPI
        "Food (all items)": "CUUR0000SAF1",
        "Food at home": "CUUR0000SAF11",
        "Food away from home": "CUUR0000SAFH",
        "Cereals & bakery": "CUUR0000SAF111",
        "Meats, poultry, fish & eggs": "CUUR0000SAF112",
        "Dairy": "CUUR0000SAF113",
        "Fruits & vegetables": "CUUR0000SAF114",
        "Nonalcoholic beverages": "CUUR0000SAF115",
        # Detailed
        "Beef & veal": "CUUR0000SEFC01",
        "Pork": "CUUR0000SEFC02",
        "Poultry": "CUUR0000SEFD",
        "Fish & seafood": "CUUR0000SEFE",
        "Eggs": "CUUR0000SEFG",
        "Milk": "CUUR0000SEFJ",
        "Cheese": "CUUR0000SEFK",
        "Ice cream": "CUUR0000SEFL",
        "Fresh fruits": "CUUR0000SEFN",
        "Fresh vegetables": "CUUR0000SEFP",
        "Processed fruits & vegetables": "CUUR0000SEFR",
    },
    usda_commodities=["CATTLE", "HOGS", "CHICKENS", "EGGS", "MILK", "WHEAT"],
    extra_signals=["fdaRecalls", "usdaPrices"],
    track_labels={
        "dairy": "dairy_yoy_pct",
        "poultry": "poultry_yoy_pct",
        "pork": "pork_yoy_pct",
        "beef": "beef_yoy_pct",
        "fish": "fish_yoy_pct",
        "eggs": "eggs_yoy_pct",
        "fresh fruits": "fresh_fruits_yoy_pct",
        "fresh vegetables": "fresh_vegetables_yoy_pct",
        "ice cream": "ice_cream_yoy_pct",
    },
    playbooks=[
        {
            "name": "dairy_margin_swap",
            "trigger": "dairy_yoy_pct > 5 and poultry_yoy_pct < 0",
            "play": (
                "Dairy up {dairy_yoy_pct}% while poultry down {poultry_yoy_pct}%. "
                "Shift cream-heavy dishes to grilled proteins this week."
            ),
        },
        {
            "name": "fda_recall_alert",
            "trigger": "fda_recent_recall_count > 5",
            "play": (
                "{fda_recent_recall_count} FDA recalls active in your state. "
                "Audit supplier chain against the recall database today."
            ),
        },
        {
            "name": "weather_rain_prep",
            "trigger": "weather_traffic_modifier < -0.1",
            "play": (
                "Rain forecast reduces foot traffic. Push delivery specials "
                "and pre-prep batch items to minimize perishable waste."
            ),
        },
    ],
    economist_context=(
        "Focus on food cost inflation across proteins, dairy, and produce. "
        "Restaurant margins are 3-9% — even small CPI shifts matter."
    ),
    synthesis_context=(
        "For restaurants, key levers are menu pricing, portion engineering, "
        "delivery mix, and labor scheduling. Examples: 'Replace cream pasta "
        "with grilled chicken' or 'Add a $12.99 family pickup on DoorDash.'"
    ),
    critique_persona="restaurant owner with 15 years experience",
    social_search_terms=["restaurant", "dining", "food", "delivery"],
)


# ── Bakery ──────────────────────────────────────────────────────
# Validated 2026-03-21: 12/12 BLS series confirmed, 8/8 news feeds validated
# Key signal: butter +3.56% MoM (Jan 2026) — most volatile bakery input
# Cost structure: ingredients 20-35%, labor 25-35%, net margin 4-15%

BAKERY = IndustryConfig(
    id="bakery",
    name="Bakeries & Patisseries",
    aliases=frozenset({
        "bakeries", "bakery", "patisserie", "bread shop", "bread bakery",
        "cake shop", "cake bakery", "pastry shop", "pastry", "donut shop",
        "donuts", "bagel shop", "bagels", "cupcake shop", "cupcakes",
        "artisan bakery", "wedding cake", "custom cakes", "bake shop",
        "home bakery", "cottage bakery", "bakery cafe",
    }),
    bls_series={
        # Input costs (what the bakery BUYS)
        "Flour & flour mixes": "CUUR0000SEFA01",
        "Eggs": "CUUR0000SEFH",
        "Dairy & related": "CUUR0000SAF114",
        "Butter": "CUUR0000SS5702",
        "Sugar & substitutes": "CUUR0000SEFR01",
        "Milk": "CUUR0000SEFJ",
        # Consumer prices (what the bakery CHARGES)
        "Bakery products": "CUUR0000SEFB",
        "Bread": "CUUR0000SEFB01",
        "Cakes, cupcakes, cookies": "CUUR0000SEFB02",
        # Context
        "Cereals & bakery": "CUUR0000SAF111",
        "Food (all items)": "CUUR0000SAF1",
    },
    usda_commodities=["WHEAT", "EGGS", "MILK", "SUGAR"],
    extra_signals=["fdaRecalls", "usdaPrices"],
    track_labels={
        "flour": "flour_yoy_pct",
        "eggs": "eggs_yoy_pct",
        "dairy": "dairy_yoy_pct",
        "butter": "butter_yoy_pct",
        "sugar": "sugar_yoy_pct",
        "milk": "milk_yoy_pct",
        "bakery products": "bakery_consumer_yoy_pct",
        "bread": "bread_yoy_pct",
        "cakes": "cakes_yoy_pct",
    },
    playbooks=[
        {
            "name": "flour_cost_alert",
            "trigger": "flour_yoy_pct > 3",
            "play": (
                "Flour up {flour_yoy_pct}%. Promote non-flour items "
                "(meringues, macarons, flourless chocolate cake). "
                "Raise bread loaf prices by $0.50 this week."
            ),
        },
        {
            "name": "egg_spike_response",
            "trigger": "eggs_yoy_pct > 8",
            "play": (
                "Eggs up {eggs_yoy_pct}%. Switch custard fills to pastry cream "
                "(fewer eggs per batch). Push vegan muffins and oil-based cakes. "
                "Batch-prep egg-heavy items in larger runs to cut waste."
            ),
        },
        {
            "name": "butter_margin_squeeze",
            "trigger": "butter_yoy_pct > 4",
            "play": (
                "Butter up {butter_yoy_pct}%. Use oil-based doughs for daily "
                "bread and reserve real butter for premium croissants and "
                "signature pastries only. Raise croissant price by $0.75."
            ),
        },
        {
            "name": "wedding_season_lock",
            "trigger": "month in [2, 3, 4] and sugar_yoy_pct > 2",
            "play": (
                "Sugar up {sugar_yoy_pct}% heading into wedding season. "
                "Lock in custom cake pricing NOW — stop honoring quotes "
                "older than 30 days. Add a delivery fuel surcharge."
            ),
        },
        {
            "name": "holiday_pre_order_push",
            "trigger": "month in [10, 11] and flour_yoy_pct > 0",
            "play": (
                "Ingredients rising into holiday peak. Open Thanksgiving and "
                "Christmas pre-orders THIS WEEK with a 10% deposit. Cap custom "
                "orders at what your ovens can handle."
            ),
        },
        {
            "name": "fda_allergen_alert",
            "trigger": "fda_recent_recall_count > 10",
            "play": (
                "{fda_recent_recall_count} FDA recalls active in your state. "
                "Audit all ingredient labels for undeclared allergens (wheat, "
                "sesame, tree nuts, eggs, milk). Print updated allergen cards "
                "for the display case today."
            ),
        },
    ],
    economist_context=(
        "Focus on flour/wheat (SEFA01), eggs (SEFH), butter (SS5702), dairy "
        "(SAF114), and sugar (SEFR01) — these represent 20-35% of bakery revenue. "
        "Net margins are 4-15%, so even a 2-3% ingredient swing matters. Track the "
        "spread between input costs (flour CPI) and consumer pricing (bakery products "
        "CPI SEFB) — a widening gap signals margin compression."
    ),
    scout_context=(
        "Watch for wedding venues, bridal expos, and farmers markets — these drive "
        "custom cake orders and foot traffic. Note new bakery or cafe openings nearby. "
        "Holiday calendars matter most: Easter, Mother's Day, graduation season, "
        "Thanksgiving, and Christmas are make-or-break revenue periods."
    ),
    synthesis_context=(
        "For bakeries, key levers are ingredient substitution (butter vs oil, "
        "premium vs commodity flour), batch size optimization, and pre-order capture. "
        "Morning traffic is 60-70% of daily revenue — display case freshness before "
        "9am is critical. Examples: 'Switch brioche to focaccia when eggs spike' or "
        "'Open Easter pre-orders by Wednesday to lock pricing.' Wedding and custom "
        "cakes are highest margin (40-60%) but most labor-intensive."
    ),
    critique_persona=(
        "bakery owner who has run a neighborhood bakery for 10 years — you bake at "
        "4am, you know flour and butter prices by heart, and you're tired of "
        "consultants who don't understand that a 3% egg price swing can wipe out "
        "your margin on custard tarts"
    ),
    social_search_terms=[
        "bakery", "bread", "pastry", "cake", "cupcake",
        "artisan bread", "wedding cake", "sourdough",
    ],
)


# ── Barber Shops & Men's Grooming ─────────────────────────────
# Validated 2026-03-22: 6/16 BLS series passed (10 returned NO DATA), 7/7 news feeds
# Key limitation: only 1 direct CPI series (SS45011 barber services)
# No USDA/FDA — beauty vertical, not food
# Cost structure: labor 40-60%, rent 15-25%, supplies 5-10%, net margin 10-20%
# $5.8B US industry, margins squeezed 12-15% in past 2 years

BARBER = IndustryConfig(
    id="barber",
    name="Barber Shops & Men's Grooming",
    aliases=frozenset({
        "barbers", "barber", "barbershop", "barber shop", "men's grooming",
        "hair salon", "salon", "salons", "beauty salon", "spa", "nail salon",
        "cosmetology", "hair stylist", "hairdresser", "men's hair",
    }),
    bls_series={
        # What customers PAY (pricing power)
        "Barber & beauty services": "CUUR0000SS45011",
        # Cost proxies
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
        # General context
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "barber": "barber_services_yoy_pct",
        "beauty": "barber_services_yoy_pct",
        "rent": "rent_yoy_pct",
        "household energy": "energy_yoy_pct",
        "services less energy": "services_yoy_pct",
    },
    playbooks=[
        {
            "name": "service_price_cover",
            "trigger": "barber_services_yoy_pct > 3",
            "play": (
                "Haircut CPI up {barber_services_yoy_pct}%. Competitors are "
                "raising prices — raise your base cut by $3-5 this month. "
                "Customers expect it when the whole market moves."
            ),
        },
        {
            "name": "rent_squeeze_response",
            "trigger": "rent_yoy_pct > 5",
            "play": (
                "Rent CPI up {rent_yoy_pct}%. Add a $15 beard trim add-on "
                "to every haircut booking — that's $60+/day in new revenue "
                "on a 4-chair shop. Post the combo price on your mirror."
            ),
        },
        {
            "name": "walk_in_weather_boost",
            "trigger": "weather_traffic_modifier > 0",
            "play": (
                "Clear weather this weekend. Put 'Walk-Ins Welcome' on your "
                "sandwich board and update your Google profile. Staff an "
                "extra barber Saturday morning."
            ),
        },
        {
            "name": "event_upsell",
            "trigger": "event_traffic_modifier > 0",
            "play": (
                "Local events this week. Promote 'Event Ready' packages on "
                "Instagram: cut + beard trim + style for $45. Tag the event "
                "and the venue."
            ),
        },
        {
            "name": "slow_season_fill",
            "trigger": "month in [1, 2]",
            "play": (
                "January/February slowdown. Text your client list today: "
                "'$5 off any service booked this week.' Fill empty chairs "
                "before rent is due Feb 1st."
            ),
        },
        {
            "name": "new_competitor_alert",
            "trigger": "establishments_yoy_change_pct > 5",
            "play": (
                "New shops opening in your area ({establishments_yoy_change_pct}% "
                "growth). Launch a loyalty card this week — 10th cut free. "
                "Post a 30-second video of your best fade on Instagram Reels."
            ),
        },
    ],
    economist_context=(
        "Focus on barber/beauty services CPI (SS45011) — this directly tracks "
        "what consumers pay for haircuts. Rent (SEHA) and energy (SAH21) are the "
        "main trackable costs. Labor is 40-60% of expenses but only tracked "
        "quarterly via QCEW. A $30 haircut nets only $12-15 after all costs."
    ),
    scout_context=(
        "Watch for proms, weddings, galas, and formal events — these drive "
        "appointment spikes and add-on services (beard trims, styling). Note "
        "new barbershop openings and cosmetology school graduations (new "
        "competitor supply). Back-to-school (Aug-Sep) is a major traffic event."
    ),
    synthesis_context=(
        "For barber shops, labor is the primary cost (not ingredients). Key "
        "levers: appointment fill rate, add-on services (beard trim = $15 "
        "incremental per cut), retail product sales (25-30% revenue potential), "
        "and walk-in capture. A barber's version of 'swap cream pasta for "
        "chicken' is 'add a $15 beard trim add-on to every booking.'"
    ),
    critique_persona=(
        "barber shop owner who runs a 4-chair shop — you know your walk-in "
        "patterns by heart, you pay your barbers 50% commission, and you're "
        "tired of advice from people who've never swept hair off a floor"
    ),
    social_search_terms=[
        "barbershop", "barber", "haircut", "men's grooming",
        "fade", "beard trim", "hair salon",
    ],
)


# ── Lookup ──────────────────────────────────────────────────────

_ALL: list[IndustryConfig] = [RESTAURANT, BAKERY, BARBER]

_INDEX: dict[str, IndustryConfig] = {}
for _cfg in _ALL:
    for _alias in _cfg.aliases:
        _INDEX[_alias] = _cfg


def resolve(business_type: str) -> IndustryConfig:
    """Resolve a business type string to its IndustryConfig.

    Falls back to RESTAURANT if no match (preserves existing behavior).
    """
    key = business_type.lower().strip()
    if key in _INDEX:
        return _INDEX[key]
    # Fuzzy substring match
    for alias, cfg in _INDEX.items():
        if alias in key or key in alias:
            return cfg
    return RESTAURANT


def list_industries() -> list[IndustryConfig]:
    """Return all registered industry configs."""
    return list(_ALL)
