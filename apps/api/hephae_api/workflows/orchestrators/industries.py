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
        "bar", "gastropub", "brewery", "wine bar", "food hall", "ghost kitchen",
        "ramen", "sushi", "thai", "chinese restaurant", "indian restaurant",
        "mediterranean", "steakhouse", "pop-up restaurant",
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
        "dairy": "dairy_mom_pct",
        "poultry": "poultry_mom_pct",
        "pork": "pork_mom_pct",
        "beef": "beef_&_veal_mom_pct",
        "fish": "fish_&_seafood_mom_pct",
        "eggs": "eggs_mom_pct",
        "fresh fruits": "fresh_fruits_mom_pct",
        "fresh vegetables": "fresh_vegetables_mom_pct",
        "ice cream": "ice_cream_mom_pct",
    },
    playbooks=[
        {
            "name": "dairy_margin_swap",
            "trigger": "dairy_mom_pct > 1.0 and poultry_mom_pct < 0",
            "play": (
                "Dairy up {dairy_mom_pct}% MoM while poultry down {poultry_mom_pct}%. "
                "Shift cream-heavy dishes to grilled proteins this week. "
                "Example: swap alfredo for chimichurri chicken — saves $1.20/plate on DoorDash."
            ),
        },
        {
            "name": "seafood_opportunity",
            "trigger": "fish_&_seafood_mom_pct < -2.0",
            "play": (
                "Fish & seafood prices dropped {fish_&_seafood_mom_pct}% this month. "
                "Add a seafood special this weekend — grilled branzino or shrimp scampi at full margin. "
                "Post it on Instagram by Thursday for maximum weekend walk-ins."
            ),
        },
        {
            "name": "fda_recall_alert",
            "trigger": "fda_recent_recall_count > 5",
            "play": (
                "{fda_recent_recall_count} FDA recalls active in your region. "
                "Cross-reference your walk-in inventory against FDA recall database this morning. "
                "Post a 'We Source Local' story on social to build trust."
            ),
        },
        {
            "name": "weather_rain_prep",
            "trigger": "weather_traffic_modifier < -0.1",
            "play": (
                "Rain forecast reduces foot traffic by ~20%. Push delivery specials on DoorDash/UberEats "
                "and pre-prep batch items (soups, stews) to minimize perishable waste. "
                "Text your regulars a rainy-day discount code."
            ),
        },
        {
            "name": "produce_spike_alert",
            "trigger": "fresh_vegetables_mom_pct > 2.0",
            "play": (
                "Fresh vegetables up {fresh_vegetables_mom_pct}% this month. "
                "Swap salad-heavy specials for grain bowls or roasted root vegetables. "
                "Negotiate with your produce distributor for a 2-week price lock."
            ),
        },
    ],
    economist_context=(
        "Focus on food cost inflation across proteins (SEFC01 Beef, SEFC02 Pork, SEFD Poultry, "
        "SEFE Fish), dairy (SAF113), and produce (SAF114). Restaurant margins are 3-9% — "
        "even a 1% CPI shift on a high-volume ingredient changes the P&L. Track MoM% changes "
        "to catch trends before they compound."
    ),
    scout_context=(
        "Watch for new restaurant openings and closures via Google Maps and local news. "
        "Key seasonal events: Valentine's Day, Mother's Day, Thanksgiving, and New Year's Eve "
        "drive peak revenue. Sports events and local festivals spike delivery demand. "
        "Monitor DoorDash/UberEats commission rate changes and NJ minimum wage updates. "
        "Track competitor promotions — happy hours, prix-fixe menus, BYOB policies."
    ),
    synthesis_context=(
        "For restaurants, key levers are menu pricing, portion engineering, "
        "delivery mix, and labor scheduling. Examples: 'Replace cream pasta "
        "with grilled chicken — saves $1.20/plate' or 'Add a $12.99 family "
        "pickup on DoorDash to capture rainy-day demand.' Always include a "
        "specific dollar amount or percentage when recommending a change."
    ),
    critique_persona=(
        "restaurant owner who runs a 40-seat neighborhood place — you negotiate with "
        "food distributors weekly, you've watched food costs jump 30% in 3 years, and "
        "you're tired of consultants who've never done a Friday dinner rush. "
        "If an insight doesn't help you make a decision THIS WEEK, it's useless."
    ),
    social_search_terms=[
        "restaurant owner costs", "food cost inflation restaurant",
        "restaurant supply chain 2026", "restaurant margins operator",
        "menu price increase strategy", "restaurant labor minimum wage NJ",
    ],
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
        "dessert shop", "dessert", "churro", "churros", "pretzel", "pretzel shop",
        "cake studio", "baked goods", "cookie shop", "cookies", "confectionery",
        "chocolate shop", "crepe", "crepes", "waffle shop", "waffles",
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
        "flour": "flour_&_flour_mixes_mom_pct",
        "eggs": "eggs_mom_pct",
        "dairy": "dairy_mom_pct",
        "butter": "butter_mom_pct",
        "sugar": "sugar_&_substitutes_mom_pct",
        "milk": "milk_mom_pct",
        "bakery products": "bakery_products_mom_pct",
        "bread": "bread_mom_pct",
        "cakes": "cakes,_cupcakes,_cookies_mom_pct",
    },
    playbooks=[
        {
            "name": "flour_cost_alert",
            "trigger": "flour_&_flour_mixes_mom_pct > 1.0",
            "play": (
                "Flour up {flour_&_flour_mixes_mom_pct}% this month. Promote non-flour items "
                "(meringues, macarons, flourless chocolate cake). "
                "Raise bread loaf prices by $0.50 this week."
            ),
        },
        {
            "name": "egg_spike_response",
            "trigger": "eggs_mom_pct > 2.0",
            "play": (
                "Eggs up {eggs_mom_pct}% this month. Switch custard fills to pastry cream "
                "(fewer eggs per batch). Push vegan muffins and oil-based cakes. "
                "Batch-prep egg-heavy items in larger runs to cut waste."
            ),
        },
        {
            "name": "butter_margin_squeeze",
            "trigger": "butter_mom_pct > 1.5",
            "play": (
                "Butter up {butter_mom_pct}% this month. Use oil-based doughs for daily "
                "bread and reserve real butter for premium croissants and "
                "signature pastries only. Raise croissant price by $0.75."
            ),
        },
        {
            "name": "wedding_season_lock",
            "trigger": "month in [2, 3, 4] and sugar_&_substitutes_mom_pct > 0.5",
            "play": (
                "Sugar up {sugar_&_substitutes_mom_pct}% heading into wedding season. "
                "Lock in custom cake pricing NOW — stop honoring quotes "
                "older than 30 days. Add a delivery fuel surcharge."
            ),
        },
        {
            "name": "holiday_pre_order_push",
            "trigger": "month in [10, 11] and flour_&_flour_mixes_mom_pct > 0",
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
        "bakery owner costs", "flour prices wholesale baker",
        "bakery supply chain 2026", "bakery labor wages",
        "baked goods CPI", "artisan bakery overhead",
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
        "hair salon", "salon", "salons", "beauty salon", "spa",
        "cosmetology", "hair stylist", "hairdresser", "men's hair",
        "fade shop", "grooming studio", "mens salon", "shave shop",
        "beard studio", "locs stylist", "braids", "wave shop",
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
        "barber": "barber_&_beauty_services_mom_pct",
        "beauty": "barber_&_beauty_services_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "household energy": "household_energy_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "service_price_cover",
            "trigger": "barber_&_beauty_services_mom_pct > 0.5",
            "play": (
                "Haircut CPI up {barber_&_beauty_services_mom_pct}% this month. "
                "Competitors are raising prices — raise your base cut by $3-5. "
                "Customers expect it when the whole market moves."
            ),
        },
        {
            "name": "rent_squeeze_response",
            "trigger": "rent_of_primary_residence_mom_pct > 0.5",
            "play": (
                "Rent CPI up {rent_of_primary_residence_mom_pct}% this month. "
                "Add a $15 beard trim add-on to every haircut booking — "
                "that's $60+/day in new revenue on a 4-chair shop."
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
        "barber owner pricing", "barbershop business costs",
        "barber shop rent increase", "men's grooming service pricing",
        "barbershop booth rental rates", "barber licensing NJ",
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


# Alias for convenience
all_industries = list_industries
