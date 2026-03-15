"""
GCS bucket access — report/image uploads.

No makePublic() calls — buckets use uniform IAM (allUsers: Storage Object Viewer).
Two buckets (configured via env vars GCS_BUCKET and GCS_CDN_BUCKET):
  - Legacy bucket: menu screenshots, menu HTML
  - CDN bucket: reports, social cards (served via CDN)
"""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Optional

from hephae_common.model_config import StorageConfig

logger = logging.getLogger(__name__)

ReportType = str


def generate_slug(name: str) -> str:
    """Convert a business name to a URL-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = slug.strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug


async def upload_menu_screenshot(slug: str, base64_data: str) -> str:
    """Upload a base64 menu screenshot to GCS and return the public URL."""
    ts = int(time.time() * 1000)
    object_path = f"{slug}/menu-{ts}.jpg"
    public_url = f"{StorageConfig.BASE_URL}/{object_path}"

    try:
        from hephae_common.firebase import get_bucket

        gcs_bucket = get_bucket()
        clean_b64 = re.sub(r"^data:image/\w+;base64,", "", base64_data)
        buffer = base64.b64decode(clean_b64)

        blob = gcs_bucket.blob(object_path)
        blob.upload_from_string(buffer, content_type="image/jpeg")
        blob.cache_control = "public, max-age=86400"
        blob.patch()

        logger.info(f"[GCS] Uploaded menu screenshot -> {public_url}")
        return public_url
    except Exception as err:
        logger.warning(f"[GCS] Failed to upload menu screenshot for {slug}: {err}")
        return ""


async def upload_menu_html(slug: str, html_content: str) -> str:
    """Upload raw menu-page HTML to GCS and return the public URL."""
    ts = int(time.time() * 1000)
    object_path = f"{slug}/menu-{ts}.html"
    public_url = f"{StorageConfig.BASE_URL}/{object_path}"

    try:
        from hephae_common.firebase import get_bucket

        gcs_bucket = get_bucket()
        blob = gcs_bucket.blob(object_path)
        blob.upload_from_string(html_content, content_type="text/html; charset=utf-8")
        blob.cache_control = "public, max-age=604800"
        blob.patch()

        logger.info(f"[GCS] Uploaded menu HTML -> {public_url}")
        return public_url
    except Exception as err:
        logger.warning(f"[GCS] Failed to upload menu HTML for {slug}: {err}")
        return ""


def _get_cdn_bucket():
    """Get the CDN GCS bucket (hephae-co-dev-prod-cdn-assets)."""
    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client()
    return client.bucket(StorageConfig.CDN_BUCKET)


async def upload_report(
    slug: str,
    report_type: ReportType,
    html_content: str,
    identity: Optional[dict] = None,
    summary: Optional[str] = None,
) -> str:
    """Upload an HTML report to CDN bucket and return the cdn.hephae.co URL.

    Reports are now served via cdn.hephae.co (CDN bucket).
    """
    ts = int(time.time() * 1000)
    file_name = f"{report_type}-{ts}.html"
    object_path = f"reports/{slug}/{file_name}"
    cdn_url = f"{StorageConfig.CDN_BASE_URL}/{object_path}"

    try:
        bucket = _get_cdn_bucket()
        blob = bucket.blob(object_path)
        blob.upload_from_string(html_content, content_type="text/html; charset=utf-8")
        blob.cache_control = "public, max-age=3600"
        blob.patch()

        logger.info(f"[CDN] Uploaded {object_path} -> {cdn_url}")
        return cdn_url
    except Exception as err:
        logger.warning(f"[CDN] Failed to upload {report_type} report for {slug}: {err}")
        # Fallback to legacy bucket
        legacy_path = f"{slug}/{file_name}"
        legacy_url = f"{StorageConfig.BASE_URL}/{legacy_path}"
        try:
            from hephae_common.firebase import get_bucket
            gcs_bucket = get_bucket()
            blob = gcs_bucket.blob(legacy_path)
            blob.upload_from_string(html_content, content_type="text/html; charset=utf-8")
            blob.cache_control = "public, max-age=3600"
            blob.patch()
            logger.info(f"[GCS] Fallback uploaded {legacy_path} -> {legacy_url}")
            return legacy_url
        except Exception as fallback_err:
            logger.warning(f"[GCS] Fallback also failed for {slug}: {fallback_err}")
            return ""


async def upload_report_to_cdn(
    slug: str,
    report_type: ReportType,
    html_content: str,
) -> str:
    """Upload an HTML report to the CDN bucket and return the public URL."""
    ts = int(time.time() * 1000)
    file_name = f"{report_type}-{ts}.html"
    object_path = f"reports/{slug}/{file_name}"
    public_url = f"{StorageConfig.CDN_BASE_URL}/{object_path}"

    try:
        bucket = _get_cdn_bucket()
        blob = bucket.blob(object_path)
        blob.upload_from_string(html_content, content_type="text/html; charset=utf-8")
        blob.cache_control = "public, max-age=3600"
        blob.patch()

        logger.info(f"[CDN] Uploaded {object_path} -> {public_url}")
        return public_url
    except Exception as err:
        logger.warning(f"[CDN] Failed to upload {report_type} report for {slug}: {err}")
        return ""


async def upload_social_card_to_cdn(
    slug: str,
    report_type: str,
    png_bytes: bytes,
) -> str:
    """Upload a social card PNG to the CDN bucket and return the public URL."""
    ts = int(time.time() * 1000)
    file_name = f"{report_type}-card-{ts}.png"
    object_path = f"cards/{slug}/{file_name}"
    public_url = f"{StorageConfig.CDN_BASE_URL}/{object_path}"

    try:
        bucket = _get_cdn_bucket()
        blob = bucket.blob(object_path)
        blob.upload_from_string(png_bytes, content_type="image/png")
        blob.cache_control = "public, max-age=86400"
        blob.patch()

        logger.info(f"[CDN] Uploaded social card -> {public_url}")
        return public_url
    except Exception as err:
        logger.warning(f"[CDN] Failed to upload social card for {slug}/{report_type}: {err}")
        return ""
