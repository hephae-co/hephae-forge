"""Composable qualification tools — pure functions that analyze HTTP responses.

Architecture:
  page_fetcher(url) → raw HTML
       ↓
       ├── domain_analyzer(url) — URL parsing only, no HTTP
       ├── platform_detector(html) — detects Shopify, Wix, WordPress, Toast, etc.
       ├── pixel_detector(html) — detects Facebook Pixel, GA, GTM, etc.
       ├── contact_path_detector(html, base_url) — finds /contact links, mailto:, etc.
       └── meta_extractor(html) — og:type, description, generator, JSON-LD, SSL
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 10


async def page_fetcher(url: str) -> dict[str, Any]:
    """Fetch a page via plain httpx GET. Returns {html, status_code, final_url, error}."""
    if not url:
        return {"html": "", "status_code": 0, "final_url": "", "error": "no_url"}
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HephaeBot/1.0)"},
        ) as client:
            resp = await client.get(url)
            return {
                "html": resp.text,
                "status_code": resp.status_code,
                "final_url": str(resp.url),
                "error": None,
            }
    except httpx.TimeoutException:
        return {"html": "", "status_code": 0, "final_url": url, "error": "timeout"}
    except httpx.ConnectError:
        return {"html": "", "status_code": 0, "final_url": url, "error": "connection_refused"}
    except Exception as e:
        return {"html": "", "status_code": 0, "final_url": url, "error": str(e)}


_DIRECTORY_DOMAINS = {
    "yelp.com", "tripadvisor.com", "yellowpages.com", "bbb.org",
    "mapquest.com", "foursquare.com", "zomato.com", "grubhub.com",
    "doordash.com", "ubereats.com", "seamless.com", "menufy.com",
    "opentable.com", "resy.com",
}

_SOCIAL_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "linkedin.com", "youtube.com",
}

_PLATFORM_SUBDOMAINS = {
    "myshopify.com", "squarespace.com", "wixsite.com",
    "weebly.com", "godaddysites.com", "wordpress.com",
    "square.site", "toast.restaurants",
}


def domain_analyzer(url: str) -> dict[str, Any]:
    """Analyze a URL to classify the domain type. No HTTP needed."""
    if not url:
        return {"domain": "", "domain_type": "unknown", "is_custom_domain": False, "is_https": False}

    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = parsed.hostname or ""
    is_https = parsed.scheme == "https"

    for dd in _DIRECTORY_DOMAINS:
        if domain == dd or domain.endswith(f".{dd}"):
            return {"domain": domain, "domain_type": "directory", "is_custom_domain": False, "is_https": is_https}

    for sd in _SOCIAL_DOMAINS:
        if domain == sd or domain.endswith(f".{sd}"):
            return {"domain": domain, "domain_type": "social", "is_custom_domain": False, "is_https": is_https}

    for ps in _PLATFORM_SUBDOMAINS:
        if domain.endswith(f".{ps}") or domain == ps:
            return {"domain": domain, "domain_type": "platform_subdomain", "is_custom_domain": False, "is_https": is_https}

    return {"domain": domain, "domain_type": "custom", "is_custom_domain": True, "is_https": is_https}


_PLATFORM_SIGNATURES: list[tuple[str, re.Pattern]] = [
    ("shopify", re.compile(r"(?:cdn\.shopify\.com|Shopify\.theme|shopify-section)", re.I)),
    ("wix", re.compile(r"(?:static\.wixstatic\.com|wix-warmup-data|X-Wix-)", re.I)),
    ("wordpress", re.compile(r"(?:wp-content/|wp-includes/|WordPress)", re.I)),
    ("squarespace", re.compile(r"(?:squarespace\.com/|squarespace-cdn|sqs-)", re.I)),
    ("toast", re.compile(r"(?:toasttab\.com|toast\.restaurants|toastcdn)", re.I)),
    ("mindbody", re.compile(r"(?:mindbodyonline\.com|healcode\.com|brandbot)", re.I)),
    ("square_online", re.compile(r"(?:square\.site|squareup\.com/appointments)", re.I)),
    ("weebly", re.compile(r"(?:weebly\.com|editmysite\.com)", re.I)),
    ("godaddy", re.compile(r"(?:godaddysites\.com|secureservercdn\.net)", re.I)),
    ("clover", re.compile(r"(?:clover\.com|clovercdn)", re.I)),
    ("lightspeed", re.compile(r"(?:lightspeed|ecwid\.com)", re.I)),
    ("vagaro", re.compile(r"(?:vagaro\.com)", re.I)),
    ("boulevard", re.compile(r"(?:joinblvd\.com|boulevard)", re.I)),
]


def platform_detector(html: str) -> dict[str, Any]:
    """Detect CMS/platform from HTML content."""
    if not html:
        return {"platform": None, "platform_detected": False, "platforms_found": []}

    found: list[str] = []
    for name, pattern in _PLATFORM_SIGNATURES:
        if pattern.search(html):
            found.append(name)

    return {
        "platform": found[0] if found else None,
        "platform_detected": len(found) > 0,
        "platforms_found": found,
    }


_PIXEL_SIGNATURES: list[tuple[str, re.Pattern]] = [
    ("facebook_pixel", re.compile(r"(?:fbq\(|connect\.facebook\.net/en_US/fbevents|facebook-pixel)", re.I)),
    ("google_analytics", re.compile(r"(?:google-analytics\.com/analytics|gtag\(|GoogleAnalyticsObject|ga\('create')", re.I)),
    ("google_tag_manager", re.compile(r"(?:googletagmanager\.com/gtm|GTM-[A-Z0-9]+)", re.I)),
    ("hotjar", re.compile(r"(?:hotjar\.com|hj\('identify')", re.I)),
    ("google_ads", re.compile(r"(?:googleadservices\.com|gtag.*config.*AW-)", re.I)),
    ("tiktok_pixel", re.compile(r"(?:analytics\.tiktok\.com|ttq\.track)", re.I)),
    ("microsoft_clarity", re.compile(r"(?:clarity\.ms)", re.I)),
    ("mixpanel", re.compile(r"(?:cdn\.mxpnl\.com|mixpanel\.init)", re.I)),
    ("segment", re.compile(r"(?:cdn\.segment\.com|analytics\.load)", re.I)),
]


def pixel_detector(html: str) -> dict[str, Any]:
    """Detect analytics/marketing pixels from HTML content."""
    if not html:
        return {"pixels_found": [], "pixel_count": 0, "has_analytics": False}

    found: list[str] = []
    for name, pattern in _PIXEL_SIGNATURES:
        if pattern.search(html):
            found.append(name)

    return {
        "pixels_found": found,
        "pixel_count": len(found),
        "has_analytics": len(found) > 0,
    }


_CONTACT_PATH_RE = re.compile(
    r'href=["\']([^"\']*(?:contact|about|get-in-touch|reach-us|connect)[^"\']*)["\']',
    re.I,
)
_MAILTO_RE = re.compile(r'href=["\']mailto:([^"\']+)["\']', re.I)
_TEL_RE = re.compile(r'href=["\']tel:([^"\']+)["\']', re.I)
_SOCIAL_LINK_RE = re.compile(
    r'href=["\'](?:https?://)?(?:www\.)?'
    r'((?:instagram|facebook|twitter|x|tiktok|linkedin|youtube|yelp)\.com/[^"\']+)["\']',
    re.I,
)


def contact_path_detector(html: str, base_url: str = "") -> dict[str, Any]:
    """Detect contact paths, mailto: links, tel: links, and social links from HTML."""
    if not html:
        return {
            "contact_paths": [], "mailto_addresses": [], "tel_numbers": [],
            "social_links": [], "has_contact_path": False,
        }

    raw_paths = _CONTACT_PATH_RE.findall(html)
    contact_paths: list[str] = []
    for p in raw_paths:
        if p.startswith("http"):
            contact_paths.append(p)
        elif base_url:
            contact_paths.append(urljoin(base_url, p))
    contact_paths = list(dict.fromkeys(contact_paths))[:5]

    mailto = list(dict.fromkeys(_MAILTO_RE.findall(html)))[:3]
    tel = list(dict.fromkeys(_TEL_RE.findall(html)))[:3]

    social_raw = _SOCIAL_LINK_RE.findall(html)
    social_links: list[str] = list(dict.fromkeys([f"https://{s}" for s in social_raw]))[:10]

    return {
        "contact_paths": contact_paths,
        "mailto_addresses": mailto,
        "tel_numbers": tel,
        "social_links": social_links,
        "has_contact_path": bool(contact_paths or mailto or tel),
    }


_META_RE = re.compile(
    r'<meta\s+(?:[^>]*?(?:name|property|http-equiv)\s*=\s*["\']([^"\']+)["\'])[^>]*?'
    r'content\s*=\s*["\']([^"\']*)["\']',
    re.I,
)
_GENERATOR_RE = re.compile(r'<meta\s+name=["\']generator["\']\s+content=["\']([^"\']+)["\']', re.I)
_JSONLD_RE = re.compile(r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>', re.I | re.S)
_TITLE_RE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)


def meta_extractor(html: str) -> dict[str, Any]:
    """Extract meta tags, JSON-LD hints, and generator from HTML."""
    if not html:
        return {
            "title": "", "description": "", "og_type": "",
            "generator": "", "jsonld_types": [], "has_structured_data": False,
        }

    meta_map: dict[str, str] = {}
    for name_or_prop, content in _META_RE.findall(html):
        meta_map[name_or_prop.lower()] = content

    gen_match = _GENERATOR_RE.search(html)
    generator = gen_match.group(1) if gen_match else ""

    title_match = _TITLE_RE.search(html)
    title = title_match.group(1).strip() if title_match else ""

    jsonld_types: list[str] = []
    for block in _JSONLD_RE.findall(html):
        type_matches = re.findall(r'"@type"\s*:\s*"([^"]+)"', block)
        jsonld_types.extend(type_matches)
    jsonld_types = list(dict.fromkeys(jsonld_types))

    return {
        "title": title,
        "description": meta_map.get("description", ""),
        "og_type": meta_map.get("og:type", ""),
        "generator": generator,
        "jsonld_types": jsonld_types,
        "has_structured_data": len(jsonld_types) > 0,
    }
