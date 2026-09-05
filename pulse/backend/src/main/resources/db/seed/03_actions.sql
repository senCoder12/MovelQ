-- Action drafts and their approval trail, for both tenants.
--
-- facts_cited is the point of this table: every number the draft quotes is tied back to the
-- insight field it came from, so an approver can check the draft against the evidence rather
-- than trusting it.

DELETE FROM approval_log WHERE tenant_id IN ('catalyst', 'vanta');

INSERT INTO action_draft (
    tenant_id, action_id, insight_id, action_type, title, body, rationale,
    recipient, facts_cited, preview, params, status
) VALUES (
    'catalyst', 'act_001', 'ins_001', 'ticket',
    'Investigate '':16'' shift-code delay capture gap',
    $doc$The rostering/scheduling path for ':16' shift_type codes appears never to write delay_minutes. 117,605 trips arrived late while reporting zero delay.$doc$,
    '58.4% attribution to the '':16'' cluster, and the gap survives both hour-of-day and vendor controls.',
    $json${"channel":"jira","project":"OPS","assignee":"platform-data@catalyst.example"}$json$::jsonb,
    $json$[{"field":"metric.value","label":"delay reconciliation gap","value":54.5,"unit":"%"},
           {"field":"impact.affected_trips","label":"trips affected","value":117605,"unit":"trips"},
           {"field":"attribution[0].contribution_pct","label":"':16' cluster contribution","value":58.4,"unit":"%"},
           {"field":"controls[0].survives","label":"survives hour-of-day control","value":true,"unit":null}]$json$::jsonb,
    $json${"subject":"[Pulse] ':16' shift codes are not writing delay_minutes","format":"markdown"}$json$::jsonb,
    $json${"priority":"P1","labels":["data-quality","rostering"]}$json$::jsonb,
    'approved'
), (
    'catalyst', 'act_002', 'ins_002', 'email',
    'Escalate escort gap to lowest-coverage vendors',
    $doc$Night escort coverage for female employees stands at 60.8%, leaving 31,838 of 81,174 legs uncovered. Two vendors account for the bulk of the shortfall.$doc$,
    'Sneha Mikhailov Travel and Meera Pavlov Travel both sit below fleet coverage on night/female legs.',
    $json${"channel":"email","to":["vendor-ops@catalyst.example"],"cc":["safety@catalyst.example"]}$json$::jsonb,
    $json$[{"field":"metric.value","label":"night escort coverage","value":60.8,"unit":"%"},
           {"field":"impact.affected_trips","label":"uncovered legs","value":31838,"unit":"legs"},
           {"field":"references[0].value","label":"baseline escort rate","value":20.2,"unit":"%"}]$json$::jsonb,
    $json${"subject":"Night escort coverage: vendor action required","format":"email"}$json$::jsonb,
    $json${"due_days":7}$json$::jsonb,
    'draft'
), (
    'catalyst', 'act_003', 'ins_003', 'ticket',
    'Audit EV-contract billing vs actual fuel type',
    $doc$2,056 trips billed under EV contract terms ran on non-electric vehicles, an exposure of about INR 2.87M a month.$doc$,
    'Affects both cost recovery and sustainability reporting.',
    $json${"channel":"jira","project":"FIN","assignee":"billing@catalyst.example"}$json$::jsonb,
    $json$[{"field":"metric.value","label":"EV contract mismatch rate","value":8.11,"unit":"%"},
           {"field":"impact.affected_trips","label":"mismatched trips","value":2056,"unit":"trips"},
           {"field":"impact.cost_inr_month","label":"monthly billing exposure","value":2870000.0,"unit":"INR"}]$json$::jsonb,
    $json${"subject":"[Pulse] EV-contract trips running on petrol/diesel","format":"markdown"}$json$::jsonb,
    $json${"priority":"P2","labels":["billing","sustainability"]}$json$::jsonb,
    'draft'
), (
    'vanta', 'act_001', 'ins_003', 'ticket',
    'Audit EV-contract billing vs actual fuel type',
    $doc$1,044 trips billed under EV contract terms ran on non-electric vehicles, an exposure of about INR 1.31M a month. One vendor carries 71.3% of it.$doc$,
    '12.39% mismatch against a fleet average of 8.11%, concentrated in a single vendor.',
    $json${"channel":"jira","project":"FIN","assignee":"billing@vanta.example"}$json$::jsonb,
    $json$[{"field":"metric.value","label":"EV contract mismatch rate","value":12.39,"unit":"%"},
           {"field":"impact.affected_trips","label":"mismatched trips","value":1044,"unit":"trips"},
           {"field":"impact.cost_inr_month","label":"monthly billing exposure","value":1310000.0,"unit":"INR"},
           {"field":"attribution[0].contribution_pct","label":"Rahul Petrov Travel contribution","value":71.3,"unit":"%"}]$json$::jsonb,
    $json${"subject":"[Pulse] EV-contract trips running on petrol/diesel","format":"markdown"}$json$::jsonb,
    $json${"priority":"P1","labels":["billing","vendor"]}$json$::jsonb,
    'approved'
)
ON CONFLICT (tenant_id, action_id) DO UPDATE SET
    action_type = EXCLUDED.action_type,
    title       = EXCLUDED.title,
    body        = EXCLUDED.body,
    rationale   = EXCLUDED.rationale,
    recipient   = EXCLUDED.recipient,
    facts_cited = EXCLUDED.facts_cited,
    preview     = EXCLUDED.preview,
    params      = EXCLUDED.params,
    status      = EXCLUDED.status,
    updated_at  = now();

INSERT INTO approval_log (tenant_id, action_draft_id, decision, actor, note, decided_at)
SELECT d.tenant_id, d.id, 'approved', 'priya.raman@catalyst.example',
       'Confirmed against the trace before approving.', now() - interval '2 hours'
FROM action_draft d
WHERE d.tenant_id = 'catalyst' AND d.action_id = 'act_001';

INSERT INTO approval_log (tenant_id, action_draft_id, decision, actor, note, decided_at)
SELECT d.tenant_id, d.id, 'approved', 'arjun.mehta@vanta.example',
       'Vendor concentration checked; raising with the vendor directly.', now() - interval '30 minutes'
FROM action_draft d
WHERE d.tenant_id = 'vanta' AND d.action_id = 'act_001';
