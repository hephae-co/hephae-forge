# Industry Config Audit: All Industries
Generated: 2026-03-22
Industries: restaurant, bakery, barber
Note: Media & Community Sources section (Phase 6) is pending background agent — scores marked TBD will be updated.

---

## Summary Scorecard

| Dimension | Weight | Restaurant | Bakery | Barber |
|-----------|--------|-----------|--------|--------|
| Alias Coverage | 10% | 85 | 55 | 75 |
| BLS Series Validity | 15% | 55 | 70 | 30 |
| Playbook Quality | 20% | 25 | 55 | 75 |
| Context String Quality | 10% | 45 | 90 | 85 |
| Media & Community | 20% | 80 | 70 | 75 |
| Pulse Signal Yield | 15% | 45 | 20 | 10 |
| Trend Summary Quality | 10% | 70 | 60 | 20 |
| **Weighted Total** | **100%** | **56** | **60** | **55** |

**Final grades:**
- Restaurant: **D** (56/100) — strong media ecosystem; held back by dead code, 0 playbooks, empty scout_context
- Bakery: **C** (60/100) — best-configured industry; media coverage validated; blocked by bls_client disconnect
- Barber: **D** (55/100) — good playbook quality; sabotaged by wrong data vertical (food CPI for a barber shop)

---

## CRITICAL SYSTEM BUG — Affects All 3 Industries

### `IndustryConfig.bls_series` and `track_labels` are dead code

**Root cause:** `bls_client.py` has its own hardcoded `FOOD_CPI_SERIES`, `DETAILED_SERIES`, and `INDUSTRY_TO_DETAILED` maps. `fetch_bls_cpi(business_type)` calls `_get_relevant_series(industry)` which uses these hardcoded maps — it **never reads `IndustryConfig.bls_series`**.

Similarly, `compute_impact_multipliers()` generates variable names by converting BLS label strings to snake_case. It **never reads `IndustryConfig.track_labels`**.

**Impact by industry:**

| Industry | What bls_client ACTUALLY fetches | What IndustryConfig.bls_series defines | Missing at runtime |
|----------|----------------------------------|----------------------------------------|--------------------|
| restaurant | FOOD_CPI_SERIES + meats/produce/dairy detailed | 19 series including same + SAFH | SAFH; mostly OK |
| bakery | FOOD_CPI_SERIES + DETAILED_SERIES["bakery"] (Cereals + Bakery products only) | 11 series incl. flour/eggs/butter/sugar/milk | flour_yoy_pct, eggs_yoy_pct, butter_yoy_pct, sugar_yoy_pct, milk_yoy_pct — ALL ABSENT |
| barber | FOOD_CPI_SERIES only (no INDUSTRY_TO_DETAILED entry for "barber") | 6 series incl. barber CPI, rent, energy | barber_services_yoy_pct, rent_yoy_pct, energy_yoy_pct, services_yoy_pct — ALL ABSENT |

**Consequence:** Every bakery playbook that references an ingredient variable, and every barber playbook that references a service/rent variable, will **silently never fire**.

### YoY% variables are not populated

Playbook triggers use `_yoy_pct` variables (e.g., `dairy_yoy_pct > 5`, `barber_services_yoy_pct > 3`). The live `nationalImpact` contains only `_mom_pct` values. `compute_impact_multipliers` only sets `dairy_yoy_pct` and `poultry_yoy_pct` via hardcoded lines, and only if `yoyPctChange is not None` in the BLS response — which it currently is not.

**Result:** 0 playbooks have fired across all 3 industries. Every single playbook trigger is either referencing a non-existent variable or a variable that is never populated.

---

## Phase 2: Alias Coverage

### Restaurant (85/100)
All 12 tested types route correctly via fuzzy substring match ("Thai Restaurant" → "restaurant", "Sushi" → "restaurant"). Bar/Gastropub/Brewery silently fall back to restaurant — borderline acceptable.

**Missing aliases to add:**
- `"bar"`, `"gastropub"`, `"brewery"`, `"wine bar"`, `"food hall"`, `"ghost kitchen"`, `"pop-up restaurant"`, `"ramen"`, `"sushi"`, `"thai"`, `"chinese restaurant"`, `"indian restaurant"`, `"mediterranean"`, `"steakhouse"`

### Bakery (55/100)
6/11 test cases correct. 5 MISS — all fall silently to restaurant:
- `"dessert shop"`, `"churro shop"`, `"pretzel shop"`, `"cake studio"`, `"baked goods"`

**Missing aliases to add:**
- `"dessert shop"`, `"dessert"`, `"churros"`, `"churro"`, `"pretzel"`, `"pretzel shop"`, `"cake studio"`, `"baked goods"`, `"cookie shop"`, `"cookies"`, `"brownie shop"`, `"mochi"`, `"crepe"`, `"crepes"`, `"waffle shop"`, `"waffles"`, `"candy shop"`, `"chocolate shop"`, `"confectionery"`

