package com.moveinsync.pulse.config;

import java.io.IOException;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

/**
 * Loads backend/.env into the Spring environment so credentials live in exactly one
 * gitignored file and never in application.yml, a run configuration, or a shell history.
 *
 * <p>Also accepts the {@code postgres://} URI Neon hands out, as {@code NEON_DATABASE_URL},
 * and splits it into the three properties the datasource binds to. One value to paste, and
 * the credentials still travel as separate JDBC properties rather than inside the URL --
 * which matters because the URL is what turns up in connection-error messages, Flyway's
 * output and startup logs, and a password in the URL turns up there with it.
 *
 * <p>Precedence, lowest last: an explicit {@code PULSE_DB_*} beats anything derived from
 * {@code NEON_DATABASE_URL}, and a real environment variable or -D flag beats .env. Absent
 * .env is not an error -- production gets its values from the process environment.
 */
public class DotenvEnvironmentPostProcessor implements EnvironmentPostProcessor {

    private static final String SOURCE_NAME = "pulse-dotenv";

    /** Tried in order, relative to the working directory. spring-boot:run starts in pulse/,
     * a packaged jar is usually run from backend/. */
    private static final List<String> CANDIDATES = List.of("backend/.env", ".env", "../backend/.env");

    private static final String NEON_URI_SOURCE_NAME = "pulse-neon-uri";
    private static final String NEON_URI_PROPERTY = "NEON_DATABASE_URL";

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        loadDotenv(environment);
        deriveDatasourcePropertiesFromNeonUri(environment);
    }

    private static void loadDotenv(ConfigurableEnvironment environment) {
        for (String candidate : CANDIDATES) {
            Path path = Path.of(candidate);
            if (Files.isRegularFile(path)) {
                Map<String, Object> values = parse(path);
                if (!values.isEmpty()) {
                    environment.getPropertySources().addLast(new MapPropertySource(SOURCE_NAME, values));
                }
                return;
            }
        }
    }

    /**
     * Turns {@code postgresql://user:password@host/db?sslmode=require&channel_binding=require}
     * into the three properties the datasource binds to. {@code channel_binding} is dropped --
     * the JDBC driver rejects it -- and {@code sslmode=require} is added if Neon left it off.
     */
    private static void deriveDatasourcePropertiesFromNeonUri(ConfigurableEnvironment environment) {
        String raw = environment.getProperty(NEON_URI_PROPERTY);
        if (raw == null || raw.isBlank() || raw.startsWith("jdbc:")) {
            return;
        }
        Map<String, Object> derived = new LinkedHashMap<>();
        try {
            URI uri = URI.create(raw.strip());
            String userInfo = uri.getUserInfo();
            if (userInfo != null) {
                int separator = userInfo.indexOf(':');
                String user = separator < 0 ? userInfo : userInfo.substring(0, separator);
                derived.put("PULSE_DB_USER", decode(user));
                if (separator >= 0) {
                    derived.put("PULSE_DB_PASSWORD", decode(userInfo.substring(separator + 1)));
                }
            }
            String port = uri.getPort() < 0 ? "" : ":" + uri.getPort();
            String database = uri.getPath() == null ? "" : uri.getPath().replaceFirst("^/", "");
            derived.put("PULSE_DB_URL",
                    "jdbc:postgresql://" + uri.getHost() + port + "/" + database + "?" + jdbcQuery(uri.getRawQuery()));
        } catch (RuntimeException ex) {
            // A malformed URI must not stop startup: the app is meant to come up and report
            // the platform database as unreachable rather than refuse to boot.
            System.err.println("[pulse] could not parse " + NEON_URI_PROPERTY + ": " + ex.getMessage());
            return;
        }
        environment.getPropertySources().addLast(new MapPropertySource(NEON_URI_SOURCE_NAME, derived));
    }

    private static String jdbcQuery(String rawQuery) {
        List<String> kept = new ArrayList<>();
        boolean hasSslMode = false;
        if (rawQuery != null && !rawQuery.isBlank()) {
            for (String pair : rawQuery.split("&")) {
                if (pair.isBlank() || pair.startsWith("channel_binding=")) {
                    continue;
                }
                hasSslMode |= pair.startsWith("sslmode=");
                kept.add(pair);
            }
        }
        if (!hasSslMode) {
            kept.add("sslmode=require");
        }
        return String.join("&", kept);
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private static Map<String, Object> parse(Path path) {
        Map<String, Object> values = new LinkedHashMap<>();
        List<String> lines;
        try {
            lines = Files.readAllLines(path, StandardCharsets.UTF_8);
        } catch (IOException ex) {
            // Never fail startup over a .env we could not read; the process environment may
            // already carry everything needed.
            System.err.println("[pulse] could not read " + path + ": " + ex.getMessage());
            return values;
        }
        for (String raw : lines) {
            String line = raw.strip();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            int equals = line.indexOf('=');
            if (equals <= 0) {
                continue;
            }
            String key = line.substring(0, equals).strip();
            String value = unquote(line.substring(equals + 1).strip());
            values.put(key, value);
        }
        return values;
    }

    private static String unquote(String value) {
        if (value.length() >= 2
                && ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'")))) {
            return value.substring(1, value.length() - 1);
        }
        return value;
    }
}
