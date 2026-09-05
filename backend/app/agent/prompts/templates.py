from __future__ import annotations

PROMPT_VERSION = "v1.0"

SYSTEM_PROMPT = """
You are MoveIQ, a Mobility Decision Intelligence assistant.
You help line managers understand business situations, their impact,
and decide on the best course of action.

CRITICAL RULES:
1. NEVER invent facts. Only use the evidence provided.
2. NEVER present estimates as guarantees.
3. Always distinguish: observed facts, historical evidence, estimated scenarios, AI reasoning.
4. When historical evidence is limited, explicitly state reduced confidence.
5. Focus on what matters to the manager: employee impact, readiness, and actions.
"""

SITUATION_INVESTIGATION_PROMPT = """
Analyze the following business situation and provide:
1. A clear summary of what is happening
2. Why this matters (business impact)
3. Historical comparison (is this normal?)
4. Contributing factors with evidence
5. Recommended action with reasoning
6. Confidence level and data quality notes

Situation Evidence:
{evidence_json}

Provide your analysis as a structured JSON with these keys:
- summary: 2-3 sentence overview
- why_it_matters: business impact explanation
- historical_comparison: comparison to baseline
- contributing_factors: list of factors with evidence type labels
- recommended_action: the preferred action with reasoning
- alternative_actions: list of alternatives with trade-offs
- confidence: HIGH/MEDIUM/LOW with explanation
- data_quality_notes: any caveats about the evidence
"""

ASK_MOVE_PROMPT = """
Answer the manager's question using ONLY the provided evidence.
Be concise and actionable. Focus on what the manager needs to decide.

Available Evidence:
{evidence_json}

Manager's Question: {question}

Provide a clear, direct answer. If the evidence is insufficient,
say so explicitly rather than guessing.
"""

EXPLANATION_PROMPT = """
Explain this situation to a line manager in 2-3 sentences.
Focus on: what happened, who is affected, and what they should do.

Situation: {situation_summary}
Impact: {impact_summary}
Historical Context: {historical_context}
"""

NARRATIVE_PROMPT = """
Generate a leadership-ready narrative summary for the following situations.
Be professional, data-driven, and action-oriented.

Situations:
{situations_json}

Provide a 1-paragraph executive summary followed by key metrics.
"""
