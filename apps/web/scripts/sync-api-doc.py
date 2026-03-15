#!/usr/bin/env python3
"""Generate the auto-maintained sections of ADMIN_APP_API.md from the OpenAPI spec.

Usage:
    python scripts/sync-api-doc.py            # Update ADMIN_APP_API.md in place
    python scripts/sync-api-doc.py --check    # Exit 1 if doc is stale (CI mode)
    python scripts/sync-api-doc.py --diff     # Show diff without writing
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root (one level above scripts/)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = PROJECT_ROOT / "ADMIN_APP_API.md"

# Add project root to sys.path so we can import the FastAPI app
sys.path.insert(0, str(PROJECT_ROOT))


def get_openapi_spec() -> dict:
    """Import the FastAPI app and return its OpenAPI schema."""
    from hephae_api.main import app

    return app.openapi()


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------

# Markers used to delimit auto-generated sections in the markdown
BEGIN_ENDPOINTS = "<!-- BEGIN:AUTO:ENDPOINTS -->"
END_ENDPOINTS = "<!-- END:AUTO:ENDPOINTS -->"
BEGIN_TYPES = "<!-- BEGIN:AUTO:TYPES -->"
END_TYPES = "<!-- END:AUTO:TYPES -->"


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref pointer like '#/components/schemas/Foo'."""
    parts = ref.lstrip("#/").split("/")
    node = spec
    for p in parts:
        node = node[p]
    return node


def _schema_to_ts(spec: dict, schema: dict, indent: int = 0) -> str:
    """Convert a JSON Schema (from OpenAPI) to a TypeScript-like interface string."""
    if "$ref" in schema:
        return _ref_name(schema["$ref"])

    if schema.get("type") == "array":
        items = schema.get("items", {})
        inner = _schema_to_ts(spec, items, indent)
        return f"{inner}[]"

    if "anyOf" in schema or "oneOf" in schema:
        variants = schema.get("anyOf") or schema.get("oneOf", [])
        non_null = [v for v in variants if v.get("type") != "null"]
        if len(non_null) == 1:
            return _schema_to_ts(spec, non_null[0], indent) + " | null"
        return " | ".join(_schema_to_ts(spec, v, indent) for v in variants)

    t = schema.get("type", "any")
    if t == "string":
        return "string"
    if t == "integer" or t == "number":
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "object":
        props = schema.get("properties")
        if not props:
            return "Record<string, any>"
        # inline object
        pad = "  " * (indent + 1)
        lines = ["{"]
        for k, v in props.items():
            optional = "?" if k not in schema.get("required", []) else ""
            ts_type = _schema_to_ts(spec, v, indent + 1)
            lines.append(f"{pad}{k}{optional}: {ts_type};")
        lines.append("  " * indent + "}")
        return "\n".join(lines)

    return "any"


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _method_label(method: str) -> str:
    return method.upper()


def generate_endpoints_section(spec: dict) -> str:
    """Generate the API Endpoints markdown section from OpenAPI paths."""
    lines: list[str] = []
    lines.append("")

    paths = spec.get("paths", {})

    # Group by prefix
    groups: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in sorted(paths.items()):
        for method, op in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                # Determine group
                if "/v1/" in path:
                    group = "V1 (Headless) Endpoints"
                elif "/capabilities/" in path:
                    group = "Capability Endpoints"
                else:
                    group = "Core Endpoints"
                groups.setdefault(group, []).append((path, method, op))

    for group_name, endpoints in groups.items():
        lines.append(f"### {group_name}")
        lines.append("")

        for path, method, op in endpoints:
            summary = op.get("summary", op.get("operationId", ""))
            lines.append(f"#### `{_method_label(method)} {path}`")
            if summary:
                lines.append(f"")
                lines.append(f"{summary}")
            lines.append("")

            # Response model
            resp_200 = op.get("responses", {}).get("200", {})
            content = resp_200.get("content", {}).get("application/json", {})
            resp_schema = content.get("schema", {})
            if resp_schema:
                if "$ref" in resp_schema:
                    model_name = _ref_name(resp_schema["$ref"])
                    lines.append(f"**Response model:** `{model_name}`")
                else:
                    # Inline schema — try to describe it
                    title = resp_schema.get("title", "")
                    if title:
                        lines.append(f"**Response model:** `{title}`")
                lines.append("")

    return "\n".join(lines)


