---
name: hephae-blog-writer
description: Generate and publish SEO-optimized, data-driven blog posts on hephae.co with interactive charts, hero images, and social sharing. Supports industry, zipcode, or combined modes. Uses latest pulse data.
argument-hint: [industry:{name} | zip:{code} | zip:{code} industry:{name} | latest]
---

# Blog Writer — Orchestrator

This skill gathers pulse data and calls the blog writer agent pipeline (which handles charts, SEO, and critique internally). You just need to fetch data and publish.

**The agent does the heavy lifting:**
- `ResearchCompilerAgent` — identifies the 3-5 best data points + designs chart specs
- `BlogWriterAgent` — writes HTML with embedded Chart.js charts (via `generate_chart_js` tool)
- `SEOEnricherAgent` — generates title tag, meta description, keywords, slug
- `BlogCritiqueAgent` — 5-test quality gate (data accuracy, charts, SEO, reader value, brand safety)
- If critique fails → BlogWriter reruns with fix instructions (1 retry)

## Input Modes

| Mode | Args | Data Source |
|------|------|-------------|
| Industry | `industry:bakery` | `industry_pulses` collection |
| Zipcode | `zip:07110` | `zipcode_weekly_pulse` collection |
| Combined | `zip:07110 industry:bakery` | Both |
| Latest | (no args) | Most recent pulse |

Arguments: $ARGUMENTS

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## STEP 1: FETCH DATA

### For industry blogs:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"industry_pulses"}],"where":{"fieldFilter":{"field":{"fieldPath":"industryKey"},"op":"EQUAL","value":{"stringValue":"INDUSTRY"}}},"orderBy":[{"field":{"fieldPath":"createdAt"},"direction":"DESCENDING"}],"limit":1}}'
```

### For zipcode blogs:
```bash
curl -s -X POST ... (query zipcode_weekly_pulse by zipCode, latest)
```

### For combined:
Fetch both.

Parse the Firestore documents into Python dicts using the `extract_val` helper pattern.

---

## STEP 2: CALL THE AGENT

```python
cd /Users/sarthak/Desktop/hephae/hephae-forge && python3 -c "
import asyncio, json

async def main():
    from hephae_agents.social.blog_writer.agent import generate_blog_post

    result = await generate_blog_post(
        business_name='SUBJECT',
        pulse_data=PULSE_DICT,           # from zipcode_weekly_pulse (or None)
        industry_pulse=INDUSTRY_DICT,    # from industry_pulses (or None)
        latest_outputs=None,             # legacy path (or business latestOutputs)
    )

    # Write HTML to temp file
    with open('/tmp/blog-content.html', 'w') as f:
        f.write(result['html_content'])

    with open('/tmp/blog-meta.json', 'w') as f:
        json.dump({
            'title': result['title'],
            'seo_meta': result['seo_meta'],
            'social_share': result['social_share'],
            'schema_org': result['schema_org'],
            'chartjs_tag': result['chartjs_tag'],
            'seo_keywords': result['seo_keywords'],
            'seo_description': result['seo_description'],
            'slug': result['slug'],
            'word_count': result['word_count'],
            'chart_count': result['chart_count'],
            'critique': result['critique'],
            'data_sources': result['data_sources'],
        }, f, indent=2)

    print(f'Title: {result[\"title\"]}')
    print(f'Words: {result[\"word_count\"]}, Charts: {result[\"chart_count\"]}')
    print(f'Critique: {\"PASS\" if result[\"critique\"].get(\"overall_pass\") else \"FAIL\"}')
    print(f'Keywords: {result[\"seo_keywords\"]}')

asyncio.run(main())
"
```

**IMPORTANT:** Replace `SUBJECT`, `PULSE_DICT`, and `INDUSTRY_DICT` with the actual parsed Firestore data from Step 1.

Check the critique result. If `overall_pass=false`, the agent already retried once. Review the `critique.rewrite_instructions` and decide whether to proceed or re-run with adjustments.

---

## STEP 3: GENERATE HERO IMAGE

Use `stat_pills` (up to 4 short data strings) to make the hero content-specific.
Pick the 3-4 most impactful numbers from the blog and pass them as pills.
The `headline` should be the single biggest number (e.g., "35.9%"), and `subtitle` the one-line interpretation.

```python
from hephae_common.social_card import generate_universal_social_card

hero = await generate_universal_social_card(
    business_name='SUBJECT',          # e.g. "NJ Restaurant Margins 2026"
    report_type='profile',            # or "margin", "traffic", "seo", "competitive"
    headline='KEY_STAT',              # single big number, e.g. "35.9%"
    subtitle='ONE LINE INTERPRETATION',  # e.g. "avg food cost — 6 pts above target"
    stat_pills=[                      # 3-4 short data strings from the blog
        'STAT 1',  # e.g. "260/399 items critical"
        'STAT 2',  # e.g. "Eggs +38.2% YoY"
        'STAT 3',  # e.g. "$95.81 avg leakage"
    ],
)
```

---

## STEP 4: PUBLISH TO HEPHAE.CO

The blog is published to **hephae.co/blog** via the hephae-website API. This is a SEPARATE service (`hephae-co-site`) from the forge web app.

### 4a. Generate Hero Image

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge && python3 -c "
import asyncio, sys
sys.path.insert(0, 'lib/common')
from hephae_common.social_card import generate_universal_social_card

async def main():
    hero = await generate_universal_social_card(
        business_name='SUBJECT',
        report_type='profile',
        headline='KEY_STAT',
        subtitle='SUBTITLE',
        highlight='Hephae Intelligence',
    )
    if hero:
        with open('/tmp/blog-hero.png', 'wb') as f:
            f.write(hero)
        print(f'Hero: {len(hero)} bytes')
    else:
        print('Hero generation failed — proceed without')
asyncio.run(main())
"
```

