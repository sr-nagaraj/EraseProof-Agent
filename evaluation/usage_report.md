# Usage report

## Final deterministic run

- Provider/model calls: none.
- Input tokens: 0.
- Output tokens: 0.
- Total and average tokens per request: 0 / 0.
- Estimated cost: 0.

The root-level `output.csv` full run processed 518 cases with this configuration and made no model call. The default submission run is deterministic when `GEMINI_API_KEY` is absent. These are measured configuration values, not estimates.

## Optional Gemini mode

When `GEMINI_API_KEY` is configured, the authorization agent may call the configured `GEMINI_MODEL` only for requests that the deterministic multilingual classifier cannot classify. The shared client records provider-reported input/output usage per model, caches validated JSON responses by prompt/model/configuration, and exposes the totals through the orchestrator. Pricing is intentionally configured with `GEMINI_INPUT_COST_PER_MILLION` and `GEMINI_OUTPUT_COST_PER_MILLION`; set current published values before reporting any Gemini cost. Do not claim a cost until a real run has produced usage.
