# Verification

Verified locally on 29 October 2026.

- 65 automated tests passed after the day-guide update, covering workflow routing, two-revision termination, research handoffs, provider failures, reference validation, budget arithmetic, API responses, progress streaming, and MCP discovery/execution. Regression cases explicitly reject the unrelated Wikipedia pages shown in the user's screenshots, validate strict candidate-ID schemas, and ensure missing hotel/food prices do not cause revisions.
- The MCP transport test launches the real local stdio server and checks a tool call without using external provider credits.
- Python dependency consistency and focused static checks passed.
- React production build and lint passed. npm audit reported zero vulnerabilities.
- Browser checks confirmed the desktop and mobile layouts, train-specific fields, and optional Pexels photo. Current output screenshots are saved as `day-guide-detail.jpg` and `budget-preview.jpg` in this folder.

## Live checks and limits

- CrewAI successfully used the configured Groq model after a compatibility adapter removed unsupported cache markers and JSON generation replaced forced-tool output conversion.
- A complete one-day live run made MCP calls, generated sourced activities, performed review, used both allowed revisions, and finalized a result. The review remained `NEEDS_REVISION`, so the result was partial.
- The live test originally required unconditional reviewer approval and failed that assertion. Its acceptance check now reflects the agreed behavior: either approval or a partial result with explicit issues after two revisions. The revised live assertion has not been rerun to avoid further provider consumption; deterministic tests cover both outcomes.
- Groq's free-tier throttling made the live run take about five minutes. Prompt evidence is compacted, full tool responses remain in the ledger, and long quota waits are surfaced as unavailable rather than silently sleeping for hours.
- Makcorps accepted the configured key for city mapping and account access. A dated Goa `/city` hotel search returned HTTP 400. The adapter reports unavailable hotel information rather than inventing a property or price. Live hotel retrieval is therefore not confirmed for that request.
- The Makcorps city API does not specify a nightly or stay-total basis for vendor quotes. Unconfirmed totals remain excluded from budget arithmetic.

Live output quality and provider availability should not be inferred from mocked test success. The optional live test remains available for checking another date, destination, or account quota.

## Day-guide verification

Live Wikipedia queries for Goa produced 16 locally verified attractions and 12 foods, including Fort Aguada, Chapora Fort, the Basilica of Bom Jesus, bebinca, cafreal, and xacuti. Three days of real MCP evidence were collected and used for live CrewAI writing/review checks. After reducing prompts and writing one day at a time, a complete three-day guide with eight visits and two foods per day was generated.

The live reviewer objected only to missing price data. The explicit review policy now retains that as an informational note and does not request itinerary revisions for it; this policy was applied to the saved response for the UI check. Missing hotel costs use the labelled editable allowance, not a provider quote.

The revised itinerary and budget screens were checked using that saved live response in an isolated local preview server, avoiding more provider calls. This is a replay of real source/agent output, not a fresh full live run of the final strict-schema implementation. Free-tier Groq throttling remains a runtime limitation; the source-guide path was also checked with real collected Wikipedia evidence and simulated model unavailability.

A fresh live single-day strict-schema CrewAI call also succeeded with the configured GPT-OSS 20B writer, returning exactly the supplied place and food IDs. The complete 65-test suite passed after the final provider compatibility change.
