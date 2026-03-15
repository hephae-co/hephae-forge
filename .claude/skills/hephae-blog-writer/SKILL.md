---
name: hephae-blog-writer
description: Generate and publish a data-driven blog post on hephae.co analyzing local business trends (social media usage, competitive landscape, etc.) for a given zip code or area and business type.
argument-hint: [zip-code business-type]
user_invocable: true
---

# Blog Writer — Research-Driven Blog Generator & Publisher

You generate and publish data-driven blog posts on hephae.co by aggregating real business data from Firestore for a locality, analyzing it, and using the blog writer agent to produce a full HTML article.

## Input

Arguments: $ARGUMENTS

### Step 1: Gather Inputs

Parse `$ARGUMENTS` for a zip code (5-digit) and business type. If missing, ask:

**If no zip code:**
Ask: "What zip code or area should I analyze? (e.g., `07110`, `07001`)"

**If no business type:**
Ask: "What business type? (e.g., `Restaurants`, `Bakeries`, `Hair Salons`)"

**Optionally ask for blog angle:**
Ask: "What angle should the blog focus on? Options:
1. **Social media landscape** — how businesses in the area use social media
2. **Competitive landscape** — competitive dynamics and market gaps
3. **SEO health** — website and digital presence quality
4. **Full market analysis** — all-of-the-above overview
(Default: social media landscape)"

Store the chosen angle. Default to "social media landscape" if user doesn't specify.

---

## Step 2: Authentication & Data Collection

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

### 2a. Find businesses in the zip code

Query Firestore for businesses with the target zip code that have analysis data:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE:runQuery" \
  -H "Content-Type: application/json" \
  -d '{
    "structuredQuery": {
      "from": [{"collectionId": "businesses"}],
      "where": {
        "fieldFilter": {
          "field": {"fieldPath": "sourceZipCode"},
          "op": "EQUAL",
          "value": {"stringValue": "<ZIP_CODE>"}
        }
      },
      "limit": 50
    }
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
businesses = []
for item in data:
    doc = item.get('document', {})
    if not doc: continue
    fields = doc.get('fields', {})
    name = fields.get('name', {}).get('stringValue', '?')
    slug = doc.get('name', '').split('/')[-1]

    # Check for social data
    social_links = fields.get('socialLinks', {}).get('mapValue', {}).get('fields', {})
    social_metrics = fields.get('socialProfileMetrics', {}).get('mapValue', {}).get('fields', {})
    latest_outputs = fields.get('latestOutputs', {}).get('mapValue', {}).get('fields', {})
    official_url = fields.get('officialUrl', {}).get('stringValue', '')
    category = fields.get('category', {}).get('stringValue', '')

    has_social = len(social_links) > 0 or len(social_metrics) > 0
    has_analysis = len(latest_outputs) > 0

    platforms = list(social_links.keys())

    print(json.dumps({
        'name': name, 'slug': slug, 'officialUrl': official_url,
        'category': category, 'platforms': platforms,
        'hasSocial': has_social, 'hasAnalysis': has_analysis,
    }))
print(f'---TOTAL: {len([i for i in data if i.get(\"document\")])} businesses')
"
```

If fewer than 3 businesses found, tell the user: "Only X businesses found in ZIP. Run `/hephae-run-forge <ZIP> <TYPE>` first to discover and analyze businesses, then try again."

### 2b. Fetch detailed social data for each business

For each business with social data, fetch the full document to extract socialLinks, socialProfileMetrics, and latestOutputs:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/businesses/<SLUG>" | python3 -c "
import sys, json

doc = json.load(sys.stdin)
fields = doc.get('fields', {})

def extract_map(field_name):
    mv = fields.get(field_name, {}).get('mapValue', {}).get('fields', {})
    result = {}
    for k, v in mv.items():
        if 'stringValue' in v: result[k] = v['stringValue']
        elif 'integerValue' in v: result[k] = int(v['integerValue'])
        elif 'doubleValue' in v: result[k] = v['doubleValue']
        elif 'mapValue' in v:
            inner = {}
            for ik, iv in v['mapValue'].get('fields', {}).items():
                if 'stringValue' in iv: inner[ik] = iv['stringValue']
                elif 'integerValue' in iv: inner[ik] = int(iv['integerValue'])
                elif 'doubleValue' in iv: inner[ik] = iv['doubleValue']
            result[k] = inner
    return result

social_links = extract_map('socialLinks')
social_metrics = extract_map('socialProfileMetrics')

# Extract key analysis outputs
latest = extract_map('latestOutputs')
outputs = {}
for key in ('seo_auditor', 'competitive_analyzer', 'traffic_forecaster', 'margin_surgeon', 'social_media_auditor'):
    if key in latest and isinstance(latest[key], dict):
        outputs[key] = {k: v for k, v in latest[key].items() if k in ('score', 'summary', 'reportUrl', 'competitor_count', 'avg_threat_level', 'menu_item_count', 'totalLeakage', 'peak_slot_score')}

name = fields.get('name', {}).get('stringValue', '?')
print(json.dumps({
    'name': name,
    'socialLinks': social_links,
    'socialMetrics': social_metrics,
    'analysisOutputs': outputs,
}, indent=2))
"
```

