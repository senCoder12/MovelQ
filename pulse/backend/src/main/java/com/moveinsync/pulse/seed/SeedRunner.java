package com.moveinsync.pulse.seed;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.core.io.support.ResourcePatternResolver;
import org.springframework.stereotype.Component;
import org.springframework.util.StreamUtils;

/**
 * Loads db/seed/*.sql when the application is started with {@code --seed}.
 *
 * <p>Idempotent by construction: insights and action drafts upsert on their tenant-scoped
 * business keys, and child rows are deleted and rewritten per tenant. Running it twice leaves
 * the database exactly as running it once did, which matters because the demo will be reset
 * more than once.
 *
 * <p>Each file is sent to Postgres whole rather than split on semicolons -- the seed uses
 * dollar-quoted literals, and a naive statement splitter would cut them in half. The whole
 * run is one transaction: a half-seeded database is worse than an unseeded one.
 */
@Component
public class SeedRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(SeedRunner.class);

    private static final String SEED_FLAG = "--seed";
    private static final String SEED_LOCATION = "classpath*:db/seed/*.sql";

    private final ObjectProvider<DataSource> dataSource;
    private final ResourcePatternResolver resolver = new PathMatchingResourcePatternResolver();

    public SeedRunner(ObjectProvider<DataSource> dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void run(String... args) throws Exception {
        if (Arrays.stream(args).noneMatch(SEED_FLAG::equals)) {
            return;
        }
        List<Resource> scripts = Arrays.stream(resolver.getResources(SEED_LOCATION))
                .sorted(Comparator.comparing(resource -> String.valueOf(resource.getFilename())))
                .toList();
        if (scripts.isEmpty()) {
            log.warn("--seed given but no scripts found at {}", SEED_LOCATION);
            return;
        }

        long startedAt = System.nanoTime();
        try (Connection connection = dataSource.getObject().getConnection()) {
            connection.setAutoCommit(false);
            try (Statement statement = connection.createStatement()) {
                for (Resource script : scripts) {
                    log.info("seeding from {}", script.getFilename());
                    statement.execute(read(script));
                }
                connection.commit();
            } catch (RuntimeException | java.sql.SQLException ex) {
                connection.rollback();
                throw ex;
            }
            logCounts(connection);
        }
        log.info("seed complete in {}ms", (System.nanoTime() - startedAt) / 1_000_000);
    }

    private static String read(Resource script) throws IOException {
        try (InputStream in = script.getInputStream()) {
            return StreamUtils.copyToString(in, StandardCharsets.UTF_8);
        }
    }

    /** Reports what landed, per tenant, so a seed run is verifiable from the log alone. */
    private static void logCounts(Connection connection) {
        String sql = """
                select tenant_id, count(*) from insight group by tenant_id
                union all
                select tenant_id || ' (actions)', count(*) from action_draft group by tenant_id
                order by 1
                """;
        try (Statement statement = connection.createStatement();
                ResultSet resultSet = statement.executeQuery(sql)) {
            while (resultSet.next()) {
                log.info("  seeded {}: {} row(s)", resultSet.getString(1), resultSet.getInt(2));
            }
        } catch (Exception ex) {
            log.warn("could not read back seed counts: {}", ex.toString());
        }
    }
}