### Barber (75/100)
7/9 correct. 2 MISS:
- `"fade shop"` → restaurant (should be barber)
- `"grooming studio"` → restaurant (should be barber)

**Questionable:** `"nail salon"` is in barber aliases — nail salons are a distinct vertical, not barber shops.

**Missing aliases to add:** `"fade shop"`, `"grooming studio"`, `"mens salon"`, `"shave shop"`, `"hot towel shave"`, `"beard studio"`, `"locs stylist"`, `"braids"`, `"wave shop"`

**Alias to REMOVE:** `"nail salon"` — different business model, wrong vertical.

**No cross-industry collisions found.**

---

## Phase 3: BLS Series Validation

### Series Status (24/25 PASS, 1 FAIL)

| Series ID | Label | Industry | Status | Latest Value | MoM% |
|-----------|-------|----------|--------|-------------|------|
| CUUR0000SAF1 | Food (all items) | all | PASS | 346.564 | +0.41% |
| CUUR0000SAF11 | Food at home | rest/bak | PASS | 318.898 | +0.46% |
| **CUUR0000SAFH** | **Food away from home** | **restaurant** | **FAIL** | **NO DATA** | — |
| CUUR0000SAF111 | Cereals & bakery | rest/bak | PASS | 367.174 | +0.09% |
| CUUR0000SAF112 | Meats, poultry, fish & eggs | restaurant | PASS | 346.309 | -0.09% |
| CUUR0000SAF113 | Dairy | restaurant | PASS | 362.604 | +1.05% |
| CUUR0000SAF114 | Fruits & vegetables | rest/bak | PASS | 238.081 | +0.98% |
| CUUR0000SAF115 | Nonalcoholic beverages | restaurant | PASS | 282.185 | +0.90% |
| CUUR0000SEFC01 | Beef & veal | restaurant | PASS | 434.921 | +0.97% |
| CUUR0000SEFC02 | Pork | restaurant | PASS | 410.762 | +1.42% |
| CUUR0000SEFD | Poultry | restaurant | PASS | 270.757 | -0.58% |
| CUUR0000SEFE | Fish & seafood | restaurant | PASS | 295.736 | **-4.33%** |
| CUUR0000SEFG | Eggs | rest/bak | PASS | 370.314 | +0.17% |
| CUUR0000SEFJ | Milk | rest/bak | PASS | 269.599 | -0.58% |
| CUUR0000SEFK | Cheese | restaurant | PASS | — | -0.20% |
| CUUR0000SEFL | Ice cream | restaurant | PASS | 395.584 | +2.78% |
| CUUR0000SEFN | Fresh fruits | restaurant | PASS | — | +0.41% |
| CUUR0000SEFP | Fresh vegetables | restaurant | PASS | 164.385 | +2.24% |
| CUUR0000SEFR | Processed fruits & veg | restaurant | PASS | 325.517 | +2.65% |
| CUUR0000SEFA01 | Flour & flour mixes | bakery | PASS | 326.768 | **-0.91%** |
| CUUR0000SS5702 | Butter | bakery | PASS | — | — |
| CUUR0000SEFR01 | Sugar & substitutes | bakery | PASS | 276.879 | -0.99% |
| CUUR0000SEFB | Bakery products | bakery | PASS | 411.850 | +0.28% |
| CUUR0000SEFB01 | Bread | bakery | PASS | 246.951 | +0.54% |
| CUUR0000SEFB02 | Cakes, cupcakes, cookies | bakery | PASS | 243.254 | -0.23% |
| CUUR0000SS45011 | Barber & beauty services | barber | PASS | 174.420 | +0.21% |
| CUUR0000SEHA | Rent of primary residence | barber | PASS | — | — |
| CUUR0000SAH21 | Household energy | barber | PASS | 288.227 | +0.24% |
| CUUR0000SASLE | Services less energy | barber | PASS | — | — |
| CUUR0000SAG1 | Other goods & services | barber | PASS | 299.123 | +0.13% |
| CUUR0000SA0 | All items (CPI-U) | barber | PASS | — | — |

**CRITICAL DATA POINT:** Flour is DOWN -0.91% MoM — the `flour_cost_alert` playbook trigger `flour_yoy_pct > 3` would NOT fire even if the variable existed. Eggs are only +0.17% — `egg_spike_response` requires >8% (correct threshold, just not firing today). Fish & seafood -4.33% MoM is the strongest signal currently — driving all zip-level pulse headlines but never appears in national playbooks.

### track_labels Wasted Signals

| Industry | BLS Series with NO track_label (data fetched but variable never named) |
|----------|-----------------------------------------------------------------------|
| restaurant | Food all items, Food at home, **Food away from home (FAILS anyway)**, Cereals & bakery, Fruits & veg, Nonalcoholic beverages, Milk, Cheese, Processed fruits & veg |
| bakery | Cereals & bakery, Food all items |
| barber | Other goods & services, All items CPI-U |

Restaurant has 9 wasted BLS series — data is fetched and never surfaced to playbooks or LLM prompts.

### BLS Gaps

