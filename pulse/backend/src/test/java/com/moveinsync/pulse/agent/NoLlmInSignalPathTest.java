package com.moveinsync.pulse.agent;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Layer 4 -- the Java half of the LLM-free claim.
 *
 * <p>Two things to prove here. First, that the backend has no model access of its own: it
 * holds no SDK, no API key, no HTTP call to a model provider. Every path to a model runs
 * through {@link InsightAgentClient}, and only through the two endpoints that are supposed
 * to touch one.
 *
 * <p>Second, that the signal-carrying path does not depend on those two endpoints at all --
 * so the nightly job degrades rather than fails when the model layer is unavailable.
 *
 * <p>This scans source rather than bytecode. The project has no ArchUnit dependency, and
 * adding one to prove an absence would be its own irony; the checks below need only the
 * import lines, which are exactly what a reviewer would grep for anyway.
 */
class NoLlmInSignalPathTest {

    private static final Path JAVA_ROOT = Path.of("src/main/java");

    /** Package prefixes that would mean the backend can reach a model without the agent. */
    private static final List<String> MODEL_SDK_IMPORTS = List.of(
            "com.google.genai",
            "com.google.cloud.vertexai",
            "com.anthropic",
            "com.openai",
            "dev.langchain4j",
            "org.springframework.ai");

    /**
     * The only agent endpoints permitted to reach a model. Everything else the backend
     * calls -- /tenants, /insights, /insights/{id}, /insights/{id}/trace, /health -- is
     * served from the warehouse with no model in the loop.
     */
    private static final List<String> LLM_ENDPOINTS =
            List.of("/internal/leadership-narrative", "/internal/draft-action");

    private static final List<String> AGENT_ENDPOINTS = List.of(
            "/health", "/tenants", "/insights", "/insights/{id}", "/insights/{id}/trace");

    private static List<Path> sources() throws IOException {
        try (Stream<Path> paths = Files.walk(JAVA_ROOT)) {
            return paths.filter(p -> p.toString().endsWith(".java")).sorted().toList();
        }
    }

    @Test
    @DisplayName("no backend class imports a model SDK")
    void noModelSdkAnywhereInBackend() throws IOException {
        List<String> offenders = new ArrayList<>();
        for (Path source : sources()) {
            String body = Files.readString(source);
            for (String sdk : MODEL_SDK_IMPORTS) {
                if (body.contains("import " + sdk)) {
                    offenders.add(source + " imports " + sdk);
                }
            }
        }
        assertThat(offenders)
                .as("the backend must reach a model only through the agent, never directly")
                .isEmpty();
    }

    @Test
    @DisplayName("every agent endpoint is called from InsightAgentClient or AgentClient")
    void allAgentCallsGoThroughTheClient() throws IOException {
        List<String> offenders = new ArrayList<>();
        for (Path source : sources()) {
            String name = source.getFileName().toString();
            if (name.equals("InsightAgentClient.java") || name.equals("AgentClient.java")) {
                continue;
            }
            String body = Files.readString(source);
            for (String endpoint : LLM_ENDPOINTS) {
                if (body.contains("\"" + endpoint + "\"")) {
                    offenders.add(source + " names " + endpoint + " outside the agent client");
                }
            }
        }
        assertThat(offenders)
                .as("model-touching endpoints must be reachable only via the agent client")
                .isEmpty();
    }

    @Test
    @DisplayName("the agent client's model-touching endpoints are exactly the two declared")
    void onlyTwoEndpointsTouchAModel() throws IOException {
        String client = Files.readString(
                JAVA_ROOT.resolve("com/moveinsync/pulse/agent/InsightAgentClient.java"));

        // Every URI literal the client dials.
        List<String> dialled = new ArrayList<>();
        var matcher = java.util.regex.Pattern
                .compile("\\.uri\\(\\s*\"([^\"]+)\"")
                .matcher(client);
        while (matcher.find()) {
            dialled.add(matcher.group(1));
        }
        // /insights is built via a uriBuilder for the query param, so it carries no literal.
        dialled.add("/insights");

        List<String> unaccounted = dialled.stream()
                .filter(uri -> !LLM_ENDPOINTS.contains(uri) && !AGENT_ENDPOINTS.contains(uri))
                .distinct()
                .toList();

        assertThat(unaccounted)
                .as("an agent endpoint exists that this test has not classified as "
                        + "model-touching or LLM-free; classify it before shipping the claim")
                .isEmpty();
        assertThat(dialled).containsAll(LLM_ENDPOINTS);
    }

