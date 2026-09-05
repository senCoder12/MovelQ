package com.moveinsync.pulse.insight;

import com.moveinsync.pulse.agent.dto.Attribution;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;

/** How much of an insight's gap a single dimension value accounts for. */
@Entity
@Table(name = "insight_attribution")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class InsightAttribution extends InsightChild {

    @Column(nullable = false, length = 64)
    private String dim;

    @Column(nullable = false, length = 256)
    private String value;

    @Column(name = "contribution_pct", nullable = false)
    private double contributionPct;

    @Column(nullable = false)
    private int n;

    protected InsightAttribution() {
    }

    public InsightAttribution(String dim, String value, double contributionPct, int n) {
        this.dim = dim;
        this.value = value;
        this.contributionPct = contributionPct;
        this.n = n;
    }

    public Attribution toDto() {
        return new Attribution(dim, value, contributionPct, n);
    }

    public String getDim() {
        return dim;
    }

    public String getValue() {
        return value;
    }

    public double getContributionPct() {
        return contributionPct;
    }

    public int getN() {
        return n;
    }
}
