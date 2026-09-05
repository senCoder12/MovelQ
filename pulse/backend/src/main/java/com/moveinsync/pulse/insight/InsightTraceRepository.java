package com.moveinsync.pulse.insight;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/** Trace rows, fetched on demand by the drill-down endpoint rather than with the brief. */
public interface InsightTraceRepository extends JpaRepository<InsightTrace, Long> {

    @Query("select t from InsightTrace t where t.insight.insightId = :insightId order by t.ordinal asc")
    List<InsightTrace> findByInsightId(@Param("insightId") String insightId);
}
