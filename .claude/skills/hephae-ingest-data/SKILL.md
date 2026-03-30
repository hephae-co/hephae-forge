---
name: hephae-ingest-data
description: Ingest external data into the Hephae datastore — research reports, AI tool discoveries, zipcode facts, industry analysis, cached signals, or raw data. Analyzes input format and routes to the correct Firestore collection.
argument-hint: [data-type] [source-description]
user_invocable: true
---

# Ingest Data — Smart Data Ingestion Skill

You accept external data from the user (pasted text, files, URLs, or structured JSON) and ingest it into the correct Hephae Firestore collection. You analyze the input, classify it, transform it if needed, and persist it.

## Input

Arguments: $ARGUMENTS

The user may provide data in various formats:
- Raw text (research report, article, analysis)
- JSON (structured data)
- URLs to fetch
- File paths to read
- Inline descriptions of AI tools, market data, zipcode facts, etc.

## Step 1: Classify the Data

Analyze `$ARGUMENTS` and any pasted content. Determine the data type:

| Data Type | Target Collection | Example Input |
|-----------|------------------|---------------|
| `research` | `research_references` | Research reports, articles, studies with URLs |
| `ai_tool` | `ai_tools` | AI tool discovery (name, vendor, capability, pricing) |
| `tech_intel` | `tech_intelligence` | Platform landscape updates for a vertical |
| `signal` | `data_cache` | Raw API data (BLS, Census, weather, IRS, etc.) |
| `industry_pulse` | `industry_pulses` | National industry trend data |
| `zipcode_facts` | `zipcode_research` | Local facts, demographics, business landscape |
| `zipcode_profile` | `zipcode_profiles` | Data source enumeration for a zipcode |
| `food_prices` | `food_price_cache` | BLS CPI or USDA commodity prices |
| `custom` | `data_cache` | Anything else — stored as a cached signal |

If unclear, ask: "What type of data is this? (research report, AI tool, industry analysis, zipcode facts, raw signal data, or something else?)"

Also determine the **scope**:
- `vertical` / `industry_key` — e.g., "restaurant", "barber"
- `zip_code` — e.g., "07110"
- `week_of` — defaults to current ISO week if not specified
- `source` — where this data came from

## Step 2: Setup Environment

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
```

## Step 3: Transform and Ingest

Based on the classified data type, run the appropriate Python script.

### For `research` — Research References
```python
import asyncio, sys, hashlib
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.research_references import save_references

refs = [
    {
        "url": "URL_HERE",
        "title": "TITLE_HERE",
        "summary": "SUMMARY_HERE",
        "topics": ["TOPIC1", "TOPIC2"],  # e.g., ["restaurant", "pricing", "inflation"]
        "relevance_score": 0.8,
        "week_of": "WEEK_OF",
    }
]
asyncio.run(save_references(refs))
```

### For `ai_tool` — AI Tool Discovery
```python
import asyncio, sys, hashlib
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.ai_tools import upsert_tool

tool_name = "TOOL_NAME"
tool_id = hashlib.sha1(f"{tool_name}:{VENDOR}".lower().encode()).hexdigest()[:12]

asyncio.run(upsert_tool(
    tool_id=tool_id,
    tool={
        "toolName": tool_name,
        "vendor": "VENDOR",
        "technologyCategory": "CATEGORY",  # e.g., "Standalone SaaS", "POS Integration"
        "url": "URL",
        "description": "DESCRIPTION",
        "pricing": "PRICING",
        "isFree": False,
        "aiCapability": "CAPABILITY",
        "reputationTier": "GROWING",  # ESTABLISHED | GROWING | NEW
        "sourceUrl": "WHERE_DISCOVERED",
    },
    vertical="VERTICAL",  # e.g., "restaurant"
    week_of="WEEK_OF",
    is_new=True,
))
```

### For `signal` / `custom` — Cached Signal Data
```python
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.data_cache import set_cached

# TTL tiers: 7 (weekly), 30 (shared), 90 (static)
asyncio.run(set_cached(
    source="SOURCE_NAME",      # e.g., "custom_research", "external_survey"
    scope_key="SCOPE_KEY",     # e.g., "07110", "NJ", "national"
    data=DATA_DICT,            # the actual data
    ttl_days=30,
))
```

### For `zipcode_facts` — Zipcode Research
```python
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.research import save_zipcode_run

report = {
    "summary": "EXECUTIVE_SUMMARY",
    "sections": {
        "SECTION_KEY": {
            "title": "SECTION_TITLE",
            "content": "SECTION_CONTENT",
            "key_facts": ["FACT1", "FACT2", "FACT3"],
        },
        # Add more sections: business_landscape, consumer_market,
        # economic_indicators, events, trending, demographics, etc.
    },
    "sources": [
        {"title": "SOURCE_TITLE", "url": "SOURCE_URL"},
    ],
}
asyncio.run(save_zipcode_run("ZIP_CODE", report))
```

### For `tech_intel` — Technology Intelligence
```python
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.tech_intelligence import save_tech_intelligence

profile = {
    "weeklyHighlight": {"title": "HIGHLIGHT_TITLE", "detail": "DETAIL"},
    "aiOpportunities": [
        {"tool": "TOOL", "capability": "CAP", "url": "URL", "actionForOwner": "ACTION"},
    ],
    "platforms": {
        "CATEGORY": {
            "leader": "LEADER",
            "alternatives": ["ALT1", "ALT2"],
            "recentUpdate": "UPDATE",
            "trend": "TREND",
        },
    },
    "emergingTrends": ["TREND1", "TREND2"],
}
asyncio.run(save_tech_intelligence("VERTICAL", "WEEK_OF", profile))
```

### For `industry_pulse` — Industry Pulse Data
```python
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_db.firestore.industry_pulse import save_industry_pulse

asyncio.run(save_industry_pulse(
    industry_key="INDUSTRY_KEY",
    week_of="WEEK_OF",
    national_signals=SIGNALS_DICT,
    national_impact=IMPACT_DICT,
    national_playbooks=PLAYBOOKS_LIST,
    trend_summary="TREND_SUMMARY_TEXT",
    signals_used=["source1", "source2"],
))
```

## Step 4: Verify Ingestion

After ingesting, verify the data was saved:

```python
import sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_common.firebase import get_db
db = get_db()

doc = db.collection('COLLECTION').document('DOC_ID').get()
if doc.exists:
    print(f"✓ Saved to {COLLECTION}/{DOC_ID}")
    d = doc.to_dict()
    print(f"  Fields: {list(d.keys())}")
else:
    print(f"✗ Document not found!")
```

## Step 5: Suggest Next Steps

After successful ingestion, suggest:
1. **Run synthesis** — `/hephae-run-synthesis [scope]` to regenerate digests incorporating the new data
2. **Check consumers** — the chatbot, Local Intel page, and overview runner will pick up the data on next load
3. **Verify in UI** — search for the business/zipcode in the web app to see the new data

## Guidelines

- **Always ask for scope** if not provided (vertical, zip code, week)
- **Default week_of** to current ISO week
- **Parse intelligently** — if user pastes a research article, extract URL/title/summary/topics automatically
- **Batch where possible** — research_references and ai_tools support batch operations
- **Log what was saved** — show the user the document ID, collection, and key fields
- **Warn on overwrites** — if a document with the same ID exists, tell the user before overwriting
- **Support multiple items** — if user provides a list of tools or references, ingest all of them
- **After ingestion, suggest running `/hephae-run-synthesis`** to incorporate the new data into digests
