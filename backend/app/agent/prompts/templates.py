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

DECISION_GENERATION_PROMPT = """
Given the following business situation and its evidence, generate a decision
comparison for a line manager who must choose an operational intervention.

Situation Evidence:
{evidence_json}

Allowed action_type values (use these exact strings, nothing else):
- DO_NOTHING
- NOTIFY_EMPLOYEES
- ESCALATE_VENDOR
- SIMULATE_VEHICLE_REASSIGNMENT
- NODAL_CONVERSION

Only propose ESCALATE_VENDOR, SIMULATE_VEHICLE_REASSIGNMENT, or NODAL_CONVERSION
if they plausibly apply to this situation's type and evidence. Always include
DO_NOTHING and NOTIFY_EMPLOYEES as baseline comparisons. Produce 3 to 5 options.

Allowed evidence_type values (use these exact strings): OBSERVED_FACT,
HISTORICAL_EVIDENCE, ESTIMATED_SCENARIO, AI_REASONING.

Return JSON only, matching exactly this shape:
{{
  "options": [
    {{
      "action_type": "...",
      "description": "one sentence describing the intervention",
      "expected_impact": "quantified or qualitative expected outcome, grounded in the evidence",
      "estimated_cost": "e.g. Zero direct cost / Negligible / Low / Medium / High",
      "confidence": "HIGH" | "MEDIUM" | "LOW",
      "supporting_evidence": ["short evidence statement grounded in the packet", "..."],
      "assumptions": ["short assumption statement", "..."],
      "evidence_type": "..."
    }}
  ],
  "recommended_action": "the action_type judged best, must be one of the options above",
  "recommendation_reasoning": "2-3 sentences explaining why this option is preferred over the others, referencing the evidence"
}}

Rules:
- NEVER invent facts. Ground expected_impact and supporting_evidence in the numbers given in the evidence.
- If historical evidence for an option is thin, mark it evidence_type ESTIMATED_SCENARIO or AI_REASONING and lower its confidence, never HIGH.
- recommended_action must exactly match one action_type present in "options".
- Output raw JSON only. No markdown fences, no commentary before or after.
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

# ── Text-to-SQL (Ask MoveIQ) ────────────────────────────────────────
# The agent only ever sees the `analytics` schema -- one read-only view
# per grain, dimensions already joined in (see db/03_analytics_layer.sql).
# app.agent.sql_guard re-validates every query before execution regardless
# of what this prompt asked for.

ANALYTICS_SCHEMA_DESCRIPTION = """
You may query ONLY these read-only views (schema "analytics"). Never
reference any other schema or table -- it is not visible to you and the
query will be rejected before it runs.

analytics.v_trip -- one row per trip
  trip_id, trip_date, year_month, day_name, is_weekend, business_unit, office,
  vendor, shift, shift_band, cab_registration, cab_capacity, cab_fuel_type,
  product_type, trip_direction, trip_nodal, route_source, delay_reason,
  actual_escort, is_driver_nc, is_cab_nc, planned_km, traveled_km, km_variance,
  planned_start_ts, actual_start_ts, planned_duration_min, actual_duration_min,
  delay_minutes, is_delayed, is_on_time (SLA <= 15 min), planned_employee_cnt,
  actual_employee_cnt, riders_actual, noshow_cnt, capacity_utilisation,
  has_quality_issue

analytics.v_leg -- one row per employee per trip
  leg_key, trip_id, stwid, gender, emp_role, trip_date, year_month,
  business_unit, office, shift, shift_band, product_type, signintype,
  boarding_status, not_boarding_reason, is_no_show, planned_pickup_ts,
  actual_pickup_ts, pickup_delay_min, is_late_pickup, planned_km, traveled_km

analytics.v_alert -- one row per alert event
  event_id, trip_id, stwid, alert_scope, alert_date, year_month,
  business_unit, event_type, severity, severity_raw, was_triaged,
  resolution_path, start_ts, acknowledge_ts, ack_latency_min, state_text, source

analytics.v_feedback -- one row per rating submission
  feedback_key, trip_id, stwid, trip_date, year_month, business_unit,
  trip_type, route_score, driver_score, cab_score, safety_score,
  marshal_score, response_lag_min

analytics.v_billing -- one row per billed line item
  bill_line_key, trip_id, cycle_start, cycle_end, business_unit, office,
  vendor, contract_code, slab_name, billed_km, trip_cost, cost_per_km, has_zero_km

analytics.mv_daily_trip_metrics -- pre-aggregated daily rollup; prefer this
  over raw v_trip for "how does X compare to Y" or trend questions
  trip_date, year_month, business_unit, office, vendor, shift_band,
  trip_direction, trips, delayed_trips, avg_delay_min, on_time_pct,
  delay_traffic, delay_driver, delay_employee, total_km, noshows,
  avg_capacity_utilisation

analytics.mv_daily_alert_metrics -- pre-aggregated daily alert rollup
  alert_date, business_unit, event_type, alert_scope, alerts, sev1, sev2,
  triaged, median_triaged_latency_min

Rules:
- SELECT statements only. One statement, no semicolons.
- Every table referenced MUST be schema-qualified as analytics.<name>.
- Always add a LIMIT (200 or fewer) unless the query already aggregates
  down to a handful of rows.
- This demo dataset's "today" is trip_date = '2026-07-15' unless the
  manager's question names a different date or month.
"""

SQL_ROUTER_PROMPT = """
A line manager asked a question about mobility operations. Decide whether
answering it requires querying the database.

{schema}

Manager's Question: {question}

Respond with raw JSON only, matching exactly this shape:
{{
  "needs_data": true | false,
  "sql": "a single read-only SELECT against analytics.* views, or null if needs_data is false",
  "reasoning": "one short sentence on why this query answers the question, or why no query is needed"
}}

If the question is a greeting, small talk, or answerable from general
operational knowledge without specific numbers, set needs_data to false
and sql to null.
"""

ANSWER_WITH_DATA_PROMPT = """
Answer the manager's question using ONLY the query results below. Be
concise and concrete, and reference the actual numbers returned. If the
result set is empty, say plainly that no matching data was found --
do not guess.

Manager's Question: {question}

SQL Query Executed:
{sql}

Query Results (JSON rows, {row_count} total, showing up to 20):
{rows_json}

Provide a clear, direct answer in 2-4 sentences.
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
