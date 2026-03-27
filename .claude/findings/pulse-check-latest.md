# Industry Pulse Check: All 19 Industries — 2026-W13
Generated: 2026-03-26T00:00:00Z
Scope: All 19 active industry pulses for week 2026-W13
Auditor: hephae-pulse-check skill (IP-1 through IP-6)

---

## Overall Grade: C (65/100)

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Signal Coverage | 25% | 73 | 4/19 industries missing expected signals |
| Signal Accuracy | 30% | 52 | Systemic YoY errors on SAG1 and SASLE; 2 industries with wrong or missing data |
| Pre-Compute Correctness | 20% | 72 | MoM values all accurate; YoY values stale or miscalculated on many series |
| Playbook Accuracy | 15% | 42 | 25/64 playbook triggers (39%) silently unparseable; 3 industries got wrong playbooks |
| Trend Summary Quality | 10% | 74 | No banned phrases; all have numbers; 1 critical mislabeling, 1 wrong-industry summary |

---

## Per-Industry Scorecard

| Industry | Grade | Score | Key Issues |
|----------|-------|-------|-----------|
| coffee_shop | A | 94 | Clean across all dimensions |
| bakery | B+ | 88 | Missing fdaRecalls; butter "MoM" is a 4-month window |
| barber | B | 82 | SAG1/SASLE YoY stale |
| dental | B | 82 | SASLE/SAG1 YoY stale; minor SEMD YoY diff |
| gym | B | 82 | SERS returns no BLS data (wrong proxy series) |
| nail_salon | B | 82 | SASLE/SAG1 YoY stale; month-based playbooks silently broken |
| pet_grooming | B | 82 | SASLE/SAG1 YoY stale |
| spa | B | 82 | SASLE/SAG1 YoY stale; month-based playbooks silently broken |
| tattoo | B | 82 | SAG1 YoY stale; month-based playbooks silently broken |
| yoga | B | 82 | SASLE/SAG1 YoY stale; month-based playbooks silently broken |
| dry_cleaner | C | 70 | SS30021 YoY wrong sign (+1.28% actual, -1.96% pulse) |
| florist | C | 70 | Produce YoY errors; SAG1 YoY stale |
| plumbing_hvac | C | 70 | Missed summer_ac_push; SASLE/SAG1 YoY stale |
| auto_repair | C | 65 | SETB01 mislabeled as "motor vehicle parts"; spring_ac_push missed |
| hair_salon | C | 65 | Missed bridal_season_capture (month=3); SASLE/SAG1 YoY stale |
| residential_cleaning | C | 65 | Missed spring_deep_clean (month=3); SASLE YoY stale |
| pizza | C | 65 | Missing fdaRecalls; multiple YoY errors |
| restaurant | D | 57 | Missing fdaRecalls; missed dairy_margin_swap; 5 YoY errors |
| food_truck | D | 44 | Wrong BLS series (got restaurant data); wrong playbooks fired; missing 2 signals |

---

## PHASE IP-1: Pulse Inventory

All 19 W13 industry pulses present in Firestore `industry_pulses` collection.
Document IDs follow `{industry_key}-2026-W13` pattern.

Signal counts at a glance:
- **3 signals** (blsCpi + usdaPrices + priceDeltas): bakery, coffee_shop, pizza, restaurant
- **2 signals** (blsCpi + priceDeltas): all other 15 industries
- **food_truck**: 2 signals — should have 3 (missing fdaRecalls and usdaPrices)

---

## PHASE IP-2: BLS Signal Verification

### Method
All 36 relevant BLS series fetched from the BLS public API in two batches. MoM% recalculated from the two most recent non-null data points. YoY% from the 13th-most-recent non-null point.

### MoM% Values — ALL CORRECT

Every MoM% value stored in nationalImpact matches the independently recalculated BLS figure. All 33 verified series pass.

Key confirmed values:
- All Items CPI-U MoM: 0.47% (PASS)
- Dairy MoM: 1.05% (PASS)
- Fish & Seafood MoM: -4.33% (PASS)
- Fresh Vegetables MoM: 2.24% (PASS)
- Butter MoM: 3.56% (PASS — but see note below)
- Gasoline MoM: 3.33% (PASS)
- Barber & Beauty Services MoM: 0.21% (PASS)
- Services Less Energy MoM: 0.38% (PASS)

**Butter note:** CUUR0000SS5702 only has data for Jan 2026 and Sep 2025 in the BLS API (bimonthly publication). The 3.56% is calculated over a 4-month window but is labeled as MoM throughout the pulse.

### YoY% Values — SYSTEMIC ERRORS

