# Pulse -- verification targets.

AGENT_PY := pulse/agent/.venv/bin/python

.PHONY: verify-llm-free
## Prove signal generation is LLM-free: static import guard, runtime
## interception, degraded-mode scan and the Java job's model independence.
## Writes docs/llm_free_verification.txt and exits non-zero on any failure.
verify-llm-free:
	@$(AGENT_PY) pulse/scripts/verify_llm_free.py

.PHONY: test
test:
	@cd pulse/agent && .venv/bin/python -m pytest tests/ -q
	@cd pulse/backend && mvn -q -o test
