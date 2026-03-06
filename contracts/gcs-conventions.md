# GCS Conventions

> Bucket: `everything-hephae`
> Public base URL: `https://storage.googleapis.com/everything-hephae/`

## Business Reports

```
reports/{slug}/{type}-{timestamp}.html
```

Report types: `profile`, `margin`, `traffic`, `seo`, `competitive`

## Menu Screenshots

```
reports/{slug}/menu-screenshot-{timestamp}.jpg
```

## Menu HTML

```
reports/{slug}/menu-html-{timestamp}.html
```

## Integration Test Reports

```
test-reports/{run-id}/report.html
test-reports/{run-id}/junit.xml
```

`run-id` format: `YYYYMMDD-HHMMSS` (e.g. `20260301-192848`).

## Rules

- Never store binary data in Firestore or BigQuery — upload to GCS, store URL only.
- All URLs are public (no signed URLs needed for reports).
- Slug generation: lowercase, hyphens, stripped specials — see `web/backend/lib/report_storage.py`.
