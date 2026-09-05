# ADR-004: Selective LLM Architecture

## Context
LLMs are powerful but slow, expensive, and non-deterministic if given raw, noisy tabular data.

## Decision
We will use a "Selective LLM" architecture.
1. Never pass raw data rows to the LLM.
2. Build structured "Evidence Packets" (JSON) deterministically via SQL/Python.
3. Pass Evidence Packets to the LLM for reasoning, action recommendation, and chat.
4. Implement caching and only trigger LLM calls on "material changes" (e.g., > 5% metric drift).

## Alternatives Considered
- **LLM Data Analyst:** Having the LLM query SQL directly. High risk of bad queries and slow response.
- **Rules Only:** Lacks the nuance and natural language explanation required for the "Ask Move" feature.

## Reason
This approach balances the reliability and speed of deterministic code with the reasoning and summarization strengths of an LLM.

## Consequences
- **Positive:** High performance, predictable costs, accurate reasoning.
- **Negative:** Requires engineering effort to build and maintain the Evidence Packet schemas.
