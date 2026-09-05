package com.moveinsync.pulse.web;

import com.moveinsync.pulse.agent.AgentHealth;

/** Combined health of the backend and the Python agent. */
public record HealthResponse(String status, String service, String version, AgentHealth agent) {
}