**Restaurant:** Missing oil/fats series (no CPI series for cooking oil — a major restaurant input). Missing `CUUR0000SEMC` (limited service meals CPI — directly tracks fast-casual pricing power).

**Bakery:** `bls_client.py` DETAILED_SERIES["bakery"] only includes `Cereals` (SEFA) and `Bakery products` (SEFB) — it's missing SEFA01 (Flour specifically, which IS in IndustryConfig but not in bls_client). Fix required in `bls_client.py`, not in `IndustryConfig`.

**Barber:** No entry in `bls_client.INDUSTRY_TO_DETAILED` for "barber" at all. Must add: `"barber": ["barber_services", "rent", "energy", "services"]` and add the corresponding DETAILED_SERIES categories.

---

## Phase 4: Playbook Quality

### Restaurant (25/100)

| Playbook | Trigger | Variables OK? | Banned? | Specificity | Category | Verdict |
|----------|---------|--------------|---------|------------|---------|---------|
| dairy_margin_swap | dairy_yoy_pct > 5 AND poultry_yoy_pct < 0 | ✗ YoY not populated | None | 1/4 (timeline only) | Input cost spike | FAIL |
| fda_recall_alert | fda_recent_recall_count > 5 | ✓ | None | 1/4 (timeline only) | Regulatory | FAIL |
| weather_rain_prep | weather_traffic_modifier < -0.1 | ✓ | None | 0/4 | Weather | FAIL |

Missing categories: input cost drop, margin squeeze, seasonal, competitive.
Play text problems: `dairy_margin_swap` says "Shift cream-heavy dishes to grilled proteins" — no dollar amount, no channel. `weather_rain_prep` says "Push delivery specials" — no platform named, no price.

### Bakery (55/100)

| Playbook | Trigger | Variables OK? | Banned? | Specificity | Currently Active? | Verdict |
|----------|---------|--------------|---------|------------|-----------------|---------|
| flour_cost_alert | flour_yoy_pct > 3 | ✗ YoY not populated | None | 3/4 | Flour -0.91% MoM → dormant | PASS (spec OK) |
| egg_spike_response | eggs_yoy_pct > 8 | ✗ YoY not populated | None | 0/4 | Eggs +0.17% → dormant | FAIL (spec) |
| butter_margin_squeeze | butter_yoy_pct > 4 | ✗ YoY not populated | None | 2/4 | — | FAIL (spec) |
| wedding_season_lock | month in [2,3,4] AND sugar_yoy_pct > 2 | ✗ YoY not populated | None | 2/4 | March: season OK, sugar -0.99% → dormant | FAIL (spec) |
| holiday_pre_order_push | month in [10,11] AND flour_yoy_pct > 0 | ✗ YoY not populated | None | 2/4 | Wrong month | FAIL (spec) |
| fda_allergen_alert | fda_recent_recall_count > 10 | ✓ | None | 3/4 | Depends on count | PASS |

Missing categories: input cost drop (no playbook for "flour is cheap, lock in pricing"), competitive.

### Barber (75/100)

| Playbook | Trigger | Variables OK? | Banned? | Specificity | Currently Active? | Verdict |
|----------|---------|--------------|---------|------------|-----------------|---------|
| service_price_cover | barber_services_yoy_pct > 3 | ✗ Not populated | None | 3/4 | +0.21% MoM (YoY unknown) | PASS (spec) |
| rent_squeeze_response | rent_yoy_pct > 5 | ✗ Not populated | None | 3/4 | — | PASS (spec) |
| walk_in_weather_boost | weather_traffic_modifier > 0 | ✓ (from weather signal) | None | 3/4 | National has no weather | PASS (spec) |
| event_upsell | event_traffic_modifier > 0 | ✓ (from catalysts) | None | 3/4 | National has no events | PASS (spec) |
| slow_season_fill | month in [1, 2] | ✓ | None | 4/4 | March → dormant | PASS |
| new_competitor_alert | establishments_yoy_change_pct > 5 | ✓ (from QCEW) | None | 3/4 | National has no QCEW | PASS (spec) |

Missing category: margin squeeze (no playbook for when costs rise but raising prices is risky).
Barber playbooks are the best-written of the three — specific dollar amounts, named channels, clear actions.

---

## Phase 5: Context String Quality

### Restaurant (45/100)
| String | Length | Score | Issue |
|--------|--------|-------|-------|
| economist_context | 125 chars | 55 | Too short, no BLS series IDs mentioned |
| **scout_context** | **0 chars** | **0** | **EMPTY — critical gap** |
| synthesis_context | 200 chars | 75 | Has concrete example ("$12.99 family pickup on DoorDash") |
| critique_persona | 41 chars | 10 | "restaurant owner with 15 years experience" — zero personality |
| social_search_terms | 4 terms | 40 | All consumer-review bait; "restaurant", "food", "dining" will surface Yelp |

