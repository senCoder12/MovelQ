# ADR-002: Alert Episode Model

## Context
Raw alerts (`alerts_data`) are noisy, repetitive, and often orphaned. Grouping them is necessary to prevent alert fatigue and provide meaningful context to the LLM and Line Managers.

## Decision
We will group raw alerts into "Episodes" using a deterministic grouping key: `business_unit + trip_id + event_type + source`, combined with a configurable time gap threshold (`ALERT_EPISODE_GAP_MINUTES`, default 15 mins).

## Alternatives Considered
- **LLM Grouping:** Too expensive, slow, and prone to hallucinations.
- **No Grouping:** Leads to overwhelming UI and useless situation detection.

## Reason
Deterministic grouping is fast, cheap, and reliable. It handles bursty, redundant alerts effectively while keeping the logic transparent and configurable.

## Consequences
- **Positive:** Clean, manageable alert contexts. Reduced LLM token usage.
- **Negative:** Requires tuning the `ALERT_EPISODE_GAP_MINUTES` to avoid merging unrelated events or splitting related ones.
