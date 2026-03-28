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

    # Topics used to fetch external research references for economist context.
    # Must match keys in reference_harvester.TOPIC_CLUSTERS.
    reference_topics: list[str] = field(default_factory=lambda: ["small_business_margins"])


# ── Restaurant ──────────────────────────────────────────────────

RESTAURANT = IndustryConfig(
    id="restaurant",
    name="Restaurants & Cafes",
    aliases=frozenset({
        "restaurants", "restaurant", "tacos", "taqueria",
        "seafood", "fish market", "deli", "delis", "diner",
        "bistro", "ice cream", "gelato", "juice bar", "smoothie",
        "butcher", "grocery", "supermarket",
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
    reference_topics=[
        "restaurant_industry_trends", "restaurant_food_cost",
        "commodity_inflation", "small_business_margins",
        "menu_pricing_strategy", "restaurant_technology",
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
    reference_topics=[
        "restaurant_food_cost", "commodity_inflation",
        "small_business_margins", "menu_pricing_strategy",
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
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
        "restaurant_technology",
    ],
)


# ── Coffee Shop / Café ──────────────────────────────────────────

COFFEE_SHOP = IndustryConfig(
    id="coffee_shop",
    name="Coffee Shops & Cafés",
    aliases=frozenset({
        "coffee", "coffee shop", "coffee shops", "cafe", "cafes", "café",
        "cafés", "espresso bar", "espresso", "tea shop", "tea house", "boba",
        "boba shop", "bubble tea", "juice cafe", "smoothie cafe", "coffee bar",
        "specialty coffee", "roaster", "coffee roaster", "latte shop",
    }),
    bls_series={
        "Food away from home": "CUUR0000SAFH",
        "Nonalcoholic beverages": "CUUR0000SAF115",
        "Dairy": "CUUR0000SAF113",
        "Milk": "CUUR0000SEFJ",
        "Sugar & substitutes": "CUUR0000SEFR01",
        "Cereals & bakery": "CUUR0000SAF111",
        "Food (all items)": "CUUR0000SAF1",
    },
    usda_commodities=["MILK", "SUGAR"],
    extra_signals=["usdaPrices"],
    track_labels={
        "dairy": "dairy_mom_pct",
        "milk": "milk_mom_pct",
        "sugar": "sugar_&_substitutes_mom_pct",
        "nonalcoholic beverages": "nonalcoholic_beverages_mom_pct",
    },
    playbooks=[
        {
            "name": "milk_cost_pass_through",
            "trigger": "milk_mom_pct > 1.5",
            "play": (
                "Milk up {milk_mom_pct}% this month — your latte cost just rose. "
                "Raise 16oz latte price by $0.25 today. Add a $1 oat milk surcharge "
                "if you haven't already — 60% of customers expect it."
            ),
        },
        {
            "name": "seasonal_drink_push",
            "trigger": "month in [9, 10, 11, 12]",
            "play": (
                "Fall/winter seasonal window. Launch a signature seasonal drink "
                "this week (pumpkin spice, spiced apple, peppermint mocha) — "
                "seasonal specials drive 20-30% revenue lift Sept-Dec."
            ),
        },
        {
            "name": "morning_rush_capture",
            "trigger": "weather_traffic_modifier > 0",
            "play": (
                "Clear weather boosts morning commuter traffic. Offer a 'morning "
                "bundle' — drip coffee + pastry for $7 before 9am. Post it on "
                "your Instagram story by 7am."
            ),
        },
        {
            "name": "loyalty_slow_day",
            "trigger": "month in [1, 2]",
            "play": (
                "January coffee slump is real. Run a double-stamp loyalty week — "
                "fill a card in 5 visits instead of 10. Text your regulars today."
            ),
        },
    ],
    economist_context=(
        "Coffee shop input costs are driven by dairy (SAF113), sugar (SEFR01), and "
        "wholesale coffee bean prices (not tracked by BLS — use ICE coffee futures as "
        "context). Net margins are 6-15%. Milk is 15-25% of a latte's cost — MoM "
        "changes matter immediately. Rent is 10-20% of revenue in high-foot-traffic locations."
    ),
    scout_context=(
        "Watch for office building occupancy changes (commuter traffic), new coffee "
        "chain openings (Starbucks, Dutch Bros expansion), and co-working spaces. "
        "Seasonal peaks: back-to-school (Aug-Sep), holiday (Nov-Dec). "
        "Remote work patterns affect morning rush — Mondays and Fridays are weakest."
    ),
    synthesis_context=(
        "For coffee shops, key levers are drink pricing ($0.25 per drink = $500/month "
        "on 2,000 drinks), add-on pastry sales, and loyalty program fill rates. "
        "Oat/alt milk surcharges ($1) are market-standard and expected. "
        "Example: 'Raise latte price by $0.25 and add $1 oat milk upcharge = $800/month lift.'"
    ),
    critique_persona=(
        "independent coffee shop owner competing against Starbucks three blocks away — "
        "you pull espresso shots at 6am, you've watched your oat milk cost double, "
        "and you know your regulars by their drink orders"
    ),
    social_search_terms=[
        "coffee shop owner costs 2026", "independent cafe vs starbucks",
        "coffee shop milk cost dairy price", "cafe owner profit margin",
        "specialty coffee business overhead", "coffee shop pricing strategy",
    ],
    reference_topics=[
        "restaurant_food_cost", "commodity_inflation",
        "small_business_margins", "menu_pricing_strategy",
        "restaurant_technology",
    ],
)


# ── Pizza & Fast Casual ──────────────────────────────────────────

PIZZA_FAST_CASUAL = IndustryConfig(
    id="pizza",
    name="Pizza & Fast Casual",
    aliases=frozenset({
        "pizza", "pizzeria", "pizza shop", "pizza restaurant", "pizza place",
        "fast casual", "fast food", "quick service", "qsr", "counter service",
        "burgers", "burger joint", "burger bar", "sandwich shop", "sandwiches",
        "sub shop", "subs", "hoagies", "wings", "chicken wings", "fried chicken",
        "poke bowl", "poke", "build-your-own", "bowl restaurant", "grain bowl",
        "wrap shop", "wraps", "calzone", "stromboli",
    }),
    bls_series={
        "Food away from home": "CUUR0000SAFH",
        "Cereals & bakery": "CUUR0000SAF111",
        "Flour & flour mixes": "CUUR0000SEFA01",
        "Cheese": "CUUR0000SEFK",
        "Dairy": "CUUR0000SAF113",
        "Meats, poultry, fish & eggs": "CUUR0000SAF112",
        "Poultry": "CUUR0000SEFD",
        "Beef & veal": "CUUR0000SEFC01",
        "Fresh vegetables": "CUUR0000SEFP",
        "Food (all items)": "CUUR0000SAF1",
    },
    usda_commodities=["WHEAT", "CATTLE", "CHICKENS", "MILK"],
    extra_signals=["fdaRecalls", "usdaPrices"],
    track_labels={
        "flour": "flour_&_flour_mixes_mom_pct",
        "cheese": "cheese_mom_pct",
        "dairy": "dairy_mom_pct",
        "poultry": "poultry_mom_pct",
        "beef": "beef_&_veal_mom_pct",
        "fresh vegetables": "fresh_vegetables_mom_pct",
    },
    playbooks=[
        {
            "name": "cheese_cost_alert",
            "trigger": "cheese_mom_pct > 1.5",
            "play": (
                "Cheese up {cheese_mom_pct}% this month — your biggest topping cost. "
                "Raise large pizza price by $1 today. Add 'extra cheese' as a $1.50 "
                "paid topping to offset cost creep."
            ),
        },
        {
            "name": "dough_cost_squeeze",
            "trigger": "flour_&_flour_mixes_mom_pct > 1.0",
            "play": (
                "Flour up {flour_&_flour_mixes_mom_pct}% this month. Batch larger "
                "dough runs Mon and Thu to reduce per-unit cost. Raise thin-crust "
                "prices by $0.75 — it uses more flour per surface area."
            ),
        },
        {
            "name": "game_day_push",
            "trigger": "event_traffic_modifier > 0",
            "play": (
                "Local event this week. Pre-promote a game-day bundle on DoorDash "
                "by Wednesday: 2 large pizzas + wings for $39.99. "
                "Party packs drive 3-5x average order value."
            ),
        },
        {
            "name": "lunch_special",
            "trigger": "month in [9, 10, 11, 12, 1, 2]",
            "play": (
                "School year season — office and student lunch traffic is highest. "
                "Run a slice + drink lunch special for $6.99 Mon-Fri "
                "on your Google Business profile starting Monday."
            ),
        },
    ],
    economist_context=(
        "Pizza/fast casual cost structure: dough ingredients 15-20%, cheese 8-12%, "
        "toppings 10-15%, labor 25-35%, net margin 5-12%. Cheese (SEFK) is the most "
        "volatile input — pizza is 30-40% cheese by cost. Track flour (SEFA01) and "
        "cheese (SEFK) MoM together — when both spike the margin disappears."
    ),
    scout_context=(
        "Watch for third-party delivery fee changes (DoorDash, UberEats commission "
        "is 15-30%). Note new fast casual chain openings. Sports events, school "
        "nights, and Friday/Saturday evenings are peak demand. "
        "Online ordering mix (40-60% of orders in most markets) affects labor planning."
    ),
    synthesis_context=(
        "For pizza/fast casual, key levers are topping pricing, delivery platform "
        "fees, bundle/combo design, and lunch traffic capture. Example: 'Raise large "
        "pizza $1 when cheese spikes — nets $200/week on 200 pies.' "
        "Bundle deals (family pack, game-day special) increase average check 3x."
    ),
    critique_persona=(
        "pizzeria owner competing with chains on every corner — you make dough at "
        "noon for evening service, your cheese rep calls you every Tuesday with "
        "price updates, and you know DoorDash takes 28% off every order"
    ),
    social_search_terms=[
        "pizzeria owner costs 2026", "pizza cheese price wholesale",
        "fast casual restaurant margins", "pizza delivery app fees DoorDash",
        "quick service restaurant supply chain", "pizza business overhead NJ",
    ],
    reference_topics=[
        "restaurant_industry_trends", "restaurant_food_cost",
        "commodity_inflation", "small_business_margins",
        "menu_pricing_strategy",
    ],
)


# ── Food Truck ───────────────────────────────────────────────────

FOOD_TRUCK = IndustryConfig(
    id="food_truck",
    name="Food Trucks & Mobile Food",
    aliases=frozenset({
        "food truck", "food trucks", "mobile food", "mobile kitchen",
        "food cart", "food stand", "street food", "pop-up food",
        "taco truck", "lunch truck", "catering truck", "roach coach",
        "mobile catering", "festival food", "food trailer",
    }),
    bls_series={
        "Food away from home": "CUUR0000SAFH",
        "Gasoline, all types": "CUUR0000SETB01",
        "Food (all items)": "CUUR0000SAF1",
        "Meats, poultry, fish & eggs": "CUUR0000SAF112",
        "Fruits & vegetables": "CUUR0000SAF114",
        "Dairy": "CUUR0000SAF113",
    },
    usda_commodities=["CATTLE", "CHICKENS", "EGGS"],
    extra_signals=["fdaRecalls", "usdaPrices"],
    track_labels={
        "gasoline": "gasoline,_all_types_mom_pct",
        "food away from home": "food_away_from_home_mom_pct",
        "meats": "meats,_poultry,_fish_&_eggs_mom_pct",
    },
    playbooks=[
        {
            "name": "fuel_cost_route",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Gas up {gasoline,_all_types_mom_pct}% this month. Cut your route "
                "to 2-3 high-density stops instead of 5-6 scattered ones. "
                "Raise menu prices by $0.50 across the board and add a $2 "
                "delivery/catering fuel surcharge."
            ),
        },
        {
            "name": "event_season_lock",
            "trigger": "month in [4, 5, 6, 7, 8, 9]",
            "play": (
                "Peak food truck season (Apr-Sep). Contact your top 3 event "
                "venues this week to lock in summer bookings. "
                "Private events pay flat fees — $800-2,000/event vs "
                "unpredictable street revenue."
            ),
        },
        {
            "name": "weather_cancellation_prep",
            "trigger": "weather_traffic_modifier < -0.15",
            "play": (
                "Bad weather ahead — street foot traffic drops 50%+. "
                "Post a covered/indoor location on Instagram TODAY. "
                "Offer 20% off pre-orders for pickup at a fixed parking spot."
            ),
        },
    ],
    economist_context=(
        "Food truck cost structure: food cost 28-35%, fuel/vehicle 10-15%, "
        "permits/commissary 5-10%, net margin 6-15%. Fuel (SETB01) is a top-3 "
        "cost and MoM volatility directly impacts route profitability. "
        "Commissary kitchen fees ($400-800/month) are fixed regardless of revenue."
    ),
    scout_context=(
        "Watch for local event calendars (festivals, farmers markets, concerts, "
        "sporting events), office park lunch permit availability, and municipal "
        "food truck permit changes. Summer is peak season; December-February "
        "is slowest. Health inspection schedule affects commissary costs."
    ),
    synthesis_context=(
        "For food trucks, key levers are route optimization, event booking mix "
        "(private events vs street), and menu pricing. Example: 'Replace 5-stop "
        "route with 2 high-density office park stops — saves $40/day in fuel.' "
        "Catering events are highest-margin — push for 30% of weekly revenue."
    ),
    critique_persona=(
        "food truck owner who's been running a lunch route for 5 years — you "
        "track gas prices like a hawk, you've been rejected from 3 permit spots, "
        "and you know that one rainy Tuesday can wipe out the whole week's margin"
    ),
    social_search_terms=[
        "food truck owner costs 2026", "food truck gas fuel prices",
        "food truck permit NJ", "mobile food business margins",
        "food truck event catering revenue", "food truck commissary kitchen cost",
    ],
    reference_topics=[
        "restaurant_food_cost", "commodity_inflation",
        "small_business_margins", "menu_pricing_strategy",
    ],
)


# ── Nail Salon ───────────────────────────────────────────────────

NAIL_SALON = IndustryConfig(
    id="nail_salon",
    name="Nail Salons",
    aliases=frozenset({
        "nail salon", "nail salons", "nails", "nail studio", "nail bar",
        "manicure", "pedicure", "gel nails", "acrylic nails", "nail tech",
        "nail art", "dip powder nails", "nail spa", "mani pedi",
        "luxury nails", "nail boutique",
    }),
    bls_series={
        "Barber & beauty services": "CUUR0000SS45011",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Other goods & services": "CUUR0000SAG1",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "barber": "barber_&_beauty_services_mom_pct",
        "beauty": "barber_&_beauty_services_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "household energy": "household_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "service_price_raise",
            "trigger": "barber_&_beauty_services_mom_pct > 0.5",
            "play": (
                "Beauty services CPI up {barber_&_beauty_services_mom_pct}% — "
                "market is moving up. Raise gel manicure by $5 and full set by "
                "$10 this week. Post your new price list on Instagram today."
            ),
        },
        {
            "name": "supply_cost_offset",
            "trigger": "rent_of_primary_residence_mom_pct > 0.5",
            "play": (
                "Overhead rising. Add a $3 'nail art' design fee per nail "
                "for any custom nail art requests — most clients expect it. "
                "Upsell gel top coat to every basic manicure for $5."
            ),
        },
        {
            "name": "holiday_gift_card",
            "trigger": "month in [11, 12]",
            "play": (
                "Holiday season: gift cards are your highest-margin revenue. "
                "Post 'Gift Card Special — buy $50 get $10 free' on "
                "Instagram and Facebook today. Display at the front desk."
            ),
        },
        {
            "name": "bridal_season",
            "trigger": "month in [4, 5, 6]",
            "play": (
                "Bridal season peak. DM the top 5 bridal boutiques in your "
                "area this week offering a bridal party package (5+ people "
                "get 15% off). One bridal party = $300-600 in a single visit."
            ),
        },
    ],
    economist_context=(
        "Nail salon cost structure: supplies 15-20%, labor 40-55%, rent 15-25%, "
        "net margin 10-20%. Supply costs (acetone, gel, acrylic powder, UV lamps) "
        "are not tracked by BLS directly — use Other goods CPI (SAG1) as proxy. "
        "Labor is the primary cost; most techs work on commission (40-50%)."
    ),
    scout_context=(
        "Watch for bridal expos, prom season (Apr-May), and holiday peaks (Nov-Dec). "
        "New nail salon openings are frequent — note competition within 0.5 miles. "
        "NJ cosmetology board licensing requirements affect tech supply. "
        "Shopping mall foot traffic patterns drive walk-in volume."
    ),
    synthesis_context=(
        "For nail salons, key levers are service menu pricing, add-on upsells "
        "(nail art, gel top coat, paraffin), and appointment fill rate. "
        "Example: 'Add $5 gel top coat upsell to every basic manicure = $300/week "
        "on 60 appointments.' Gift cards in November capture holiday revenue early."
    ),
    critique_persona=(
        "nail salon owner who has 6 techs and knows every client by name — "
        "you buy supplies from three different vendors to get the best price, "
        "your rent went up 18% last year, and you're tired of clients who "
        "want intricate nail art at commodity prices"
    ),
    social_search_terms=[
        "nail salon owner costs 2026", "nail salon supply prices",
        "nail salon pricing strategy", "nail tech commission rates",
        "nail salon business overhead NJ", "beauty service CPI inflation",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Hair Salon (Women's) ─────────────────────────────────────────

HAIR_SALON = IndustryConfig(
    id="hair_salon",
    name="Hair Salons",
    aliases=frozenset({
        "hair salon", "hair salons", "women's salon", "women's hair",
        "beauty salon", "beauty shop", "blow dry bar", "blowout bar",
        "hair studio", "hair spa", "color salon", "highlights", "balayage",
        "keratin treatment", "extensions", "braiding salon", "locs salon",
        "natural hair salon", "kids haircuts", "family salon", "unisex salon",
        "cosmetologist", "cosmetology",
    }),
    bls_series={
        "Barber & beauty services": "CUUR0000SS45011",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "barber": "barber_&_beauty_services_mom_pct",
        "beauty": "barber_&_beauty_services_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "color_service_pricing",
            "trigger": "barber_&_beauty_services_mom_pct > 0.5",
            "play": (
                "Beauty services CPI up {barber_&_beauty_services_mom_pct}% — "
                "raise your base color service by $10 this week. "
                "Add a $15 'toning gloss' add-on to every color service."
            ),
        },
        {
            "name": "rent_increase_offset",
            "trigger": "rent_of_primary_residence_mom_pct > 0.5",
            "play": (
                "Rent rising. Introduce a $15 conditioning treatment "
                "add-on to every chemical service this week. "
                "On 8 chemical services/day, that's $120/day in new revenue."
            ),
        },
        {
            "name": "bridal_season_capture",
            "trigger": "month in [3, 4, 5, 6]",
            "play": (
                "Bridal peak season. Post your bridal package pricing on "
                "Instagram and Pinterest this week. Partner with one "
                "local venue for a cross-referral deal — ask them to "
                "include your card in their vendor packet."
            ),
        },
        {
            "name": "back_to_school",
            "trigger": "month in [8, 9]",
            "play": (
                "Back-to-school season drives family hair appointments. "
                "Run a 'Kids' Cut $15' promo this week to bring parents in "
                "who then book their own services. Post on Nextdoor and Facebook."
            ),
        },
    ],
    economist_context=(
        "Hair salon cost structure: color/chemical supplies 10-18%, labor 40-55%, "
        "rent 12-20%, net margin 10-18%. Chemical supply costs (developer, color, "
        "bleach) are not tracked by BLS — use SAG1 as proxy. Labor is the "
        "dominant cost; stylists work on commission (45-55%) or booth rental ($150-400/wk)."
    ),
    scout_context=(
        "Watch for bridal season (Mar-Jun), back-to-school (Aug-Sep), holiday "
        "styling peak (Nov-Dec), prom season (Apr-May). Note new salon openings, "
        "chain expansions (Great Clips, Supercuts), and cosmetology school "
        "graduation dates (new stylist supply). NJ cosmetology licensing renewals matter."
    ),
    synthesis_context=(
        "For hair salons, key levers are chemical service pricing, add-on treatments, "
        "booth rental rates, and retail product sales (20-25% margin potential). "
        "Example: 'Add $15 conditioning treatment to every color service = $600/week "
        "on 40 color appointments.' Retail markup is 50-100% — push at every visit."
    ),
    critique_persona=(
        "hair salon owner with 8 stylists, half on commission, half on booth rent — "
        "you manage color inventory weekly, your rent went up $400 last year, "
        "and you're tired of training new stylists only to have them leave"
    ),
    social_search_terms=[
        "hair salon owner costs 2026", "salon color supply prices",
        "hair salon booth rental rates NJ", "beauty salon business overhead",
        "hair salon pricing increase", "cosmetology business margins",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Spa & Massage ────────────────────────────────────────────────

SPA_MASSAGE = IndustryConfig(
    id="spa",
    name="Spas & Massage Studios",
    aliases=frozenset({
        "spa", "spas", "day spa", "massage", "massage therapy", "massage studio",
        "massage therapist", "wellness spa", "med spa", "medspa", "medical spa",
        "facial spa", "skincare studio", "esthetician", "waxing studio",
        "waxing salon", "body wrap", "wellness center", "reflexology",
        "float tank", "float spa", "cryotherapy",
    }),
    bls_series={
        "Barber & beauty services": "CUUR0000SS45011",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "barber": "barber_&_beauty_services_mom_pct",
        "beauty": "barber_&_beauty_services_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "household energy": "household_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "package_pricing",
            "trigger": "barber_&_beauty_services_mom_pct > 0.5",
            "play": (
                "Personal care services CPI up {barber_&_beauty_services_mom_pct}%. "
                "Raise 60-minute massage by $10 this week. Bundle "
                "3-pack packages at $20 off to lock in revenue upfront."
            ),
        },
        {
            "name": "holiday_gift_cards",
            "trigger": "month in [11, 12]",
            "play": (
                "Holiday spa gift cards are your highest-demand product Nov-Dec. "
                "Post 'Give the Gift of Relaxation' on Instagram today. "
                "Add 10% bonus value on gift cards over $100. "
                "Display at checkout with a QR code."
            ),
        },
        {
            "name": "membership_push",
            "trigger": "month in [1, 2]",
            "play": (
                "January wellness resolutions drive spa membership interest. "
                "Launch a 'New Year Wellness Membership' — 1 massage/month "
                "for $79 (vs $110 single session). Email your entire client "
                "list this week."
            ),
        },
        {
            "name": "energy_cost_offset",
            "trigger": "household_energy_mom_pct > 1.5",
            "play": (
                "Energy costs rising — your heated tables, steamers, and "
                "lighting are expensive. Add a $5 'facility fee' to all "
                "services. Framed correctly as a wellness surcharge, "
                "90% of clients accept it without question."
            ),
        },
    ],
    economist_context=(
        "Spa/massage cost structure: labor 45-60%, rent 15-25%, supplies 5-10%, "
        "energy 3-8%, net margin 10-20%. Therapist labor is the main variable cost. "
        "Energy costs matter more for spas than most service businesses — "
        "heated tables, steamers, UV sanitizers, and HVAC run continuously."
    ),
    scout_context=(
        "Watch for Valentine's Day (Feb), Mother's Day (May), holiday peak (Nov-Dec) "
        "— these are the three biggest spa revenue windows. Note new med spa "
        "openings (Botox clinics are direct competitors for high-end clients). "
        "Corporate wellness contracts are high-value recurring revenue."
    ),
    synthesis_context=(
        "For spas, key levers are membership conversion, gift card pre-sales, "
        "add-on services (hot stone, aromatherapy, face mask), and corporate "
        "wellness packages. Example: 'Convert 10 clients to $79/month membership = "
        "$790 guaranteed monthly revenue.' Memberships reduce churn by 60%."
    ),
    critique_persona=(
        "day spa owner with 4 massage therapists — you bought high-end tables "
        "that cost $3k each, your clients expect warm towels and organic oils, "
        "and you've had to raise prices twice in two years just to cover energy bills"
    ),
    social_search_terms=[
        "spa owner costs 2026", "massage therapy business overhead",
        "spa membership model revenue", "day spa pricing strategy",
        "esthetician business costs NJ", "wellness spa profit margin",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Tattoo Studio ────────────────────────────────────────────────

TATTOO_STUDIO = IndustryConfig(
    id="tattoo",
    name="Tattoo & Piercing Studios",
    aliases=frozenset({
        "tattoo", "tattoo shop", "tattoo studio", "tattoo parlor",
        "ink shop", "tattoo artist", "piercing", "piercing studio",
        "body piercing", "tattoo and piercing", "body art", "microblading",
        "permanent makeup", "cosmetic tattoo",
    }),
    bls_series={
        "Other goods & services": "CUUR0000SAG1",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "rent": "rent_of_primary_residence_mom_pct",
        "other goods": "other_goods_&_services_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "flash_event",
            "trigger": "month in [10]",
            "play": (
                "October is peak tattoo season. Run a Friday the 13th "
                "flash tattoo event — $31 flash designs, cash only. "
                "Post the flash sheet on Instagram by Tuesday with "
                "a 'limited spots' countdown."
            ),
        },
        {
            "name": "summer_push",
            "trigger": "month in [5, 6, 7]",
            "play": (
                "Summer skin season — people want tattoos to show off. "
                "Post your artist's best summer work on Instagram Reels "
                "this week. Offer $20 off any tattoo booked in June for July/Aug completion."
            ),
        },
        {
            "name": "deposit_policy",
            "trigger": "rent_of_primary_residence_mom_pct > 0.5",
            "play": (
                "Overhead rising. Enforce a non-refundable $50-100 deposit "
                "on ALL bookings this week. No-show rate drops 70% with deposits, "
                "protecting your artists' time and your revenue."
            ),
        },
        {
            "name": "supply_cost_menu",
            "trigger": "other_goods_&_services_mom_pct > 0.5",
            "play": (
                "Supply costs rising (ink, needles, gloves). Raise your minimum "
                "by $10 this week to $80-100. "
                "A tattoo under $80 doesn't cover supplies at today's prices."
            ),
        },
    ],
    economist_context=(
        "Tattoo studio cost structure: supplies (ink, needles, gloves) 8-15%, "
        "labor/artist share 40-50%, rent 15-25%, net margin 15-25%. "
        "Supply costs are not tracked by BLS directly — use SAG1 as proxy. "
        "Artists typically work on 40-50% commission or daily booth rental ($100-200/day)."
    ),
    scout_context=(
        "Watch for convention season (tattoo conventions are top marketing events), "
        "Halloween/October (peak demand), summer (exposure-driven demand). "
        "Health department inspection schedules matter — a failed inspection "
        "means immediate closure. Note new studio openings in your 2-mile radius."
    ),
    synthesis_context=(
        "For tattoo studios, key levers are booking deposit enforcement, flash "
        "event revenue, artist booth rental vs commission mix, and social media "
        "visibility. Example: 'Requiring $75 deposit reduces no-shows by 70% = "
        "recapturing 3 lost slots/week at $150 average = $450/week.' "
        "Instagram is the primary discovery channel — post daily."
    ),
    critique_persona=(
        "tattoo studio owner with 3 artists — you handle health department "
        "inspections, supply orders, and Instagram, while your artists focus on ink. "
        "You've eaten the cost of too many no-shows and you know that one "
        "supply shortage can shut down a full day of appointments"
    ),
    social_search_terms=[
        "tattoo shop owner business costs", "tattoo studio overhead 2026",
        "tattoo supply prices inflation", "tattoo artist booth rental rates",
        "tattoo business NJ regulations", "body art studio profit margin",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Auto Repair & Mechanic ───────────────────────────────────────

AUTO_REPAIR = IndustryConfig(
    id="auto_repair",
    name="Auto Repair & Mechanics",
    aliases=frozenset({
        "auto repair", "auto mechanic", "mechanic", "car repair", "car mechanic",
        "auto shop", "garage", "automotive", "oil change", "tire shop",
        "tire service", "brake shop", "transmission shop", "body shop",
        "auto body", "collision repair", "detailing", "car detailing",
        "auto detailing", "lube shop", "muffler shop", "alignment shop",
        "used car dealer", "car dealer",
    }),
    bls_series={
        "Motor vehicle maintenance & repair": "CUUR0000SETA02",
        "Gasoline, all types": "CUUR0000SETB01",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Other goods & services": "CUUR0000SAG1",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "motor vehicle": "motor_vehicle_maintenance_&_repair_mom_pct",
        "gasoline": "gasoline,_all_types_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
    },
    playbooks=[
        {
            "name": "labor_rate_raise",
            "trigger": "motor_vehicle_maintenance_&_repair_mom_pct > 0.5",
            "play": (
                "Auto repair CPI up {motor_vehicle_maintenance_&_repair_mom_pct}% — "
                "the market supports higher rates. Raise your labor rate by "
                "$5-10/hour this week. Post your updated rate on your website and "
                "Google profile — customers check before calling."
            ),
        },
        {
            "name": "parts_cost_offset",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Parts and fluid costs rising with fuel prices. Add a $15 "
                "'shop supply fee' to every invoice this week. "
                "Industry standard — 95% of shops charge it."
            ),
        },
        {
            "name": "winter_prep_push",
            "trigger": "month in [9, 10]",
            "play": (
                "October is your best month for winter prep upsells. "
                "Email your customer list: 'Winter service special — tire "
                "changeover + oil change + battery check for $129.' "
                "Batch-book slots for November before your schedule fills."
            ),
        },
        {
            "name": "spring_ac_push",
            "trigger": "month in [3, 4, 5]",
            "play": (
                "Spring = AC service season. Add an AC system check "
                "to every service order as a $79 upsell from March through May. "
                "Post 'Is your AC ready for summer?' on Facebook and Nextdoor."
            ),
        },
    ],
    economist_context=(
        "Auto repair cost structure: parts 35-45%, labor 30-40%, rent 8-15%, "
        "net margin 10-20%. Parts prices are highly correlated with fuel prices — "
        "when gasoline (SETB01) spikes, so do motor vehicle parts. "
        "Track motor vehicle maintenance CPI (SETA02) to benchmark your labor rate."
    ),
    scout_context=(
        "Watch for new dealership service center openings (direct competition for "
        "late-model cars) and national chain expansion (Midas, Meineke, Valvoline). "
        "NJ vehicle inspection requirements drive seasonal demand (odd/even year cycle). "
        "Winter (Nov-Mar) is peak for brake, battery, and tire services."
    ),
    synthesis_context=(
        "For auto repair, key levers are labor rate (per hour), parts markup "
        "(40-60% standard), shop supply fees, and upsell capture on every RO. "
        "Example: 'Add $15 shop supply fee to every invoice = $750/week on 50 ROs.' "
        "Customers who come in for oil changes are worth $800+/year in total services."
    ),
    critique_persona=(
        "independent auto shop owner competing against dealerships and national chains — "
        "you order parts at 6am, you know your lift utilization by bay, "
        "and you've watched your technicians get poached by dealerships twice this year"
    ),
    social_search_terms=[
        "auto repair shop owner costs 2026", "mechanic shop overhead NJ",
        "automotive parts prices inflation", "auto repair labor rate increase",
        "independent shop vs dealership", "car repair business margins",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
        "commodity_inflation",
    ],
)


# ── Residential Cleaning ─────────────────────────────────────────

RESIDENTIAL_CLEANING = IndustryConfig(
    id="residential_cleaning",
    name="Residential Cleaning Services",
    aliases=frozenset({
        "cleaning", "cleaning service", "house cleaning", "home cleaning",
        "residential cleaning", "maid service", "housekeeping", "housekeeper",
        "cleaning company", "deep cleaning", "move-in cleaning", "move-out cleaning",
        "post-construction cleaning", "apartment cleaning", "condo cleaning",
        "janitorial", "janitorial service", "office cleaning", "commercial cleaning",
    }),
    bls_series={
        "Household operations": "CUUR0000SAH2",
        "Rent of primary residence": "CUUR0000SEHA",
        "Gasoline, all types": "CUUR0000SETB01",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "gasoline": "gasoline,_all_types_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
        "household operations": "household_operations_mom_pct",
    },
    playbooks=[
        {
            "name": "rate_increase_cycle",
            "trigger": "services_less_energy_mom_pct > 0.5",
            "play": (
                "Service sector wages rising {services_less_energy_mom_pct}% — "
                "raise your recurring client rates by $10-15/visit with "
                "2 weeks notice this week. 85% of loyal clients accept "
                "annual increases without canceling."
            ),
        },
        {
            "name": "fuel_surcharge",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Gas up {gasoline,_all_types_mom_pct}% — your crews drive "
                "50-80 miles/day. Add a $5 fuel surcharge to every job this week. "
                "Email all clients today. It's standard in the industry."
            ),
        },
        {
            "name": "spring_deep_clean",
            "trigger": "month in [3, 4]",
            "play": (
                "Spring cleaning season. Email your entire client list "
                "offering a one-time deep clean add-on for $75 "
                "($120 for new clients). Spring deep cleans are fully booked "
                "by April — start selling now."
            ),
        },
        {
            "name": "new_mover_capture",
            "trigger": "establishments_yoy_change_pct > 3",
            "play": (
                "New construction and moves happening in your area. "
                "Post 'Move-in/Move-out Deep Clean — $199' on Nextdoor today. "
                "Partner with one local real estate agent for referral deals."
            ),
        },
    ],
    economist_context=(
        "Residential cleaning cost structure: labor 55-70%, supplies 5-10%, "
        "vehicle/fuel 8-12%, net margin 10-20%. Labor is the overwhelming cost — "
        "minimum wage increases directly impact margins. Fuel (SETB01) is the "
        "second most volatile cost. Supplies (cleaning chemicals) are not tracked by BLS."
    ),
    scout_context=(
        "Watch for NJ minimum wage changes (scheduled increases affect your labor "
        "cost immediately). Note new housing construction and apartment complex "
        "openings (move-in/move-out cleaning demand). Spring and fall are "
        "peak demand seasons. Holiday pre-cleaning (Nov-Dec) is high-value."
    ),
    synthesis_context=(
        "For cleaning services, key levers are recurring client rate, job size "
        "optimization, fuel surcharges, and add-on services. Example: 'Raise "
        "recurring biweekly rate $10 for 30 clients = $300/month in new revenue.' "
        "Recurring clients are worth $1,200-2,400/year — prioritize retention over acquisition."
    ),
    critique_persona=(
        "residential cleaning company owner with 6 cleaners — you schedule "
        "routes at 6am, you've seen your labor costs rise 25% in 2 years, "
        "and you're tired of clients who want 4-hour deep cleans at 2-hour prices"
    ),
    social_search_terms=[
        "cleaning business owner costs 2026", "house cleaning service pricing NJ",
        "residential cleaning business overhead", "cleaning company labor wages",
        "maid service fuel surcharge", "cleaning business profit margin",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Plumbing & HVAC ──────────────────────────────────────────────

PLUMBING_HVAC = IndustryConfig(
    id="plumbing_hvac",
    name="Plumbing & HVAC Services",
    aliases=frozenset({
        "plumber", "plumbing", "plumbing service", "plumber service",
        "hvac", "hvac service", "heating", "cooling", "air conditioning",
        "ac repair", "furnace repair", "boiler", "boiler service",
        "electrician", "electrical", "electrical contractor",
        "home services", "home repair", "handyman", "handyman service",
        "contractor", "general contractor", "roofing", "roofer",
        "insulation", "waterproofing",
    }),
    bls_series={
        "Motor vehicle maintenance & repair": "CUUR0000SETA02",
        "Gasoline, all types": "CUUR0000SETB01",
        "Household energy": "CUUR0000SAH21",
        "Rent of primary residence": "CUUR0000SEHA",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "gasoline": "gasoline,_all_types_mom_pct",
        "household energy": "household_energy_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "fuel_parts_surcharge",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Fuel and parts costs rising {gasoline,_all_types_mom_pct}% — "
                "add a $25 'materials & travel surcharge' to every service call. "
                "Update your quote template today. Customers expect it."
            ),
        },
        {
            "name": "winter_hvac_push",
            "trigger": "month in [8, 9, 10]",
            "play": (
                "HVAC maintenance season before winter. Email all past "
                "clients with a $149 furnace tune-up offer this week. "
                "Customers who book maintenance in Oct-Nov are worth $500+ "
                "when the furnace breaks in January."
            ),
        },
        {
            "name": "summer_ac_push",
            "trigger": "month in [4, 5]",
            "play": (
                "Pre-summer AC tune-up season. Call your top 20 clients "
                "this week offering priority AC service at $99 — "
                "framed as 'beat the summer rush.' "
                "AC service in May costs $99; emergency AC in July costs $300."
            ),
        },
        {
            "name": "emergency_call_rate",
            "trigger": "household_energy_mom_pct > 1.0",
            "play": (
                "Energy costs rising = more heating/cooling failures. "
                "Raise your emergency service rate by $25 this week. "
                "Post '24/7 Emergency Plumbing & HVAC' on Google Business "
                "— emergency searches convert at 80%."
            ),
        },
    ],
    economist_context=(
        "Plumbing/HVAC cost structure: parts/materials 35-45%, labor 35-45%, "
        "vehicle/fuel 8-12%, net margin 10-20%. Material costs track with "
        "copper, steel, and PVC prices — not directly in BLS but correlated "
        "with fuel indices. Labor rates for licensed technicians are rising "
        "faster than general services (SASLE) due to shortage."
    ),
    scout_context=(
        "Watch for NJ permit changes (permit fees affect project margins), "
        "new housing construction (installation work demand), and extreme "
        "weather events (emergency call volume spikes). NJ contractor licensing "
        "requirements and insurance minimums affect entry barriers."
    ),
    synthesis_context=(
        "For plumbing/HVAC, key levers are service rate (hourly), material "
        "markup (40-60% standard), maintenance contract conversion, and "
        "emergency call premium. Example: 'Sell 10 annual maintenance contracts "
        "at $299 = $2,990 guaranteed revenue, zero marketing cost.' "
        "Recurring maintenance contracts are the highest-lifetime-value revenue."
    ),
    critique_persona=(
        "plumbing/HVAC owner with 4 trucks — you're licensed and insured in "
        "NJ, you've had to raise your hourly rate three times in two years "
        "just to keep pace with material costs, and you're competing against "
        "guys who work unlicensed for cash"
    ),
    social_search_terms=[
        "plumber business costs 2026", "HVAC business overhead NJ",
        "plumbing contractor pricing", "HVAC technician labor shortage",
        "home services business margin", "contractor parts prices inflation",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
        "commodity_inflation",
    ],
)


# ── Gym & Fitness Studio ─────────────────────────────────────────

GYM_FITNESS = IndustryConfig(
    id="gym",
    name="Gyms & Fitness Studios",
    aliases=frozenset({
        "gym", "fitness center", "health club", "fitness club", "workout",
        "crossfit", "crossfit gym", "boxing gym", "martial arts",
        "personal training", "personal trainer", "boot camp",
        "group fitness", "cycling studio", "spin class", "hiit studio",
        "functional fitness", "powerlifting gym", "weightlifting",
        "sports complex", "recreation center",
    }),
    bls_series={
        "Recreational reading materials": "CUUR0000SERS",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "rent": "rent_of_primary_residence_mom_pct",
        "household energy": "household_energy_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "january_membership_push",
            "trigger": "month in [1]",
            "play": (
                "January resolution season is your biggest acquisition window. "
                "Run a 'First month free, then $49/month' offer this week — "
                "end the promotion January 15th. New Year sign-ups have "
                "40% higher 6-month retention than summer sign-ups."
            ),
        },
        {
            "name": "summer_shred_push",
            "trigger": "month in [4, 5]",
            "play": (
                "Pre-summer fitness push starts now. Launch a '30-day "
                "Summer Shred Challenge' for $79 — runs May 1-31. "
                "Post before/after testimonials on Instagram. "
                "Challenges convert at 3x the rate of standard memberships."
            ),
        },
        {
            "name": "energy_cost_offset",
            "trigger": "household_energy_mom_pct > 1.5",
            "play": (
                "Energy costs rising — HVAC and lighting in a gym space "
                "can be $2,000-5,000/month. Raise monthly membership by $3 "
                "this cycle. Add a $5/month 'facility fee' for new enrollments."
            ),
        },
        {
            "name": "personal_training_upsell",
            "trigger": "services_less_energy_mom_pct > 0.5",
            "play": (
                "Service wages rising. Upsell personal training packages to "
                "your top 20 members this week — 4 sessions for $199 "
                "(vs $60/session single). "
                "Personal training revenue has 60% margin vs 30% for floor memberships."
            ),
        },
    ],
    economist_context=(
        "Gym cost structure: rent 30-45%, labor 25-35%, energy 8-15%, "
        "equipment/maintenance 5-10%, net margin 5-15%. Rent is the largest "
        "cost and hardest to reduce — gym spaces require 3,000-10,000 sq ft. "
        "Energy costs are unusually high due to HVAC requirements."
    ),
    scout_context=(
        "Watch for January resolution season (peak acquisition), summer (peak "
        "for body-focused marketing), and new gym openings (Planet Fitness at "
        "$10/month is the primary price competition). NJ recreation center "
        "expansions affect mid-tier gym market."
    ),
    synthesis_context=(
        "For gyms, key levers are membership pricing, personal training attach "
        "rate, class pack vs unlimited pricing, and churn reduction. Example: "
        "'Reduce churn from 8% to 6% per month = 20 more members = $1,000/month "
        "at $50 average.' Personal training is the highest-margin revenue (60%)."
    ),
    critique_persona=(
        "independent gym owner competing against $10/month chains — you've "
        "got $15k in monthly rent and 200 members, your peak hours are "
        "5-7pm weekdays, and you know that equipment maintenance surprises "
        "can wipe out a quarter's profit"
    ),
    social_search_terms=[
        "gym owner costs 2026", "fitness studio business overhead",
        "gym membership pricing strategy", "crossfit gym profit margin",
        "fitness studio energy costs NJ", "personal training business model",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
        "restaurant_technology",
    ],
)


# ── Yoga & Pilates Studio ────────────────────────────────────────

YOGA_PILATES = IndustryConfig(
    id="yoga",
    name="Yoga & Pilates Studios",
    aliases=frozenset({
        "yoga", "yoga studio", "pilates", "pilates studio", "barre",
        "barre studio", "barre class", "dance studio", "dance",
        "hot yoga", "bikram yoga", "meditation", "meditation studio",
        "mindfulness studio", "wellness studio", "stretch lab",
        "mobility studio", "aerial yoga", "prenatal yoga",
    }),
    bls_series={
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "rent": "rent_of_primary_residence_mom_pct",
        "household energy": "household_energy_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "new_year_intro",
            "trigger": "month in [1]",
            "play": (
                "January wellness resolutions. Run a 30-day intro offer: "
                "unlimited classes for $49. Cap it at 30 new students. "
                "Email your waitlist and post on Instagram by Jan 2nd. "
                "Intro offers convert to full memberships at 40%."
            ),
        },
        {
            "name": "class_pack_revenue",
            "trigger": "rent_of_primary_residence_mom_pct > 0.5",
            "play": (
                "Overhead rising. Push 10-class packs at $149 this week "
                "(vs $18/drop-in). Class packs generate $14.90/class vs "
                "$18 drop-in but capture revenue 60 days in advance. "
                "Email your drop-in clients today."
            ),
        },
        {
            "name": "hot_yoga_energy",
            "trigger": "household_energy_mom_pct > 1.5",
            "play": (
                "Energy costs rising — hot yoga and heated pilates studios "
                "pay 2-3x standard energy rates. Add $2 to all class passes "
                "this month. Frame as a 'heated studio surcharge.'"
            ),
        },
        {
            "name": "corporate_wellness",
            "trigger": "month in [8, 9]",
            "play": (
                "September is when HR teams set Q4 wellness budgets. "
                "Email 10 local companies this week offering a corporate "
                "wellness package — 20 employee passes/month for $799. "
                "Corporate contracts are recession-proof revenue."
            ),
        },
    ],
    economist_context=(
        "Yoga/pilates studio cost structure: rent 35-50%, teacher labor 25-35%, "
        "energy 5-10%, net margin 8-18%. Rent per sq ft is often higher than gyms "
        "due to premium location preference. Pilates reformer studios have higher "
        "equipment costs ($3-5k per reformer) but can charge $35-50/class."
    ),
    scout_context=(
        "Watch for new studio openings from national chains (CorePower, Club Pilates "
        "are expanding rapidly). Teacher training completions increase local competition. "
        "January and September are the two biggest enrollment windows. "
        "Prenatal yoga is a growing underserved niche."
    ),
    synthesis_context=(
        "For yoga/pilates, key levers are class pack vs membership pricing, "
        "teacher utilization (classes per teacher per week), and intro offer "
        "conversion rate. Example: 'Convert 5 intro students/month to $99 "
        "unlimited = $500/month, compounding each month.' "
        "Pilates (reformer) has 60% higher revenue per class than yoga."
    ),
    critique_persona=(
        "yoga studio owner with 4 teachers and a Reformer room — you've "
        "watched Club Pilates open two studios in your market this year, "
        "your rent is $4,500/month, and you know your retention rate better "
        "than most studio owners know their class schedule"
    ),
    social_search_terms=[
        "yoga studio owner costs 2026", "pilates studio business overhead",
        "yoga studio pricing strategy", "pilates reformer studio margin",
        "barre studio business model", "wellness studio NJ competition",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
        "restaurant_technology",
    ],
)


# ── Dental Office ────────────────────────────────────────────────

DENTAL = IndustryConfig(
    id="dental",
    name="Dental Offices",
    aliases=frozenset({
        "dentist", "dental office", "dental practice", "dental clinic",
        "orthodontist", "orthodontics", "oral surgeon", "oral surgery",
        "periodontist", "endodontist", "pediatric dentist", "cosmetic dentist",
        "teeth whitening", "dental implants", "dental", "family dentist",
        "general dentistry",
    }),
    bls_series={
        "Dental services": "CUUR0000SEMD",
        "Rent of primary residence": "CUUR0000SEHA",
        "Household energy": "CUUR0000SAH21",
        "Services less energy": "CUUR0000SASLE",
        "Other goods & services": "CUUR0000SAG1",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "dental": "dental_services_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "fee_schedule_update",
            "trigger": "dental_services_mom_pct > 0.5",
            "play": (
                "Dental services CPI up {dental_services_mom_pct}% — the market "
                "supports a fee schedule update. Increase your UCR fees by "
                "3-5% this week. Update your insurance fee schedule requests "
                "at the same time — most plans allow annual renegotiation."
            ),
        },
        {
            "name": "year_end_benefits_push",
            "trigger": "month in [10, 11]",
            "play": (
                "October-November: patients with dental insurance lose "
                "unspent benefits December 31st. Email your entire patient "
                "list TODAY: 'Use your 2026 benefits before they expire.' "
                "This is your single highest-conversion email of the year."
            ),
        },
        {
            "name": "new_patient_push",
            "trigger": "month in [1, 9]",
            "play": (
                "January (new insurance year) and September (back-to-school) "
                "are peak new patient months. Run a 'New Patient Special — "
                "exam + cleaning + X-rays for $99' offer on Google Ads "
                "this week. New patients are worth $500-2,000/year."
            ),
        },
        {
            "name": "cosmetic_upsell",
            "trigger": "dental_services_mom_pct > 0",
            "play": (
                "Patient willingness to pay for dental services is up. "
                "Add a whitening consult to every hygiene appointment this "
                "week. Professional whitening at $400-600 has 80% margin — "
                "it's the easiest add-on in dentistry."
            ),
        },
    ],
    economist_context=(
        "Dental practice cost structure: supplies/lab 8-12%, labor (staff) 25-35%, "
        "rent 5-10%, equipment/debt service 10-15%, net margin 25-40%. Dental has "
        "the highest margins of any healthcare-adjacent small business. Dental "
        "services CPI (SEMD) tracks consumer pricing — use to benchmark fee schedules."
    ),
    scout_context=(
        "Watch for dental group acquisitions (DSOs are buying independent practices "
        "at high multiples but they also compete aggressively). Insurance network "
        "changes affect patient flow significantly. Year-end benefit expiration "
        "(Oct-Dec) is the most predictable demand surge in the industry."
    ),
    synthesis_context=(
        "For dental offices, key levers are fee schedule optimization, insurance "
        "vs out-of-pocket mix, new patient acquisition cost, and cosmetic case "
        "conversion. Example: 'Convert 5 whitening cases/month at $500 = "
        "$2,500 in elective revenue at 80% margin.' Year-end recall is the "
        "single highest-ROI marketing activity for any dental practice."
    ),
    critique_persona=(
        "dental practice owner with 2 chairs and a hygienist — you spend "
        "$800/month on insurance billing, you've fought with every major "
        "insurance plan over reimbursement rates, and you know that one "
        "broken CBCT scanner can shut down your practice for a week"
    ),
    social_search_terms=[
        "dental practice owner costs 2026", "dentist business overhead NJ",
        "dental fee schedule increase", "dental practice insurance reimbursement",
        "dental office profit margin", "DSO vs independent practice",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Florist ──────────────────────────────────────────────────────

FLORIST = IndustryConfig(
    id="florist",
    name="Florists & Flower Shops",
    aliases=frozenset({
        "florist", "flower shop", "flowers", "floral shop", "floral studio",
        "floral design", "wedding florist", "event florist", "flower delivery",
        "florist delivery", "boutique florist", "garden center", "nursery",
        "plant shop", "succulent shop", "flower market",
    }),
    bls_series={
        "Fresh fruits": "CUUR0000SEFN",
        "Fresh vegetables": "CUUR0000SEFP",
        "Gasoline, all types": "CUUR0000SETB01",
        "Rent of primary residence": "CUUR0000SEHA",
        "Other goods & services": "CUUR0000SAG1",
        "Food (all items)": "CUUR0000SAF1",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "gasoline": "gasoline,_all_types_mom_pct",
        "fresh fruits": "fresh_fruits_mom_pct",
        "fresh vegetables": "fresh_vegetables_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
    },
    playbooks=[
        {
            "name": "valentines_prep",
            "trigger": "month in [1]",
            "play": (
                "Valentine's Day is your Super Bowl. Pre-order red roses NOW — "
                "January wholesale rose prices are 40% lower than the first "
                "week of February. Lock in pricing from your supplier this week."
            ),
        },
        {
            "name": "mothers_day_push",
            "trigger": "month in [4]",
            "play": (
                "Mother's Day is 4-6 weeks away. Open pre-orders this week. "
                "Cap your order volume to what you can actually fulfill. "
                "Post your Mother's Day arrangements on Instagram with "
                "'Pre-order now — limited availability.'"
            ),
        },
        {
            "name": "wedding_season_lock",
            "trigger": "month in [2, 3]",
            "play": (
                "Wedding season bookings happen Feb-Mar for June-Sept weddings. "
                "Lock in all wholesale pricing NOW before spring supply tightens. "
                "Require a 50% deposit on all wedding floral contracts — "
                "no exceptions."
            ),
        },
        {
            "name": "delivery_fuel_cost",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Fuel up {gasoline,_all_types_mom_pct}% — add a $5-8 "
                "delivery surcharge to all delivery orders this week. "
                "Most customers expect it. Batch deliveries by neighborhood "
                "to cut total miles driven."
            ),
        },
    ],
    economist_context=(
        "Florist cost structure: flowers/supplies 40-50%, labor 20-30%, "
        "rent 10-15%, delivery 5-10%, net margin 5-15%. Perishable inventory "
        "is the key management challenge — unsold flowers are 100% loss. "
        "Holiday concentration is extreme: Valentine's Day and Mother's Day "
        "are 30-40% of annual revenue."
    ),
    scout_context=(
        "Watch for local wedding venue bookings (direct signal for wedding "
        "florals demand), hospital construction or openings (sympathy arrangements), "
        "and funeral home activity. Valentine's Day, Mother's Day, and holiday "
        "season (Dec) are the three make-or-break revenue windows."
    ),
    synthesis_context=(
        "For florists, key levers are holiday pre-order capture, wedding contract "
        "deposits, wholesale buying timing, and waste reduction. Example: "
        "'Pre-order Valentine's roses in January = 40% lower input cost on your "
        "highest-volume item.' Wedding florals are highest margin (35-45%) but "
        "require deposits to protect cash flow."
    ),
    critique_persona=(
        "florist who has run a flower shop for 12 years — you're at the market "
        "at 5am twice a week, you've lost money on wilted roses before Valentine's "
        "Day, and you know that one big wedding can be worth $3,000 in a single day"
    ),
    social_search_terms=[
        "florist business costs 2026", "flower shop overhead NJ",
        "wholesale flower prices 2026", "wedding florist profit margin",
        "florist Valentine's Day prep", "flower shop delivery costs",
    ],
    reference_topics=[
        "small_business_margins", "commodity_inflation",
    ],
)


# ── Dry Cleaner & Laundry ────────────────────────────────────────

DRY_CLEANER = IndustryConfig(
    id="dry_cleaner",
    name="Dry Cleaners & Laundry Services",
    aliases=frozenset({
        "dry cleaner", "dry cleaning", "laundry", "laundromat", "laundry service",
        "wash and fold", "alterations", "tailoring", "tailor", "seamstress",
        "clothing alterations", "dry clean", "cleaners", "garment care",
        "linen service", "uniform service",
    }),
    bls_series={
        "Laundry & dry cleaning": "CUUR0000SS30021",
        "Household energy": "CUUR0000SAH21",
        "Rent of primary residence": "CUUR0000SEHA",
        "Services less energy": "CUUR0000SASLE",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "laundry": "laundry_&_dry_cleaning_mom_pct",
        "household energy": "household_energy_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
    },
    playbooks=[
        {
            "name": "energy_price_adjustment",
            "trigger": "household_energy_mom_pct > 1.5",
            "play": (
                "Energy up {household_energy_mom_pct}% — your commercial "
                "washers and dryers run 8-10 hours/day. Raise per-piece "
                "prices by $0.50-1.00 this week and add a $5 "
                "'energy surcharge' to orders over $50."
            ),
        },
        {
            "name": "service_price_cover",
            "trigger": "laundry_&_dry_cleaning_mom_pct > 0.5",
            "play": (
                "Dry cleaning CPI up {laundry_&_dry_cleaning_mom_pct}% — "
                "market is moving. Raise your standard suit cleaning price "
                "by $1.50 this week. Customers expect gradual annual increases."
            ),
        },
        {
            "name": "spring_wedding_push",
            "trigger": "month in [3, 4, 5]",
            "play": (
                "Wedding season. Post your 'Wedding Dress Cleaning & "
                "Preservation' package on Instagram and your Google Business "
                "profile this week — $175-250 for preservation. "
                "Wedding dress cleaning has 70% margin."
            ),
        },
        {
            "name": "corporate_accounts",
            "trigger": "month in [1, 9]",
            "play": (
                "January (new fiscal year) and September (Q4 planning) are "
                "when businesses set vendor contracts. Email 10 local offices "
                "and restaurants this week offering a corporate laundry "
                "account — uniform service is weekly recurring revenue."
            ),
        },
    ],
    economist_context=(
        "Dry cleaner cost structure: energy 15-25%, labor 30-40%, chemicals "
        "10-15%, rent 10-20%, net margin 8-18%. Energy is the most volatile "
        "cost — commercial cleaning equipment is energy-intensive. "
        "Perc (PERC solvent) costs are tracked by industry but not BLS — "
        "many shops switching to GreenEarth or CO2 cleaning to reduce chemical costs."
    ),
    scout_context=(
        "Watch for office building occupancy rates (suits and dress shirts are "
        "the core business), restaurant openings (linen service), and local "
        "event venues (tablecloth and event linen). Remote work reduced "
        "weekday dry cleaning demand by 30-40% permanently."
    ),
    synthesis_context=(
        "For dry cleaners, key levers are per-piece pricing, energy surcharges, "
        "specialty services (wedding dress, leather, alterations), and "
        "corporate/restaurant accounts. Example: 'Add $1.50 to suit cleaning "
        "= $750/month on 500 suits.' Corporate accounts are 2-3x higher LTV "
        "than residential clients."
    ),
    critique_persona=(
        "dry cleaner owner who bought the business 8 years ago — you manage "
        "chemical compliance, equipment maintenance, and customer pickups, "
        "and you've watched remote work cut your suit cleaning volume "
        "by 35% in 3 years"
    ),
    social_search_terms=[
        "dry cleaner business costs 2026", "laundry service overhead NJ",
        "dry cleaning energy costs", "dry cleaner pricing strategy",
        "laundry service business margin", "dry cleaning chemical costs",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Pet Grooming ─────────────────────────────────────────────────

PET_GROOMING = IndustryConfig(
    id="pet_grooming",
    name="Pet Grooming & Care",
    aliases=frozenset({
        "pet grooming", "dog grooming", "groomer", "pet groomer",
        "dog groomer", "cat grooming", "pet salon", "dog salon",
        "mobile groomer", "mobile dog grooming", "pet spa",
        "pet care", "doggy daycare", "dog daycare", "dog boarding",
        "pet boarding", "dog walker", "dog walking", "pet sitting",
        "veterinarian", "vet", "animal hospital", "pet store",
    }),
    bls_series={
        "Other goods & services": "CUUR0000SAG1",
        "Rent of primary residence": "CUUR0000SEHA",
        "Gasoline, all types": "CUUR0000SETB01",
        "Services less energy": "CUUR0000SASLE",
        "All items (CPI-U)": "CUUR0000SA0",
    },
    usda_commodities=[],
    extra_signals=[],
    track_labels={
        "gasoline": "gasoline,_all_types_mom_pct",
        "rent": "rent_of_primary_residence_mom_pct",
        "services less energy": "services_less_energy_mom_pct",
        "other goods": "other_goods_&_services_mom_pct",
    },
    playbooks=[
        {
            "name": "service_rate_increase",
            "trigger": "services_less_energy_mom_pct > 0.5",
            "play": (
                "Service wages and costs rising {services_less_energy_mom_pct}% — "
                "raise your standard groom by $5-10 for new bookings this week. "
                "Email clients with 2 weeks notice. Pet owners rarely cancel "
                "over a $5-10 increase."
            ),
        },
        {
            "name": "holiday_early_booking",
            "trigger": "month in [10, 11]",
            "play": (
                "Holiday grooming season books up in November. Email your "
                "entire client list TODAY: 'Book your holiday groom now — "
                "December slots fill in 2 weeks.' Charge a $20 deposit "
                "on holiday bookings."
            ),
        },
        {
            "name": "mobile_fuel_surcharge",
            "trigger": "gasoline,_all_types_mom_pct > 2.0",
            "play": (
                "Fuel up {gasoline,_all_types_mom_pct}% this month. "
                "Add a $10 mobile travel surcharge to all mobile appointments. "
                "Optimize routes to cluster appointments by neighborhood — "
                "save 20-30% on fuel per day."
            ),
        },
        {
            "name": "spring_shedding_push",
            "trigger": "month in [3, 4, 5]",
            "play": (
                "Spring shedding season — your most in-demand period. "
                "Post 'Spring deshedding treatment — $25 add-on' on Instagram "
                "this week. Deshedding adds $25-40 per appointment with "
                "5 minutes of extra work."
            ),
        },
    ],
    economist_context=(
        "Pet grooming cost structure: labor 40-55%, supplies 10-15%, "
        "rent 10-20%, vehicle/fuel (mobile) 8-15%, net margin 15-25%. "
        "The pet industry is recession-resistant — pet spending held flat "
        "during 2008-2009. Supply costs (shampoo, conditioner, blades) "
        "are not tracked by BLS; use SAG1 as proxy."
    ),
    scout_context=(
        "Watch for new pet housing (apartment complexes with pet-friendly "
        "policies drive new customer acquisition), grooming chain openings "
        "(PetSmart, Petco groomers are primary competition), and "
        "summer (shedding season) and holiday (Dec) demand spikes."
    ),
    synthesis_context=(
        "For pet groomers, key levers are appointment frequency, add-on "
        "services (deshedding, teeth brushing, nail grinding), and recurring "
        "client retention. Example: 'Sell monthly grooming memberships at "
        "$65/month = guaranteed $65 vs $80 one-time = lower but predictable.' "
        "Recurring bookings at 4-6 week intervals are the margin engine."
    ),
    critique_persona=(
        "pet groomer who has run a 2-table salon for 7 years — you know "
        "every dog by name, you've been bitten 50 times, and you're tired "
        "of clients who cancel the morning of the appointment after "
        "you've already blocked the slot"
    ),
    social_search_terms=[
        "pet groomer business costs 2026", "dog grooming pricing NJ",
        "pet grooming business overhead", "mobile groomer fuel costs",
        "pet grooming supply prices", "dog groomer business margin",
    ],
    reference_topics=[
        "small_business_margins", "labor_costs_restaurants",
    ],
)


# ── Lookup ──────────────────────────────────────────────────────

_ALL: list[IndustryConfig] = [
    RESTAURANT, BAKERY, BARBER,
    COFFEE_SHOP, PIZZA_FAST_CASUAL, FOOD_TRUCK,
    NAIL_SALON, HAIR_SALON, SPA_MASSAGE, TATTOO_STUDIO,
    AUTO_REPAIR, RESIDENTIAL_CLEANING, PLUMBING_HVAC,
    GYM_FITNESS, YOGA_PILATES, DENTAL,
    FLORIST, DRY_CLEANER, PET_GROOMING,
]

_INDEX: dict[str, IndustryConfig] = {}
for _cfg in _ALL:
    for _alias in _cfg.aliases:
        _INDEX[_alias] = _cfg
    _INDEX[_cfg.id] = _cfg  # always index by id so resolve(industry_key) works


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
