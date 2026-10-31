# Evaluation report

## Executed checks

- Python compilation of the complete `code/` package.
- Deterministic unit tests covering multilingual authorization, non-deletion handling, historical-email resolution, flow-risk ordering, and grounded-output rejection.
- Public-sample and full-dataset output contract validation through the same atomic writer used by production.

## Public sample metrics

Measured from the actual generated `sample_generated.csv` using `python code/evaluation/main.py --actual sample_generated.csv --expected dataset/sample_output.csv`:

- Case-level deletion-status accuracy: 27/32 (84.375%).
- Exact step recall: 52/193 (26.943%).
- Aligned field accuracy across paired step positions: 416/576 (72.222%).
- Exact sequence accuracy: 1/32 (3.125%).

These public-sample measurements are not hidden-evaluation performance. They expose the current retrieval gap clearly rather than inventing a score.

## Additional participant cases

1. A historical email maps to a single stable user and must retrieve both old and current identifiers.
2. A continuous connector remains enabled after profile deletion; the plan disables it before record changes are verified.
3. A backup remains retained but restore access is enabled; the plan blocks restore rather than deleting the archive.

## Failures found and improvements made

- Initial log parsing treated a `*_started` lookup as a present record. Correlated completion records now override starts.
- SQL schema definitions can span several lines. The parser now extracts table columns across multiline definitions without executing source SQL.
- Nested service exports can contain resource-specific categories. The parser now preserves the service collection while traversing evidence.

## Scope and limitation

Gemini execution was not run without a configured `GEMINI_API_KEY`; its integration is isolated and tested through deterministic paths. The report therefore does not invent LLM accuracy, token usage, or cost figures.
