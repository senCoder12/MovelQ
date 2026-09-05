-- catalyst -- all three confirmed insights.
-- Figures match the validated agent output; nothing here is invented.

INSERT INTO insight (
    tenant_id, insight_id, severity,
    metric_id, metric_name, metric_value, metric_unit, metric_n, metric_window,
    entity_dim, entity_ref, entity_name,
    impact_affected_trips, impact_late_minutes_total, impact_cost_inr_month,
    data_quality_excluded_pct, data_quality_confidence,
    narrative_headline, narrative_body, recommended_actions, coincident_events
) VALUES (
    'catalyst', 'ins_001', 92,
    'delay_reconciliation_gap', 'Delay reconciliation gap (reported vs computed)', 54.5, '%', 215885, 'trailing_30d',
    'fleet', 'ALL', 'Fleet-wide',
    117605, NULL, NULL,
    0.0, 'high',
    '117,605 trips arrived late while reporting zero delay',
    $doc$54.5% of trips report delay_minutes as zero/null while computed_arrival_delay_min exceeds 10 minutes. The ':16' shift-suffix cluster carries 58.4% of the contradiction and the gap survives both hour-of-day and vendor controls.$doc$,
    $json$[{"type":"ticket","title":"Investigate ':16' shift-code delay capture gap","draft":"Rostering/scheduling path for ':16' shift_type codes never writes delay_minutes.","rationale":"58.4% attribution, survives hour and vendor controls."}]$json$::jsonb,
    '[]'::jsonb
), (
    'catalyst', 'ins_002', 71,
    'escort_coverage_night_female', 'Night escort coverage (female employees)', 60.8, '%', 81174, 'trailing_30d',
    'segment', 'night_female_escort', 'Night trips, female employees',
    31838, NULL, NULL,
    0.0, 'medium',
    'Night escort coverage for female employees stops at 61%',
    $doc$60.8% coverage (31,838 of 81,174 legs uncovered), well above the 20.2% baseline escort rate across all legs but plateaued short of full coverage.$doc$,
    $json$[{"type":"ticket","title":"Escalate escort gap to lowest-coverage vendors","draft":"Sneha Mikhailov Travel and Meera Pavlov Travel lag fleet coverage on night/female legs.","rationale":"Two vendors account for the bulk of uncovered legs."}]$json$::jsonb,
    '[]'::jsonb
), (
    'catalyst', 'ins_003', 58,
    'ev_contract_mismatch_rate', 'EV-contract trips run on non-EV fuel', 8.11, '%', 25351, 'trailing_30d',
    'contract_type', 'EV', 'EV Contract',
    2056, NULL, 2870000.0,
    0.0, 'medium',
    '2,056 trips billed on EV contracts ran on petrol or diesel',
    $doc$8.11% of EV-contract rows (2,056 of 25,351) show actual_cab_fuel_type as petrol or diesel instead of electric.$doc$,
    $json$[{"type":"ticket","title":"Audit EV-contract billing vs actual fuel type","draft":"2,056 trips billed under EV contract terms ran on non-electric vehicles.","rationale":"Direct billing/contract-compliance exposure."}]$json$::jsonb,
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

-- Child rows have no natural key, so they are rewritten wholesale per insight.
DELETE FROM insight_reference   WHERE tenant_id = 'catalyst';
DELETE FROM insight_attribution WHERE tenant_id = 'catalyst';
DELETE FROM insight_control     WHERE tenant_id = 'catalyst';
DELETE FROM insight_trace       WHERE tenant_id = 'catalyst';

INSERT INTO insight_reference (tenant_id, insight_id, ordinal, ref_type, label, value_num, value_text, unit) VALUES
    ('catalyst', 'ins_001', 0, 'peer',       'next-worst shift-suffix contradiction rate', 38.2,  NULL, 'percent'),
    ('catalyst', 'ins_001', 1, 'computed',   'mean reported delay_minutes',                 1.38,  NULL, 'minutes'),
    ('catalyst', 'ins_001', 2, 'computed',   'mean computed_arrival_delay_min',             9.87,  NULL, 'minutes'),
    ('catalyst', 'ins_001', 3, 'computed',   'share of all trips in '':16'' shift codes',  14.15,  NULL, 'percent'),
    ('catalyst', 'ins_002', 0, 'historical', 'baseline escort rate across all legs',       20.2,   NULL, 'percent'),
    ('catalyst', 'ins_003', 0, 'computed',   'expected fuel_type for EV contract',          NULL, 'electric', 'text');

INSERT INTO insight_attribution (tenant_id, insight_id, ordinal, dim, value, contribution_pct, n) VALUES
    ('catalyst', 'ins_001', 0, 'shift_suffix', ':16',                     58.4, 29854),
    ('catalyst', 'ins_001', 1, 'vendor_id',    'Vikram Mikhailov Travel', 55.0,  9417),
    ('catalyst', 'ins_002', 0, 'vendor_id',    'Sneha Mikhailov Travel',  61.0, 14620),
    ('catalyst', 'ins_002', 1, 'vendor_id',    'Meera Pavlov Travel',     59.7, 11940);

INSERT INTO insight_control (tenant_id, insight_id, ordinal, control, gap_pp, survives) VALUES
    ('catalyst', 'ins_001', 0, 'hour_of_day', 47.6, true),
    ('catalyst', 'ins_001', 1, 'vendor',      55.1, true);

INSERT INTO insight_trace (
    tenant_id, insight_id, ordinal, query_id, params, numerator, denominator, exclusions,
    validation_status, validation_notes
) VALUES
    ('catalyst', 'ins_001', 0, 'suffix_table',
     '{"group_by":"shift_type_suffix"}'::jsonb, 117605, 215885, '[]'::jsonb,
     'pass', 'row counts reconcile against raw ingest table'),
    ('catalyst', 'ins_001', 1, 'vendor_control_8e',
     '{"hours":[16,17,18,19]}'::jsonb, 9417, 17111, '["trips missing vendor_id (0.4%)"]'::jsonb,
     'pass', 'gap survives hour-of-day and vendor controls'),
    ('catalyst', 'ins_002', 0, 'escort_coverage_by_vendor',
     '{"segment":"night_female"}'::jsonb, 49336, 81174, '[]'::jsonb,
     'warn', 'vendor roster join has 2 unmatched vendor_ids'),
    ('catalyst', 'ins_003', 0, 'ev_contract_fuel_mismatch',
     '{"contract_type":"EV"}'::jsonb, 2056, 25351, '[]'::jsonb,
     'pass', 'fuel_type field non-null for all EV-contract rows');
