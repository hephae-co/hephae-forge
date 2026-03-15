"""Per-agent Rubric definitions for ADK rubric-based eval quality scoring.

Each agent's rubrics are positive criteria — things the final response MUST
satisfy to pass the RUBRIC_BASED_FINAL_RESPONSE_QUALITY_V1 metric.
"""

from __future__ import annotations

from google.adk.evaluation.eval_rubrics import Rubric, RubricContent


def _r(rubric_id: str, text: str, description: str = "") -> Rubric:
    return Rubric(
        rubric_id=rubric_id,
        rubric_content=RubricContent(text_property=text),
        description=description,
        type="POSITIVE",
    )


SEO_AUDITOR_RUBRICS: list[Rubric] = [
    _r(
        "seo_json_structure",
        "The response is valid JSON containing an overallScore field with a number between 0 and 100.",
        "Validates top-level report structure and score range.",
    ),
    _r(
        "seo_sections_present",
        "The response includes a 'sections' array with at least 3 entries, each having a name, score, and recommendations list.",
        "Validates that all major SEO categories are covered.",
    ),
    _r(
        "seo_url_field",
        "The response includes a 'url' field matching the audited website.",
        "Traceability — response is linked to the correct site.",
    ),
    _r(
        "seo_actionable_recs",
        "At least one section contains a non-empty recommendations list with specific, actionable items.",
        "Ensures the report is useful for improving SEO, not just diagnostic.",
    ),
]

TRAFFIC_FORECASTER_RUBRICS: list[Rubric] = [
    _r(
        "traffic_business_name",
        "The response references the business name provided in the input.",
        "Confirms the forecast is scoped to the correct business.",
    ),
    _r(
        "traffic_peak_hours",
        "The response includes peak hours or busy time period data (e.g., a peakHours array or equivalent field).",
        "Core output of the traffic forecaster.",
    ),
    _r(
        "traffic_insights",
        "The response includes at least one insight or explanation about traffic patterns.",
        "Ensures the output goes beyond raw data to provide context.",
    ),
    _r(
        "traffic_recommendations",
        "The response includes at least one recommendation for staffing, inventory, or operations.",
        "Practical actionability of the forecast.",
    ),
]

COMPETITIVE_ANALYZER_RUBRICS: list[Rubric] = [
    _r(
        "competitive_json_structure",
        "The response is valid JSON with an overallScore field (0-100) and a competitors array.",
        "Validates report shape.",
    ),
    _r(
        "competitive_min_competitors",
        "The competitors array contains at least 2 profiled competitors, each with a name and location.",
        "Confirms actual competitor research was performed.",
    ),
    _r(
        "competitive_market_positioning",
        "The response includes a marketPositioning or positioning field describing the business's competitive stance.",
        "Core strategic output.",
    ),
    _r(
        "competitive_strategic_recs",
        "The response includes specific strategic recommendations for how the business can differentiate or improve.",
        "Actionability.",
    ),
]

MARGIN_SURGEON_RUBRICS: list[Rubric] = [
    _r(
        "margin_json_structure",
        "The response is valid JSON with an overall_score field (0-100) and a menu_items array.",
        "Validates report structure.",
    ),
    _r(
        "margin_menu_items",
        "The menu_items array contains at least 3 items, each with a name and estimated margin or cost indicator.",
        "Confirms menu analysis was performed.",
    ),
    _r(
        "margin_strategic_advice",
        "The response includes a strategic_advice field with at least one specific pricing or cost recommendation.",
        "Actionability for the business owner.",
    ),
    _r(
        "margin_profit_leakage",
        "The response identifies at least one area of profit leakage or cost reduction opportunity.",
        "Core diagnostic value of the margin surgeon.",
    ),
]

SOCIAL_MEDIA_AUDITOR_RUBRICS: list[Rubric] = [
    _r(
        "social_json_structure",
        "The response is valid JSON containing a platforms array and an overallScore field.",
        "Validates report shape.",
    ),
    _r(
        "social_platforms_scored",
        "Each entry in the platforms array has a platform name and a score between 0 and 100.",
        "Ensures per-platform scoring.",
    ),
    _r(
        "social_recommendations",
        "The response includes at least 2 specific recommendations for improving the business's social media presence.",
        "Actionability.",
    ),
    _r(
        "social_content_analysis",
        "The response analyzes posting frequency, content quality, or engagement levels for at least one platform.",
        "Depth of the audit.",
    ),
]

