---
name: hephae-run-synthesis
description: Run the Hephae synthesis pipeline — generates industry and zip-level weekly digests from existing pulse data. Can target a specific zip code, industry, or run the full cycle.
argument-hint: [zip-code|industry-key|all]
user_invocable: true
---

# Run Synthesis — Weekly Digest Generator

You run the Hephae synthesis pipeline locally, which combines existing weekly pulse outputs (zip pulse, industry pulse, tech intelligence) into pre-computed digest documents.

## Input

Arguments: $ARGUMENTS

### Step 1: Parse Arguments

Parse `$ARGUMENTS`:
- **Zip code** (5-digit): Run synthesis for that specific zip code
- **Industry key** (e.g., `restaurant`, `barber`): Run industry digest only
- **`all`** or empty: Run full synthesis cycle (all industries + all registered zips)

If no arguments provided, ask: "What should I synthesize? A zip code (e.g., `07110`), industry (e.g., `restaurant`), or `all`?"

### Step 2: Determine Week

Calculate the current ISO week:

```bash
python3 -c "from datetime import datetime; d=datetime.utcnow(); print(f'{d.year}-W{d.isocalendar()[1]:02d}')"
```

### Step 3: Ensure Environment

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge
source .venv/bin/activate
```

Verify packages are importable:

```bash
python3 -c "from hephae_agents.synthesis.runner import generate_industry_digest, generate_zip_digest; print('OK')"
```

If this fails, install packages:
```bash
pip install -e lib/common -e lib/db -e lib/integrations -e agents
```

### Step 4: Run Synthesis

Based on the parsed input, run one of the following Python scripts:

#### For a specific industry:
```bash
python3 -c "
import asyncio
from hephae_agents.synthesis.runner import generate_industry_digest

async def main():
    result = await generate_industry_digest('INDUSTRY_KEY', 'WEEK_OF')
    print(f'Industry digest: {result.get(\"id\", \"failed\")}')
    if result.get('narrative'):
        print(f'Narrative preview: {result[\"narrative\"][:200]}...')
    if result.get('keyTakeaways'):
        for t in result['keyTakeaways']:
            print(f'  • {t}')

asyncio.run(main())
"
```

#### For a specific zip code:
First, look up the zip's city/state/county and business type from registered_zipcodes:

```bash
python3 -c "
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_common.firebase import get_db

async def main():
    db = get_db()
    doc = db.collection('registered_zipcodes').document('ZIP_CODE').get()
    if doc.exists:
        d = doc.to_dict()
        print(f'city={d.get(\"city\")}, state={d.get(\"state\")}, county={d.get(\"county\")}')
        print(f'businessTypes={d.get(\"businessTypes\", [\"Restaurants\"])}')
    else:
        print('Not registered — using defaults')

asyncio.run(main())
"
```

Then generate the industry digest first (if not already done), then the zip digest:

```bash
python3 -c "
import asyncio
from hephae_agents.synthesis.runner import generate_industry_digest, generate_zip_digest

async def main():
    # Industry digest first
    print('=== Industry Digest ===')
    ind = await generate_industry_digest('INDUSTRY_KEY', 'WEEK_OF')
    print(f'ID: {ind.get(\"id\", \"failed\")}')

    # Zip digest
    print()
    print('=== Zip Digest ===')
    digest = await generate_zip_digest(
        zip_code='ZIP_CODE',
        business_type='BUSINESS_TYPE',
        week_of='WEEK_OF',
        city='CITY',
        state='STATE',
        county='COUNTY',
        industry_key='INDUSTRY_KEY',
    )
    print(f'ID: {digest.get(\"id\", \"failed\")}')
    if digest.get('weeklyBrief'):
        print(f'Brief: {digest[\"weeklyBrief\"][:300]}...')
    if digest.get('actionItems'):
        print('Action items:')
        for a in digest['actionItems']:
            print(f'  • {a}')
    if digest.get('localFacts'):
        print('Local facts:')
        for f in digest['localFacts']:
            print(f'  • {f}')

asyncio.run(main())
"
```

#### For all (full cycle):
```bash
python3 -c "
import asyncio, sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
sys.path.insert(0, 'lib/integrations')
sys.path.insert(0, 'agents')
from hephae_common.firebase import get_db
from hephae_agents.synthesis.runner import generate_industry_digest, generate_zip_digest
from datetime import datetime

async def main():
    db = get_db()
    now = datetime.utcnow()
    week_of = f'{now.year}-W{now.isocalendar()[1]:02d}'
    print(f'Synthesis cycle for {week_of}')

    # Get active zips
    docs = db.collection('registered_zipcodes').where('status', '==', 'active').get()
    zips = [d.to_dict() for d in docs]
    print(f'Found {len(zips)} active zip codes')

    # Collect unique industries
    industries = set()
    for z in zips:
        for bt in z.get('businessTypes', ['Restaurants']):
            bt_lower = bt.lower()
            if 'restaurant' in bt_lower or 'food' in bt_lower:
                industries.add('restaurant')
            elif 'barber' in bt_lower or 'salon' in bt_lower:
                industries.add('barber')
            else:
                industries.add('restaurant')

    # Phase 1: Industry digests
    print(f'\n=== Phase 1: {len(industries)} industry digests ===')
    for ind in industries:
        try:
            result = await generate_industry_digest(ind, week_of)
            print(f'  ✓ {ind}: {result.get(\"id\", \"failed\")}')
        except Exception as e:
            print(f'  ✗ {ind}: {e}')

    # Phase 2: Zip digests
    total = sum(len(z.get('businessTypes', ['Restaurants'])) for z in zips)
    print(f'\n=== Phase 2: {total} zip digests ===')
    for z in zips:
        for bt in z.get('businessTypes', ['Restaurants']):
            bt_lower = bt.lower()
            ind_key = 'barber' if ('barber' in bt_lower or 'salon' in bt_lower) else 'restaurant'
            try:
                result = await generate_zip_digest(
                    zip_code=z['zipCode'],
                    business_type=bt,
                    week_of=week_of,
                    city=z.get('city', ''),
                    state=z.get('state', ''),
                    county=z.get('county', ''),
                    industry_key=ind_key,
                )
                print(f'  ✓ {z[\"zipCode\"]}/{bt}: {result.get(\"id\", \"failed\")}')
            except Exception as e:
                print(f'  ✗ {z[\"zipCode\"]}/{bt}: {e}')

    print('\nDone!')

asyncio.run(main())
"
```

### Step 5: Verify Results

After running, check what was saved:

```bash
python3 -c "
import sys
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
from hephae_common.firebase import get_db

db = get_db()

# Check industry digests
print('=== Industry Digests ===')
for doc in db.collection('industry_digests').order_by('generatedAt', direction='DESCENDING').limit(5).get():
    d = doc.to_dict()
    print(f'  {doc.id}: narrative={len(d.get(\"narrative\",\"\"))} chars, takeaways={len(d.get(\"keyTakeaways\",[]))}')

print()
print('=== Weekly Digests ===')
for doc in db.collection('weekly_digests').order_by('generatedAt', direction='DESCENDING').limit(5).get():
    d = doc.to_dict()
    print(f'  {doc.id}: brief={len(d.get(\"weeklyBrief\",\"\"))} chars, actions={len(d.get(\"actionItems\",[]))}')
"
```

### Step 6: Report Results

Show the user:
1. How many digests were generated
2. Preview of the narrative/brief content
3. Action items generated
4. Any errors that occurred
5. Firestore document IDs for reference
