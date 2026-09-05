package com.moveinsync.pulse.web;

import com.moveinsync.pulse.agent.AgentClient;
import com.moveinsync.pulse.agent.AgentHealth;
import com.moveinsync.pulse.health.PlatformDbProbe;
import com.moveinsync.pulse.health.WarehouseProbe;
import com.moveinsync.pulse.web.HealthResponse.Agent;
import com.moveinsync.pulse.web.HealthResponse.PlatformDb;
import com.moveinsync.pulse.web.HealthResponse.Warehouse;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Reports the platform database, the agent and the warehouse separately. Never requires a
 * tenant -- see {@link TenantFilter#shouldNotFilter} -- and never fails: an unreachable
 * dependency is reported, not thrown. */
@RestController
@RequestMapping("/api")
public class HealthController {

    private final AgentClient agentClient;
    private final PlatformDbProbe platformDbProbe;
    private final WarehouseProbe warehouseProbe;

    public HealthController(AgentClient agentClient, PlatformDbProbe platformDbProbe, WarehouseProbe warehouseProbe) {
        this.agentClient = agentClient;
        this.platformDbProbe = platformDbProbe;
        this.warehouseProbe = warehouseProbe;
    }

    @GetMapping("/health")
    public HealthResponse health() {
        PlatformDb platformDb = platformDbProbe.probe();
        Warehouse warehouse = warehouseProbe.probe();
        AgentHealth agentHealth = agentClient.health();
        Agent agent = new Agent(HealthResponse.UP.equals(agentHealth.status()),
                agentHealth.status(), agentHealth.service(), agentHealth.version());

        boolean allUp = platformDb.reachable() && agent.reachable() && warehouse.present() && warehouse.readable();
        String status = allUp ? HealthResponse.UP : HealthResponse.DEGRADED;
        return new HealthResponse(status, "pulse-backend", "0.1.0", platformDb, agent, warehouse);
    }
}
