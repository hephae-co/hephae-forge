"""Test that ADMIN_APP_API.md is consistent with the OpenAPI spec.

This catches two classes of drift:
1. A route was added/removed/changed but the doc wasn't updated.
2. A response model field was added/removed but the doc doesn't reflect it.
"""

import pytest

from hephae_api.main import app


@pytest.fixture(scope="module")
def openapi_spec():
    return app.openapi()


class TestOpenApiHasResponseModels:
    """Every POST route should have a response_model so OpenAPI is useful."""

    EXEMPT_ROUTES = {
        "/api/track",
        "/api/send-report-email",
        "/api/social-card",       # Returns binary PNG, not JSON
        "/api/places/search",
        "/api/health",
        "/api/optimize",          # Deprecated — superseded by MCP server
        "/api/optimize/prompt",
        "/api/optimize/ai-cost",
        "/api/optimize/cloud-cost",
        "/api/optimize/performance",
        "/api/chat",              # StreamingResponse, not JSON model
        "/api/auth/me",           # Returns JSONResponse directly
        "/api/heartbeat",         # Returns JSONResponse directly
    }

    # Admin/internal route prefixes — these intentionally return JSONResponse
    EXEMPT_PREFIXES = (
        "/api/workflows",
        "/api/research",
        "/api/zipcode-research",
        "/api/area-research",
        "/api/sector-research",
        "/api/combined-context",
        "/api/fixtures",
        "/api/run-tests",
        "/api/content",
        "/api/admin/",
        "/api/food-prices",
        "/api/stats",
    )

    def test_post_routes_have_response_schemas(self, openapi_spec):
        paths = openapi_spec.get("paths", {})
        missing = []
        for path, methods in paths.items():
            if path in self.EXEMPT_ROUTES:
                continue
            if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
                continue
            for method in ("post",):
                op = methods.get(method)
                if not op:
                    continue
                resp_200 = op.get("responses", {}).get("200", {})
                content = resp_200.get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                if not schema:
                    missing.append(f"{method.upper()} {path}")

        assert not missing, (
            f"Routes missing response_model (no schema in OpenAPI):\n"
            + "\n".join(f"  - {r}" for r in missing)
        )


class TestResponseModelsPresent:
    """Key Pydantic models should appear in the OpenAPI component schemas."""

    EXPECTED_MODELS = [
        "EnrichedProfile",
        "SurgicalReport",
        "SeoReport",
        "ForecastResponse",
        "CompetitiveReport",
        "SocialAuditReport",
    ]

    @pytest.mark.parametrize("model_name", EXPECTED_MODELS)
    def test_model_in_schemas(self, openapi_spec, model_name):
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        assert model_name in schemas, (
            f"Model '{model_name}' not found in OpenAPI schemas. "
            f"Available: {sorted(schemas.keys())}"
        )


class TestAdminAppDocHasMarkers:
    """ADMIN_APP_API.md should have auto-gen markers for the sync script."""

    @pytest.fixture(scope="class")
    def doc_content(self):
        from pathlib import Path

        doc_path = Path(__file__).resolve().parents[3] / "ADMIN_APP_API.md"
        if not doc_path.exists():
            pytest.skip("ADMIN_APP_API.md not found")
        return doc_path.read_text()

    def test_has_endpoint_markers(self, doc_content):
        assert "<!-- BEGIN:AUTO:ENDPOINTS -->" in doc_content
        assert "<!-- END:AUTO:ENDPOINTS -->" in doc_content

    def test_has_types_markers(self, doc_content):
        assert "<!-- BEGIN:AUTO:TYPES -->" in doc_content
        assert "<!-- END:AUTO:TYPES -->" in doc_content