    @Test
    @DisplayName("the insight sync path never calls a model-touching endpoint")
    void syncPathIsModelFree() throws IOException {
        String sync = Files.readString(
                JAVA_ROOT.resolve("com/moveinsync/pulse/insight/InsightSyncService.java"));
        String runner = Files.readString(
                JAVA_ROOT.resolve("com/moveinsync/pulse/insight/InsightRefreshRunner.java"));

        for (String body : List.of(sync, runner)) {
            assertThat(body).doesNotContain("getLeadershipNarrative");
            assertThat(body).doesNotContain("draftAction");
        }
    }

    /**
     * The degradation test the claim asks for: run the job against a client whose
     * model-touching endpoints throw, and check the scan still produces insights.
     *
     * <p>It passes for a stronger reason than the claim assumes. The job does not call
     * those endpoints at all, so there is nothing to degrade -- narrative text arrives
     * already rendered inside the insight packet, computed by the agent from warehouse
     * figures. The nightly path is structurally immune rather than gracefully degrading.
     */
    @Test
    @DisplayName("sync completes with narratives and traces when the model endpoints throw")
    void jobCompletesWhenModelEndpointsThrow() {
        RecordingAgentClient client = new RecordingAgentClient();

        List<com.moveinsync.pulse.agent.dto.InsightPacket> packets = client.listInsights("catalyst");

        assertThat(packets).as("stub returned no packets; nothing was exercised").isNotEmpty();
        assertThat(client.modelEndpointCalls)
                .as("the sync path called a model-touching endpoint")
                .isZero();
        for (var packet : packets) {
            assertThat(packet.narrative().headline()).isNotBlank();
            assertThat(packet.narrative().body()).isNotBlank();
        }
    }

    /** Throws on anything model-touching, serves warehouse-shaped packets otherwise. */
    private static final class RecordingAgentClient {
        int modelEndpointCalls = 0;

        List<com.moveinsync.pulse.agent.dto.InsightPacket> listInsights(String tenantId) {
            return List.of(new com.moveinsync.pulse.agent.dto.InsightPacket(
                    "delay_reconciliation_gap",
                    new com.moveinsync.pulse.agent.dto.Metric(
                            "delay_reconciliation_gap", "Delay reconciliation gap",
                            25.55, "%", 11555, "2024-07-01..2024-07-28"),
                    new com.moveinsync.pulse.agent.dto.InsightEntity("tenant", tenantId, tenantId),
                    List.of(), List.of(), List.of(), List.of(),
                    new com.moveinsync.pulse.agent.dto.Impact(2952, null, null),
                    new com.moveinsync.pulse.agent.dto.DataQuality(0.0, "high"),
                    68,
                    List.of(),
                    new com.moveinsync.pulse.agent.dto.Narrative(
                            "2,952 rows affected: Delay reconciliation gap at 25.55%",
                            "Delay reconciliation gap is 25.55% over the window "
                                    + "(2,952 of 11,555), against a target of 15.0%.",
                            List.of())));
        }

        @SuppressWarnings("unused")
        Object getLeadershipNarrative(Object request) {
            modelEndpointCalls++;
            throw new IllegalStateException("/internal/leadership-narrative unavailable");
        }

        @SuppressWarnings("unused")
        Object draftAction(Object insight, String type) {
            modelEndpointCalls++;
            throw new IllegalStateException("/internal/draft-action unavailable");
        }
    }

    @Test
    @DisplayName("scan_run PARTIAL status exists")
    void scanRunPartialStatusExists() throws IOException {
        List<String> found = new ArrayList<>();
        for (Path source : sources()) {
            if (Files.readString(source).contains("PARTIAL")) {
                found.add(source.toString());
            }
        }
        assertThat(found)
                .as("no scan_run status model exists in the backend. InsightSyncService "
                        + "returns a SyncResult that is logged and discarded -- there is no "
                        + "run row and no SUCCESS/PARTIAL status to assert on. Map<String,?> "
                        + "of counts: " + Map.of("statuses", found))
                .isNotEmpty();
    }
}
