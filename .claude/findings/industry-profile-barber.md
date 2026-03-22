# Industry Profile: Barber Shops & Men's Grooming
Generated: 2026-03-22
Category: **beauty**
Registration Status: pending

## Research Summary

Barber shops are a $5.8B US industry growing 1.7% annually, with the global market projected at $26.7B by 2026. The business model is simple — haircuts ($30 avg), beard trims ($15-25), and product retail (25-30% of revenue potential). But margins have shrunk 12-15% over the past two years due to rising rent (+15%), supply costs (doubled in 2 years), and labor pressure (skilled barbers demanding higher commissions).

Labor is 40-60% of expenses — THE dominant cost. A $30 haircut nets only $12-15 in actual profit after supplies, utilities, insurance, and equipment depreciation. The key challenge for 2026: rising overhead while price-sensitive clients skip add-ons and stretch time between visits.

Unlike food verticals, there are NO FDA/USDA data sources. The primary automated signals are: BLS barber services CPI (what customers pay), rent CPI, energy CPI, QCEW employment trends, and Google News queries for supply costs and regulatory changes.

## BLS CPI Series (6 validated, 10 tested)

### Consumer Price Series (what the barber CHARGES)

| Series ID | Label | Value | MoM% | Status |
|-----------|-------|-------|------|--------|
| CUUR0000SS45011 | Barber & beauty shop services | 174.4 | +0.21% | PASS — **KEY SERIES** |

### Cost Context Series (what the barber PAYS)

| Series ID | Label | Value | MoM% | Status |
|-----------|-------|-------|------|--------|
| CUUR0000SEHA | Rent of primary residence | 442.2 | +0.10% | PASS — tracks rent pressure |
| CUUR0000SAH21 | Household energy | 288.2 | +0.24% | PASS — utilities cost |
| CUUR0000SASLE | Services less energy | 439.8 | +0.38% | PASS — broad services inflation |
| CUUR0000SAG1 | Other goods & services | 299.1 | +0.13% | PASS — includes personal care |
| CUUR0000SA0 | All items (CPI-U) | 326.8 | +0.47% | PASS — general inflation context |

### FAILED Series (dropped)

| Series ID | Label | Status |
|-----------|-------|--------|
| CUUR0000SEGL01 | Haircuts (men) | NO DATA |
| CUUR0000SEGL02 | Haircuts (women) | NO DATA |
| CUUR0000SEGP01 | Personal care products | NO DATA |
| CUUR0000SEGP02 | Cosmetics/bath | NO DATA |
| CUUR0000SEGL | Personal care services | NO DATA |
| CUUR0000SEGP | Personal care products | NO DATA |
| CUUR0000SS45 | Personal care (broad) | NO DATA |

## News Feeds (7/7 validated)

| Query | Articles | Sample Headlines |
|-------|----------|-----------------|
| barber shop business industry news | 67 | "Fire damages Davison barbershop" |
| haircut prices barber 2026 | 79 | "Why Smart Salons Are Adding Men's Hair Systems" |
| barber shop licensing regulations | 55 | "Texas rule requiring proof of legal status" |
| men grooming industry trends 2026 | 71 | "Men's Grooming Market Surges: Key Trends" |
| barber shop software booking platform | 34 | "Barber Booking Apps Market CAGR of 15.4%" |
| barber stylist wages labor cost | 74 | "California labor rule leaves nail workers uncertain" |
| barber shop opening new competition | 64 | "Barbershop sues former employees who opened competing shop" |

## Communities (verified)

| Community | Platform | Business-Focused? | Verified Via | Usable? |
|-----------|---------|-------------------|-------------|---------|
| r/Barbers | Reddit | Mix — technique + some business | WebSearch | LOW — not found in business-specific search |
| BarberEVO | barberevo.com | Mix — style trends + industry business | WebFetch (crawled) | No RSS, Cloudflare likely |
| DINGG blog | dingg.app/blogs | YES — operational profitability data | WebFetch (crawled, extracted numbers) | Google News covers |
| Barbershop Forums | barbershopforums.com | Grooming + shop culture | WebSearch | LOW — mostly consumer |
| NJ License Board | newjersey.mylicense.com | License verification | WebSearch verified | Competitor intel source |

## Cost Structure (sourced from DINGG article + industry data)

