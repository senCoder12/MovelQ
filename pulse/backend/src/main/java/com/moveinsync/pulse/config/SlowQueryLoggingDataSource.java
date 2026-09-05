package com.moveinsync.pulse.config;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;

import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.datasource.DelegatingDataSource;

/**
 * Times every statement and warns about the slow ones.
 *
 * <p>Neon is in us-east-2 and the demo runs from India, so a perfectly healthy query already
 * costs 150-250ms. That makes the usual "log everything" approach useless -- what matters is
 * the query that costs materially more than one round trip, which is the signal for an
 * accidental N+1 or a missing index. Anything past the threshold is logged with its duration
 * and SQL.
 *
 * <p>Implemented as a JDBC proxy rather than Hibernate's own slow-query log so the timing
 * covers the real round trip and is reported at WARN.
 */
public class SlowQueryLoggingDataSource extends DelegatingDataSource {

    private static final Logger log = LoggerFactory.getLogger(SlowQueryLoggingDataSource.class);

    private final long thresholdMs;

    public SlowQueryLoggingDataSource(DataSource delegate, long thresholdMs) {
        super(delegate);
        this.thresholdMs = thresholdMs;
    }

    @Override
    public Connection getConnection() throws SQLException {
        return wrap(super.getConnection());
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
        return wrap(super.getConnection(username, password));
    }

    private Connection wrap(Connection connection) {
        return (Connection) Proxy.newProxyInstance(
                Connection.class.getClassLoader(),
                new Class<?>[] {Connection.class},
                new ConnectionHandler(connection, thresholdMs));
    }

    /** Returns statement proxies that remember the SQL they were prepared with. */
    private record ConnectionHandler(Connection delegate, long thresholdMs) implements InvocationHandler {

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            Object result = invokeDelegate(delegate, method, args);
            if (result instanceof CallableStatement || result instanceof PreparedStatement || result instanceof Statement) {
                String sql = args != null && args.length > 0 && args[0] instanceof String text ? text : "<unknown>";
                return wrapStatement((Statement) result, sql, thresholdMs);
            }
            return result;
        }
    }

    private static Statement wrapStatement(Statement statement, String sql, long thresholdMs) {
        Class<?> statementInterface = statement instanceof CallableStatement ? CallableStatement.class
                : statement instanceof PreparedStatement ? PreparedStatement.class
                : Statement.class;
        return (Statement) Proxy.newProxyInstance(
                statementInterface.getClassLoader(),
                new Class<?>[] {statementInterface},
                new StatementHandler(statement, sql, thresholdMs));
    }

    /** Times anything named execute*: execute, executeQuery, executeUpdate, executeBatch. */
    private record StatementHandler(Statement delegate, String sql, long thresholdMs) implements InvocationHandler {

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            if (!method.getName().startsWith("execute")) {
                return invokeDelegate(delegate, method, args);
            }
            String executedSql = args != null && args.length > 0 && args[0] instanceof String text ? text : sql;
            long startedAt = System.nanoTime();
            try {
                return invokeDelegate(delegate, method, args);
            } finally {
                long elapsedMs = (System.nanoTime() - startedAt) / 1_000_000;
                if (elapsedMs > thresholdMs) {
                    log.warn("slow query: {}ms (threshold {}ms) -- {}", elapsedMs, thresholdMs, oneLine(executedSql));
                }
            }
        }
    }

    private static Object invokeDelegate(Object delegate, Method method, Object[] args) throws Throwable {
        try {
            return method.invoke(delegate, args);
        } catch (InvocationTargetException ex) {
            throw ex.getTargetException();
        }
    }

    private static String oneLine(String sql) {
        String collapsed = sql.replaceAll("\\s+", " ").strip();
        return collapsed.length() > 500 ? collapsed.substring(0, 500) + " ..." : collapsed;
    }
}
