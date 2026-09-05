package com.moveinsync.pulse.web;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import com.moveinsync.pulse.agent.dto.InsightPacket;
import com.moveinsync.pulse.insight.BriefCache;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * Persona-scoped insight feed, served from Postgres.
 *
 * <p>One database round trip per call, or none while the per-tenant cache is warm. Ordering
 * (severity desc) and tenant scoping both happen in that query -- there is no post-filtering
 * here, because a tenant predicate applied in Java is a tenant predicate someone can forget
 * to apply.
 */
@RestController
@RequestMapping("/api")
public class BriefController {

    private static final Set<String> PERSONAS = Set.of("ops", "strategic", "shift");

    private final BriefCache briefCache;

    public BriefController(BriefCache briefCache) {
        this.briefCache = briefCache;
    }

    @GetMapping("/brief")
    public BriefResponse brief(@RequestParam String persona) {
        if (!PERSONAS.contains(persona)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "unknown persona: " + persona);
        }
        List<InsightPacket> packets = briefCache.insights();
        return new BriefResponse(persona, Instant.now(), packets);
    }
}
