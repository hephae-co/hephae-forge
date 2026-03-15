"""Runner for the Social Outreach Generator."""

import logging
from typing import Any, Dict, Optional
from hephae_common.adk_helpers import run_agent_to_json
from hephae_common.models import OutreachResponse
from skills.industry_intelligence import get_industry_config
from .agent import OutreachGeneratorAgent
from .prompts import build_outreach_prompt

logger = logging.getLogger(__name__)

async def run_social_outreach_generation(
    business_data: Dict[str, Any],
    insights: Dict[str, Any],
    industry: str = "Restaurants",
    report_url: str = "",
) -> Optional[OutreachResponse]:
    """Generate personalized outreach content using industry intelligence.
    
    Args:
        business_data: Basic identity (name, address, etc.)
        insights: Key findings from analysis
        industry: Business category (e.g. Restaurants)
        report_url: URL to the full generated report
        
    Returns:
        OutreachResponse if successful, None otherwise.
    """
    industry_config = get_industry_config(industry)
    
    # Enrich business_data with report_url for the generator
    biz_context = {**business_data, "report_url": report_url}
    
    prompt = build_outreach_prompt(
        biz_context, 
        industry_config.model_dump(), 
        insights
    )
    
    try:
        result = await run_agent_to_json(
            OutreachGeneratorAgent,
            prompt,
            app_name="HephaeSocial",
        )
        if result:
            return OutreachResponse(**result)
    except Exception as e:
        logger.error(f"[OutreachGenerator] Failed for {business_data.get('name')}: {e}")
        
    return None
