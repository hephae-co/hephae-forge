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

```python
from hephae_common.social_card import generate_universal_social_card

hero = await generate_universal_social_card(
    business_name='SUBJECT',
    report_type='profile',
    headline='KEY_STAT_FROM_BLOG',
    subtitle='SUBTITLE',
    highlight='Hephae Intelligence',
)
```

---

## STEP 4: PUBLISH

### 4a. Assemble full HTML page

Read `/tmp/blog-content.html` and `/tmp/blog-meta.json`, then wrap with the Hephae template:

```python
from hephae_common.report_templates import build_blog_report
from hephae_common.report_storage import upload_report

full_html = build_blog_report(
    article_html=blog_html + social_share_html,
    business_name=subject,
    title=title,
    hero_image_url=hero_url,
    primary_color='#d97706',
)

# Inject SEO meta, Schema.org, and Chart.js into <head>
full_html = full_html.replace('</head>', f'{seo_meta}\n{schema_org}\n{chartjs_tag}\n</head>')

url = await upload_report(slug=slug, report_type='blog', html_content=full_html)
```

### 4b. Save to Firestore

```python
db.collection('content_posts').add({
    'type': 'blog',
    'platform': 'blog',
    'status': 'published',
    'title': title,
    'content': blog_html,
    'blogUrl': url,
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
**URL:** {url}
**Words:** {word_count} · **Charts:** {chart_count}
**Critique:** {PASS/FAIL}
**SEO Keywords:** {keywords}

**Share:**
- [Twitter]({twitter_share_url})
- [LinkedIn]({linkedin_share_url})
```

---

## Key References

| Area | File |
|------|------|
| Blog agent pipeline | `agents/hephae_agents/social/blog_writer/agent.py` |
| Blog prompts | `agents/hephae_agents/social/blog_writer/prompts.py` |
| Blog tools (charts, SEO, share) | `agents/hephae_agents/social/blog_writer/tools.py` |
| Report templates | `lib/common/hephae_common/report_templates.py` |
| Report upload (GCS) | `lib/common/hephae_common/report_storage.py` |
| Social card generator | `lib/common/hephae_common/social_card.py` |
| Industry pulses | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Zip pulses | `lib/db/hephae_db/firestore/weekly_pulse.py` |

## What NOT To Do

- Do NOT write blog HTML yourself — the agent handles it (with charts via tools).
- Do NOT skip the critique check — if it failed after retry, review before publishing.
- Do NOT publish without hero image — it's the OG image for social sharing.
- Do NOT invent data to pass to the agent — only use real pulse data.