| Cost Driver | % of Revenue | BLS Series | Notes |
|-------------|-------------|------------|-------|
| Labor (barber wages/commissions) | 40-60% | None monthly (QCEW quarterly) | BIGGEST COST — gap in monthly tracking |
| Rent | 15-25% | SEHA (rent CPI) | Up 15% in 2 years per DINGG |
| Supplies (clippers, blades, sanitizers) | 5-10% | None (news coverage only) | Doubled in past 2 years |
| Utilities (electric, water, HVAC) | 3-5% | SAH21 (household energy) | |
| Product inventory (pomades, beard oil) | 5-8% | None | Retail products = 25-30% revenue potential |
| Insurance, licenses, misc | 3-5% | None | |
| **Net margin** | **10-20%** (pre-squeeze) | SS45011 vs costs | Shrunk 12-15% recently |

## Seasonal Calendar

| Month(s) | Demand | Key Events | Notes |
|----------|--------|------------|-------|
| Jan-Feb | LOW | New Year, post-holiday | Slowest period — clients stretch between visits |
| Mar | MEDIUM | Spring break | Uptick from winter slump |
| Apr-May | HIGH | Prom season, Easter | Formal event grooming spikes |
| Jun-Aug | HIGH | Wedding season, summer events | Consistent demand, add-ons (beard trims) |
| Sep | HIGH | Back to school | Family haircuts, fresh-start cuts |
| Oct | MEDIUM | Halloween | Steady but no event spike |
| Nov-Dec | HIGH | Thanksgiving, Christmas, NYE | Pre-holiday grooming rush |

## Self-Critique

| Finding | Issue | Resolution |
|---------|-------|-----------|
| Only 1 directly relevant CPI series (SS45011) | Food has 16 series, beauty has 1 | Supplement with rent, energy, services CPI as cost proxies |
| No product/supply cost CPI | Supplies doubled but no tracking | Gap: Google News "barber supplies costs" + "clipper prices" |
| No monthly labor cost data | Labor is 40-60% but only QCEW quarterly | Gap: fundamentally limits cost-pressure playbooks |
| No FDA/USDA equivalent | Expected for non-food vertical | Use licensing board data + news for regulatory signals |
| BarberEVO has no RSS, likely Cloudflare | Can't automate trade news directly | Google News queries validated as alternative |

## Playbooks (6 designed)

| Name | Trigger | Play | Fires Now? |
|------|---------|------|-----------|
| service_price_cover | barber_services_yoy_pct > 3 | Haircut CPI up {barber_services_yoy_pct}%. Competitors are raising prices — raise your base cut by $3-5 this month. | No (+0.21% MoM) |
| rent_squeeze_response | rent_yoy_pct > 5 | Rent CPI up {rent_yoy_pct}%. Add a $15 beard trim add-on to every haircut booking — that's $60+/day in new revenue on a 4-chair shop. | Monitoring |
| walk_in_weather_boost | weather_traffic_modifier > 0 | Clear weather + weekend. Put 'No Appointment Needed' on your sandwich board and Google profile. Staff an extra barber. | Seasonal |
| event_upsell | event_traffic_modifier > 0 | Local events this week — prom, wedding, formal. Promote 'Event Ready' packages: cut + beard trim + style for $45. Tag the event on social. | Seasonal |
| slow_season_fill | month in [1, 2] | January slowdown. Text your client list: '$5 off any service booked this week.' Fill empty chairs before rent is due. | N/A (wrong month) |
| new_competitor_alert | establishments_yoy_change_pct > 5 | New shops opening in your area ({establishments_yoy_change_pct}% growth). Differentiate: launch a loyalty card — 10th cut free. Post a 30-second video of your best fade on Instagram. | Check QCEW |

## Technology Platforms

| Platform | What It Does | Market Position |
|----------|-------------|----------------|
| Booksy | Barber-focused booking + consumer marketplace | Strong barber-specific market |
| Fresha | Free booking + POS, pay-per-new-client | World's largest beauty/wellness booking |
| Vagaro | Scheduling, POS, payroll, CRM | Major US player since 2009 |
| Square Appointments | POS + booking, free solo tier | Widespread, familiar |
| GlossGenius | Salon-focused booking + payments | Growing |

## Regulatory Sources

| Source | Data | API? | Verified? |
|--------|------|------|-----------|
| NJ Cosmetology Board | License verification (no separate barber license in NJ) | newjersey.mylicense.com (web lookup) | YES — WebSearch verified |
| State licensing boards (50 states) | New license filings = competitor early warning | No unified API; per-state scrapers needed | WebSearch — varies by state |
| OSHA salon safety | Chemical exposure, ventilation | No API | Reference only |