### 4b. Upload Hero to CDN

```bash
python3 -c "
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('hephae-co-dev-prod-cdn-assets')
blob = bucket.blob('reports/SLUG/blog-hero.png')
blob.upload_from_filename('/tmp/blog-hero.png')
blob.cache_control = 'public, max-age=86400'
blob.patch()
print(f'https://cdn.hephae.co/reports/SLUG/blog-hero.png')
"
```

### 4c. Post to hephae.co/blog

The hephae-website (`hephae-co-site`) has a blog API:
- **Collection:** `blog_posts` (NOT `content_posts`)
- **Endpoint:** `POST /api/blog/posts`
- **Auth:** `Authorization: Bearer {FORGE_API_KEY}` (default: `hephae-forge-secret`)

```bash
WEBSITE_URL="https://hephae-co-site-hlifczmzgq-uc.a.run.app"

curl -s -X POST "$WEBSITE_URL/api/blog/posts" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer hephae-forge-secret" \
  -d "$(python3 -c "
import json, re

with open('/tmp/blog-content.html') as f:
    html = f.read()

# Extract title from H1
m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else 'Untitled'

# Extract first paragraph as excerpt
pm = re.search(r'<p>(.*?)</p>', html, re.DOTALL)
excerpt = re.sub(r'<[^>]+>', '', pm.group(1))[:250] if pm else ''

with open('/tmp/blog-meta.json') as f:
    meta = json.load(f)

print(json.dumps({
    'title': title,
    'slug': meta.get('slug', 'blog-post'),
    'content': html,
    'excerpt': excerpt,
    'coverImage': 'HERO_CDN_URL',
    'metaDescription': meta.get('seo_description', ''),
}))
")"
```

The response should be `{"success": true, "id": "..."}`.

The blog is now live at `https://hephae.co/blog/{slug}`.

### 4d. Also save to forge Firestore (for tracking)

```python
db.collection('content_posts').add({
    'type': 'blog',
    'platform': 'blog',
    'status': 'published',
    'title': title,
    'blogUrl': f'https://hephae.co/blog/{slug}',
    'heroImageUrl': hero_url,
    'hashtags': seo_keywords,
    'wordCount': word_count,
    'chartCount': chart_count,
    'critiquePass': critique.get('overall_pass', False),
    'publishedAt': datetime.utcnow(),
})
```

---

## STEP 5: REPORT

```markdown
## Blog Published

**Title:** {title}
**URL:** https://hephae.co/blog/{slug}
**Words:** {word_count} · **Charts:** {chart_count}
**Critique:** {PASS/FAIL}
**SEO Keywords:** {keywords}
**Hero Image:** {hero_url}

**Share:**
- [Twitter](https://twitter.com/intent/tweet?text={title}&url=https://hephae.co/blog/{slug})
- [LinkedIn](https://www.linkedin.com/sharing/share-offsite/?url=https://hephae.co/blog/{slug})
```

---

## Key References

| Area | File |
|------|------|
| Blog agent pipeline | `agents/hephae_agents/social/blog_writer/agent.py` |
| Blog prompts | `agents/hephae_agents/social/blog_writer/prompts.py` |
| Blog tools (charts, SEO, share) | `agents/hephae_agents/social/blog_writer/tools.py` |
| Social card generator | `lib/common/hephae_common/social_card.py` |
| Industry pulses | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Zip pulses | `lib/db/hephae_db/firestore/weekly_pulse.py` |
| **hephae-website server** | `/Users/sarthak/Desktop/hephae/hephae-website/server.js` |
| **hephae-website blog page** | `/Users/sarthak/Desktop/hephae/hephae-website/components/BlogPage.tsx` |
| **hephae-website blog post** | `/Users/sarthak/Desktop/hephae/hephae-website/components/BlogPostPage.tsx` |

## Important Notes

- Blog publishes to **`hephae-co-site`** (hephae-website), NOT `hephae-forge-web`
- Firestore collection is **`blog_posts`** (NOT `content_posts`)
- Auth key is `FORGE_API_KEY` (default: `hephae-forge-secret`)
- The website has its own SEO middleware for `/blog/:slug` that injects meta tags server-side

## What NOT To Do

- Do NOT publish to `content_posts` only — the website reads from `blog_posts`
- Do NOT skip the hero image — it's the cover image on the blog list page
- Do NOT skip the critique check — if it failed after retry, review before publishing
- Do NOT invent data — only use real pulse data