def generate_types_section(spec: dict) -> str:
    """Generate the Core TypeScript Interfaces section from OpenAPI component schemas."""
    lines: list[str] = []
    lines.append("")

    schemas = spec.get("components", {}).get("schemas", {})
    if not schemas:
        lines.append("*No schemas found in OpenAPI spec.*")
        return "\n".join(lines)

    # Skip internal/envelope schemas
    skip_prefixes = ("HTTPValidationError", "ValidationError", "Body_")

    for name, schema in sorted(schemas.items()):
        if any(name.startswith(p) for p in skip_prefixes):
            continue

        lines.append(f"#### `{name}`")
        lines.append("")
        lines.append("```typescript")

        # Build interface
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        if not props:
            # Could be an enum or simple type
            if "enum" in schema:
                lines.append(f"type {name} = {' | '.join(repr(v) for v in schema['enum'])};")
            else:
                lines.append(f"// {schema.get('type', 'unknown')} type")
        else:
            lines.append(f"interface {name} {{")
            for prop_name, prop_schema in props.items():
                optional = "?" if prop_name not in required else ""
                ts_type = _schema_to_ts(spec, prop_schema)
                lines.append(f"  {prop_name}{optional}: {ts_type};")
            lines.append("}")

        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown merging
# ---------------------------------------------------------------------------


def update_doc(doc: str, spec: dict) -> str:
    """Replace auto-generated sections in the doc with fresh content from the spec."""
    endpoints_content = generate_endpoints_section(spec)
    types_content = generate_types_section(spec)

    # If markers don't exist yet, inject them at the right heading locations
    if BEGIN_ENDPOINTS not in doc:
        # Insert markers after "## API Endpoints" heading
        doc = re.sub(
            r"(## API Endpoints\n)",
            rf"\1\n{BEGIN_ENDPOINTS}\n{END_ENDPOINTS}\n",
            doc,
        )

    if BEGIN_TYPES not in doc:
        doc = re.sub(
            r"(## Core TypeScript Interfaces\n)",
            rf"\1\n{BEGIN_TYPES}\n{END_TYPES}\n",
            doc,
        )

    # Replace content between markers
    if BEGIN_ENDPOINTS in doc and END_ENDPOINTS in doc:
        doc = re.sub(
            rf"{re.escape(BEGIN_ENDPOINTS)}.*?{re.escape(END_ENDPOINTS)}",
            f"{BEGIN_ENDPOINTS}\n{endpoints_content}\n{END_ENDPOINTS}",
            doc,
            flags=re.DOTALL,
        )

    if BEGIN_TYPES in doc and END_TYPES in doc:
        doc = re.sub(
            rf"{re.escape(BEGIN_TYPES)}.*?{re.escape(END_TYPES)}",
            f"{BEGIN_TYPES}\n{types_content}\n{END_TYPES}",
            doc,
            flags=re.DOTALL,
        )

    return doc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Sync ADMIN_APP_API.md with OpenAPI spec")
    parser.add_argument("--check", action="store_true", help="Exit 1 if doc is stale")
    parser.add_argument("--diff", action="store_true", help="Show diff without writing")
    args = parser.parse_args()

    spec = get_openapi_spec()
    current = DOC_PATH.read_text()
    updated = update_doc(current, spec)

    if current == updated:
        print("ADMIN_APP_API.md is up to date.")
        sys.exit(0)

    if args.check:
        # Show what's different
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="ADMIN_APP_API.md (current)",
            tofile="ADMIN_APP_API.md (expected)",
        )
        sys.stderr.writelines(diff)
        print("ADMIN_APP_API.md is STALE. Run `python scripts/sync-api-doc.py` to update.")
        sys.exit(1)

    if args.diff:
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="current",
            tofile="updated",
        )
        sys.stdout.writelines(diff)
        sys.exit(0)

    DOC_PATH.write_text(updated)
    print(f"Updated {DOC_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
