# Workflow Pipeline
> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

## 1. Phase Transitions (WorkflowPhase)

```
                          +--------+
                          | QUEUED |
                          +---+----+
                              |
                              v
                        +-----------+
                        | DISCOVERY |
                        +-----+-----+
                              |
                              v
                      +---------------+
                      | QUALIFICATION |
                      +-------+-------+
                              |
                              v
                        +----------+
                        | ANALYSIS |
                        +-----+----+
                              |
                              v
                       +------------+
                       | EVALUATION |
                       +------+-----+
                              |
                              v
                        +----------+
                        | APPROVAL |----> (pauses for human review)
                        +-----+----+
                              |
                              v
                        +----------+
                        | OUTREACH |
                        +-----+----+
                              |
                              v
                       +-----------+
                       | COMPLETED |
                       +-----------+

  Any phase may transition to:
                        +--------+
                        | FAILED |
                        +--------+
```

Source: `lib/common/hephae_common/models.py` — `WorkflowPhase(str, Enum)`

| Value | Description |
|-------|-------------|
| `queued` | Workflow created, waiting to start |
| `discovery` | Scanning zip codes for businesses |
| `qualification` | Scoring and classifying discovered businesses |
| `analysis` | Running capabilities (SEO, traffic, competitive, margin, social) |
| `evaluation` | Evaluator agents validate capability outputs |
| `approval` | Paused for human review — engine returns here |
| `outreach` | Generating and sending outreach for approved businesses |
| `completed` | All phases finished successfully |
| `failed` | Unrecoverable error — `lastError` field contains details |

---

## 2. Business Phase Transitions (BusinessPhase)

```
  PENDING --> ENRICHING --> ANALYZING --> ANALYSIS_DONE
                                              |
                                              v
                                         EVALUATING --> EVALUATION_DONE
                                                             |
                                              +--------------+--------------+
                                              v                             v
                                          APPROVED                      REJECTED
                                              |
                                              v
                                        OUTREACHING
                                           |     |
                                           v     v
                                  OUTREACH_DONE  OUTREACH_FAILED
```

Source: `lib/common/hephae_common/models.py` — `BusinessPhase(str, Enum)`

| Value | Description |
|-------|-------------|
| `pending` | Discovered, awaiting processing |
| `enriching` | Contact/metadata enrichment in progress |
| `analyzing` | Capability agents running |
| `analysis_done` | All capabilities completed (or business skipped) |
| `evaluating` | Evaluator agents scoring outputs |
| `evaluation_done` | Evaluation complete |
| `approved` | Human approved for outreach |
| `rejected` | Human rejected |
| `outreaching` | Outreach generation in progress |
| `outreach_done` | Outreach sent successfully |
| `outreach_failed` | Outreach delivery failed |

Non-qualified businesses (parked/disqualified) are set directly to `analysis_done` and skipped during analysis.

---

## 3. Phase Details

| Phase | What It Does | Source File | Timeout / Limits |
|-------|-------------|-------------|-----------------|
| **DISCOVERY** | Scans one or more zip codes to find local businesses via Google Places / Maps. Runs zipcode, area, and sector research in parallel. Resolves URLs for all discovered businesses. | `apps/api/hephae_api/workflows/phases/discovery.py` | None (research staleness: 7 days full, 24h volatile) |
| **QUALIFICATION** | Scores each business via metadata scan (Step A), optional full probe crawl (Step B), and batched LLM classification (Step C) for ambiguous cases. Classifies as QUALIFIED, PARKED, or DISQUALIFIED. | `apps/api/hephae_api/workflows/phases/qualification.py`, `agents/hephae_agents/qualification/scanner.py` | None |
| **ANALYSIS** | Enriches qualified businesses (contact, persona, menu, competitors), then runs all enabled capabilities concurrently. Follows up with batch insights and batch synthesis (traffic + competitive). | `apps/api/hephae_api/workflows/phases/analysis.py`, `apps/api/hephae_api/workflows/phases/enrichment.py` | 40 min polling safety valve (`MAX_POLL_DURATION_SECONDS = 2400`), 10 min stuck-task threshold (`STUCK_TASK_THRESHOLD_SECONDS = 600`), 3 retries per capability with backoff [10s, 30s, 60s] |
| **EVALUATION** | Runs evaluator agents for each capability output. Pass threshold: score >= 80 AND !isHallucinated. Uses batch evaluation with fallback to sequential. | `apps/api/hephae_api/workflows/phases/evaluation.py` | `BATCH_EVAL_FALLBACK_TIMEOUT` = 300s (5 min) |
| **APPROVAL** | Engine pauses and returns control. Human reviews evaluation results in admin UI. Resumes via `resume_from_outreach()`. | `apps/api/hephae_api/workflows/engine.py` (line 104) | None (indefinite human wait) |
| **OUTREACH** | Generates personalized outreach materials for approved businesses and sends them. Skipped if zero businesses are approved. | `apps/api/hephae_api/workflows/phases/outreach.py` | None |