| Series | Label | BLS YoY% | Pulse YoY% | Error | Affected Industries |
|--------|-------|----------|------------|-------|---------------------|
| CUUR0000SAG1 | Other goods & services | **5.51%** | **4.53%** | -18% | auto_repair, barber, dental, florist, hair_salon, nail_salon, pet_grooming, plumbing_hvac, spa, tattoo, yoga (11 industries) |
| CUUR0000SASLE | Services less energy | **3.33%** | **2.92%** | -12% | barber, dental, dry_cleaner, gym, hair_salon, nail_salon, pet_grooming, plumbing_hvac, residential_cleaning, spa, tattoo, yoga (12 industries) |
| CUUR0000SEFC01 | Beef & veal | **18.39%** | **15.25%** | -17% | restaurant, food_truck, pizza |
| CUUR0000SEFC02 | Pork | **16.68%** | **12.37%** | -26% | restaurant, food_truck |
| CUUR0000SEFE | Fish & seafood | **2.87%** | **3.50%** | +22% | restaurant, food_truck |
| CUUR0000SEFN | Fresh fruits | **2.76%** | **3.20%** | +16% | restaurant, food_truck, florist |
| CUUR0000SEFP | Fresh vegetables | **12.40%** | **11.24%** | -9% | restaurant, food_truck, pizza, florist |
| CUUR0000SS30021 | Laundry/dry cleaning | **+1.28%** | **-1.96%** | WRONG SIGN | dry_cleaner |
| CUUR0000SEMD | Dental services | **7.83%** | **7.59%** | -3% | dental (acceptable) |

**Root cause for SAG1/SASLE:** The YoY error is consistent at exactly -18% for SAG1 and -12% for SASLE across all affected industries. This indicates a stale cache baseline — the 13-period lookback used in `compute_price_deltas()` is referencing a cached value from one month earlier than current, making the Feb 2025 comparison period incorrect.

**Root cause for protein YoYs (beef, pork):** The high relative errors on beef/pork YoY suggest the Jan 2025 baseline value was cached when data was preliminary and has since been revised upward by BLS.

**Root cause for dry cleaner SS30021 YoY sign reversal:** The YoY for SS30021 is -1.96% but BLS shows +1.28%. A 3.24pp absolute error with a sign flip suggests the YoY calculation is using the wrong comparison month entirely for this series.

---

## PHASE IP-3: Trend Summary Audit

### Banned Phrase Scan
All 19 trend summaries: **CLEAN** — zero occurrences of "consider", "monitor", "capitalize", "leverage", "strategic", "proactive", "stay informed", "be aware", "keep an eye on", or "be mindful."

### Number Count
All 19 trend summaries contain 6-15 specific percentages. All numbers reference actual nationalImpact values. Summaries are data-grounded, not generic.

### Critical Issue 1: Auto Repair — SETB01 Mislabeled

CUUR0000SETB01 = **"Gasoline, all types"** in BLS and in IndustryConfig.

Trend summary text:
> "a 3.33% month-over-month increase in **motor vehicle parts and equipment costs** (CUUR0000SETB01)"

This is factually wrong. The LLM described a gasoline index as "motor vehicle parts." An auto shop owner reading this would misunderstand where the 3.33% MoM increase is coming from. The repair/maintenance CPI (SETA02) declined 1.21% MoM — the two series tell opposite stories and the summary mislabels which one is rising.

### Critical Issue 2: Food Truck — Wrong Industry Context

Trend summary first sentence:
> "The most notable movement in the **restaurant supply chain** this week..."

