-- vanta -- the EV billing insight only, with vanta's own figures.
--
-- Same business key as catalyst's third insight ('ins_003') on purpose: insight ids are
-- unique per tenant, so the switcher moving between catalyst and vanta has to return
-- genuinely different rows for the same id. A leak would be obvious.

INSERT INTO insight (
    tenant_id, insight_id, severity,
    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
    entity_dim, entity_ref, entity_name,
    impact_affected_trips, impact_late_minutes_total, impact_cost_inr_month,
    data_quality_excluded_pct, data_quality_confidence,
    narrative_headline, narrative_body, recommended_actions, coincident_events
) VALUES (
    'vanta', 'ins_003', 64,
    'ev_contract_mismatch_rate', 'EV-contract trips run on non-EV fuel', 12.39, '%', 8426, 'trailing_30d',
    'contract_type', 'EV', 'EV Contract',
    1044, NULL, 1310000.0,
    1.2, 'medium',
    '1,044 trips billed on EV contracts ran on petrol or diesel',
    $doc$12.39% of EV-contract rows (1,044 of 8,426) show actual_cab_fuel_type as petrol or diesel instead of electric. The mismatch rate is half again what the fleet average looks like, on a smaller contract base.$doc$,
    $json$[{"type":"ticket","title":"Audit EV-contract billing vs actual fuel type","draft":"1,044 trips billed under EV contract terms ran on non-electric vehicles.","rationale":"12.39% mismatch on the EV contract base; direct billing exposure."}]$json$::jsonb,
    '[]'::jsonb
)
ON CONFLICT (tenant_id, insight_id) DO UPDATE SET
    severity                  = EXCLUDED.severity,
    metric_id                 = EXCLUDED.metric_id,
    metric_name               = EXCLUDED.metric_name,
    metric_value              = EXCLUDED.metric_value,
    metric_unit               = EXCLUDED.metric_unit,
    metric_n                  = EXCLUDED.metric_n,
    metric_window             = EXCLUDED.metric_window,
    entity_dim                = EXCLUDED.entity_dim,
    entity_ref                = EXCLUDED.entity_ref,
    entity_name               = EXCLUDED.entity_name,
    impact_affected_trips     = EXCLUDED.impact_affected_trips,
    impact_late_minutes_total = EXCLUDED.impact_late_minutes_total,
    impact_cost_inr_month     = EXCLUDED.impact_cost_inr_month,
    data_quality_excluded_pct = EXCLUDED.data_quality_excluded_pct,
    data_quality_confidence   = EXCLUDED.data_quality_confidence,
    narrative_headline        = EXCLUDED.narrative_headline,
    narrative_body            = EXCLUDED.narrative_body,
    recommended_actions       = EXCLUDED.recommended_actions,
    coincident_events         = EXCLUDED.coincident_events,
    updated_at                = now();

DELETE FROM insight_reference   WHERE tenant_id = 'vanta';
DELETE FROM insight_attribution WHERE tenant_id = 'vanta';
DELETE FROM insight_control     WHERE tenant_id = 'vanta';
DELETE FROM insight_trace       WHERE tenant_id = 'vanta';

INSERT INTO insight_reference (tenant_id, insight_id, ordinal, ref_type, label, value_num, value_text, unit) VALUES
    ('vanta', 'ins_003', 0, 'computed', 'expected fuel_type for EV contract', NULL, 'electric', 'text'),
    ('vanta', 'ins_003', 1, 'peer',     'EV mismatch rate, fleet average',    8.11, NULL,       'percent');

INSERT INTO insight_attribution (tenant_id, insight_id, ordinal, dim, value, contribution_pct, n) VALUES
    ('vanta', 'ins_003', 0, 'vendor_id', 'Rahul Petrov Travel', 71.3, 744);

INSERT INTO insight_control (tenant_id, insight_id, ordinal, control, gap_pp, survives) VALUES
    ('vanta', 'ins_003', 0, 'vendor', 9.8, true);

INSERT INTO insight_trace (
    tenant_id, insight_id, ordinal, query_id, params, numerator, denominator, exclusions,
    validation_status, validation_notes
) VALUES
    ('vanta', 'ins_003', 0, 'ev_contract_fuel_mismatch',
     '{"contract_type":"EV"}'::jsonb, 1044, 8426, '["contracts missing fuel_type (1.2%)"]'::jsonb,
     'pass', 'fuel_type present for 98.8% of EV-contract rows');