---

## 4. Capability Registry

Source: `apps/api/hephae_api/workflows/capabilities/registry.py`

| Name | Display Name | Firestore Output Key | Should Run Condition | Runner | Evaluator Agent | Eval Compressor |
|------|-------------|---------------------|---------------------|--------|----------------|-----------------|
| `seo` | SEO Audit | `seo_auditor` | Business has `officialUrl` | `hephae_agents.seo_auditor.runner.run_seo_audit` | `SeoEvaluatorAgent` (`wf_seo_eval`) | Strips `rawPageSpeed`, `pagespeedData`, `lighthouseData`; truncates recommendations to 3 per section |
| `traffic` | Traffic Forecast | `traffic_forecaster` | Always (no condition) | `hephae_agents.traffic_forecaster.runner.run_traffic_forecast` | `TrafficEvaluatorAgent` (`wf_traffic_eval`) | None |
| `competitive` | Competitive Analysis | `competitive_analyzer` | Always (no condition) | `hephae_agents.competitive_analysis.runner.run_competitive_analysis` | `CompetitiveEvaluatorAgent` (`wf_comp_eval`) | Strips full competitor profiles; keeps only `name`, `threat_level`, `summary`, `score` |
| `margin_surgeon` | Margin Surgeon | `margin_surgeon` | Business has `menuScreenshotBase64` or `menuUrl` | `hephae_agents.margin_analyzer.runner.run_margin_analysis` (advanced_mode=True) | `MarginSurgeonEvaluatorAgent` (`wf_margin_eval`) | None |
| `social` | Social Media Insights | `social_media_auditor` | Always (no condition) | `hephae_agents.social.media_auditor.runner.run_social_media_audit` | None (no evaluator) | None |

---

## 5. Qualification Scoring

Source: `agents/hephae_agents/qualification/scanner.py` — `_score_business()`

### Base Signals

| Signal | Points | Condition |
|--------|--------|-----------|
| Custom domain | +15 | `domain_info.is_custom_domain` is true |
| Platform subdomain | +8 | `domain_type == "platform_subdomain"` (Shopify/Wix/etc) |
| HTTPS | +3 | `domain_info.is_https` is true |
| Platform detected | +10 | `platform_info.platform_detected` is true |
| Multiple analytics pixels | +10 | `pixel_count >= 2` |
| Single analytics pixel | +5 | `pixel_count == 1` |
| Contact path found | +8 | `contact_info.has_contact_path` is true |
| Mailto link | +5 | `contact_info.mailto_addresses` is non-empty |
| Tel link | +3 | `contact_info.tel_numbers` is non-empty |
| Strong social presence | +8 | 3 or more social links |
| Some social presence | +4 | 1-2 social links |
| JSON-LD structured data | +5 | `meta_info.has_structured_data` is true |
| Has page title | +2 | Title exists and length > 3 |

### Special Bonus Signals