### Bakery (90/100)
| String | Length | Score | Issue |
|--------|--------|-------|-------|
| economist_context | 345 chars | 95 | Names BLS series IDs, states margin range, tracks spread between input and consumer CPI |
| scout_context | 286 chars | 85 | Specific events, holiday calendar, competitor types |
| synthesis_context | 429 chars | 90 | Concrete examples, specific levers, margin %s |
| critique_persona | 242 chars | 95 | Real person, specific pain point ("3% egg swing wipes margin on custard tarts") |
| social_search_terms | 8 terms | 70 | "bakery", "pastry", "cake" are consumer-facing; "bakery owner flour costs" would be better |

### Barber (85/100)
| String | Length | Score | Issue |
|--------|--------|-------|-------|
| economist_context | 275 chars | 90 | Names CPI series, states commission model, realistic margin |
| scout_context | 268 chars | 85 | Specific events (proms, weddings), back-to-school |
| synthesis_context | 327 chars | 90 | Concrete example, specific levers, revenue % for retail |
| critique_persona | 196 chars | 85 | Real person, specific pain point ("never swept hair off a floor") |
| social_search_terms | 7 terms | 65 | "barber", "haircut", "hair salon" are consumer-facing |

---

## Phase 6: Media & Community Sources

Scores: Restaurant **80/100** | Bakery **70/100** | Barber **75/100**

---

### RESTAURANT

**Trade Publications & News — ADD**

| Source | URL | RSS | Verdict | Notes |
|--------|-----|-----|---------|-------|
| Nation's Restaurant News | nrn.com | `https://www.nrn.com/rss.xml` — 50 items, March 20 2026 | **ADD** | Flagship US restaurant trade pub; daily ops signal |
| Restaurant Business Online | restaurantbusinessonline.com | `/feed` — 50 items, March 20 2026 | **ADD** | Strong finance and ops coverage |
| Modern Restaurant Management | modernrestaurantmanagement.com | None found | **ADD** | Consistently ops-heavy content |
| Total Food Service | totalfood.com | `https://totalfood.com/feed/` — 10 items | **ADD** | NYC/NJ-focused foodservice trade |
| Restaurant Dive | restaurantdive.com | `https://www.restaurantdive.com/feeds/news/` — confirmed | **ADD** | Active, ops-focused; confirmed RSS feed |
| NJBIZ | njbiz.com | `https://njbiz.com/feed/` — 10 items verified | **ADD** | NJ-specific business news; restaurant openings, policy |
| James Beard 2026 Independent Report | jamesbeard.org | Annual | **ADD** | 380+ owners surveyed; annual anchor data |
| Restaurant365 2026 Survey | restaurant365.com | Annual | **ADD** | 4,000-location cost benchmarks |
| NRA Press Releases | restaurant.org | Manual | **ADD** (policy/annual data only) | State of Industry + regulatory signals |

**Reddit Communities — ADD**

| Community | Members | Verdict | Notes |
|-----------|---------|---------|-------|
| r/restaurantowners | ~17,000 | **ADD** | RSS: `.rss`; explicitly ops-focused owner community |
| r/smallbusiness | ~708,000 | **ADD** | Use keyword filter "restaurant costs margins"; large signal pool |
| r/restaurant (143k) | 143,000 | **SKIP** | Consumer-dominated; too much noise |

**Google News RSS Queries — Validated with article counts**

| Query | Articles | Signal Quality |
|-------|----------|---------------|
| `restaurant+food+cost+supply+chain+NJ` | **81** | **GOOD** — NJ-specific, fresh; top: "Rising Food Costs" (QSR Mag) |
| `restaurant+health+inspection+compliance+regulation+New+Jersey` | **74** | **GOOD** — NJ-specific; top: "3 Monmouth County restaurants cited for health violations" (APP) |
| `restaurant+labor+cost+minimum+wage+New+Jersey+2026` | **71** | **GOOD** — NJ min wage to $15.49/hr Jan 2026; Restaurant Dive coverage |
| `restaurant+consumer+spending+dining+trends+2026` | **63** | MODERATE — McKinsey + Restaurant Dive trend pieces |
| `restaurant+delivery+platform+fees+DoorDash+Uber+Eats+commission` | **51** | GOOD — DoorDash/Grubhub NYC cap fee settlement coverage |
| `restaurant+industry+trends+2026` | 100 | MODERATE — stale SEO content at top; NJ queries above are better |

**social_search_terms Assessment**

| Current Term | Problem | Replacement |
|-------------|---------|-------------|
| `restaurant industry news` | Surfaces consumer media, not SMB ops | `restaurant food cost inflation operator 2026` |
| `food service trends` | Generic; consumer food trend content | `food service labor costs supplier pricing NJ 2026` |
| `restaurant owner` | Reasonable but listicle-heavy | Keep; add `independent` qualifier |
| `food costs` | Extremely generic; commodity + consumer articles | `restaurant operator supply chain 2026` |
| `menu pricing` | Also pulls consumer review angles | `menu price increase strategy restaurant operator` |
| `dining` | **REMOVE** — 100% consumer intent (best dining in NJ, Zagat) | `foodservice margins` |

**Add:** `restaurant labor minimum wage NJ 2026`, `food tariff restaurant cost 2026`, `DoorDash commission fee restaurant operator`

