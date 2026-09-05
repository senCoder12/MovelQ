package com.moveinsync.pulse.health;

import java.nio.file.Files;
import java.nio.file.Path;

import com.moveinsync.pulse.config.WarehouseProperties;
import com.moveinsync.pulse.web.HealthResponse.Warehouse;

import org.springframework.stereotype.Component;

/** Checks that the DuckDB warehouse file is where the agent expects it and can be read.
 *
 * <p>Presence and permissions only. The backend never opens the file -- the Python agent owns
 * it, and two processes holding a DuckDB file is how you corrupt one. */
@Component
public class WarehouseProbe {

    private final WarehouseProperties properties;

    public WarehouseProbe(WarehouseProperties properties) {
        this.properties = properties;
    }

    public Warehouse probe() {
        Path path = properties.path().toAbsolutePath().normalize();
        try {
            boolean present = Files.isRegularFile(path);
            if (!present) {
                return new Warehouse(false, false, path.toString(), null, "warehouse file not found");
            }
            boolean readable = Files.isReadable(path);
            Long size = readable ? Files.size(path) : null;
            return new Warehouse(true, readable, path.toString(), size,
                    readable ? null : "warehouse file is not readable");
        } catch (Exception ex) {
            return new Warehouse(false, false, path.toString(), null, ex.getMessage());
        }
    }
}