The food truck trend summary is entirely written for restaurants. It discusses fish/seafood, beef, pork, cheese, dairy — none of which are in the food truck BLS series config. Gasoline (the food truck's primary cost driver) is completely absent. This summary would actively mislead a food truck owner.

### Summary Quality Table

| Industry | Numbers | Accuracy | Issues | Rating |
|----------|---------|----------|--------|--------|
| coffee_shop | 9 | All correct | None | HIGH |
| bakery | 11 | All correct | Butter "MoM" is 4-month | HIGH |
| dental | 8 | Minor YoY diff | None | HIGH |
| dry_cleaner | 6 | SS30021 YoY wrong sign | None | MEDIUM |
| restaurant | 14 | Multiple YoY errors | None | MEDIUM |
| auto_repair | 8 | Numbers accurate | SETB01 mislabeled as "motor vehicle parts" | LOW |
| food_truck | 15 | Multiple YoY errors | Wrong industry; says "restaurant supply chain" | LOW |

---

## PHASE IP-4: Playbook Accuracy

### Critical Bug: 25/64 Playbook Triggers (39%) Are Silently Unparseable

**File:** `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py`
**Function:** `_parse_trigger()` (line 305–313)
**Regex:** `r'^(\S+)\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)$'`

This regex handles only `variable op value` (e.g., `butter_mom_pct > 1.5`). It returns `None` for:
- `month in [3, 4, 5]` — seasonal triggers
- `dairy_mom_pct > 1.0 and poultry_mom_pct < 0` — compound conditions

When `None` is returned, the loop logs a warning and silently skips the playbook. No exception is raised, no flag is stored in the pulse document. The failure is invisible in production.

**25 broken trigger patterns (parsed result: FAIL):**

| Industry | Playbook | Trigger |
|----------|---------|---------|
| restaurant | dairy_margin_swap | `dairy_mom_pct > 1.0 and poultry_mom_pct < 0` |
| bakery | wedding_season_lock | `month in [2, 3, 4] and sugar_&_substitutes_mom_pct > 0.5` |
| bakery | holiday_pre_order_push | `month in [10, 11] and flour_&_flour_mixes_mom_pct > 0` |
| barber | slow_season_fill | `month in [1, 2]` |
| coffee_shop | seasonal_drink_push | `month in [9, 10, 11, 12]` |
| coffee_shop | loyalty_slow_day | `month in [1, 2]` |
| pizza | lunch_special | `month in [9, 10, 11, 12, 1, 2]` |
| food_truck | event_season_lock | `month in [4, 5, 6, 7, 8, 9]` |
| nail_salon | holiday_gift_card | `month in [11, 12]` |
| nail_salon | bridal_season | `month in [4, 5, 6]` |
| hair_salon | bridal_season_capture | `month in [3, 4, 5, 6]` |
| hair_salon | back_to_school | `month in [8, 9]` |
| spa | holiday_gift_cards | `month in [11, 12]` |
| spa | membership_push | `month in [1, 2]` |
| tattoo | flash_event | `month in [10]` |
| tattoo | summer_push | `month in [5, 6, 7]` |
| auto_repair | winter_prep_push | `month in [9, 10]` |
| auto_repair | spring_ac_push | `month in [3, 4, 5]` |
| residential_cleaning | spring_deep_clean | `month in [3, 4]` |
| plumbing_hvac | winter_hvac_push | `month in [8, 9, 10]` |
| plumbing_hvac | summer_ac_push | `month in [4, 5]` |
| gym | january_membership_push | `month in [1]` |
| gym | summer_shred_push | `month in [4, 5]` |
| yoga | new_year_intro | `month in [1]` |
| yoga | corporate_wellness | `month in [8, 9]` |

**W13 (March 2026) playbooks that SHOULD have fired but did not:**

| Industry | Playbook | Trigger | Evidence |
|----------|---------|---------|---------|
| auto_repair | spring_ac_push | `month in [3, 4, 5]` | March = month 3 |
| hair_salon | bridal_season_capture | `month in [3, 4, 5, 6]` | March = month 3 |
| residential_cleaning | spring_deep_clean | `month in [3, 4]` | March = month 3 |
| restaurant | dairy_margin_swap | `dairy > 1.0 AND poultry < 0` | dairy=1.05, poultry=-0.58 — both conditions met |

### Food Truck: Wrong Restaurant Playbooks Fired

food_truck matched `seafood_opportunity` and `produce_spike_alert`. These are RESTAURANT playbooks.

Cause chain:
1. food_truck nationalImpact contains restaurant series (see Section IP-5)
2. `match_industry_playbooks()` found no matching triggers (gasoline variable absent)
3. Fell back to global `match_playbooks()` registry
4. Restaurant playbooks in global registry matched: fish_&_seafood_mom_pct=-4.33% and fresh_vegetables_mom_pct=2.24%

A food truck owner is being told "Fish & seafood prices dropped 4.33% — add a seafood special this weekend." This is restaurant advice, not relevant to a food truck.

### Playbook Verdict Table

| Industry | Should Fire | Did Fire | Correct? |
|----------|------------|---------|---------|
| auto_repair | spring_ac_push | none | NO |
| bakery | butter_margin_squeeze | butter_margin_squeeze | YES |
| barber | none | none | YES |
| coffee_shop | none | none | YES |
| dental | none | none | YES |
| dry_cleaner | none | none | YES |
| florist | none | none | YES |
| food_truck | none | seafood_opportunity + produce_spike_alert | NO — wrong playbooks |
| gym | none | none | YES |
| hair_salon | bridal_season_capture | none | NO |
| nail_salon | none | none | YES |
| pet_grooming | none | none | YES |
| pizza | none | none | YES |
| plumbing_hvac | none (month=3 not in summer/fall windows) | none | YES |
| residential_cleaning | spring_deep_clean | none | NO |
| restaurant | seafood_opportunity + produce_spike_alert + dairy_margin_swap | seafood_opportunity + produce_spike_alert | PARTIAL |
| spa | none | none | YES |
| tattoo | none | none | YES |
| yoga | none | none | YES |

---

## PHASE IP-5: Cross-Industry Analysis

### Signal Coverage by Vertical

| Signal | Food Verticals | Non-Food |
|--------|---------------|---------|
| blsCpi | All 5 | All 14 |
| priceDeltas | All 5 | All 14 |
| usdaPrices | bakery, coffee_shop, pizza, restaurant | N/A |
| fdaRecalls | **NONE** | N/A |

FDA is absent from all food verticals. Root cause (code-level):

`generate_industry_pulse()` in `industry_pulse.py` (line 73):
```python
national_signals = await fetch_national_signals(
    business_type,
    config_bls_series=dict(industry.bls_series) if industry.bls_series else None,
)
```
No `state` argument is passed. `fetch_national_signals()` defaults to `state=""`. Inside `fetch_fda()`:
```python
async def fetch_fda(state: str) -> dict[str, Any]:
    if not state:
        return {}
```
Empty string causes immediate return. FDA never fetched. `fda_recent_recall_count` never set. `fda_recall_alert` and `fda_allergen_alert` playbooks can never fire for any industry pulse.

### Food Truck BLS Series Identity Issue

food_truck nationalImpact contains all restaurant series (fish, beef, pork, cheese, eggs, dairy, etc.) instead of its own config series (gasoline, food away from home, meats aggregate, fruits/veg, dairy).

food_truck IndustryConfig.bls_series:
- Gasoline, all types: CUUR0000SETB01
- Food away from home: CUUR0000SAFH
- Food (all items): CUUR0000SAF1
- Meats, poultry, fish & eggs: CUUR0000SAF112
- Fruits & vegetables: CUUR0000SAF114
- Dairy: CUUR0000SAF113

None of these match what's actually in the food_truck nationalImpact. The most likely root cause is a BLS cache collision: the data_cache key for blsCpi is `business_type` string. If a prior run cached restaurant BLS data under the `food_truck` key (possibly from when Bug 2 from the previous debug report — resolve() falling back to RESTAURANT — was active), that stale restaurant CPI data would have persisted and been served from cache this week.

### Cross-Industry Consistency

All shared BLS series values (all_items CPI, rent, energy) are identical across every industry that uses them. This confirms the BLS fetching mechanism is working correctly for shared series.

### Gym BLS Series Issue

`GYM_FITNESS.bls_series` includes `"Recreational reading materials": "CUUR0000SERS"`. BLS API returns **NO DATA** for CUUR0000SERS (the series has been discontinued or never had data at this level). The gym pulse therefore has no gym-specific pricing CPI. SASLE (services less energy) and rent are present as proxies but SERS contributes nothing.

---

## Issues Found

### P0 — Critical (Production Inaccuracies)

**Issue 1: 39% of playbook triggers silently broken**
25/64 playbooks never fire. `_parse_trigger()` rejects `month in [...]` and compound `and` conditions. The code logs a warning but continues silently. For W13: 3 industries missed seasonal playbooks they should have received (auto_repair spring_ac_push, hair_salon bridal_season_capture, residential_cleaning spring_deep_clean), plus restaurant missed dairy_margin_swap.
- File: `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` line 302

**Issue 2: FDA signal absent from all food verticals**
`generate_industry_pulse()` calls `fetch_national_signals()` without passing `state`. `fetch_fda(state="")` returns `{}`. `fda_recent_recall_count` is never populated. `fda_recall_alert` (restaurant) and `fda_allergen_alert` (bakery) can never fire.
- File: `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` line 73

**Issue 3: Food truck receiving restaurant BLS data**
food_truck nationalImpact and trend summary are entirely based on restaurant series. Gasoline (the food truck's most important cost driver) is absent. `fuel_cost_route` playbook can never fire. Owners receive restaurant-specific advice.

**Issue 4: SETB01 mislabeled as "motor vehicle parts" in auto_repair trend summary**
CUUR0000SETB01 = Gasoline, all types. The LLM trend summary describes it as "motor vehicle parts and equipment costs" — factually incorrect. This misleads auto shop owners about their cost environment.

### P1 — High (Data Quality)

**Issue 5: SAG1 YoY understated by 18% across 11 industries**
`other_goods_&_services_yoy_pct` = 4.53% in pulse vs BLS actual 5.51%. Affects all non-food service industries using SAG1.

**Issue 6: SASLE YoY understated by 12% across 12 industries**
`services_less_energy_yoy_pct` = 2.92% in pulse vs BLS actual 3.33%. Affects all service-oriented industries.

**Issue 7: Dry cleaner SS30021 YoY wrong sign**
Pulse reports -1.96% YoY; BLS actual = +1.28%. Trend summary tells dry cleaning owners their service prices are declining YoY when they are actually rising.

**Issue 8: Beef & veal YoY understated by 17%**
15.25% in pulse vs 18.39% actual. Understates ongoing beef inflation for restaurants.

**Issue 9: Pork YoY understated by 26%**
12.37% in pulse vs 16.68% actual. Most severe protein YoY error. Pork is up 16.7% annually; pulse says 12.4%.

**Issue 10: restaurant dairy_margin_swap not fired despite both conditions being met**
dairy_mom_pct = 1.05 > 1.0 (true). poultry_mom_pct = -0.58 < 0 (true). Trigger is a compound `and` expression — unparseable by the trigger regex.

### P2 — Medium (Configuration Bugs)

**Issue 11: Gym uses CUUR0000SERS which returns no BLS data**
`GYM_FITNESS.bls_series` includes "Recreational reading materials" (SERS) which has no data from BLS. No fitness-specific pricing CPI is being tracked.
- File: `apps/api/hephae_api/workflows/orchestrators/industries.py` (GYM_FITNESS definition)

**Issue 12: Bakery egg series stored as raw series ID**
`CUUR0000SEFH` stores as `cuur0000sefh_mom_pct` in nationalImpact (raw ID) rather than `eggs_mom_pct` (the track_labels key). `egg_spike_response` playbook evaluates `eggs_mom_pct` which is `None`, so it can never fire even if eggs spike.

**Issue 13: Butter MoM labeled as monthly but is a 4-month window**
SS5702 has bimonthly data gaps. Jan 2026 vs Sep 2025 = 4-month change labeled as "MoM."

**Issue 14: food_truck missing usdaPrices signal**
`food_truck.extra_signals = ["fdaRecalls", "usdaPrices"]` but only blsCpi + priceDeltas fetched. Same state="" root cause as Issue 2.

### P3 — Low

**Issue 15: Fish & seafood YoY overstated** — 3.50% pulse vs 2.87% BLS (22% relative, 0.63pp absolute).

**Issue 16: Fresh fruits YoY overstated** — 3.20% pulse vs 2.76% BLS (16% relative, 0.44pp absolute).

**Issue 17: Fresh vegetables YoY understated** — 11.24% pulse vs 12.40% BLS (9% relative, 1.16pp absolute).

---

## Recommendations

**Fix 1 (P0 — playbook triggers):** Extend `_parse_trigger()` to handle `month in [...]` and compound `and` expressions. Simplest approach: inject `"month": current_month` into the impact dict before playbook evaluation, and add a `_eval_list_trigger()` path for `in` operators. For compound `and` triggers, either split into two separate playbook entries in the config, or add an `and` condition combiner to the trigger evaluator.

**Fix 2 (P0 — FDA missing):** Pass a non-empty state sentinel to `generate_industry_pulse()`, or modify `fetch_national_signals()` to accept `state=None` as "national" (no state filter for FDA). The national FDA query without a state filter returns the most recent recalls across the US.

**Fix 3 (P0 — food_truck BLS cache collision):** Delete `data_cache` document with key `blsCpi:food_truck` from Firestore and force-regenerate the food_truck W13 pulse. Verify `is_food_business("food_truck")` returns True (it should, given FOOD_TYPES set) and confirm `config_bls_series` override is being applied correctly through the full call chain.

**Fix 4 (P1 — YoY stale cache):** Audit `compute_price_deltas()` in `hephae_integrations.bls_client`. The 13-period lookback calculation for SAG1 and SASLE appears to be reading a comparison value from one month prior to the correct Feb 2025 baseline. Check whether the YoY window slides correctly when BLS data has irregular periods (some months have `-` values).

**Fix 5 (P2 — gym SERS):** Replace `"Recreational reading materials": "CUUR0000SERS"` in `GYM_FITNESS.bls_series` with a meaningful series. Best option: `CUUR0000SERC` (Recreation) or remove and use only SASLE + rent + energy.

**Fix 6 (P2 — bakery egg label):** Audit why `CUUR0000SEFH` is stored as a raw series ID key. The `track_labels` mapping `"eggs": "eggs_mom_pct"` is correct; the issue is in `compute_price_deltas()` where the BLS label for SEFH may not match "eggs" as a substring for the track_labels lookup.