**Intelligence Gaps:**
- Energy/utilities costs — no NJ-specific utility trend source
- Delivery platform fee changes — news coverage exists but no dedicated RSS
- NJ food inspection bulletins — no RSS; manual monitoring only
- Restaurant insurance cost trends

---

### BAKERY

**Trade Publications & News — ADD**

| Source | URL | RSS | Verdict | Notes |
|--------|-----|-----|---------|-------|
| Baking Business | bakingbusiness.com | Confirm via `/feed`; daily newsletter | **ADD** | Primary US commercial baking trade; CPI and ingredient cost coverage |
| Bake Magazine | bakemag.com | `https://www.bakemag.com/rss/articles` — 30 items, March 20 2026 | **ADD** | Active confirmed RSS; trade-professional focus |
| Commercial Baking | commercialbaking.com | None confirmed | **ADD** | Active B2B commercial bakery publication |
| Bakery and Snacks | bakeryandsnacks.com | None confirmed | **ADD** | Global supply chain and ingredient science coverage |
| American Bakers Association | americanbakers.org | Manual (latest March 16 2026) | **ADD** (regulatory only) | Ingredient regulation, labeling changes, azodicarbonamide phase-out |
| Retail Bakers of America | retailbakersofamerica.org | "News You Knead" newsletter (free, members) | **ADD** | Most SMB-relevant bakery association; merger with ABA in progress |

**Reddit Communities**

| Community | Verdict | Notes |
|-----------|---------|-------|
| r/bakery | **DEAD** | 1 subscriber — do not use |
| r/Baking | **SKIP** | 2M members, home/hobby baking; no business ops signal |
| r/smallbusiness (filtered) | **ADD** | Use keyword filter "bakery costs flour pricing"; large signal pool |
| The Fresh Loaf (thefreshloaf.com) | **ADD** | Professional baker community; has dedicated business/commercial section |

**Google News RSS Queries — Validated with article counts**

| Query | Articles | Signal Quality |
|-------|----------|---------------|
| `bakery+food+safety+FDA+regulation+compliance+2026` | **52** | **GOOD** — GRAS updates, food safety summit, allergen rules |
| `bakery+POS+technology+online+ordering+platform+2026` | **51** | MODERATE — technology/ops; Toast and Forbes coverage |
| `bakery+ingredient+cost+flour+butter+supply+chain+2026` | **25** | **GOOD** — "Lansing bakery lowers prices as ingredient costs ease"; wheat prices signal |
| `bakery+consumer+trends+seasonal+demand+wedding+cake+2026` | **13** | MODERATE — seasonal demand signal |
| `bakery+New+Jersey+opening+closing+artisan+patisserie` | **33** | GOOD — NJ.com "71 best bakeries" + new openings/closings |
| `artisan+bakery+business+trends` | 50 | **WEAK** — UK-focused and stale; use NJ-specific query above instead |

**social_search_terms Assessment**

| Current Term | Problem | Replacement |
|-------------|---------|-------------|
| `bakery business` | Startup/listicle content; no live ops | `retail bakery operating costs 2026` |
| `bread prices` | Consumer price comparison | `flour wheat commodity prices commercial baker 2026` |
| `flour costs` | Ingredient-relevant but also speculator content | Keep; add `bakery operator supply chain` as companion |
| `bakery owner` | How-to/startup heavy | Combine with `costs margins profit 2026` |
| `artisan bakery` | Style/culture and consumer reviews | `artisan bakery overhead ingredient cost` |

**Add:** `baked goods CPI 2026`, `wholesale flour price increase baker`, `bakery labor wages small business`

