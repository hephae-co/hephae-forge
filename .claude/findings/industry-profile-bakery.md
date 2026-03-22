# Industry Profile: Bakeries & Patisseries
Generated: 2026-03-22
Category: **food**
Registration Status: pending (awaiting user review)

## Research Summary

Bakeries operate on tight margins (4-15% net) with ingredients consuming 20-35% of revenue. The five most volatile inputs are flour, eggs, butter, sugar, and milk — all tracked by BLS CPI with monthly updates. Butter is currently the most volatile (+3.56% MoM in Jan 2026), while flour and eggs are declining (-0.91% and -0.96% respectively). This creates a clear ingredient-swap opportunity right now.

The bakery industry spans cottage/home bakeries (20-40% margins, no rent) to commercial retail (4-9% margins). Peak demand runs Nov-Dec (holiday baking) and Feb-Jun (wedding season). January is the dead month. The US specialty bakery market is growing at 4.65% CAGR to $9.02B by 2032.

Key owner challenges: ingredient price volatility, 8-15% spoilage/waste rates, labor efficiency, and seasonal demand swings. Allergen compliance (9 major allergens per FDA FALCPA + FASTER Act) is a constant regulatory pressure — 319 wheat-related FDA recalls were found.

## BLS CPI Series (16/16 validated via API — Feb 2026 data)

### Input Cost Series (what the bakery BUYS)

| Series ID | Label | Value | MoM% | Status |
|-----------|-------|-------|------|--------|
| CUUR0000SEFA01 | Flour & flour mixes | 326.8 | -0.91% | PASS |
| CUUR0000SEFH | Eggs | 288.7 | -0.96% | PASS |
| CUUR0000SAF114 | Dairy & related | 238.1 | +0.98% | PASS |
| CUUR0000SS5702 | Butter | 435.2 | +3.56% | PASS (Jan, 1mo lag) |
| CUUR0000SEFR01 | Sugar & substitutes | 276.9 | -0.99% | PASS |
| CUUR0000SEFJ | Milk | 269.6 | -0.58% | PASS |
| CUUR0000SEFL | Ice cream | 395.6 | +2.78% | PASS |
| CUUR0000SEFA | Cereals | 290.8 | -0.33% | PASS |

### Consumer Price Series (what the bakery CHARGES)

| Series ID | Label | Value | MoM% | Status |
|-----------|-------|-------|------|--------|
| CUUR0000SEFB | Bakery products | 411.9 | +0.28% | PASS |
| CUUR0000SEFB01 | Bread | 247.0 | +0.54% | PASS |
| CUUR0000SEFB02 | Cakes, cupcakes, cookies | 243.3 | -0.23% | PASS |

### Context Series

| Series ID | Label | Value | MoM% | Status |
|-----------|-------|-------|------|--------|
| CUUR0000SAF111 | Cereals & bakery products | 367.2 | +0.09% | PASS |
| CUUR0000SEFS | Sugar & sweets (broad) | 314.0 | -1.04% | PASS |
| CUUR0000SAF1 | Food (all items) | 346.6 | +0.41% | PASS |
| CUUR0000SAF11 | Food at home | 318.9 | +0.46% | PASS |
| CUUR0000SEFG | Eggs (detailed) | 370.3 | +0.17% | PASS |

## USDA Commodities

| Commodity | Bakery Relevance | Available in NASS? |
|-----------|-----------------|-------------------|
| WHEAT | Flour — largest volume input | Yes |
| EGGS | Used in most recipes, highly volatile | Yes |
| MILK | Butter, cream, custards | Yes |
| SUGAR | Sweetener in everything | Limited (sugarcane/beet) |

## News Feeds (8/8 validated Google News RSS)

| Query | Articles | Sample Headlines |
|-------|----------|-----------------|
| bakery industry ingredient costs | 73 | "Global conditions affect ingredient prices" |
| flour wheat prices 2026 | 73 | "Wheat flour prices declined in Feb 2026" |
| egg prices shortage bakery | 75 | "Restaurants and Bakeries Rethinking Eggs" |
| butter dairy prices costs | 100 | "Dairy Market: Consumer Demand for Protein" |
| FDA recall bakery allergen | 80 | "Cake mix recall upgraded to highest FDA risk" |
| wedding cake trends 2026 | 74 | "7 Wedding Cake Trends for 2026" |
| sourdough artisan bread trend | 54 | "Gut-Friendly Bread Bites; artisan bread trend" |
| bakery business profit margin | 63 | "Grand Rapids businesses ask for support" |

## Communities (verified)