DISCOVERY_PIPELINE_RUBRICS: list[Rubric] = [
    _r(
        "discovery_business_identity",
        "The response includes the business name and address matching the input.",
        "Confirms the pipeline profiled the correct business.",
    ),
    _r(
        "discovery_contact_info",
        "The response includes at least one contact data point: phone number, email, or website URL.",
        "Minimum useful discovery output.",
    ),
    _r(
        "discovery_social_or_web",
        "The response includes at least one social media link or an official website URL.",
        "Online presence discovery.",
    ),
    _r(
        "discovery_category",
        "The response includes a business category or type classification.",
        "Enables downstream capability routing.",
    ),
]

BLOG_WRITER_RUBRICS: list[Rubric] = [
    _r(
        "blog_post_present",
        "The response includes at least one complete blog post with a title and body text.",
        "Core output check.",
    ),
    _r(
        "blog_min_length",
        "The blog post body contains at least 300 words.",
        "Ensures substantive content, not a stub.",
    ),
    _r(
        "blog_business_relevance",
        "The blog content is clearly relevant to the business described in the input (mentions the business type, location, or services).",
        "Grounding check.",
    ),
    _r(
        "blog_professional_tone",
        "The writing is professional, grammatically correct, and free of placeholder text like [INSERT NAME].",
        "Quality bar for publishable content.",
    ),
]

EMAIL_OUTREACH_RUBRICS: list[Rubric] = [
    _r(
        "email_valid_json",
        "The response is valid JSON with 'subject' and 'body' fields.",
        "Output structure validation.",
    ),
    _r(
        "email_subject_concise",
        "The subject line is under 60 characters.",
        "Subject line should fit in inbox preview.",
    ),
    _r(
        "email_body_concise",
        "The email body is under 200 words.",
        "Keep emails short and punchy for better open/click rates.",
    ),
    _r(
        "email_has_cta",
        "The body contains a clear call to action referencing hephae.co or requesting a reply.",
        "Core conversion element.",
    ),
    _r(
        "email_uses_data",
        "The body leads with a specific data finding, number, or score from the business analysis.",
        "Data-driven hook for credibility.",
    ),
    _r(
        "email_professional_tone",
        "The email is conversational but professional, with no generic platitudes like 'I hope this finds you well'.",
        "Tone should feel human and authentic.",
    ),
]

CONTACT_FORM_RUBRICS: list[Rubric] = [
    _r(
        "contact_valid_json",
        "The response is valid JSON with a 'message' field.",
        "Output structure validation.",
    ),
    _r(
        "contact_concise",
        "The message is 3-4 sentences maximum.",
        "Contact forms have strict character/time constraints.",
    ),
    _r(
        "contact_specific_insight",
        "The message includes a specific insight about the business (e.g., a number, score, or data point).",
        "Demonstrates analysis, not generic copy.",
    ),
    _r(
        "contact_has_cta",
        "The message ends with a clear call to action (link to hephae.co, request a call, or ask for reply).",
        "Core conversion element.",
    ),
    _r(
        "contact_natural_tone",
        "The message reads as natural human communication, not robotic or spammy.",
        "Tone should feel authentic to increase likelihood of response.",
    ),
]

# Maps agentKey (Firestore output key) → list of Rubric objects
AGENT_RUBRICS: dict[str, list[Rubric]] = {
    "seo_auditor": SEO_AUDITOR_RUBRICS,
    "traffic_forecaster": TRAFFIC_FORECASTER_RUBRICS,
    "competitive_analyzer": COMPETITIVE_ANALYZER_RUBRICS,
    "margin_surgeon": MARGIN_SURGEON_RUBRICS,
    "social_media_auditor": SOCIAL_MEDIA_AUDITOR_RUBRICS,
    "discovery_pipeline": DISCOVERY_PIPELINE_RUBRICS,
    "blog_writer": BLOG_WRITER_RUBRICS,
    "outreach_email": EMAIL_OUTREACH_RUBRICS,
    "outreach_contactForm": CONTACT_FORM_RUBRICS,
}
