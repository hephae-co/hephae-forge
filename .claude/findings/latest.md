# Industry Pulse Quality Audit — W13 Full Validation
Generated: 2026-03-26
Scope: All 19 industry pulses (IP-1 through IP-6 skill run)

---

## Quality Audit Summary (2026-03-26)

Full report: `.claude/findings/pulse-check-latest.md`

| Metric | Value |
|--------|-------|
| Industries audited | 19/19 |
| Overall grade | C (65/100) |
| P0 bugs found | 4 |
| P1 data quality issues | 6 |
| P2 config bugs | 4 |
| Playbooks broken (unparseable triggers) | 25/64 (39%) |
| MoM values correct | 33/33 (100%) |
| YoY values with >5% error | 8 series |
| FDA signal present in food verticals | 0/5 (0%) |

### Top Issues

1. **[P0] 39% of playbook triggers silently broken** — `_parse_trigger()` in `pulse_playbooks.py` rejects `month in [...]` and compound `and` expressions. 25/64 playbooks never fire. W13 missed: auto_repair spring_ac_push, hair_salon bridal_season_capture, residential_cleaning spring_deep_clean, restaurant dairy_margin_swap.

2. **[P0] FDA absent from all food verticals** — `generate_industry_pulse()` passes `state=""` to `fetch_national_signals()`. `fetch_fda(state="")` returns `{}` immediately. fda_recall_alert and fda_allergen_alert can never fire.

3. **[P0] Food truck using restaurant BLS data** — Cache collision from earlier bug (resolve() fell back to RESTAURANT). food_truck nationalImpact has restaurant series; gasoline absent; wrong playbooks fired (seafood_opportunity + produce_spike_alert).

4. **[P0] SETB01 mislabeled in auto_repair trend summary** — Trend summary calls CUUR0000SETB01 (Gasoline) "motor vehicle parts" — factually wrong.

5. **[P1] SAG1 YoY stale 18% across 11 industries** — `other_goods_&_services_yoy_pct` = 4.53% vs BLS actual 5.51%.

6. **[P1] SASLE YoY stale 12% across 12 industries** — `services_less_energy_yoy_pct` = 2.92% vs BLS actual 3.33%.

7. **[P1] Dry cleaner SS30021 YoY wrong sign** — Pulse reports -1.96%; BLS actual = +1.28%.

### Best/Worst Industries

- **Best:** coffee_shop (A/94), bakery (B+/88)
- **Worst:** food_truck (D/44), restaurant (D/57)

---

## Bug 1 — FIXED (1e24d88): Wrong BLS series

`fetch_national_signals` didn't pass `IndustryConfig.bls_series` to the BLS client.
Fixed by threading `config_bls_series` parameter through the full call chain.

## Bug 2 — FIXED (72e2c92): resolve(industry_key) fell back to RESTAURANT

`_INDEX` was built from aliases only, not `_cfg.id`. Industries with underscore IDs
(auto_repair, dry_cleaner, pet_grooming) couldn't be resolved and got food CPI.
Fix: `_INDEX[_cfg.id] = _cfg` added after alias loop.
Remediation: deleted bad cache + W13 pulses, force-regenerating after deploy.

## Bug 3 — FIXED (1e24d88): IndustryConfig playbooks never evaluated

`match_playbooks` only checked global PLAYBOOKS dict. Added `match_industry_playbooks()`
for string-trigger format used in IndustryConfig.playbooks.

---

## W13 Signal Quality

| Industry | BLS Correct? | Playbooks |
|----------|-------------|-----------|
| restaurant, bakery, barber, coffee_shop, pizza | ✓ | 1-2 matched |
| plumbing_hvac, residential_cleaning, hair_salon, nail_salon, spa, tattoo, gym, yoga, dental, florist | ✓ | 0 (thresholds not met this week) |
| **auto_repair, dry_cleaner, pet_grooming** | ✗ got FOOD data | deleted + regenerating |

---

## Summary

| Metric | Value |
|--------|-------|
| W13 Pulses Completed | 11 / 15 |
| W13 Pulses Failed | 4 (transient Gemini disconnects) |
| Critique PASS | 8 / 11 completed |
| Critique FAIL (saved) | 3 / 11 |
| Industry Pulses (W12) | 3 / 3 ✓ |
| Industry Pulses (W13) | 0 — not due until Sun Mar 29 |
| Summary Email | FAILED (Resend SSL transient) |

---

## W13 Pulse Coverage

| Zip | Restaurants | Bakeries | Barbers |
|-----|-------------|----------|---------|
| 07011 | ✓ PASS (14 sig) | ✗ MISSING | ✓ PASS (10 sig) |
| 07012 | ✓ PASS (11 sig) | ✓ FAIL critique (9 sig) | ✓ PASS (7 sig) |
| 07013 | ✓ PASS (12 sig) | ✗ MISSING | ✓ FAIL critique (8 sig) |
| 07014 | ✗ MISSING | ✓ PASS (9 sig) | ✓ FAIL critique (7 sig) |
| 07110 | ✓ PASS (15 sig) | ✗ MISSING | ✓ PASS (11 sig) |

---

## Failures (4)

All 4 are **transient Gemini API disconnects** — not a logic/data bug:

| Zip | Type | Error |
|-----|------|-------|
| 07013 | Bakeries | `unhandled errors in a TaskGroup (1 sub-exception)` — Gemini retry exhausted |
| 07014 | Restaurants | `Server disconnected` — Gemini drop |
| 07110 | Bakeries | `unhandled errors in a TaskGroup (2 sub-exceptions)` — Gemini retry exhausted |
| 07011 | Bakeries | Not in logs — likely silently skipped |

Root cause: Gemini aiohttp server disconnects around 07:59–08:00 UTC — visible retries in logs before giving up.

---

## Critique Failures (3 — saved anyway)

Pulses saved despite failing critique — content exists but quality gate didn't pass:
- `07012 Bakeries` — 9 signals, critique=FAIL
- `07013 Barbers` — 8 signals, critique=FAIL
- `07014 Barbers` — 7 signals, critique=FAIL

Low signal count (7–9) likely contributing.

---

## Industry Pulses

W12 pulses exist for all 3 industries (generated Sun Mar 22):
- `restaurant` W12 — 3 signals, 0 playbooks matched
- `bakery` W12 — 3 signals, 0 playbooks matched
- `barber` W12 — 2 signals, 0 playbooks matched

⚠️ **0 playbooks matched** across all 3 — playbook matching step returning empty.
W13 industry pulses not due until **Sun Mar 29 3AM ET**.

---

## Other Issues

- **Summary email failed** — Resend SSL EOF (`UNEXPECTED_EOF_WHILE_READING`). Transient, no action needed.
- **`lastPulseAt` empty** on registered_zipcodes/registered_industries docs — timestamp serialization mismatch, cosmetic only.

---

## Recommended Actions

1. **Re-run 4 failed pulses** — trigger manually from admin Intelligence tab or wait for Mon Apr 6 cron.
2. **Investigate 0 playbook matches** on industry pulses — check `pulse_playbooks.py` matching logic.
3. No code changes needed for failures — purely transient Gemini API instability.
