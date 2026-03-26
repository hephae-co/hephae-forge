# Discovery Audit — Contact Coverage & Enrichment Due Diligence

Audits discovered businesses for contact coverage: how many have emails, contact forms, both, or nothing. Identifies enrichment gaps and surfaces actionable next steps.

## Input

| Arg | Scope |
|-----|-------|
| `job:<id>` | All businesses from a specific discovery job |
| `zip:<code>` | Single zip code |
| `county:<name>` | Named county — maps to known zip lists (essex, bergen, hudson, passaic, union) |
| `zips:07110,07042,...` | Comma-separated zip codes |
| No args / `latest` | Most recent discovery job |

Arguments:

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## STEP 1: RESOLVE SCOPE

### If `job:<id>`:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/discovery_jobs/JOB_ID" | python3 -c "
import json, sys
def extract_val(f):
    if 'stringValue' in f: return f['stringValue']
    if 'integerValue' in f: return int(f['integerValue'])
    if 'doubleValue' in f: return float(f['doubleValue'])
    if 'booleanValue' in f: return f['booleanValue']
    if 'nullValue' in f: return None
    if 'timestampValue' in f: return f['timestampValue']
    if 'arrayValue' in f: return [extract_val(v) for v in f['arrayValue'].get('values', [])]
    if 'mapValue' in f: return {k: extract_val(v) for k, v in f['mapValue'].get('fields', {}).items()}
    return str(f)
