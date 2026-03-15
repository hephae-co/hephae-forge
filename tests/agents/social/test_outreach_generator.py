"""Unit tests for the Social Outreach Generator Agent."""

import pytest
from unittest.mock import AsyncMock, patch
from hephae_common.models import OutreachResponse
from hephae_agents.social.outreach_generator.runner import run_social_outreach_generation

SAMPLE_BIZ_DATA = {
    "name": "Mama's Pizza",
    "city": "Nutley",
    "address": "123 Main St, Nutley, NJ",
}

SAMPLE_INSIGHTS = {
    "summary": "High engagement on Instagram but losing 30% profit to DoorDash fees.",
    "key_findings": [
        "No direct ordering link on Instagram bio",
        "Menu prices are 15% lower than local average",
    ]
}

SAMPLE_AGENT_RESULT = {
    "pitch_angle": "Aggregator Escape",
    "email": {
        "subject": "Mama's Pizza: Keep 100% of your delivery revenue",
        "body_html": "<h2>Hi Mama's Pizza,</h2><p>We noticed you are doing great on Instagram but losing a lot to aggregator fees...</p>",
        "body_text": "Hi Mama's Pizza, We noticed...",
        "hashtags": ["#NutleyEats", "#PizzaProfits"],
        "image_prompts": ["A steaming pizza with a 'Keep 100%' badge"],
        "cta_link": "https://hephae.co/report/mamas-pizza"
    },
    "contact_form": {
        "body_text": "Hi, I have a growth report for Mama's Pizza showing how to escape DoorDash fees."
    }
}

@pytest.mark.asyncio
async def test_run_social_outreach_generation_success():
    """Test successful outreach generation with mocked ADK."""
    with patch("packages.capabilities.hephae_capabilities.social.outreach_generator.runner.run_agent_to_json", new_callable=AsyncMock) as mock_run:
        mock_gen = AsyncMock()
        mock_run.return_value = SAMPLE_AGENT_RESULT
        
        result = await run_social_outreach_generation(
            business_data=SAMPLE_BIZ_DATA,
            insights=SAMPLE_INSIGHTS,
            industry="Restaurants",
            report_url="https://hephae.co/report/mamas-pizza"
        )
        
        assert isinstance(result, OutreachResponse)
        assert result.pitch_angle == "Aggregator Escape"
        assert "Mama's Pizza" in result.email.subject
        assert "<h2>" in result.email.body_html
        assert len(result.email.hashtags) > 0
        assert len(result.contact_form.body_text) > 0
        assert result.email.cta_link == "https://hephae.co/report/mamas-pizza"

@pytest.mark.asyncio
async def test_run_social_outreach_generation_failure():
    """Test failure handling in outreach generation."""
    with patch("packages.capabilities.hephae_capabilities.social.outreach_generator.runner.run_agent_to_json", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = Exception("ADK Failure")
        
        result = await run_social_outreach_generation(
            business_data=SAMPLE_BIZ_DATA,
            insights=SAMPLE_INSIGHTS
        )
        
        assert result is None