Run this for each business (up to 15). You can run multiple curl commands in parallel.

### 2c. Also fetch area research if available

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE:runQuery" \
  -H "Content-Type: application/json" \
  -d '{
    "structuredQuery": {
      "from": [{"collectionId": "area_research"}],
      "where": {
        "compositeFilter": {
          "op": "AND",
          "filters": [
            {"fieldFilter": {"field": {"fieldPath": "zipCodes"}, "op": "ARRAY_CONTAINS", "value": {"stringValue": "<ZIP_CODE>"}}},
            {"fieldFilter": {"field": {"fieldPath": "businessType"}, "op": "EQUAL", "value": {"stringValue": "<BUSINESS_TYPE>"}}}
          ]
        }
      },
      "limit": 1
    }
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data:
    doc = item.get('document', {})
    if doc:
        fields = doc.get('fields', {})
        area = fields.get('area', {}).get('stringValue', '')
        print(f'Area: {area}')
        print(f'Doc ID: {doc[\"name\"].split(\"/\")[-1]}')
"
```

---

## Step 3: Aggregate & Analyze

Now that you have all the data, build an aggregated analysis. Do NOT use any tools for this — use your own analytical reasoning.

### For "Social media landscape" angle:

Aggregate across all businesses:
- **Platform adoption rates**: What % of businesses have Instagram? Facebook? Twitter/X? TikTok? Yelp?
- **Follower distribution**: Median followers per platform, top performers, businesses with zero presence
- **Engagement patterns**: Posting frequency trends, engagement indicators
- **Content themes**: Common hashtags, content types
- **Gaps**: Businesses with no social presence at all, businesses on only 1 platform
- **Standout performers**: Which businesses are crushing it and why

### For "Competitive landscape" angle:

- Average/median SEO scores across businesses
- Competitive density, threat levels
- Market gaps and opportunities
- Pricing landscape (from margin data)

### For "SEO health" angle:

- Distribution of SEO scores across businesses
- Common weaknesses (technical, content, UX, performance, authority)
- Best/worst performers
- Website presence rates

### For "Full market analysis":

Combine all of the above.

Build the analysis as a structured text document (markdown-style) — this becomes the input for the blog writer.

---

## Step 4: Generate the Blog Post

Use the API to generate the blog. Start the API if needed (same as hephae-run-forge skill).

First check if the API is running:
```bash
curl -s http://localhost:8080/health 2>/dev/null | head -1
```

If not running:
```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge/apps/api && .venv/bin/uvicorn hephae_api.main:app --port 8080 &
```

Then call the blog writer directly via Python (bypasses auth):

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge && .venv/bin/python3 -c "
import asyncio, json, sys

async def main():
    from hephae_agents.social.blog_writer import generate_blog_post

    # The aggregated data goes in as latestOutputs format
    # We pack it as a 'marketing_swarm' output since that's what the blog writer expects for social analysis
    latest_outputs = {
        'marketing_swarm': {
            'summary': '''<PASTE YOUR AGGREGATED ANALYSIS HERE>''',
            'score': 0,
        },
        # Include any individual business analysis data you want highlighted
        'seo_auditor': {
            'summary': '''<AGGREGATE SEO SUMMARY>''',
            'score': <MEDIAN_SCORE>,
        },
        'competitive_analyzer': {
            'summary': '''<AGGREGATE COMPETITIVE SUMMARY>''',
            'competitor_count': <TOTAL_COMPETITORS>,
        },
    }

    result = await generate_blog_post(
        business_name='<BUSINESS_TYPE> in <ZIP_CODE>',
        latest_outputs=latest_outputs,
    )

    print(json.dumps({
        'title': result['title'],
        'word_count': result['word_count'],
        'data_sources': result['data_sources'],
        'html_length': len(result['html_content']),
    }))

    # Write HTML to temp file for upload
    with open('/tmp/hephae-blog-output.html', 'w') as f:
        f.write(result['html_content'])

    print('HTML written to /tmp/hephae-blog-output.html')

asyncio.run(main())
" 2>&1
```

