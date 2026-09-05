package com.moveinsync.pulse.insight;

import com.moveinsync.pulse.agent.dto.Control;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;

/** A confounder the gap was tested against, and whether the gap survived it. */
@Entity
@Table(name = "insight_control")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class InsightControl extends InsightChild {

    @Column(name = "control", nullable = false, length = 128)
    private String control;

    @Column(name = "gap_pp", nullable = false)
    private double gapPp;

    @Column(nullable = false)
    private boolean survives;

    protected InsightControl() {
    }

    public InsightControl(String control, double gapPp, boolean survives) {
        this.control = control;
        this.gapPp = gapPp;
        this.survives = survives;
    }

    public Control toDto() {
        return new Control(control, gapPp, survives);
    }

    public String getControl() {
        return control;
    }

    public double getGapPp() {
        return gapPp;
    }

    public boolean isSurvives() {
        return survives;
    }
}