| Signal | Points | Condition |
|--------|--------|-----------|
| **Innovation Gap** | +20 | Modern platform (toast, shopify, square_online, mindbody, clover, lightspeed, vagaro, boulevard) AND zero social links |
| **Aggregator Escape** | +20 | Dining category AND on delivery aggregator (doordash, grubhub, ubereats, seamless) AND weak/no own website |
| **Economic Delta** | +15 | High-income area (from research demographics) AND has custom domain AND no analytics |
| **Dining Pricing Env** | +5 | Dining category AND area research has `pricingEnvironment` data |
| **Services Gap** | +10 | Services category (salon, spa, repair, medical, dental, vet) AND has custom domain AND no contact/booking path |
| **Retail Gap** | +8 | Retail category (retail, shop, store, boutique) AND has custom domain AND no e-commerce platform detected |
| **Tech-Forward for Sector** | +5 | Sector research has `technologyAdoption` data AND platform detected |

### Full Probe (Step B) — Additional Signals

Source: `_run_full_probe_crawl_only()` in same file

| Signal | Points | Condition |
|--------|--------|-----------|
| Email found via crawl | +10 | `deterministicContact.email` found in full crawl |
| Phone found via crawl | +5 | `deterministicContact.phone` found in full crawl |
| Social links via crawl | +8 | 2+ social anchors found in full crawl |
| Delivery platforms | +5 | 1+ delivery platform links found |
| JSON-LD via crawl | +3 | `jsonLd.@type` present in crawl data |

### Rule-Based Auto-Qualification (bypasses threshold)

These rules qualify a business regardless of numeric score:

1. **Custom domain + analytics + contact path** — `is_custom_domain AND has_analytics AND has_contact_path`
2. **Platform site + contact path** — `platform_detected AND has_contact_path`

### Classification Boundaries

| Outcome | Condition |
|---------|-----------|
| DISQUALIFIED | Chain/franchise detected, OR URL is social/directory page, OR site returns 404/dead |
| PARKED (no URL) | No website URL available |
| PARKED (unreachable) | Site unreachable but may recover — flagged for full probe |
| QUALIFIED | Rule match OR score >= dynamic threshold |
| PARKED (close) | Score >= threshold - 15 — flagged `needs_full_probe` |
| PARKED (below) | Score < threshold - 15 |

---

## 6. Dynamic Threshold Formula

Source: `agents/hephae_agents/qualification/threshold.py`

**Base threshold:** 40

### Saturation Adjustments

| Condition | Threshold |
|-----------|-----------|
| `saturationLevel == "saturated"` OR `existingBusinessCount >= 40` | 60 |
| `saturationLevel == "high"` OR `existingBusinessCount >= 20` | 50 |
| `saturationLevel == "low"` OR `existingBusinessCount < 10` | 30 |
| `saturationLevel == "moderate"` (default) | 40 (base) |

### Opportunity Adjustment

| Condition | Adjustment |
|-----------|-----------|
| `marketOpportunity.score > 70` | -10 (lowers bar) |

### Clamp Range

```
threshold = max(20, min(70, threshold))
```

Final threshold is always in **[20, 70]**.

### Research Context Inputs

`extract_research_context()` builds the context dict from:

| Source | Extracted Key | Used For |
|--------|--------------|----------|
| Area research | `area_summary` (competitiveLandscape, marketOpportunity) | Saturation + opportunity adjustments |
| Zipcode research | `demographics` (from `report.sections.demographics`) | Economic Delta scoring signal |
| Sector research | `sector_summary` (industryAnalysis.technologyAdoption) | Tech-Forward scoring signal |

---

## 7. PROMOTE_KEYS

Source: `apps/api/hephae_api/workflows/phases/analysis.py`

Fields promoted from enrichment sub-agent output to the top-level Firestore business document:

| Key | Category |
|-----|----------|
| `phone` | Contact |
| `email` | Contact |
| `emailStatus` | Contact |
| `contactFormUrl` | Contact |
| `contactFormStatus` | Contact |
| `hours` | Operations |
| `googleMapsUrl` | Location |
| `socialLinks` | Social |
| `logoUrl` | Branding |
| `favicon` | Branding |
| `primaryColor` | Branding |
| `secondaryColor` | Branding |
| `persona` | Identity |
| `menuUrl` | Content |
| `competitors` | Market |
| `news` | Market |
| `validationReport` | QA |