data = json.load(sys.stdin)
fields = {k: extract_val(v) for k, v in data.get('fields', {}).items()}
targets = fields.get('targets', [])
zips = list({t['zipCode'] for t in targets if isinstance(t, dict)})
print('ZIPS:', ','.join(sorted(zips)))
print('JOB_NAME:', fields.get('name', ''))
print('STATUS:', fields.get('status', ''))
p = fields.get('progress', {})
print('PROGRESS:', f\"{p.get('completedZips',0)}/{p.get('totalZips','?')} zips, {p.get('totalBusinesses',0)} biz\")
"
```

### If `latest` / no args:

Query the most recent completed discovery job:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"discovery_jobs"}],"where":{"fieldFilter":{"field":{"fieldPath":"status"},"op":"EQUAL","value":{"stringValue":"completed"}}},"orderBy":[{"field":{"fieldPath":"completedAt"},"direction":"DESCENDING"}],"limit":1}}'
```

### County zip code maps (use when `county:` arg):

```python
COUNTY_ZIPS = {
    "essex":   ["07003","07006","07007","07028","07039","07040","07041","07042","07043","07044",
                "07050","07052","07068","07079","07101","07102","07103","07104","07105","07106",
                "07107","07108","07109","07110","07111","07112","07114"],
    "bergen":  ["07401","07403","07407","07410","07417","07418","07419","07420","07422","07423",
                "07430","07432","07436","07446","07450","07451","07452","07456","07458","07461",
                "07463","07470","07481","07495","07601","07602","07603","07604","07605","07606",
                "07607","07608","07621","07624","07626","07627","07628","07630","07631","07632",
                "07640","07641","07642","07643","07644","07645","07646","07647","07648","07649",
                "07650","07652","07653","07656","07657","07660","07661","07662","07663","07666",
                "07670","07675","07676","07677"],
    "hudson":  ["07002","07029","07030","07032","07047","07086","07087","07093","07094","07096",
                "07097","07099","07302","07303","07304","07305","07306","07307","07308","07309",
                "07310","07311"],
    "passaic": ["07004","07009","07055","07058","07060","07440","07444","07457","07465","07501",
                "07502","07503","07504","07505","07506","07508","07509","07510","07511","07512",
                "07513","07514","07522","07524","07533","07538","07543","07544"],
    "union":   ["07008","07016","07023","07027","07033","07036","07060","07061","07062","07063",
                "07065","07066","07067","07080","07081","07083","07088","07090","07091","07092",
                "07201","07202","07203","07204","07205","07206","07207","07208"],
}
```

---

## STEP 2: QUERY BUSINESSES

For each zip code, query the `businesses` collection. Use parallel requests (one per zip, batched in groups of 10):

```python
import urllib.request, json, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get('TOKEN') or '...'  # from gcloud auth print-access-token
PROJECT = '...'
BASE = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents:runQuery'

def extract_val(f):
    if 'stringValue' in f: return f['stringValue']
    if 'integerValue' in f: return int(f['integerValue'])
    if 'doubleValue' in f: return float(f['doubleValue'])
    if 'booleanValue' in f: return f['booleanValue']
    if 'nullValue' in f: return None
    if 'timestampValue' in f: return f['timestampValue']
    if 'arrayValue' in f: return [extract_val(v) for v in f['arrayValue'].get('values', [])]
    if 'mapValue' in f: return {k: extract_val(v) for k, v in f['mapValue'].get('fields', {}).items()}
    return str(f)

def fetch_zip(zip_code):
    query = {
        'structuredQuery': {
            'from': [{'collectionId': 'businesses'}],
            'where': {'fieldFilter': {'field': {'fieldPath': 'zipCode'}, 'op': 'EQUAL', 'value': {'stringValue': zip_code}}},
            'limit': 500
        }
    }
    req = urllib.request.Request(BASE,
        data=json.dumps(query).encode(),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return zip_code, [d for d in data if 'document' in d]

# Fetch in parallel
results = {}
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(fetch_zip, z): z for z in zip_codes}
    for future in as_completed(futures):
        zip_code, docs = future.result()
        results[zip_code] = docs
```

---

## STEP 3: CATEGORIZE EACH BUSINESS

For each business document, classify into one of 5 buckets:

```python
def classify(fields):
    # Check both top-level and nested identity subfield
    identity = fields.get('identity') or {}
    if not isinstance(identity, dict): identity = {}

    email = fields.get('email') or identity.get('email')
    email_status = fields.get('emailStatus') or identity.get('emailStatus')
    contact_form = fields.get('contactFormUrl') or identity.get('contactFormUrl')
    contact_status = fields.get('contactFormStatus') or identity.get('contactFormStatus')
    official_url = fields.get('officialUrl') or identity.get('officialUrl') or fields.get('website')

    has_email = bool(email) or email_status == 'found'
    has_contact = bool(contact_form) or contact_status == 'found'

    if has_email and has_contact:   return 'both'
    if has_email:                   return 'email_only'
    if has_contact:                 return 'contact_only'
    if official_url:                return 'website_no_contact'  # enrichment gap
    return 'no_website'
```

**Bucket definitions:**

| Bucket | Label | Meaning |
|--------|-------|---------|
| `both` | Email + Form | Has email AND contact form URL — highest quality |
| `email_only` | Email only | Has verified email, no contact form |
| `contact_only` | Form only | Has contact form URL, no direct email |
| `website_no_contact` | Website, unenriched | Has a website but enrichment didn't run or failed |
| `no_website` | No digital presence | No website found — unreachable digitally |

---

## STEP 4: COMPUTE STATS

```python
stats = {
    'total': 0,
    'both': 0,
    'email_only': 0,
    'contact_only': 0,
    'website_no_contact': 0,  # enrichment gap — actionable
    'no_website': 0,
}

per_zip = {}   # zip_code → same dict
examples = {bucket: [] for bucket in stats}  # up to 3 examples per bucket

for zip_code, docs in results.items():
    zip_stats = {k: 0 for k in stats}
    for doc in docs:
        fields = {k: extract_val(v) for k, v in doc['document'].get('fields', {}).items()}
        bucket = classify(fields)
        stats['total'] += 1
        stats[bucket] += 1
        zip_stats['total'] += 1
        zip_stats[bucket] += 1

        # Collect examples
        name = (fields.get('identity') or {}).get('name') or doc['document']['name'].split('/')[-1]
        url = fields.get('officialUrl') or (fields.get('identity') or {}).get('officialUrl') or ''
        email_val = fields.get('email') or (fields.get('identity') or {}).get('email') or ''
        form_val = fields.get('contactFormUrl') or (fields.get('identity') or {}).get('contactFormUrl') or ''
        if len(examples[bucket]) < 3:
            examples[bucket].append({
                'name': name, 'zip': zip_code, 'url': url,
                'email': email_val, 'contactForm': form_val
            })

    per_zip[zip_code] = zip_stats

reachable = stats['both'] + stats['email_only'] + stats['contact_only']
enrichment_gap = stats['website_no_contact']
```

---

## STEP 5: PRODUCE OUTPUT

Print to console immediately:

```
=== Discovery Audit: {scope_label} ===
Total businesses:  {total}

CONTACT COVERAGE:
  Email + Form         : {both:4d}  ({both/total*100:.1f}%)
  Email only           : {email_only:4d}  ({email_only/total*100:.1f}%)
  Contact Form only    : {contact_only:4d}  ({contact_only/total*100:.1f}%)
  ─────────────────────────────────────────
  Reachable (any)      : {reachable:4d}  ({reachable/total*100:.1f}%)

GAPS:
  Website, unenriched  : {website_no_contact:4d}  ← trigger enrichment to unlock these
  No website           : {no_website:4d}  ← unreachable via digital channels

PER-ZIP (top 10 by reachable count):
  {sorted table by reachable desc}

ENRICHMENT OPPORTUNITY:
  If enrichment ran on the {website_no_contact} unenriched businesses,
  estimated uplift: +{estimated_emails} emails, +{estimated_forms} contact forms
  (based on {reachable/max(reachable+website_no_contact,1)*100:.0f}% historical enrichment rate)
```

---

## STEP 6: WRITE FINDINGS FILE

Write to `.claude/findings/discovery-audit-{scope}.md`:

```markdown
# Discovery Audit: {scope_label}
Generated: {ISO timestamp}
Scope: {zip codes or job ID}

## Summary

| Bucket | Count | % |
|--------|-------|---|
| Email + Contact Form | {both} | {pct}% |
| Email only | {email_only} | {pct}% |
| Contact Form only | {contact_only} | {pct}% |
| **Reachable (any)** | **{reachable}** | **{pct}%** |
| Website, not enriched | {website_no_contact} | {pct}% |
| No website | {no_website} | {pct}% |
| **Total** | **{total}** | 100% |

## Per-Zip Breakdown

| Zip | Total | Email | Form | Both | Unenriched | No Website |
|-----|-------|-------|------|------|-----------|------------|
{per_zip rows sorted by reachable desc}

## Examples

### With Email
{up to 3 examples with name, zip, email}

### With Contact Form Only
{up to 3 examples with name, zip, contactFormUrl}

### Website But Not Enriched
{up to 3 examples with name, zip, website URL}

## Next Steps

1. **Trigger enrichment** on {website_no_contact} unenriched businesses to extract contact info
2. **Outreach pipeline**: {reachable} businesses are ready for outreach now
3. **Low-signal zips**: {zips with 0 reachable} — consider re-running discovery with broader business types
```

Also update `.claude/findings/latest.md`.

---

## Key Codebase References

| Area | File |
|------|------|
| Discovery jobs Firestore | `lib/db/hephae_db/firestore/discovery_jobs.py` |
| Business Firestore | `lib/db/hephae_db/firestore/businesses.py` |
| Enrichment pipeline | `apps/api/hephae_api/workflows/enrichment_utils.py` |
| Discovery orchestrator | `apps/api/hephae_api/workflows/scheduled_discovery/orchestrator.py` |
| Quality gate | `apps/api/hephae_api/workflows/scheduled_discovery/quality_gate.py` |
| Email unsubscribes | `lib/db/hephae_db/firestore/email_unsubscribes.py` |
| Outreach communicator | `agents/hephae_agents/outreach/communicator.py` |

## What NOT To Do

- Do NOT modify any business documents. Read-only audit.
- Do NOT trigger enrichment or outreach. Only report and recommend.
- Do NOT count `emailStatus=None` as "no email" if `email` field has a value — check both.
- Do NOT skip the `identity` subfield — some businesses nest contact info there after enrichment.
- Do NOT report 0 reachable for a zip as a bug without first checking if enrichment ran.
