# Forge Requirements (hephae-forge)

This document specifies what hephae-admin expects from hephae-forge (the sibling project that provides the actual AI capabilities).

## API Endpoints

### Discovery / Enrichment

**`POST /api/v1/discover`**

Called during the enrichment step before running capabilities. Returns a full enriched business profile.

Request body:
```json
{
  "name": "Business Name",
  "address": "123 Main St, City ST 12345",
  "docId": "business-slug"
}
```

Expected response (`EnrichedProfile`):
```json
{
  "name": "Business Name",
  "address": "123 Main St, City ST 12345",
  "officialUrl": "https://example.com",
  "socialLinks": {
    "facebook": "https://facebook.com/example",
    "instagram": "https://instagram.com/example",
    "yelp": "https://yelp.com/biz/example"
  },
  "menuUrl": "https://example.com/menu",
  "menuScreenshotGcs": "gs://hephae-co-assets/menus/business-slug.png",
  "competitors": ["Competitor A", "Competitor B"],
  "colors": {
    "primary": "#FF5722",
    "secondary": "#2196F3"
  },
  "persona": "Family-friendly Italian restaurant with a focus on traditional recipes"
}
```

Requirements:
- Discovery must persist full enriched profiles (social links, menu URL/screenshot GCS link, competitors, colors, persona)
- Menu data (image/HTML/link) must be stored in GCS during discovery and available via the enriched profile
- The `menuScreenshotGcs` field should be a GCS URI pointing to a screenshot of the business menu page

### Capability Endpoints (V0 — `/api/capabilities/`)

**`POST /api/capabilities/seo`** — SEO Audit
**`POST /api/capabilities/traffic`** — Foot Traffic Forecast
**`POST /api/capabilities/competitive`** — Competitive Analysis

All accept:
```json
{
  "identity": { "name": "...", "address": "...", "docId": "..." }
}
```

### Capability Endpoints (V1 — `/api/v1/`)

**`POST /api/v1/analyze`** — Margin Surgeon Analysis

Accepts:
```json
{
  "identity": {
    "name": "Business Name",
    "address": "123 Main St",
    "docId": "business-slug",
    "menuUrl": "https://example.com/menu",
    "menuScreenshotGcs": "gs://...",
    "competitors": ["..."],
    "colors": { "primary": "#...", "secondary": "#..." },
    "persona": "..."
  }
}
```

Expected response:
```json
{
  "overall_score": 75,
  "menu_items": [
    {
      "name": "Margherita Pizza",
      "price": 14.99,
      "estimated_cost": 4.50,
      "margin_percent": 70,
      "category": "Pizza"
    }
  ],
  "strategic_advice": [
    "Consider raising prices on high-margin appetizers by 10-15%",
    "Bundle desserts with entrees to increase average ticket"
  ],
  "summary": "The restaurant has healthy margins on core items but is underpricing appetizers relative to market."
}
```

Requirements:
- All V1 endpoints must accept `EnrichedProfile` as identity (the full enriched profile from `/api/v1/discover`)
- The margin analysis should use menu data (screenshot/URL) to extract actual menu items and prices
- `strategic_advice` items should be specific and actionable, referencing actual menu items and prices

## Data Flow

```
hephae-admin                          hephae-forge
     |                                      |
     |  POST /api/v1/discover               |
     |  { name, address, docId }            |
     | -----------------------------------> |
     |  <- EnrichedProfile                  |
     |                                      |
     |  POST /api/capabilities/seo          |
     |  { identity: EnrichedProfile }       |
     | -----------------------------------> |
     |  <- SEO audit results                |
     |                                      |
     |  POST /api/capabilities/traffic      |
     |  { identity: EnrichedProfile }       |
     | -----------------------------------> |
     |  <- Traffic forecast results         |
     |                                      |
     |  POST /api/capabilities/competitive  |
     |  { identity: EnrichedProfile }       |
     | -----------------------------------> |
     |  <- Competitive analysis results     |
     |                                      |
     |  POST /api/v1/analyze                |
     |  { identity: EnrichedProfile }       |
     | -----------------------------------> |
     |  <- Margin analysis results          |
```

## Firestore Persistence

hephae-admin writes capability results to `businesses/{slug}.latestOutputs`:

| Capability | Firestore Key | Source Endpoint |
|---|---|---|
| SEO | `latestOutputs.seo_auditor` | `/api/capabilities/seo` |
| Traffic | `latestOutputs.traffic_forecaster` | `/api/capabilities/traffic` |
| Competitive | `latestOutputs.competitive_analyzer` | `/api/capabilities/competitive` |
| Margin Surgeon | `latestOutputs.margin_surgeon` | `/api/v1/analyze` |
| Insights | `insights` (top-level) | Generated locally by hephae-admin |

hephae-forge should NOT need to read from these keys — hephae-admin handles all persistence after receiving API responses.
