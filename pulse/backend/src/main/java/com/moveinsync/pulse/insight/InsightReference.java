package com.moveinsync.pulse.insight;

import com.moveinsync.pulse.agent.dto.Reference;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;

/** A comparison point attached to an insight. insight.schema.json types reference.value as
 * number|string, so both columns exist and exactly one is populated. */
@Entity
@Table(name = "insight_reference")
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class InsightReference extends InsightChild {

    @Column(name = "ref_type", nullable = false, length = 32)
    private String refType;

    @Column(nullable = false, length = 512)
    private String label;

    @Column(name = "value_num")
    private Double valueNum;

    @Column(name = "value_text", length = 512)
    private String valueText;

    @Column(length = 32)
    private String unit;

    protected InsightReference() {
    }

    public InsightReference(String refType, String label, Object value, String unit) {
        this.refType = refType;
        this.label = label;
        this.unit = unit;
        if (value instanceof Number number) {
            this.valueNum = number.doubleValue();
        } else if (value != null) {
            this.valueText = value.toString();
        }
    }

    /** Back to the contract shape: whichever column was populated becomes reference.value. */
    public Reference toDto() {
        return new Reference(refType, label, valueNum != null ? valueNum : valueText, unit);
    }

    public String getRefType() {
        return refType;
    }

    public String getLabel() {
        return label;
    }

    public Double getValueNum() {
        return valueNum;
    }

    public String getValueText() {
        return valueText;
    }

    public String getUnit() {
        return unit;
    }
}
