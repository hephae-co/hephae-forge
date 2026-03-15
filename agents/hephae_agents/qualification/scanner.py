"""Qualification scanner — orchestrates tools to score and classify businesses.

Two-step process:
  Step A: Metadata Scan — lightweight HTTP fetch + composable analyzers
  Step B: Full Probe — existing crawl + LLM classifier, ONLY if Step A is ambiguous

Classification:
  QUALIFIED → Deep Discovery (Tier 3)
  PARKED → stored for future batch (no website or below threshold)
  DISQUALIFIED → chain/closed/not-a-business
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from hephae_agents.qualification.chains import is_chain
from hephae_agents.qualification.tools import (
    page_fetcher,
    domain_analyzer,
    platform_detector,
    pixel_detector,
    contact_path_detector,
    meta_extractor,
)
from hephae_agents.qualification.threshold import compute_dynamic_threshold

logger = logging.getLogger(__name__)

QUALIFIED = "QUALIFIED"
PARKED = "PARKED"
DISQUALIFIED = "DISQUALIFIED"


class QualificationResult:
    """Result of qualifying a single business."""

    __slots__ = ("outcome", "score", "threshold", "reasons", "probe_data", "needs_full_probe")

    def __init__(
        self,
        outcome: str,
        score: int = 0,
        threshold: int = 40,
        reasons: list[str] | None = None,
        probe_data: dict[str, Any] | None = None,
        needs_full_probe: bool = False,
    ):
        self.outcome = outcome
        self.score = score
        self.threshold = threshold
        self.reasons = reasons or []
        self.probe_data = probe_data or {}
        self.needs_full_probe = needs_full_probe

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "score": self.score,
            "threshold": self.threshold,
            "reasons": self.reasons,
            "probeData": self.probe_data,
            "needsFullProbe": self.needs_full_probe,
        }


def _score_business(
    name: str,
    category: str,
    url: str,
    domain_info: dict[str, Any],
    platform_info: dict[str, Any],
    pixel_info: dict[str, Any],
    contact_info: dict[str, Any],
    meta_info: dict[str, Any],
    fetch_result: dict[str, Any],
    research_context: dict[str, Any] | None = None,
) -> tuple[int, list[str]]:
    """Compute a qualification score from all tool outputs. Returns (score, reasons)."""
    score = 0
    reasons: list[str] = []

    if domain_info.get("is_custom_domain"):
        score += 15
        reasons.append("+15: custom domain")
    elif domain_info.get("domain_type") == "platform_subdomain":
        score += 8
        reasons.append("+8: platform subdomain (Shopify/Wix/etc)")

    if domain_info.get("is_https"):
        score += 3
        reasons.append("+3: HTTPS")

    if platform_info.get("platform_detected"):
        platform = platform_info.get("platform")
        score += 10
        reasons.append(f"+10: platform detected ({platform})")

    pixel_count = pixel_info.get("pixel_count", 0)
    if pixel_count >= 2:
        score += 10
        reasons.append(f"+10: multiple analytics pixels ({pixel_count})")
    elif pixel_count == 1:
        score += 5
        reasons.append("+5: analytics pixel detected")

    if contact_info.get("has_contact_path"):
        score += 8
        reasons.append("+8: contact path found")
    if contact_info.get("mailto_addresses"):
        score += 5
        reasons.append("+5: mailto link found")
    if contact_info.get("tel_numbers"):
        score += 3
        reasons.append("+3: tel link found")

    social_count = len(contact_info.get("social_links", []))
    if social_count >= 3:
        score += 8
        reasons.append(f"+8: strong social presence ({social_count} links)")
    elif social_count >= 1:
        score += 4
        reasons.append(f"+4: some social presence ({social_count} links)")

    if meta_info.get("has_structured_data"):
        score += 5
        reasons.append("+5: JSON-LD structured data")

    title = meta_info.get("title", "")
    if title and len(title) > 3:
        score += 2
        reasons.append("+2: has page title")

    # Innovation Gap Pattern
    has_modern_platform = platform_info.get("platform") in (
        "toast", "shopify", "square_online", "mindbody", "clover",
        "lightspeed", "vagaro", "boulevard",
    )
    has_no_social = social_count == 0
    if has_modern_platform and has_no_social:
        score += 20
        reasons.append("+20: Innovation Gap — modern platform but no social presence")

    # Aggregator Escape Score
    cat_lower = (category or "").lower()
    is_dining = any(k in cat_lower for k in ("restaurant", "food", "dining", "cafe", "bakery", "pizza", "deli"))
    if is_dining:
        social_links_str = " ".join(contact_info.get("social_links", []))
        on_aggregator = any(
            agg in social_links_str.lower()
            for agg in ("doordash", "grubhub", "ubereats", "seamless")
        )
        has_weak_website = (
            not domain_info.get("is_custom_domain")
            or fetch_result.get("status_code", 0) >= 400
        )
        if on_aggregator and has_weak_website:
            score += 20
            reasons.append("+20: Aggregator Escape — on delivery platforms but weak/no own website")

    # Economic Delta Score
    if research_context:
        demographics = research_context.get("demographics")
        if isinstance(demographics, dict):
            key_facts = demographics.get("key_facts", [])
            content = demographics.get("content", "")
            income_text = " ".join(key_facts) + " " + content

            is_high_income = any(
                term in income_text.lower()
                for term in ("high income", "wealthy", "affluent", "above average income", "median income")
            )

            if is_high_income and domain_info.get("is_custom_domain") and not pixel_info.get("has_analytics"):
                score += 15
                reasons.append("+15: Economic Delta — wealthy area + poor digital presence")

    # Vertical-Specific Signals
    if is_dining:
        if research_context and research_context.get("area_summary"):
            pricing = research_context["area_summary"].get("pricingEnvironment")
            if pricing and isinstance(pricing, dict):
                score += 5
                reasons.append("+5: dining in tracked pricing environment")

    if any(k in cat_lower for k in ("service", "salon", "spa", "repair", "medical", "dental", "vet")):
        if domain_info.get("is_custom_domain") and not contact_info.get("has_contact_path"):
            score += 10
            reasons.append("+10: Services — has website but no contact/booking path")

    if any(k in cat_lower for k in ("retail", "shop", "store", "boutique")):
        if domain_info.get("is_custom_domain") and not platform_info.get("platform_detected"):
            score += 8
            reasons.append("+8: Retail — custom domain but no e-commerce platform")

    # Sector-Specific Tech Signals
    if research_context:
        sector = research_context.get("sector_summary")
        if sector and isinstance(sector, dict):
            industry = sector.get("industryAnalysis") or {}
            tech_adoption = industry.get("technologyAdoption", [])
            if tech_adoption and platform_info.get("platform_detected"):
                score += 5
                reasons.append("+5: tech-forward for sector")

    return score, reasons


async def qualify_business(
    name: str,
    url: str,
    category: str = "",
    research_context: dict[str, Any] | None = None,
    threshold: int | None = None,
) -> QualificationResult:
    """Qualify a single business through Step A (metadata scan)."""
    if is_chain(name):
        return QualificationResult(outcome=DISQUALIFIED, reasons=["Chain/franchise detected"])

    if not url:
        return QualificationResult(outcome=PARKED, reasons=["No website URL"])

    domain_info = domain_analyzer(url)

    if domain_info["domain_type"] in ("social", "directory"):
        return QualificationResult(
            outcome=DISQUALIFIED,
            reasons=[f"URL is a {domain_info['domain_type']} page, not business's own domain"],
            probe_data={"domain": domain_info},
        )

    fetch_result = await page_fetcher(url)
    html = fetch_result.get("html", "")
    status = fetch_result.get("status_code", 0)

    if status == 404 or (status >= 400 and not html):
        return QualificationResult(
            outcome=DISQUALIFIED,
            reasons=[f"Site returns {status}/dead"],
            probe_data={"domain": domain_info, "fetch_status": status},
        )

    if fetch_result.get("error") and not html:
        return QualificationResult(
            outcome=PARKED, score=0,
            reasons=[f"Site unreachable: {fetch_result['error']}"],
            probe_data={"domain": domain_info, "fetch_error": fetch_result["error"]},
            needs_full_probe=True,
        )

    platform_info = platform_detector(html)
    pixel_info = pixel_detector(html)
    contact_info = contact_path_detector(html, fetch_result.get("final_url", url))
    meta_info = meta_extractor(html)

    dyn_threshold = threshold if threshold is not None else compute_dynamic_threshold(research_context)
    score, reasons = _score_business(
        name=name, category=category, url=url,
        domain_info=domain_info, platform_info=platform_info,
        pixel_info=pixel_info, contact_info=contact_info,
        meta_info=meta_info, fetch_result=fetch_result,
        research_context=research_context,
    )

    probe_data: dict[str, Any] = {
        "domain": domain_info, "platform": platform_info,
        "pixels": pixel_info, "contact": contact_info,
        "meta": meta_info, "fetch_status": status,
    }

    # Rule-based classification (~80%)
    if domain_info["is_custom_domain"] and pixel_info["has_analytics"] and contact_info["has_contact_path"]:
        return QualificationResult(
            outcome=QUALIFIED, score=score, threshold=dyn_threshold,
            reasons=reasons + ["Rule: custom domain + analytics + contact path"],
            probe_data=probe_data,
        )

    if platform_info["platform_detected"] and contact_info["has_contact_path"]:
        return QualificationResult(
            outcome=QUALIFIED, score=score, threshold=dyn_threshold,
            reasons=reasons + ["Rule: platform site + contact path"],
            probe_data=probe_data,
        )

    if score >= dyn_threshold:
        return QualificationResult(
            outcome=QUALIFIED, score=score, threshold=dyn_threshold,
            reasons=reasons, probe_data=probe_data,
        )

    if score >= dyn_threshold - 15:
        return QualificationResult(
            outcome=PARKED, score=score, threshold=dyn_threshold,
            reasons=reasons + [f"Score {score} close to threshold {dyn_threshold} — needs full probe"],
            probe_data=probe_data, needs_full_probe=True,
        )

    return QualificationResult(
        outcome=PARKED, score=score, threshold=dyn_threshold,
        reasons=reasons + [f"Score {score} below threshold {dyn_threshold}"],
        probe_data=probe_data,
    )


async def _run_llm_classifier(
    name: str, category: str, probe_data: dict[str, Any],
    research_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM classifier for ambiguous cases (~20%). Uses cheapest Gemini tier."""
    try:
        import json as _json
        import os
        from google import genai
        from hephae_common.model_config import AgentModels

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"is_hvt": False, "reason": "No API key"}

        domain = probe_data.get("domain", {})
        platform = probe_data.get("platform", {})
        meta = probe_data.get("meta", {})
        contact = probe_data.get("contact", {})

        market_signals = ""
        if research_context:
            area = research_context.get("area_summary", {})
            competitive = area.get("competitiveLandscape", {}) if isinstance(area, dict) else {}
            market_signals = (
                f"Market saturation: {competitive.get('saturationLevel', 'unknown')}, "
                f"Business count: {competitive.get('existingBusinessCount', 'unknown')}"
            )

        prompt = (
            f"You are a business qualification classifier. Determine if this business is a "
            f"High-Value Target (HVT) for AI-driven marketing and outreach services.\n\n"
            f"Business: {name}\nCategory: {category}\n"
            f"Domain type: {domain.get('domain_type', 'unknown')}\n"
            f"Platform: {platform.get('platform', 'none')}\n"
            f"Analytics: {probe_data.get('pixels', {}).get('pixels_found', [])}\n"
            f"Has contact path: {contact.get('has_contact_path', False)}\n"
            f"Social links: {len(contact.get('social_links', []))}\n"
            f"Page title: {meta.get('title', '')}\n"
            f"Structured data types: {meta.get('jsonld_types', [])}\n"
            f"{f'Market context: {market_signals}' if market_signals else ''}\n\n"
            f"An HVT is a local business that would benefit from AI outreach — "
            f"they have some digital presence but gaps we can fill.\n\n"
            f'Return ONLY valid JSON: {{"is_hvt": true/false, "reason": "one sentence explanation"}}'
        )

        client = genai.Client(api_key=api_key)
        res = await client.aio.models.generate_content(
            model=AgentModels.PRIMARY_MODEL, contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return _json.loads(res.text)

    except Exception as e:
        logger.warning(f"[QualScanner] LLM classifier failed for {name}: {e}")
        return {"is_hvt": False, "reason": f"LLM error: {e}"}


async def _run_full_probe(
    name: str, url: str, category: str,
    partial_result: QualificationResult,
    research_context: dict[str, Any] | None = None,
) -> QualificationResult:
    """Step B: Full browser crawl + LLM classifier for ambiguous cases."""
    try:
        from hephae_agents.shared_tools.playwright import crawl_web_page

        crawl_data = await crawl_web_page(url)

        extra_score = 0
        extra_reasons: list[str] = []

        det_contact = crawl_data.get("deterministicContact", {})
        if det_contact.get("email"):
            extra_score += 10
            extra_reasons.append("+10: email found via full crawl")
            partial_result.probe_data["email"] = det_contact["email"]
        if det_contact.get("phone"):
            extra_score += 5
            extra_reasons.append("+5: phone found via full crawl")
            partial_result.probe_data["phone"] = det_contact["phone"]

        social_anchors = crawl_data.get("socialAnchors", {})
        social_count = sum(1 for v in social_anchors.values() if v)
        if social_count >= 2:
            extra_score += 8
            extra_reasons.append(f"+8: social links found via full crawl ({social_count})")
            partial_result.probe_data["social_anchors"] = social_anchors

        delivery = crawl_data.get("deliveryPlatforms", {})
        delivery_count = sum(1 for v in delivery.values() if v)
        if delivery_count > 0:
            extra_score += 5
            extra_reasons.append(f"+5: delivery platforms found ({delivery_count})")
            partial_result.probe_data["delivery_platforms"] = delivery

        jsonld = crawl_data.get("jsonLd", {})
        if jsonld.get("@type"):
            extra_score += 3
            extra_reasons.append("+3: JSON-LD from full crawl")

        new_score = partial_result.score + extra_score
        all_reasons = partial_result.reasons + extra_reasons
        dyn_threshold = partial_result.threshold

        if new_score >= dyn_threshold:
            return QualificationResult(
                outcome=QUALIFIED, score=new_score, threshold=dyn_threshold,
                reasons=all_reasons, probe_data=partial_result.probe_data,
            )

        # Still ambiguous — use LLM classifier as tiebreaker
        if new_score >= dyn_threshold - 10:
            llm_result = await _run_llm_classifier(name, category, partial_result.probe_data, research_context)
            if llm_result.get("is_hvt"):
                all_reasons.append(f"+LLM: {llm_result.get('reason', 'HVT')}")
                return QualificationResult(
                    outcome=QUALIFIED, score=new_score, threshold=dyn_threshold,
                    reasons=all_reasons, probe_data=partial_result.probe_data,
                )
            all_reasons.append(f"-LLM: {llm_result.get('reason', 'not HVT')}")

        return QualificationResult(
            outcome=PARKED, score=new_score, threshold=dyn_threshold,
            reasons=all_reasons + [f"Full probe score {new_score} still below threshold {dyn_threshold}"],
            probe_data=partial_result.probe_data,
        )

    except Exception as e:
        logger.error(f"[QualScanner] Full probe failed for {name}: {e}")
        return partial_result


async def qualify_businesses(
    businesses: list[dict[str, Any]],
    research_context: dict[str, Any] | None = None,
    threshold: int | None = None,
    run_full_probe: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Qualify a batch of businesses. Returns {qualified, parked, disqualified}."""
    dyn_threshold = threshold if threshold is not None else compute_dynamic_threshold(research_context)

    results: dict[str, list[dict[str, Any]]] = {"qualified": [], "parked": [], "disqualified": []}

    async def _qualify_one(biz: dict[str, Any]) -> tuple[dict[str, Any], QualificationResult]:
        name = biz.get("name", "")
        url = biz.get("url") or biz.get("website") or biz.get("officialUrl") or ""
        category = biz.get("category") or biz.get("businessType") or ""
        result = await qualify_business(
            name=name, url=url, category=category,
            research_context=research_context, threshold=dyn_threshold,
        )
        return biz, result

    step_a_results = await asyncio.gather(
        *[_qualify_one(b) for b in businesses], return_exceptions=True,
    )

    needs_probe: list[tuple[dict[str, Any], QualificationResult]] = []

    for item in step_a_results:
        if isinstance(item, BaseException):
            logger.error(f"[QualScanner] Qualification error: {item}")
            continue
        biz, result = item
        if result.needs_full_probe and run_full_probe:
            needs_probe.append((biz, result))
        else:
            entry = {**biz, "qualification": result.to_dict()}
            results[result.outcome.lower()].append(entry)

    if needs_probe:
        logger.info(f"[QualScanner] Running full probe for {len(needs_probe)} ambiguous businesses")

        async def _probe_one(biz: dict[str, Any], partial: QualificationResult) -> tuple[dict[str, Any], QualificationResult]:
            name = biz.get("name", "")
            url = biz.get("url") or biz.get("website") or biz.get("officialUrl") or ""
            category = biz.get("category") or biz.get("businessType") or ""
            result = await _run_full_probe(name, url, category, partial, research_context)
            return biz, result

        probe_results = await asyncio.gather(
            *[_probe_one(b, r) for b, r in needs_probe], return_exceptions=True,
        )

        for item in probe_results:
            if isinstance(item, BaseException):
                logger.error(f"[QualScanner] Full probe error: {item}")
                continue
            biz, result = item
            entry = {**biz, "qualification": result.to_dict()}
            results[result.outcome.lower()].append(entry)

    q_count = len(results["qualified"])
    p_count = len(results["parked"])
    d_count = len(results["disqualified"])
    logger.info(
        f"[QualScanner] Results: {q_count} qualified, {p_count} parked, {d_count} disqualified "
        f"(threshold={dyn_threshold})"
    )
    return results