**Intelligence Gaps:**
- USDA ERS wheat pricing (https://www.ers.usda.gov/topics/crops/wheat/) — not currently used in config; best US-specific flour cost source
- NJ food handler certification — no active bulletin source
- Bakery packaging costs — no dedicated feed
- Cottage food / home bakery regulations by state

---

### BARBER

**Trade Publications & News — ADD**

| Source | URL | RSS | Verdict | Notes |
|--------|-----|-----|---------|-------|
| BarberEVO Magazine | barberevo.com/category/industry-news | None confirmed | **ADD** (industry news only) | Active, March 20 2026; style-heavy, limited cost/margin coverage |
| Barbers Illustrated Magazine | barbersillustratedmagazine.com | Newsletter ($9.99/mo digital) | **ADD** | Most ops-focused barber publication; "How to Build a $10K+ Barber Month," pricing strategy |
| National Association of Barbers | nationalbarbers.org | Free weekly newsletter | **ADD** | Only national US barber association with free weekly newsletter |
| NABBA | nationalbarberboards.com | Manual | **ADD** (regulatory only) | Tracks state barber licensing changes across all 50 states |
| **AHP Legislative Updates** | **associatedhairprofessionals.com/updates/legislative-updates** | **Bi-weekly web page** | **ADD — CRITICAL** | **NJ-specific barber regulatory updates confirmed Feb 27 2026; covers licensing compacts, textured hair mandates, FICA tip tax** |
| Professional Beauty Association (PBA) | probeauty.org | Blog + newsletter | Partly free | **ADD** | Covers FICA tip tax, licensing wins, barber advocacy |

**Reddit Communities**

| Community | Members | Verdict | Notes |
|-----------|---------|---------|-------|
| r/Barber | 143,535 | **ADD** | RSS: `.rss`; "#1 community for barbers by barbers"; filter by "pricing", "rent", "booth", "owner" |
| r/smallbusiness (filtered) | ~708,000 | **ADD** | Use "barbershop" keyword filter; owners post occasionally |

**Google News RSS Queries — Validated with article counts**

| Query | Articles | Signal Quality |
|-------|----------|---------------|
| `men%27s+grooming+industry+revenue+cost+2026` | **71** | **GOOD** — "Men's Grooming Market Surges: Key Trends" (NIQ); broadest automated signal |
| `%22barbershop%22+OR+%22barber+shop%22+costs+OR+pricing+OR+regulation+New+Jersey` | **40** | **GOOD** — NJ-specific; "Mikie Sherrill announces utility cost controls" (NJ Gov) |
| `barbershop+barber+licensing+regulation+pricing+2026` | **16** | MODERATE — "New Board modifying cosmetology guidelines" (WDAM-TV); Texas/national coverage |
| `men%27s+grooming+market+booking+technology+2026` | 10 | MODERATE — SQUIRE and booking app coverage |
| `barber+shop+industry+trends+2026` | 50 | **DEAD** — off-topic results (safety razor market reports); do not use |
| `hair+care+salon+labor+costs+pricing` | 80 | **DEAD** — Singapore salon lists + Thai tourism; do not use |

**Note:** Booth rental/independent contractor regulation returned 0 results — this is a confirmed intelligence gap, not a query issue.

**social_search_terms Assessment**

| Current Term | Problem | Replacement |
|-------------|---------|-------------|
| `barber shop business` | Startup guides and salary articles | Keep; add `costs rent 2026` |
| `barber industry` | Very broad; licensing articles and style magazines | `barber shop owner operating costs 2026` |
| `hair care costs` | Consumer pricing ("how much does a haircut cost") | `barber shop supply costs products wholesale` |
| `barber owner` | Income/salary and business advice — reasonable | Keep; combine with `pricing strategy margins` |
| `grooming trends` | Consumer-facing product trends | `men's grooming service price increase operator 2026` |
| `haircut` | **REMOVE** — 100% consumer intent | `barber business pricing strategy` |
| `fade` | **REMOVE** — 100% style/consumer content | `barbershop booth rental rates 2026` |
| `beard trim` | **REMOVE** — 100% consumer/tutorial | `barber licensing renewal requirements 2026` |

**Add:** `barbershop+booth+rental+rates+2026`, `barber+shop+rent+increase+small+business`

**Intelligence Gaps:**
- Product/supply wholesale pricing (clippers, chairs, disposables) — no dedicated feed
- NJ barber board bulletins — no RSS; use AHP Legislative Updates (best available) and manual NJ Consumer Affairs check
- Booth rental / independent contractor classification — zero news coverage confirmed; this is a genuine gap
- Men's grooming wholesale-to-retail cost passthrough dynamics

---

### Regulatory Sources (All Industries)

| Source | Relevant To | Status | Notes |
|--------|-------------|--------|-------|
| FDA Recalls RSS | restaurant, bakery | **`https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/recalls/rss.xml`** — 20 items verified, March 19 2026 | ✓ Working — filter for: `food`, `allergen`, `flour`, `nut`, `dairy`. Note: `/food/rss.xml` returns 404 — use `/recalls/rss.xml` |
| NJ Dept of Health Retail Food | restaurant, bakery | Manual only — last reviewed March 13 2026; no RSS | Check quarterly; covers N.J.A.C. 8:24 compliance |
| NJ Consumer Affairs Cosmetology/Barber Board | barber | Manual only — no RSS | Barber license renewal every 2 years (even years); no CE required; Feb 2026 updates (curriculum, restroom inclusivity) |
| **AHP Legislative Updates** | **barber** | **Bi-weekly updates — NJ entry confirmed Feb 27 2026** | **Best available NJ barber regulatory signal; also covers textured hair mandates, FICA tip tax** |
| NABBA | barber | Manual — track state-level license changes | Best cross-state barber regulatory source |

---

## Phase 7: Live Pulse Cross-Check

### Signal Yield vs Expected

| Signal | Restaurant Expected? | Restaurant Got? | Bakery Expected? | Bakery Got? | Barber Expected? | Barber Got? |
|--------|---------------------|----------------|-----------------|-------------|-----------------|-------------|
| blsCpi | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| usdaPrices | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| fdaRecalls | ✓ | ✗ MISSING | ✓ | ✗ MISSING | ✗ | ✗ |
| priceDeltas | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

fdaRecalls is in `extra_signals` for both restaurant and bakery but is NOT in the national pulse `signalsUsed` — the national signal fetch likely skips it (requires state parameter not available at industry level).

### nationalImpact Variable Audit

**Bakery** — expected from track_labels, actual from pulse:

| Expected Variable | In nationalImpact? | Notes |
|-----------------|-------------------|-------|
| flour_yoy_pct | ✗ ABSENT | BLS doesn't fetch SEFA01 for bakery at runtime |
| eggs_yoy_pct | ✗ ABSENT | BLS doesn't fetch SEFH for bakery at runtime |
| butter_yoy_pct | ✗ ABSENT | BLS doesn't fetch SS5702 for bakery at runtime |
| sugar_yoy_pct | ✗ ABSENT | BLS doesn't fetch SEFR01 for bakery at runtime |
| milk_yoy_pct | ✗ ABSENT | BLS doesn't fetch SEFJ for bakery at runtime |
| bakery_consumer_yoy_pct | ✗ ABSENT | SEFB IS in bls_client bakery, but only MoM computed |
| bread_yoy_pct | ✗ ABSENT | Not in bls_client bakery series |
| cakes_yoy_pct | ✗ ABSENT | Not in bls_client bakery series |
| dairy_mom_pct | ✓ present | 1.05% — from broad food CPI series |
| bakery_products_mom_pct | ✓ present | 0.28% — from DETAILED_SERIES["bakery"] |

**Barber** — expected from track_labels, actual from pulse:

| Expected Variable | In nationalImpact? | Notes |
|-----------------|-------------------|-------|
| barber_services_yoy_pct | ✗ ABSENT | SS45011 not in bls_client, no INDUSTRY_TO_DETAILED["barber"] |
| rent_yoy_pct | ✗ ABSENT | SEHA not in bls_client |
| energy_yoy_pct | ✗ ABSENT | SAH21 not in bls_client |
| services_yoy_pct | ✗ ABSENT | SASLE not in bls_client |
| (all 10 keys in barber pulse) | food CPI data | Completely wrong — food prices for a barber shop |

### Playbook Activation

All 3 industries: `nationalPlaybooks: []` — zero playbooks fired.

| Reason | Affected Playbooks |
|--------|--------------------|
| Variable never populated (bls_client gap) | bakery: all 4 ingredient playbooks; barber: service_price_cover, rent_squeeze_response, new_competitor_alert |
| Variable never populated (YoY not computed) | restaurant: dairy_margin_swap, bakery: wedding_season_lock, holiday_pre_order_push |
| Threshold not met | restaurant: dairy_yoy_pct only 1.05% (needs >5%) |
| National pulse has no weather signal | restaurant: weather_rain_prep; barber: walk_in_weather_boost |
| National pulse has no events signal | barber: event_upsell |
| National pulse has no QCEW | barber: new_competitor_alert |

### Trend Summary Quality

| Industry | Length | Specific Numbers? | Industry-Relevant? | Banned Phrases? | Score |
|----------|--------|-----------------|-------------------|----------------|-------|
| restaurant | 1075 chars | ✓ (2.24%, 2.65%, -4.33%) | ✓ | None | 70 |
| bakery | 978 chars | ✓ (1.05%, 0.98%, 0.46%) | Partially — discusses dairy/fruits broadly, not butter/flour specifically | None | 60 |
| barber | 930 chars | ✓ (0.41%, 1.05%, 0.98%) | ✗ ENTIRELY WRONG — food grocery prices for a barber shop | None | 20 |

---

## Critical Issues (Ranked by Impact)

1. **[CRITICAL] `IndustryConfig.bls_series` is never read at runtime** — `bls_client.py` uses hardcoded `INDUSTRY_TO_DETAILED` map. `bakery` only gets 2 detailed series (Cereals, Bakery products). `barber` gets food CPI data. Fix: add `INDUSTRY_TO_DETAILED["bakery"]` with all bakery input series; add `INDUSTRY_TO_DETAILED["barber"]` with service/rent/energy; wire `IndustryConfig.bls_series` into `_get_relevant_series()` OR update the hardcoded map.

2. **[CRITICAL] YoY% variables not computed** — `compute_impact_multipliers` only sets `dairy_yoy_pct` and `poultry_yoy_pct` via hardcoded lines; all other `_yoy_pct` triggers silently evaluate to `None`. Fix: in `compute_impact_multipliers`, compute YoY from BLS 12-month-ago data point, or switch all playbook triggers to use `_mom_pct` variables which ARE populated.

3. **[CRITICAL] Barber national pulse is entirely wrong** — barber gets food CPI data (dairy, fruits, meats). Its trend summary discusses grocery prices. Zero barber-relevant intelligence is produced. Fix: add `"barber"` to `bls_client.INDUSTRY_TO_DETAILED` with service/rent/energy categories.

4. **[HIGH] All playbooks dormant** — 0/15 total playbooks across all industries have ever fired in any pulse run. This means the entire playbook layer produces zero output.

5. **[HIGH] `fdaRecalls` signal missing from national pulses** — listed in `extra_signals` for food verticals but not fetched at industry level (requires state param). Bakery's fda_allergen_alert and restaurant's fda_recall_alert can never fire nationally.

6. **[HIGH] Restaurant `scout_context` is empty** — LLM scout agent receives zero guidance on seasonal events, competitor types, or local factors for restaurants.

7. **[HIGH] Restaurant `critique_persona` is generic** — 41-char string provides no grounding for the critique agent.

8. **[MEDIUM] Bakery alias coverage at 55%** — "Dessert Shop", "Churro Shop", "Cake Studio", "Baked Goods" silently fall to restaurant.

9. **[MEDIUM] `CUUR0000SAFH` (Food away from home) returns no data** — this is the primary consumer-side pricing series for restaurants; its absence means restaurant pricing power is invisible.

10. **[MEDIUM] 9 wasted BLS series in restaurant config** — data fetched but no track_label → never surfaces to playbooks or agents.

---

## Recommended Fixes (Prioritized)

### Fix 1 — Wire IndustryConfig into bls_client (CRITICAL, 1 file)
File: `lib/integrations/hephae_integrations/bls_client.py`
```python
def _get_relevant_series(industry: str, config=None) -> dict[str, str]:
    # If IndustryConfig provided, use its bls_series directly
    if config and config.bls_series:
        return dict(config.bls_series)
    # ...existing fallback logic...
```
Then in `fetch_bls_cpi(business_type)`, resolve the IndustryConfig and pass it.

### Fix 2 — Add barber to INDUSTRY_TO_DETAILED (CRITICAL, 1 line)
File: `lib/integrations/hephae_integrations/bls_client.py`
```python
INDUSTRY_TO_DETAILED["barber"] = []  # no food categories
INDUSTRY_TO_DETAILED["barbershop"] = []
# Add new DETAILED_SERIES categories for service businesses:
DETAILED_SERIES["services"] = {
    "Barber & beauty services": "CUUR0000SS45011",
    "Services less energy": "CUUR0000SASLE",
    "Rent of primary residence": "CUUR0000SEHA",
    "Household energy": "CUUR0000SAH21",
}
INDUSTRY_TO_DETAILED["barber"] = ["services"]
```

### Fix 3 — Fix playbook triggers to use MoM% (HIGH, industries.py)
Either:
a) Change all `_yoy_pct` triggers to `_mom_pct` and adjust thresholds (e.g., `dairy_yoy_pct > 5` → `dairy_mom_pct > 0.5`)
b) Fix the BLS fetcher to request a wider year range (2024-2026) so YoY can be computed

