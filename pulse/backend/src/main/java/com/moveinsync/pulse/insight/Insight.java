package com.moveinsync.pulse.insight;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import com.moveinsync.pulse.agent.dto.CoincidentEvent;
import com.moveinsync.pulse.agent.dto.RecommendedAction;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import org.hibernate.annotations.Filter;
import org.hibernate.annotations.FilterDef;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.ParamDef;
import org.hibernate.type.SqlTypes;

/**
 * One insight, mirroring contracts/insight.schema.json.
 *
 * <p>Declares the {@code tenantFilter} used by every entity in the application.
 * {@link com.moveinsync.pulse.tenant.TenantFilterAspect} enables it per session;
 * it is not {@code autoEnabled}, because an auto-enabled filter with no parameter
 * silently matches nothing rather than failing loudly.
 */
@Entity
@Table(name = "insight")
@FilterDef(
        name = "tenantFilter",
        parameters = @ParamDef(name = "tenantId", type = String.class))
@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
public class Insight {

    public static final String SOURCE_SEED = "seed";
    public static final String SOURCE_AGENT = "agent";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false, updatable = false, length = 64)
    private String tenantId;

    /** Business key from the agent, e.g. "ins_001". Unique per tenant, not globally. */
    @Column(name = "insight_id", nullable = false, updatable = false, length = 64)
    private String insightId;

    @Column(nullable = false)
    private int severity;

    @Column(name = "metric_id", nullable = false, length = 128)
    private String metricId;

    @Column(name = "metric_name", nullable = false, length = 256)
    private String metricName;

    @Column(name = "metric_value", nullable = false)
    private double metricValue;

    @Column(name = "metric_unit", nullable = false, length = 32)
    private String metricUnit;

    @Column(name = "metric_n", nullable = false)
    private int metricN;

    @Column(name = "metric_window", nullable = false, length = 64)
    private String metricWindow;

    @Column(name = "entity_dim", nullable = false, length = 64)
    private String entityDim;

    /** entity.id in the contract; named _ref here so it never reads as the primary key. */
    @Column(name = "entity_ref", nullable = false, length = 128)
    private String entityRef;

    @Column(name = "entity_name", nullable = false, length = 256)
    private String entityName;

    @Column(name = "impact_affected_trips")
    private Integer impactAffectedTrips;

    @Column(name = "impact_late_minutes_total")
    private Double impactLateMinutesTotal;

    @Column(name = "impact_cost_inr_month")
    private Double impactCostInrMonth;

    @Column(name = "data_quality_excluded_pct", nullable = false)
    private double dataQualityExcludedPct;

    @Column(name = "data_quality_confidence", nullable = false, length = 16)
    private String dataQualityConfidence;

    @Column(name = "narrative_headline", nullable = false, columnDefinition = "text")
    private String narrativeHeadline;

    @Column(name = "narrative_body", nullable = false, columnDefinition = "text")
    private String narrativeBody;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "recommended_actions", nullable = false, columnDefinition = "jsonb")
    private List<RecommendedAction> recommendedActions = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "coincident_events", nullable = false, columnDefinition = "jsonb")
    private List<CoincidentEvent> coincidentEvents = new ArrayList<>();

    /** "agent" for a generated insight, "seed" for a demo fixture. The sync only ever
     * deletes its own output, so a stale generated insight disappears while the seed
     * fallback survives. */
    @Column(name = "source", nullable = false, length = 16)
    private String source = SOURCE_SEED;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @OneToMany(mappedBy = "insight", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("ordinal ASC")
    @Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
    private List<InsightReference> references = new ArrayList<>();

    @OneToMany(mappedBy = "insight", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("ordinal ASC")
    @Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
    private List<InsightAttribution> attributions = new ArrayList<>();

    @OneToMany(mappedBy = "insight", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("ordinal ASC")
    @Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
    private List<InsightControl> controls = new ArrayList<>();

    @OneToMany(mappedBy = "insight", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("ordinal ASC")
    @Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")
    private List<InsightTrace> traces = new ArrayList<>();

    protected Insight() {
    }

    public Insight(String tenantId, String insightId) {
        this.tenantId = tenantId;
        this.insightId = insightId;
    }

    @PrePersist
    void onInsert() {
        Instant now = Instant.now();
        createdAt = createdAt == null ? now : createdAt;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }

    /** Adds a child and wires both sides, so tenant_id and insight_id come from the parent
     * and a child can never be built pointing at a different tenant. */
    public Insight addReference(InsightReference child) {
        child.setInsight(this);
        child.setOrdinal(references.size());
        references.add(child);
        return this;
    }

    public Insight addAttribution(InsightAttribution child) {
        child.setInsight(this);
        child.setOrdinal(attributions.size());
        attributions.add(child);
        return this;
    }

    public Insight addControl(InsightControl child) {
        child.setInsight(this);
        child.setOrdinal(controls.size());
        controls.add(child);
        return this;
    }

    public Insight addTrace(InsightTrace child) {
        child.setInsight(this);
        child.setOrdinal(traces.size());
        traces.add(child);
        return this;
    }

    public void clearChildren() {
        references.clear();
        attributions.clear();
        controls.clear();
        traces.clear();
    }

    public Long getId() {
        return id;
    }

    public String getTenantId() {
        return tenantId;
    }

    public String getInsightId() {
        return insightId;
    }

    public int getSeverity() {
        return severity;
    }

    public void setSeverity(int severity) {
        this.severity = severity;
    }

    public String getMetricId() {
        return metricId;
    }

    public void setMetricId(String metricId) {
        this.metricId = metricId;
    }

    public String getMetricName() {
        return metricName;
    }

    public void setMetricName(String metricName) {
        this.metricName = metricName;
    }

    public double getMetricValue() {
        return metricValue;
    }

    public void setMetricValue(double metricValue) {
        this.metricValue = metricValue;
    }

    public String getMetricUnit() {
        return metricUnit;
    }

    public void setMetricUnit(String metricUnit) {
        this.metricUnit = metricUnit;
    }

    public int getMetricN() {
        return metricN;
    }

    public void setMetricN(int metricN) {
        this.metricN = metricN;
    }

    public String getMetricWindow() {
        return metricWindow;
    }

    public void setMetricWindow(String metricWindow) {
        this.metricWindow = metricWindow;
    }

    public String getEntityDim() {
        return entityDim;
    }

    public void setEntityDim(String entityDim) {
        this.entityDim = entityDim;
    }

    public String getEntityRef() {
        return entityRef;
    }

    public void setEntityRef(String entityRef) {
        this.entityRef = entityRef;
    }

    public String getEntityName() {
        return entityName;
    }

    public void setEntityName(String entityName) {
        this.entityName = entityName;
    }

    public Integer getImpactAffectedTrips() {
        return impactAffectedTrips;
    }

    public void setImpactAffectedTrips(Integer impactAffectedTrips) {
        this.impactAffectedTrips = impactAffectedTrips;
    }

    public Double getImpactLateMinutesTotal() {
        return impactLateMinutesTotal;
    }

    public void setImpactLateMinutesTotal(Double impactLateMinutesTotal) {
        this.impactLateMinutesTotal = impactLateMinutesTotal;
    }

    public Double getImpactCostInrMonth() {
        return impactCostInrMonth;
    }

    public void setImpactCostInrMonth(Double impactCostInrMonth) {
        this.impactCostInrMonth = impactCostInrMonth;
    }

    public double getDataQualityExcludedPct() {
        return dataQualityExcludedPct;
    }

    public void setDataQualityExcludedPct(double dataQualityExcludedPct) {
        this.dataQualityExcludedPct = dataQualityExcludedPct;
    }

    public String getDataQualityConfidence() {
        return dataQualityConfidence;
    }

    public void setDataQualityConfidence(String dataQualityConfidence) {
        this.dataQualityConfidence = dataQualityConfidence;
    }

    public String getNarrativeHeadline() {
        return narrativeHeadline;
    }

    public void setNarrativeHeadline(String narrativeHeadline) {
        this.narrativeHeadline = narrativeHeadline;
    }

    public String getNarrativeBody() {
        return narrativeBody;
    }

    public void setNarrativeBody(String narrativeBody) {
        this.narrativeBody = narrativeBody;
    }

    public List<RecommendedAction> getRecommendedActions() {
        return recommendedActions;
    }

    public void setRecommendedActions(List<RecommendedAction> recommendedActions) {
        this.recommendedActions = recommendedActions == null ? new ArrayList<>() : recommendedActions;
    }

    public List<CoincidentEvent> getCoincidentEvents() {
        return coincidentEvents;
    }

    public void setCoincidentEvents(List<CoincidentEvent> coincidentEvents) {
        this.coincidentEvents = coincidentEvents == null ? new ArrayList<>() : coincidentEvents;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public List<InsightReference> getReferences() {
        return references;
    }

    public List<InsightAttribution> getAttributions() {
        return attributions;
    }

    public List<InsightControl> getControls() {
        return controls;
    }

    public List<InsightTrace> getTraces() {
        return traces;
    }
}
