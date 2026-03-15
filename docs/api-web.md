# Hephae Forge — API Reference

> Single source of truth for all API capabilities and endpoints.
> Update this file in the same commit when changing any endpoint or capability.

## Base URL

```
Local:      http://localhost:8000 (unified API)
Production: https://hephae-forge-api-hlifczmzgq-ue.a.run.app
```

Both web and admin UIs proxy `/api/*` to this src.

---

# Part 1: Business Capabilities

These are the AI-powered analyses Hephae runs for any business. Each capability takes a business identity as input and returns a structured report.

## Discovery

**What it does:** Crawls a business's website and the open web to build a complete digital profile — contact info, social links, menu, competitors, news mentions, brand identity, and social media metrics.

**Pipeline:** 5 stages (site crawl → entity match → fan-out research → social profiling → validation review)

**Output:** Enriched business profile with verified URLs, social metrics, competitor list, and news coverage.

## Margin Surgery

**What it does:** Analyzes a restaurant's menu pricing against commodity costs, local market rates, and margin benchmarks. Identifies items where the business is losing money ("profit leakage").

**Output:** Per-item leakage amounts, overall margin score (0-100), strategic pricing advice.

## SEO Audit

**What it does:** Evaluates a business's website against search engine optimization best practices — indexing, web vitals, content hierarchy, meta tags, mobile readiness, and local SEO signals.

**Output:** Overall score (0-100), section-by-section breakdown with specific recommendations.

## Foot Traffic Forecast

**What it does:** Predicts 3-day foot traffic patterns using local events, weather, day-of-week trends, and area demographics. Identifies peak hours and slow periods.

**Output:** Daily forecasts with hourly time slots, traffic scores, and staffing recommendations.

## Competitive Analysis

**What it does:** Identifies the 3 closest competitors and compares them across pricing, digital presence, reviews, and market positioning. Assesses threat levels and strategic gaps.

**Output:** Competitor profiles, threat scores, market summary, and actionable recommendations.

## Social Media Audit

**What it does:** Evaluates a business's presence across Instagram, Facebook, Twitter, TikTok, and Yelp. Analyzes posting frequency, engagement, follower growth, and content strategy.

**Output:** Per-platform analysis, overall social score (0-100), content strategy recommendations.

## Content Generation (Outreach)

**What it does:** Generates ready-to-publish outreach content across 5 channels — Instagram caption, Facebook post, Twitter/X post, email (subject + body), and contact form message. Each is tailored to the business's profile and analysis results.

**Output:** Platform-specific content with character limits, CTAs, and personalized insights.

---

# Part 2: Technical API Reference

## Authentication

| Context | Mechanism | Header |
|---------|-----------|--------|
| Web UI → API | HMAC-SHA256 signing | `x-forge-timestamp` + `x-forge-signature` |
| User auth (optional) | Firebase ID token | `X-Firebase-Token` |
| Admin UI → API | Firebase ID token (required) | `X-Firebase-Token` |
| V1 headless | API key | `x-api-key` |
| Cloud Run service-to-service | GCP identity token | `Authorization: Bearer ...` |

Admin routes require the user's email to be in the `ADMIN_EMAIL_ALLOWLIST`.

---

## Discovery & Enrichment Endpoints

### `POST /api/discover`
Full 5-stage discovery pipeline. Returns enriched business profile.
Auth: HMAC + optional Firebase token (links business to user if authenticated).

```json
// Request
{ "identity": { "name": "...", "address": "...", "officialUrl": "..." } }

// Response: EnrichedProfile
{
  "name": "Bosphorus Turkish Cuisine",
  "address": "123 Franklin Ave, Nutley, NJ 07110",
  "officialUrl": "https://bosphorusnutley.com",
  "phone": "...", "email": "...",
  "socialLinks": { "instagram": "...", "facebook": "...", ... },
  "competitors": [{ "name": "...", "url": "...", "reason": "..." }],
  "socialProfileMetrics": { ... },
  "reportUrl": "https://cdn.hephae.co/reports/..."
}
```

### `POST /api/v1/discover`
Legacy v1 wrapper. Auth: API key.
```json
{ "query": "Bosphorus Nutley NJ" }
```

---

## Capability Endpoints

All accept `{ "identity": EnrichedProfile }` and return capability-specific reports.
Auth: HMAC signing.

### `POST /api/capabilities/seo`
Returns `SeoReport`: `{ overallScore, summary, sections[], reportUrl }`

### `POST /api/capabilities/traffic`
Returns `ForecastResponse`: `{ summary, forecast[], reportUrl }`

### `POST /api/capabilities/competitive`
Returns `CompetitiveReport`: `{ market_summary, competitors[], recommendations[], reportUrl }`

### `POST /api/capabilities/marketing`
Returns `SocialAuditReport`: `{ overall_score, summary, platforms[], reportUrl }`

### `POST /api/analyze` (Margin Surgery)
Accepts: `{ "url": "...", "enrichedProfile": EnrichedProfile, "advancedMode": false }`
Returns `SurgicalReport`: `{ menu_items[], strategic_advice[], overall_score, reportUrl }`

---

## Chat Endpoint

### `POST /api/chat`
Conversational AI with Firestore session persistence. Uses real Firebase UID when authenticated, falls back to "anonymous".

```json
// Request
{
  "messages": [{ "role": "user", "text": "..." }],
  "sessionId": "...",
  "businessLocated": false,
  "context": { "businessName": "...", "seoReport": { ... } }
}

// Response
{
  "role": "model",
  "text": "...",
  "sessionId": "...",
  "triggerCapabilityHandoff": true,
  "locatedBusiness": { ... }
}
```

---

## Auth Endpoint

### `POST /api/auth/me`
Creates or returns user doc on first Google sign-in. Auth: Firebase token (required).

```json
// Response
{
  "uid": "firebase-uid",
  "email": "user@example.com",
  "displayName": "...",
  "photoURL": "...",
  "businesses": ["bosphorus-turkish-cuisine"]
}
```

---

## Utility Endpoints

### `POST /api/track`
Lead capture — logs search queries and email submissions.

### `POST /api/send-report-email`
Sends report URL to user via Resend email API.

### `GET /api/places/autocomplete?input=...`
Google Places autocomplete proxy.

### `GET /api/places/details?place_id=...`
Google Places details proxy (returns BaseIdentity).

### `POST /api/social-card`
Generates social share card image for a report.

### `POST /api/social-posts/generate`
Generates social media posts for a business report.

### `GET /api/health`
Health check: `{ "status": "ok" }`

---

## Capability Registry

Source of truth: `apps/api/backend/workflows/capabilities/registry.py`

| Capability | Runner | Firestore Key | Evaluator |
|------------|--------|---------------|-----------|
| SEO Audit | `hephae_agents.seo_auditor.runner` | `seo_auditor` | Yes |
| Traffic Forecast | `hephae_agents.traffic_forecaster.runner` | `traffic_forecaster` | Yes |
| Competitive Analysis | `hephae_agents.competitive_analysis.runner` | `competitive_analyzer` | Yes |
| Margin Surgery | `hephae_agents.margin_analyzer.runner` | `margin_surgeon` | Yes |
| Social Media Audit | `hephae_agents.social.media_auditor.runner` | `social_media_auditor` | No |
