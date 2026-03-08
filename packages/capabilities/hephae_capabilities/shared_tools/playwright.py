"""
Playwright shared tools — page scraping and screenshot capture.

crawl_web_page:
  Comprehensive single-page scraper. Extracts links, meta tags, JSON-LD,
  favicon, logo, colors, social links, delivery platforms, contact info,
  and body text. Returns structured JSON — never binary/base64.

screenshot_page:
  Full-page JPEG screenshot + raw HTML capture. Returns base64-encoded
  screenshot and HTML string.

Port of src/agents/tools/playwrightTool.ts.
"""

from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def crawl_web_page(
    url: str,
    scroll_to_bottom: bool = True,
    find_menu_link: bool = False,
) -> dict[str, Any]:
    """
    Crawl a web page using a headless browser.
    Extracts links, meta tags, JSON-LD, favicon, logo, colors, social links,
    delivery platform links, contact info (phone/email), and body text.
    Returns structured JSON.

    Args:
        url: The full URL to crawl (e.g. https://example.com).
        scroll_to_bottom: Scroll to bottom to trigger lazy-loaded content (default: True).
        find_menu_link: Attempt to find a dedicated menu page link (default: False).

    Returns:
        dict with extracted page data.
    """
    browser = None
    try:
        from playwright.async_api import async_playwright

        logger.info(f"[PlaywrightCrawlTool] Crawling {url}...")
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        pw = await async_playwright().__aenter__()
        browser = await pw.chromium.launch()
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if scroll_to_bottom:
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)

        # Extract all data in a single page.evaluate call
        result = await page.evaluate(
            """(params) => {
                const { origin, findMenuLink } = params;

                const toHex = (color) => {
                    if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') return null;
                    const m = color.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (!m) return color.startsWith('#') ? color : null;
                    const r = parseInt(m[1]).toString(16).padStart(2, '0');
                    const g = parseInt(m[2]).toString(16).padStart(2, '0');
                    const b = parseInt(m[3]).toString(16).padStart(2, '0');
                    return `#${r}${g}${b}`;
                };

                const abs = (u) => {
                    if (!u) return null;
                    if (u.startsWith('//')) return 'https:' + u;
                    if (u.startsWith('/')) return origin + u;
                    if (u.startsWith('http')) return u;
                    return null;
                };

                // META TAGS
                const metaTags = {};
                document.querySelectorAll('meta').forEach(m => {
                    const key = m.getAttribute('property') || m.getAttribute('name');
                    const val = m.getAttribute('content');
                    if (key && val) metaTags[key] = val;
                });

                // FAVICON
                const faviconEl =
                    document.querySelector('link[rel="apple-touch-icon-precomposed"]') ||
                    document.querySelector('link[rel="apple-touch-icon"][sizes="180x180"]') ||
                    document.querySelector('link[rel="apple-touch-icon"]') ||
                    document.querySelector('link[rel="icon"][type="image/png"][sizes="32x32"]') ||
                    document.querySelector('link[rel="icon"][type="image/png"]') ||
                    document.querySelector('link[rel="icon"][type="image/svg+xml"]') ||
                    document.querySelector('link[rel="icon"]') ||
                    document.querySelector('link[rel="shortcut icon"]');
                const favicon = abs(faviconEl?.href || faviconEl?.getAttribute('href'));

                // LOGO
                const logoImg =
                    document.querySelector('img[src*="logo"]') ||
                    document.querySelector('img[alt*="logo" i]') ||
                    document.querySelector('img[alt*="brand" i]') ||
                    document.querySelector('[class*="logo"] img') ||
                    document.querySelector('[id*="logo"] img') ||
                    document.querySelector('[class*="brand"] img') ||
                    document.querySelector('header img:first-of-type') ||
                    document.querySelector('nav img:first-of-type') ||
                    document.querySelector('.navbar img:first-of-type');

                let logoUrl = abs(
                    logoImg?.src ||
                    logoImg?.getAttribute('data-src') ||
                    logoImg?.getAttribute('data-lazy-src') ||
                    logoImg?.getAttribute('data-original')
                );
                if (!logoUrl) {
                    const ogImg = document.querySelector('meta[property="og:image"]');
                    logoUrl = abs(ogImg?.getAttribute('content'));
                }

                // COLORS
                const themeColor = metaTags['theme-color'] || null;
                let primaryColor = themeColor ? toHex(themeColor) : null;
                if (!primaryColor) {
                    const headerEl =
                        document.querySelector('header') ||
                        document.querySelector('nav') ||
                        document.querySelector('.navbar') ||
                        document.querySelector('[class*="header"]') ||
                        document.querySelector('[id*="header"]');
                    if (headerEl) {
                        primaryColor = toHex(getComputedStyle(headerEl).backgroundColor);
                    }
                }
                if (!primaryColor) primaryColor = '#4f46e5';
                const bodyBg = toHex(getComputedStyle(document.body).backgroundColor);
                const secondaryColor = bodyBg || '#ffffff';

                // PERSONA
                const bodyText = document.body.innerText.toLowerCase();
                let persona = 'Local Business';
                if (/artisanal|craft|organic|farm.to|hand.crafted|locally sourced/.test(bodyText)) {
                    persona = 'Modern Artisan';
                } else if (/est\\.|family.owned|family owned|since \\d{4}|established|generations/.test(bodyText)) {
                    persona = 'Classic Establishment';
                } else if (/fast|quick|express|drive.through|delivery/.test(bodyText)) {
                    persona = 'Quick Service';
                } else if (/fine dining|michelin|prix fixe|sommelier|tasting menu/.test(bodyText)) {
                    persona = 'Fine Dining';
                }

                // ALL LINKS (capped at 200)
                const allAnchors = Array.from(document.querySelectorAll('a[href]'));
                const allLinks = allAnchors
                    .map(a => ({
                        href: a.href,
                        text: (a.innerText || '').trim().substring(0, 100),
                        ariaLabel: a.getAttribute('aria-label') || undefined,
                    }))
                    .filter(l => l.href && l.href.startsWith('http'))
                    .slice(0, 200);

                // SOCIAL LINKS
                const hrefList = allAnchors.map(a => a.href).filter(Boolean);
                const findSocial = (domain) =>
                    hrefList.find(h => h.includes(domain) && !h.includes('share') && !h.includes('sharer') && !h.includes('intent')) || undefined;
                const findSocialByAttr = (keyword) => {
                    const el = allAnchors.find(a => {
                        const label = (a.getAttribute('aria-label') || '').toLowerCase();
                        const title = (a.getAttribute('title') || '').toLowerCase();
                        const cls = (a.className || '').toLowerCase();
                        return (label.includes(keyword) || title.includes(keyword) || cls.includes(keyword))
                            && a.href && a.href.startsWith('http');
                    });
                    return el?.href || undefined;
                };

                const socialAnchors = {
                    instagram: findSocial('instagram.com/') || findSocialByAttr('instagram'),
                    facebook: findSocial('facebook.com/') || findSocialByAttr('facebook'),
                    twitter: findSocial('twitter.com/') || findSocial('x.com/') || findSocialByAttr('twitter'),
                    yelp: findSocial('yelp.com/') || findSocialByAttr('yelp'),
                    tiktok: findSocial('tiktok.com/') || findSocialByAttr('tiktok'),
                };

                // DELIVERY PLATFORMS
                // Filter out doordash.com/business/ links — those are marketing partner pages, not real storefronts
                const findDelivery = (domain, exclude) => {
                    const url = hrefList.find(h =>
                        h.includes(domain) && !h.includes('share') && !h.includes('sharer') && !h.includes('intent')
                        && (!exclude || !exclude.some(ex => h.includes(ex)))
                    );
                    return url || undefined;
                };
                // For DoorDash, also filter attr-based fallback to exclude /business/ links
                const doordashByAttr = findSocialByAttr('doordash');
                const doordashUrl = findDelivery('doordash.com/', ['/business/', '/merchant/'])
                    || (doordashByAttr && !doordashByAttr.includes('/business/') && !doordashByAttr.includes('/merchant/') ? doordashByAttr : undefined);
                const deliveryPlatforms = {
                    grubhub: findDelivery('grubhub.com/') || findSocialByAttr('grubhub'),
                    doordash: doordashUrl,
                    ubereats: findDelivery('ubereats.com/') || findSocialByAttr('ubereats'),
                    seamless: findDelivery('seamless.com/') || findSocialByAttr('seamless'),
                    toasttab: findDelivery('toasttab.com/') || findSocialByAttr('toasttab'),
                };

                // CONTACT
                const telLink = document.querySelector('a[href^="tel:"]');
                const phone = telLink ? telLink.href.replace('tel:', '').trim() : undefined;
                const mailtoLink = document.querySelector('a[href^="mailto:"]');
                const email = mailtoLink ? mailtoLink.href.replace('mailto:', '').trim() : undefined;

                // JSON-LD
                const jsonLdBlocks = [];
                try {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
                    for (const s of scripts) {
                        const data = JSON.parse(s.textContent || '{}');
                        const entities = Array.isArray(data) ? data : [data];
                        jsonLdBlocks.push(...entities);
                    }
                } catch (_) {}

                const restaurantLd = jsonLdBlocks.find(e =>
                    e['@type'] === 'Restaurant' || e['@type'] === 'FoodEstablishment' ||
                    e['@type'] === 'LocalBusiness'
                ) || null;

                const ldPhone = restaurantLd?.telephone || undefined;
                const ldHours = restaurantLd?.openingHours || undefined;
                const ldEmail = restaurantLd?.email || undefined;
                const sameAs = restaurantLd?.sameAs
                    ? (Array.isArray(restaurantLd.sameAs) ? restaurantLd.sameAs : [restaurantLd.sameAs])
                    : [];

                // MENU LINK (optional)
                let menuUrl = null;
                if (findMenuLink) {
                    // Priority 1: anchor text strongly indicates a menu page
                    const menuTextPattern = /\\b(menu|our menu|full menu|view menu|see menu|food menu|dinner menu|lunch menu|lunch|dinner|lunch.*dinner|food|drinks|eat|dine|dining)\\b/i;
                    // Priority 2: href path indicates a menu page
                    const menuHrefPattern = /\\/menu|\\/food|\\/dining|\\/eat|\\/drinks|menu\\.pdf|baslik=.*menu|baslik=.*lunch|baslik=.*dinner/i;

                    // First try: navigation/header links (most reliable)
                    const navAnchors = Array.from(
                        document.querySelectorAll('nav a[href], header a[href], [class*="nav"] a[href], [class*="menu-bar"] a[href], [id*="nav"] a[href]')
                    );
                    const navMenu = navAnchors.find(a => {
                        const text = (a.innerText || '').trim();
                        return text.length > 0 && text.length < 40 && menuTextPattern.test(text);
                    });

                    // Second try: any anchor with menu text
                    const anyMenu = !navMenu && allAnchors.find(a => {
                        const text = (a.innerText || '').trim();
                        return text.length > 0 && text.length < 40 && menuTextPattern.test(text)
                            && !a.href.includes('instagram.com') && !a.href.includes('facebook.com')
                            && !a.href.includes('doordash.com') && !a.href.includes('ubereats.com')
                            && !a.href.includes('grubhub.com');
                    });

                    // Third try: href path matching
                    const hrefMenu = !navMenu && !anyMenu && allAnchors.find(a =>
                        a.href && menuHrefPattern.test(a.href)
                        && !a.href.includes('doordash.com') && !a.href.includes('ubereats.com')
                        && !a.href.includes('grubhub.com')
                    );

                    const menuAnchor = navMenu || anyMenu || hrefMenu;
                    if (menuAnchor) {
                        const href = menuAnchor.href;
                        menuUrl = href.startsWith('/') ? origin + href : href;
                    }
                }

                // BODY TEXT SAMPLE
                const bodyTextSample = document.body.innerText.substring(0, 5000);

                return {
                    favicon,
                    logoUrl,
                    primaryColor,
                    secondaryColor,
                    persona,
                    metaTags,
                    socialAnchors,
                    deliveryPlatforms,
                    phone: phone || ldPhone,
                    email: email || ldEmail,
                    hours: ldHours,
                    jsonLd: restaurantLd,
                    sameAs,
                    allLinks,
                    menuUrl,
                    bodyTextSample,
                };
            }""",
            {"origin": origin, "findMenuLink": find_menu_link},
        )

        logger.info(
            "[PlaywrightCrawlTool] Extracted: hasLogo=%s, hasFavicon=%s, primaryColor=%s, persona=%s, linkCount=%d",
            bool(result.get("logoUrl")),
            bool(result.get("favicon")),
            result.get("primaryColor"),
            result.get("persona"),
            len(result.get("allLinks", [])),
        )

        return result

    except Exception as error:
        logger.error(f"[PlaywrightCrawlTool] Failed: {error}")
        return {
            "error": f"Crawl failed: {error}",
            "favicon": None,
            "logoUrl": None,
            "primaryColor": "#4f46e5",
            "secondaryColor": "#ffffff",
            "persona": "Local Business",
            "metaTags": {},
            "socialAnchors": {},
            "deliveryPlatforms": {},
            "allLinks": [],
            "jsonLd": None,
            "sameAs": [],
            "bodyTextSample": "",
            "menuUrl": None,
        }
    finally:
        if browser:
            await browser.close()


