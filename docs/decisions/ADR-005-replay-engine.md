# ADR-005: Replay Engine

## Context
We need a way to demonstrate the system and test the agentic loop realistically, given that our dataset is historical (e.g., July 2026).

## Decision
We will build a Replay Engine that accepts a target simulated date/time, reads historical events up to that point, and injects them into the system as if they are happening live.

## Alternatives Considered
- **Mock Data Generators:** Hard to capture the true complexity and edge cases of real mobility data.
- **Static Demo Dashboards:** Does not demonstrate the dynamic, agentic nature of the system.

## Reason
Using actual historical data played back sequentially proves the system works on real-world complexity and perfectly supports demo walkthroughs.

## Consequences
- **Positive:** Highly realistic demos, excellent for integration testing.
- **Negative:** Adds complexity to the backend (managing simulated time vs real time).
