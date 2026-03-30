# Gemini Context Caching: Technical Guide

Context caching allows you to store frequently used data (like massive system prompts, large PDF libraries, or entire codebases) in the model's memory to avoid paying full price for every request.

## 1. Implicit Caching (Automatic)
Gemini 2.5+ models automatically cache long prefixes of your prompts.

- **Thresholds**: 
  - Flash: ~1,024 tokens
  - Pro: ~4,096 tokens
- **Cost**: No storage fee. 75-90% discount on input tokens for "hits".
- **Trigger**: Send the exact same prefix (including system instructions) in multiple requests.
- **Verification**: Check `usage_metadata.cached_content_token_count` in response.

## 2. Explicit Caching (Manual)
Create a specific cache object for high-volume, static context.

- **Threshold**: Minimum 32,768 tokens.
- **Cost**: 
  - Storage: ~$1.00/M tokens/hr (Flash); ~$4.50/M tokens/hr (Pro).
  - Input: Guaranteed 75-90% discount on cached tokens.
- **Workflow**: 
  1. Create cache with TTL (Time-to-Live).
  2. Reference cache ID in `GenerateContentConfig`.
  3. Update TTL to keep it alive for long-running sessions.

## 3. The "Prefix Alignment" Rule
Caching only works if the cached content is at the **very beginning** of the prompt.
- **Good**: `[Cached System Prompt] + [Cached Document] + [User Query]`
- **Bad**: `[Current Date] + [Cached System Prompt] + [User Query]` (The dynamic date at the start breaks the cache hit for everything following it).

## 4. Break-Even Analysis
Use Explicit Caching if:
- Context is > 32k tokens.
- You expect > 3 queries per hour on the same context.
- Latency reduction is a priority (caching significantly speeds up Time-to-First-Token).
