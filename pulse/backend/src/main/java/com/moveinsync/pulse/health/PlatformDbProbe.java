package com.moveinsync.pulse.health;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

import javax.sql.DataSource;

import com.moveinsync.pulse.web.HealthResponse.PlatformDb;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

/**
 * Measures whether Neon answers, and how long it takes.
 *
 * <p>The DataSource is resolved through an {@link ObjectProvider} so this probe does not drag
 * the connection pool into existence during startup -- the whole point is that health can be
 * asked before the database has ever answered.
 */
@Component
public class PlatformDbProbe {

    private static final Logger log = LoggerFactory.getLogger(PlatformDbProbe.class);

    /** Long enough for a Neon cold start to succeed, short enough that /api/health answers. */
    private static final int QUERY_TIMEOUT_SECONDS = 8;

    private final ObjectProvider<DataSource> dataSource;

    public PlatformDbProbe(ObjectProvider<DataSource> dataSource) {
        this.dataSource = dataSource;
    }

    public PlatformDb probe() {
        long startedAt = System.nanoTime();
        try (Connection connection = dataSource.getObject().getConnection();
                Statement statement = connection.createStatement()) {
            statement.setQueryTimeout(QUERY_TIMEOUT_SECONDS);
            try (ResultSet resultSet = statement.executeQuery("select 1")) {
                resultSet.next();
            }
            long latencyMs = elapsedMs(startedAt);
            return PlatformDb.up(latencyMs, serverVersion(connection), migrationVersion(statement));
        } catch (Exception ex) {
            long latencyMs = elapsedMs(startedAt);
            log.warn("platform db unreachable after {}ms: {}", latencyMs, ex.toString());
            return PlatformDb.down(latencyMs, ex.getMessage());
        }
    }

    private static long elapsedMs(long startedAtNanos) {
        return (System.nanoTime() - startedAtNanos) / 1_000_000;
    }

    private static String serverVersion(Connection connection) {
        try {
            return connection.getMetaData().getDatabaseProductVersion();
        } catch (Exception ex) {
            return null;
        }
    }

    /** The Flyway version actually in the database, so health answers "which schema is this?"
     * without anyone opening a psql session. */
    private static String migrationVersion(Statement statement) {
        try (ResultSet resultSet = statement.executeQuery(
                "select version from flyway_schema_history where success order by installed_rank desc limit 1")) {
            return resultSet.next() ? resultSet.getString(1) : null;
        } catch (Exception ex) {
            // Schema history absent means migrations have not run yet. Not an error here.
            return null;
        }
    }
}
