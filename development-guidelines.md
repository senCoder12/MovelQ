# Development Guidelines

## Core Rules

1. **Domain logic NOT in API routes:** API routes must only handle HTTP concerns and call domain services.
2. **Frontend NOT calculating backend business metrics:** The UI is a view layer. All complex metrics come pre-calculated from the API.
3. **LLM NOT processing raw data:** Never send raw DB rows to the LLM. Use structured Evidence Packets.
4. **Data access through repositories/services:** No raw SQL queries inside route handlers or domain entities.
5. **Configuration NOT hard-coded:** Use environment variables and `pydantic-settings`.
6. **All domain concepts require explicit models:** Use Pydantic models for concepts like `Shift`, `Situation`, `Episode`.
7. **Situation correlation logic centralized:** Detect situations in a dedicated domain service.
8. **Alert episode logic centralized:** Alert grouping happens in one place.
9. **New situation types require tests:** Write unit tests when adding new situation patterns.
10. **New API endpoints require docs:** Update OpenAPI/Swagger and README when adding endpoints.
11. **Breaking changes require documentation:** Notify the team and update architecture docs.
12. **Don't bypass service/repository boundaries:** Keep layers decoupled.
13. **Don't add infrastructure without justification:** Stick to Neon + FastAPI + React unless heavily justified.
14. **Avoid duplicated business rules:** Use shared utility functions for shared logic.
15. **Preserve backward compatibility:** Do not break existing API consumers (like Replay engine).

---

## How-To Guides

### Add a New Situation Type
1. Define the type in `SituationType` enum (`app/domain/models.py`).
2. Implement detection logic in `SituationService`.
3. Create unit tests for the detection logic.
4. Update the LLM prompt context to understand the new type.

### Add a New Action
1. Define the action in `ActionType` enum.
2. Implement the executor in `ActionService`.
3. Ensure it writes an outcome record to the database.

### Add a New LLM Provider
1. Implement the `LLMProvider` interface.
2. Update the DI container or factory to support the new provider based on env vars.

### Replace Neon with Another Store
1. Create new implementations of all Repository interfaces.
2. Update database connection settings.
3. Keep the domain logic intact.
