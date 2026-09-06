# ADR-003: Situation Domain Model

## Context
Signals and alert episodes need to be elevated into actionable business contexts for the Line Manager. We need a clear lifecycle for these entities.

## Decision
We will implement a `Situation` domain model with a defined lifecycle enum (`DETECTED`, `INVESTIGATING`, `ACTION_RECOMMENDED`, `ACTIONED`, `VERIFYING`, `RESOLVED`) and specific situation types. A deduplication strategy will prevent multiple open situations for the same underlying issue.

## Alternatives Considered
- **Stateless Alerts:** Fails to capture the workflow of resolving issues.
- **Complex BPMN Engine:** Overkill for the current MVP scope.

## Reason
A finite state machine for Situations maps perfectly to the Line Manager's workflow and allows the frontend to easily display actionable states.

## Consequences
- **Positive:** Clear business logic, easy to test, supports UI states directly.
- **Negative:** Requires strict state transition enforcement in the backend.
