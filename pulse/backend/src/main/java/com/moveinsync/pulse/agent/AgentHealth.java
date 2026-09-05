package com.moveinsync.pulse.agent;

/** Health payload returned by the Python agent's GET /health. */
public record AgentHealth(String status, String service, String version) {
}
