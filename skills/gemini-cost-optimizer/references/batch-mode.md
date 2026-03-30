# Gemini Batch API: Cost Optimization Guide

The Batch API is designed for high-throughput, non-urgent tasks. It offers a significant cost reduction (typically 50%) in exchange for a longer processing window (up to 24 hours).

## 1. When to Use Batch Mode
- **Non-Real-Time Workloads**: Nightly data processing, bulk document analysis, or periodic database cleaning.
- **Large Volumes**: When processing thousands of prompts where immediate response is not required.
- **Cost-Sensitive Pipelines**: Tasks where a 50% discount outweighs the 24-hour SLA.

## 2. Pricing & Efficiency
- **Cost**: 50% discount on standard standard token rates for the selected model.
- **Rate Limits**: Batch requests often have separate, higher rate limits than interactive traffic, allowing for massive parallel processing without hitting 429 errors.

## 3. Workflow
1.  **Prepare Batch File**: Create a `.jsonl` file where each line is a separate request object (with `request_id`, `method`, and `params`).
2.  **Upload to GCS**: Store the `.jsonl` file in a Google Cloud Storage bucket.
3.  **Submit Batch Job**: Call the Batch API with the GCS path.
4.  **Poll for Completion**: Monitor the job status.
5.  **Download Results**: Retrieve the output `.jsonl` from the specified GCS output path.

## 4. Optimization Tip
Combine **Batch Mode** with **Context Caching** for maximum savings. If all requests in a batch share a large common prefix, you only pay the "Cached Input" rate (which is already 90% off) *plus* the 50% Batch discount.