| Community | Platform | Business-Focused? | Verified Via | Usable? |
|-----------|---------|-------------------|-------------|---------|
| r/Baking (4.3M) | Reddit | Mostly consumer; some business threads | WebSearch | LOW — search for "pricing" threads |
| r/AskBaking | Reddit | Mix technique + business | WebSearch | LOW |
| Cottage Food Business | Facebook Group | YES — pricing, licensing, scaling | WebSearch | Manual only |
| Bakers4Bakers | bakers4bakers.org | YES — staffing, inventory, finance, marketing | WebFetch (crawled homepage) | Manual only (membership) |
| Better Baker Club | Website | YES — pricing, business operations | WebSearch | Manual only |
| Bake Magazine | bakemag.com | YES — trade publication, business ops | WebFetch (crawled homepage) | Cloudflare blocked RSS, use Google News |

## Cost Structure (sourced)

| Cost Driver | % of Revenue | BLS Series |
|-------------|-------------|------------|
| Ingredients (flour, eggs, butter, sugar, milk) | 20-35% | SEFA01, SEFH, SAF114, SS5702, SEFR01, SEFJ |
| Labor (bakers, counter staff) | 25-35% | Not tracked monthly by CPI |
| Rent + utilities | 8-15% | Not tracked in scope |
| Waste/spoilage | 5-18% of ingredients | N/A (operational) |
| Packaging | 2-4% | Not tracked |
| **Net margin** | **4-15%** (specialty up to 25%) | Input vs consumer CPI spread |

## Seasonal Calendar

| Month(s) | Demand | Key Events | Playbook Triggers |
|----------|--------|------------|------------------|
| Jan | LOW | New Year's resolutions | Dead month — promote sourdough/health items |
| Feb | MEDIUM | Valentine's Day | Custom cakes, chocolate items |
| Mar-Apr | RISING | Easter, spring weddings begin | Easter bread, hot cross buns, custom cakes |
| May | HIGH | Mother's Day, graduations | Cake orders peak |
| Jun-Sep | HIGH | Wedding season | Custom cakes (40-60% margin) — busiest |
| Oct | MEDIUM | Halloween | Themed cookies, pumpkin items |
| Nov-Dec | VERY HIGH | Thanksgiving + Christmas | Pre-order critical, holiday cookies/pies |
| Late summer | LOW | Back to school | Gap between wedding + holiday seasons |

## Self-Critique

| Finding | Issue | Resolution |
|---------|-------|-----------|
| No cocoa/chocolate BLS series | Patisseries depend on chocolate costs | Gap: Google News "cocoa prices" query covers indirectly |
| No monthly labor cost data | Labor is 25-35% of revenue | Gap: Annual BLS OES data only; QCEW covers employment trends |
| Facebook groups can't be automated | Best business communities are on FB | Use Google Search for sentiment; note as manual resource |
| Butter CPI 1-month lag | SS5702 lags other food CPI by 1 month | Acceptable — noted in config comments |
| Reddit signal is LOW for bakery | No dedicated business owner sub | Include r/Baking with search terms but rate as low signal |

## Playbooks (6 designed)

| Name | Trigger | Play | Fires Now? |
|------|---------|------|-----------|
| flour_cost_alert | flour_yoy_pct > 3 | Raise bread prices by $0.50, promote flourless items | No (flour -0.91% MoM) |
| egg_spike_response | eggs_yoy_pct > 8 | Switch to pastry cream, push vegan options | No (eggs -0.96% MoM) |
| butter_margin_squeeze | butter_yoy_pct > 4 | Oil-based doughs for daily, butter for premium only | CLOSE (butter +3.56% MoM) |
| wedding_season_lock | month in [2,3,4] and sugar_yoy_pct > 2 | Lock custom cake pricing, stop honoring old quotes | No (sugar -0.99%) |
| holiday_pre_order_push | month in [10,11] and flour_yoy_pct > 0 | Open pre-orders with 10% deposit this week | N/A (wrong month) |
| fda_allergen_alert | fda_recent_recall_count > 10 | Audit allergen labels, print updated cards for display | YES (319 recalls active) |

## Technology Platforms

| Platform | What It Does | Market Position |
|----------|-------------|----------------|
| Toast POS | POS + kitchen display, bakery cafe focused | Market leader for food businesses |
| KORONA POS | Inventory + production tracking for retail bakeries | Strong for retail bakeries |
| BakeSmart | Recipe costing, production scheduling, bakery-specific | Specialist — highest relevance |
| Square | General POS, free tier | Common for small/cottage bakeries |
| Craftybase | Small-batch cost tracking for home bakers | Niche — cottage bakery |

## Regulatory Sources

| Source | Data Available | API? | Verified? |
|--------|---------------|------|-----------|
| FDA FALCPA + FASTER Act | 9 major allergens must be labeled | FDA Enforcement API (free) | YES — 319 wheat recalls confirmed |
| State cottage food laws | Sales limits, labeling requirements per state | No API (reference only) | WebSearch verified |
| Local health departments | Inspection scores, violations | Socrata in major metros | Not validated per-city |
