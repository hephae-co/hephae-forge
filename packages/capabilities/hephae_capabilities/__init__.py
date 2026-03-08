"""Hephae Capabilities — stateless AI agents with runner functions.

Each capability exposes a runner function:
    identity/context in → report dict out.

Usage:
    from hephae_capabilities.seo_auditor.runner import run_seo_audit
    report = await run_seo_audit(identity, business_context)
"""