# ---------------------------------------------------------------------------
# Screenshot tool
# ---------------------------------------------------------------------------

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
)


async def screenshot_page(
    url: str,
    quality: int = 55,
    wait_seconds: float = 2.0,
) -> dict[str, Any]:
    """Take a full-page JPEG screenshot and capture raw HTML from a URL.

    Args:
        url: The page URL to screenshot.
        quality: JPEG quality 1-100 (default 55 — good for GCS uploads).
        wait_seconds: Extra seconds to wait after networkidle (default 2.0).

    Returns:
        dict with keys:
          screenshot_base64: base64-encoded JPEG string (empty on failure).
          html: raw HTML string (empty on failure).
          error: error message string or None.
    """
    browser = None
    try:
        from playwright.async_api import async_playwright

        logger.info(f"[ScreenshotTool] Capturing {url} (q={quality})...")
        pw = await async_playwright().__aenter__()
        browser = await pw.chromium.launch()
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=_DEFAULT_UA,
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(int(wait_seconds * 1000))

        buf = await page.screenshot(full_page=True, type="jpeg", quality=quality)
        html = await page.content()

        b64 = base64.b64encode(buf).decode()
        logger.info(f"[ScreenshotTool] Done: {len(buf) // 1024}KB screenshot, {len(html)} chars HTML")

        return {"screenshot_base64": b64, "html": html, "error": None}

    except Exception as exc:
        logger.warning(f"[ScreenshotTool] Failed for {url}: {exc}")
        return {"screenshot_base64": "", "html": "", "error": str(exc)}
    finally:
        if browser:
            await browser.close()
