package com.moveinsync.pulse.web;

import com.moveinsync.pulse.agent.AgentClient;
import com.moveinsync.pulse.agent.AgentHealth;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class HealthController {

    private final AgentClient agentClient;

    public HealthController(AgentClient agentClient) {
        this.agentClient = agentClient;
    }

    @GetMapping("/health")
    public HealthResponse health() {
        AgentHealth agent = agentClient.health();
        return new HealthResponse("UP", "pulse-backend", "0.1.0", agent);
    }
}
