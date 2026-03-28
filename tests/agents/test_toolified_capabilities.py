"""Tests for Toolified Capabilities (Hub-and-Spoke) — real registry, no mocks."""

from __future__ import annotations

import pytest
from google.adk.tools import FunctionTool


class TestCapabilityRegistry:
    """Real registry lookups — no mocks."""

    def test_get_capability_seo_auditor_returns_object(self):
        """Real registry returns a capability object for seo_auditor."""
        from hephae_api.workflows.capabilities.registry import get_capability

        cap = get_capability("seo_auditor")
        assert cap is not None
        assert cap.name == "seo_auditor"
        assert callable(cap.runner)

    def test_get_capability_margin_surgeon_returns_object(self):
        """Real registry returns a capability for margin_surgeon."""
        from hephae_api.workflows.capabilities.registry import get_capability

        cap = get_capability("margin_surgeon")
        assert cap is not None
        assert cap.name == "margin_surgeon"

    def test_get_capability_nonexistent_returns_none(self):
        """Querying a nonexistent capability returns None (not KeyError)."""
        from hephae_api.workflows.capabilities.registry import get_capability

        result = get_capability("nonexistent_capability_xyz")
        assert result is None

    def test_get_enabled_capabilities_returns_list(self):
        """get_enabled_capabilities returns a non-empty list."""
        from hephae_api.workflows.capabilities.registry import get_enabled_capabilities

        caps = get_enabled_capabilities()
        assert isinstance(caps, list)
        assert len(caps) >= 4  # seo, traffic, competitive, margin at minimum
        names = {c.name for c in caps}
        assert "seo_auditor" in names
        assert "margin_surgeon" in names


class TestCapabilityTools:
    """Real FunctionTool wrapping — no mocks."""

    def test_get_capability_tool_returns_function_tool(self):
        """get_capability_tool wraps a real capability as an ADK FunctionTool."""
        from hephae_api.workflows.capabilities.tools import get_capability_tool

        tool = get_capability_tool("seo_auditor")
        assert isinstance(tool, FunctionTool)

    def test_capability_tool_name_format(self):
        """Tool name follows run_{capability} convention."""
        from hephae_api.workflows.capabilities.tools import get_capability_tool

        tool = get_capability_tool("seo_auditor")
        assert tool.name.startswith("run_")

    def test_get_all_capability_tools_returns_list(self):
        """get_all_capability_tools returns one FunctionTool per enabled capability."""
        from hephae_api.workflows.capabilities.tools import get_all_capability_tools

        tools = get_all_capability_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 4
        for t in tools:
            assert isinstance(t, FunctionTool)