**IMPORTANT:** Replace the placeholder values in the Python script with the ACTUAL aggregated data you built in Step 3. Pack the analysis into the `summary` fields — the blog writer agent will use these to craft the narrative.

The business_name should be descriptive of the locality, e.g., "Restaurants in Livingston, NJ (07039)" or "Bakeries in Newark, NJ (07110)".

---

## Step 5: Upload & Publish

### 5a. Wrap in Hephae blog template and upload to CDN

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge && .venv/bin/python3 -c "
import asyncio, json

async def main():
    from hephae_common.report_templates import build_blog_report
    from hephae_common.report_storage import upload_report, generate_slug
    from hephae_common.social_card import generate_universal_social_card

    # Read the generated HTML
    with open('/tmp/hephae-blog-output.html') as f:
        article_html = f.read()

    slug = generate_slug('<BUSINESS_TYPE>-in-<ZIP_CODE>')
    title = '<BLOG_TITLE_FROM_STEP_4>'

    # Generate hero image
    hero_bytes = await generate_universal_social_card(
        business_name='<BUSINESS_TYPE> in <AREA>',
        report_type='profile',
        headline='<HEADLINE_STAT>',
        subtitle='<SUBTITLE>',
        highlight='Hephae Blog',
    )

    # Build full HTML page with Hephae branding
    full_html = build_blog_report(
        article_html=article_html,
        business_name='<BUSINESS_TYPE> in <AREA>',
        title=title,
        hero_image_url='',
        primary_color='#4F46E5',
        logo_url='',
        favicon_url='',
    )

    # Upload to CDN
    report_url = await upload_report(
        slug=slug,
        report_type='blog',
        html_content=full_html,
    )

    print(f'Blog URL: {report_url}')

    # Save as content_post in Firestore
    from hephae_db.firestore.content import save_content_post
    post_id = await save_content_post({
        'type': 'blog',
        'platform': 'blog',
        'status': 'published',
        'sourceType': 'combined_context',
        'sourceId': slug,
        'sourceLabel': '<BUSINESS_TYPE> in <ZIP_CODE>',
        'content': article_html,
        'title': title,
        'hashtags': [<KEYWORDS>],
        'publishedAt': __import__('datetime').datetime.utcnow(),
    })
    print(f'Content post ID: {post_id}')

asyncio.run(main())
" 2>&1
```

### 5b. Extract and report the blog URL

Parse the output for the `Blog URL:` line. This is the public CDN URL.

---

## Step 6: Report to User

Present the final result:

```
## Blog Published

**Title:** <title>
**URL:** <cdn_url>
**Word Count:** <count>
**Data Sources:** <sources>
**Keywords:** <hashtags>

Based on analysis of <N> <business_type> businesses in <zip_code>:
- <key finding 1>
- <key finding 2>
- <key finding 3>
```

---

## Important Notes

- The blog writer agent needs `GEMINI_API_KEY` in the environment.
- If no businesses have been discovered/analyzed in the target zip code, the user needs to run `/hephae-run-forge` first.
- The aggregated analysis you build in Step 3 is the most critical part — the blog quality depends entirely on the richness and specificity of the data you feed into it.
- Blog posts are uploaded to `cdn.hephae.co` and saved to the `content_posts` Firestore collection.
- Always include real data points (actual follower counts, actual scores, actual business names) — never fabricate statistics.
- The blog angle determines what data to prioritize, but include cross-cutting insights when interesting correlations exist.
