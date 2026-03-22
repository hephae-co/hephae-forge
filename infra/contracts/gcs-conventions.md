# GCS Conventions
> Auto-generated from codebase on 2026-03-22. Do not edit manually.

All GCS operations are in `lib/db/hephae_db/gcs/storage.py`. No `makePublic()` calls -- buckets use uniform IAM (`allUsers: Storage Object Viewer`).

---

## Buckets

| Bucket | Env Var | Base URL Env Var | Purpose | Access |
|---|---|---|---|---|
| Legacy bucket | `GCS_BUCKET` | `GCS_BASE_URL` | Menu screenshots, menu HTML | Public (uniform IAM) |
| CDN bucket | `GCS_CDN_BUCKET` | `CDN_BASE_URL` | Reports, social cards | Public via CDN (`cdn.hephae.co`) |

Configuration is centralized in `lib/common/hephae_common/model_config.py` :: `StorageConfig`:

```python
class StorageConfig:
    BUCKET = os.getenv("GCS_BUCKET", "")
    BASE_URL = os.getenv("GCS_BASE_URL", "")
    CDN_BUCKET = os.getenv("GCS_CDN_BUCKET", "")
    CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")
```

---

## Path Patterns

### Legacy Bucket (menu assets)

| Path Pattern | Content Type | Cache Control | Upload Function |
|---|---|---|---|
| `{slug}/menu-{timestamp_ms}.jpg` | `image/jpeg` | `public, max-age=86400` (1 day) | `upload_menu_screenshot()` |
| `{slug}/menu-{timestamp_ms}.html` | `text/html; charset=utf-8` | `public, max-age=604800` (7 days) | `upload_menu_html()` |

**URL format:** `{GCS_BASE_URL}/{slug}/menu-{timestamp_ms}.{ext}`

### CDN Bucket (reports and cards)

| Path Pattern | Content Type | Cache Control | Upload Function |
|---|---|---|---|
| `reports/{slug}/{report_type}-{timestamp_ms}.html` | `text/html; charset=utf-8` | `public, max-age=3600` (1 hour) | `upload_report()`, `upload_report_to_cdn()` |
| `cards/{slug}/{report_type}-card-{timestamp_ms}.png` | `image/png` | `public, max-age=86400` (1 day) | `upload_social_card_to_cdn()` |

**URL format:** `{CDN_BASE_URL}/reports/{slug}/{report_type}-{timestamp_ms}.html`
**URL format:** `{CDN_BASE_URL}/cards/{slug}/{report_type}-card-{timestamp_ms}.png`

---

## Report Types

The `report_type` parameter accepts any string. Common values used across the codebase:

- `seo` -- SEO audit report
- `margin` -- Margin analysis report
- `traffic` -- Traffic forecast report
- `competitive` -- Competitive analysis report
- `marketing` -- Marketing report
- `social-audit` -- Social media audit
- `blog` -- Blog post

---

## Fallback Behavior

`upload_report()` includes a fallback chain:

1. **Try CDN bucket** (`GCS_CDN_BUCKET`) -- primary path
2. **If CDN fails, try legacy bucket** (`GCS_BUCKET`) -- fallback path writes to `{slug}/{report_type}-{timestamp_ms}.html`
3. **If both fail, return empty string** -- caller handles gracefully

`upload_report_to_cdn()` does NOT fallback -- returns empty string on failure.

---

## Key Rules

1. **No blobs in Firestore** -- all binary data (screenshots, HTML, PNGs) must go to GCS. The `strip_blobs()` function in `discovery.py` removes `menuScreenshotBase64` before any DB write.
2. **URLs are stored in Firestore** -- after upload, the public URL is stored in the business document (e.g., `menuScreenshotUrl`, `menuHtmlUrl`) or in `latestOutputs.{agent}.reportUrl`.
3. **Timestamps in filenames** -- all uploads include millisecond timestamps to avoid collisions and enable versioning.
4. **No signed URLs** -- all assets are publicly accessible via uniform IAM bucket policy.

---

## Source Files

| File | Functions |
|---|---|
| `lib/db/hephae_db/gcs/storage.py` | `upload_menu_screenshot()`, `upload_menu_html()`, `upload_report()`, `upload_report_to_cdn()`, `upload_social_card_to_cdn()` |
| `lib/common/hephae_common/model_config.py` | `StorageConfig` (bucket names and base URLs) |