### Fix 4 — Add restaurant scout_context and fix critique_persona
File: `apps/api/hephae_api/workflows/orchestrators/industries.py`
- `scout_context`: "Watch for new restaurant openings and closures via Google Maps and Yelp. Key seasonal events: Valentine's Day, Mother's Day, Thanksgiving, and New Year's Eve drive peak revenue. Sports events and local festivals spike delivery demand."
- `critique_persona`: "restaurant owner who runs a 40-seat neighborhood place — you negotiate with food distributors weekly, you've watched food costs jump 30% in 3 years, and you're tired of consultants who've never done a Friday dinner rush"

### Fix 5 — Add bakery aliases
`"dessert shop"`, `"dessert"`, `"churro"`, `"pretzel"`, `"cake studio"`, `"baked goods"`, `"cookie shop"`, `"confectionery"`, `"chocolate shop"`, `"crepe"`, `"waffle shop"`

### Fix 6 — Improve social_search_terms (all 3)
- restaurant: add `"restaurant owner costs"`, `"food cost inflation"`, `"restaurant supply chain"`, `"restaurant margins"` — replace generic `"food"`, `"dining"`
- bakery: add `"bakery owner costs"`, `"flour prices"`, `"bakery supply chain"` — replace `"bakery"`, `"pastry"`
- barber: add `"barber owner pricing"`, `"barbershop business"`, `"salon rent costs"` — replace `"haircut"`, `"hair salon"`

### Fix 7 — Add SAFH alternative for restaurant
`CUUR0000SAFH` returns no data. Replace with `CUUR0000SEMC` (Limited-service meals, series ID to confirm) which tracks fast-casual/restaurant consumer prices.

---

## Media & Community Sources

See Phase 6 above for full source inventory, RSS query results, and social_search_terms assessment.

**Quick summary of ADD sources:**
- Restaurant: 8 publications/annual reports + 1 Reddit community + 3 RSS queries (1 strong, 2 need replacement)
- Bakery: 6 publications/associations + 1 filtered Reddit community + 3 RSS queries (1 moderate, 2 need replacement)
- Barber: 4 publications/associations + 1 Reddit community + 1 of 3 RSS queries useful; 2 dead queries need replacement

**No NJ-specific regulatory feeds exist for any industry** — all three NJ regulatory bodies require manual monitoring.

**All existing `social_search_terms`** across all 3 industries are primarily consumer-facing and will surface reviews, salary articles, and startup guides rather than business operations intelligence. See Phase 6 for per-industry replacement terms.
