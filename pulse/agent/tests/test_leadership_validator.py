from app.agent import validator

INPUT_PAYLOAD = {
    "period": "July 2026",
    "tiles": [
        {"label": "Trips analysed", "value": "215,885", "reference": "July 2026", "direction": "neutral"},
        {"label": "Delay data reliable", "value": "45.5%", "reference": "of trips", "direction": "bad"},
    ],
    "findings": [
        {
            "insight_id": "ins_001",
            "severity": 92,
            "metric": {"id": "delay_reconciliation_gap", "name": "Delay reconciliation gap", "value": 54.5, "unit": "%", "n": 215885},
            "impact": {"affected_trips": 117605, "cost_inr_month": 2870000.0},
            "attribution": [{"dim": "shift_suffix", "value": ":16", "contribution_pct": 58.4, "n": 29854}],
        }
    ],
}


def test_extract_numbers_plain():
    assert validator.extract_numbers("117,605 trips, 58.4% contradiction") == {117605.0, 58.4}


def test_extract_numbers_expands_indian_suffixes():
    assert validator.extract_numbers("billed ₹2.87M this month") == {2870000.0}
    assert validator.extract_numbers("1.2Cr saved") == {12000000.0}


def test_collect_input_numbers_walks_nested_structure():
    numbers = validator.collect_input_numbers(INPUT_PAYLOAD)
    assert 215885.0 in numbers
    assert 45.5 in numbers
    assert 58.4 in numbers
    assert 2870000.0 in numbers


def test_validate_passes_when_every_number_is_grounded():
    output = {
        "headline": "Reported delay data is unreliable across half the fleet",
        "summary": "215,885 trips were analysed; only 45.5% have reliable delay data.",
        "findings": [
            {
                "insight_id": "ins_001",
                "body": "117,605 trips show the contradiction, 58.4% of the ':16' cluster.",
                "recommendation": "Audit the ':16' scheduling path.",
            }
        ],
    }
    result = validator.validate(INPUT_PAYLOAD, output)
    assert result.ok, result.ungrounded


def test_validate_flags_a_rounded_or_invented_number():
    output = {
        "headline": "Coverage stops at 61%",
        "summary": "215,885 trips were analysed.",
        "findings": [
            {"insight_id": "ins_001", "body": "Affects 117,605 trips.", "recommendation": "Audit it."}
        ],
    }
    result = validator.validate(INPUT_PAYLOAD, output)
    assert not result.ok
    assert 61.0 in result.ungrounded


def test_validate_ignores_insight_id_field():
    # insight_id strings like "ins_001" must never be scanned for numbers --
    # otherwise every response would spuriously fail on an un-grounded "1".
    output = {
        "headline": "Reported delay data is unreliable across half the fleet",
        "summary": "215,885 trips were analysed; 45.5% have reliable delay data.",
        "findings": [{"insight_id": "ins_001", "body": "n/a", "recommendation": "Audit it."}],
    }
    result = validator.validate(INPUT_PAYLOAD, output)
    assert result.ok, result.ungrounded
