package com.moveinsync.pulse.insight;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.moveinsync.pulse.agent.dto.TraceEntry;
import com.moveinsync.pulse.agent.dto.Validation;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** The query behind an insight: what was counted, what was excluded, and whether the
 * numbers reconciled. This is the drill-down the /insights/{id}/trace endpoint serves. */
@Entity
@Table(name = "insight_trace")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class InsightTrace extends InsightChild {

    @Column(name = "query_id", nullable = false, length = 128)
    private String queryId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "params", nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> params = new LinkedHashMap<>();

    @Column(nullable = false)
    private int numerator;

    @Column(nullable = false)
    private int denominator;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "exclusions", nullable = false, columnDefinition = "jsonb")
    private List<String> exclusions = new ArrayList<>();

    @Column(name = "validation_status", nullable = false, length = 16)
    private String validationStatus;

    @Column(name = "validation_notes", columnDefinition = "text")
    private String validationNotes;

    protected InsightTrace() {
    }

    public InsightTrace(String queryId, Map<String, Object> params, int numerator, int denominator,
            List<String> exclusions, String validationStatus, String validationNotes) {
        this.queryId = queryId;
        this.params = params == null ? new LinkedHashMap<>() : new LinkedHashMap<>(params);
        this.numerator = numerator;
        this.denominator = denominator;
        this.exclusions = exclusions == null ? new ArrayList<>() : new ArrayList<>(exclusions);
        this.validationStatus = validationStatus;
        this.validationNotes = validationNotes;
    }

    public TraceEntry toDto() {
        return new TraceEntry(queryId, params, numerator, denominator, exclusions,
                new Validation(validationStatus, validationNotes));
    }

    public String getQueryId() {
        return queryId;
    }

    public Map<String, Object> getParams() {
        return params;
    }

    public int getNumerator() {
        return numerator;
    }

    public int getDenominator() {
        return denominator;
    }

    public List<String> getExclusions() {
        return exclusions;
    }

    public String getValidationStatus() {
        return validationStatus;
    }

    public String getValidationNotes() {
        return validationNotes;
    }
}
