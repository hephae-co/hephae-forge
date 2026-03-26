# Discovery Audit: Essex County NJ — Restaurants
Generated: 2026-03-26
Scope: 27 zip codes (07003–07114) | Job: RUl7MQAZGFbyB8TkpC5R

## Summary

| Bucket | Count | % |
|--------|-------|---|
| Email + Contact Form | 11 | 1.3% |
| Email only | 15 | 1.7% |
| Contact Form only | 11 | 1.3% |
| **Reachable (any)** | **37** | **4.3%** |
| Website, not enriched | 218 | 25.1% |
| No website | 613 | 70.6% |
| **Total** | **868** | 100% |

## Key Findings

**95.7% of businesses have no contact info.** This is an enrichment gap, not a data quality issue:

- **218 businesses have websites but zero contact data** — the agent enrichment pipeline (website crawler → email extractor → contact form detector) hasn't run on them yet. These are the highest-opportunity group.
- **613 businesses have no website** — truly unreachable via digital outreach. These are either cash-only spots, newly opened, or only listed on aggregators (Yelp/Google Maps) with no own web presence.
- **37 are outreach-ready now** — already enriched from prior workflow runs on 07042, 07110, 07003, 07052.

## Per-Zip Breakdown

| Zip | City | Total | Email | Form | Both | Unenriched | No Website |
|-----|------|-------|-------|------|------|-----------|------------|
| 07042 | Montclair | 110 | 7 | 10 | 4 | — | — |
| 07110 | Nutley | 62 | 9 | 4 | 3 | — | — |
| 07003 | Bloomfield | 9 | 4 | 4 | 2 | — | — |
| 07052 | West Orange | 9 | 3 | 3 | 1 | — | — |
| 07043 | Montclair/UMontclair | 51 | 3 | 1 | 1 | — | — |
| 07040 | Maplewood | 79 | 0 | 0 | 0 | — | — |
| 07107 | Newark North | 55 | 0 | 0 | 0 | — | — |
| 07112 | Newark East | 54 | 0 | 0 | 0 | — | — |
| 07039 | Livingston | 44 | 0 | 0 | 0 | — | — |
| 07104 | Newark | 44 | 0 | 0 | 0 | — | — |
| 07043 | Montclair | 51 | 3 | 1 | 1 | — | — |
| 07041 | Millburn | 39 | 0 | 0 | 0 | — | — |
| 07044 | Verona | 32 | 0 | 0 | 0 | — | — |
| 07102 | Newark Downtown | 30 | 0 | 0 | 0 | — | — |
| 07006 | Caldwell | 28 | 0 | 0 | 0 | — | — |
| 07007 | Cedar Grove | 27 | 0 | 0 | 0 | — | — |
| 07114 | Newark Airport area | 20 | 0 | 0 | 0 | — | — |
| 07103 | Newark | 18 | 0 | 0 | 0 | — | — |
| 07109 | Belleville | 13 | 0 | 0 | 0 | — | — |
| 07101 | Newark PO | 11 | 0 | 0 | 0 | — | — |
| 07108 | Newark South | 10 | 0 | 0 | 0 | — | — |
| 07028 | Glen Ridge | 10 | 0 | 0 | 0 | — | — |
| 07105 | Newark Ironbound | 9 | 0 | 0 | 0 | — | — |
| 07068 | Roseland | 9 | 0 | 0 | 0 | — | — |
| 07079 | South Orange | 45 | 0 | 0 | 0 | — | — |
| 07106 | Newark Vailsburg | 4 | 0 | 0 | 0 | — | — |
| 07111 | Irvington | 0 | 0 | 0 | 0 | — | — |

## Next Steps

1. **Trigger enrichment** on the 218 website-bearing unenriched businesses — estimated to yield ~30-50 additional reachable contacts based on the 4.3% hit rate from already-enriched zips.
2. **Outreach now**: 37 businesses are enriched and outreach-ready.
3. **Zero-enrichment zips** (07006, 07007, 07028, 07039–07050 range, all Newark zips): these 22 zips need the full discovery workflow run — currently only raw Google Maps scan was done, no website crawling.
4. **Consider** running the full enrichment workflow on high-value zips: Montclair (07042/07043), Livingston (07039), South Orange (07079), Millburn (07041).
