package com.moveinsync.pulse.config;

import java.nio.file.Path;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Where the DuckDB analytical warehouse lives.
 *
 * <p>The backend never opens this file -- the Python agent owns it. All the backend does is
 * check that it is present and readable, so /api/health can tell "the warehouse is missing"
 * apart from "the agent is down". */
@ConfigurationProperties(prefix = "pulse.warehouse")
public record WarehouseProperties(Path path) {

    public WarehouseProperties {
        path = path == null ? Path.of("data/warehouse.duckdb") : path;
    }
}
