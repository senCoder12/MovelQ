package com.moveinsync.pulse.tenant;

import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.hibernate.Session;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.orm.jpa.EntityManagerFactoryUtils;
import org.springframework.orm.jpa.EntityManagerHolder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * Enables the Hibernate {@code tenantFilter} for the duration of every repository call,
 * parameterised from {@link TenantContextHolder}.
 *
 * <p>Two things make this enforcement rather than convention:
 *
 * <ul>
 *   <li>A repository call with no tenant in context throws {@link MissingTenantException}.
 *       There is no "unscoped" mode to fall back to.
 *   <li>The filter is enabled on the <em>same</em> Hibernate session the repository will use.
 *       Outside a transaction, {@code EntityManager.unwrap} would hand back a throwaway
 *       session and the filter would be enabled on a session nobody queries through. So when
 *       no transaction is running the aspect opens an EntityManager and binds it to the
 *       thread, the way OpenEntityManagerInView does, and the repository then resolves to
 *       that same one.
 * </ul>
 *
 * <p>Binding rather than opening a transaction is a latency decision. Neon is ~300ms away
 * from where this is demoed, and wrapping a single read in a transaction costs a COMMIT
 * round trip on top of the query -- measurably about half the brief's response time. Reads
 * run in autocommit and pay one round trip. Writes are unaffected: Spring Data's own
 * {@code @Transactional} starts a transaction on the bound EntityManager, so the filter is
 * still enabled on the session that does the work.
 *
 * <p>Ordered ahead of Spring's transaction advisor so the filter is in place before any
 * query runs.
 */
@Aspect
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class TenantFilterAspect {

    public static final String FILTER_NAME = "tenantFilter";
    public static final String FILTER_PARAM = "tenantId";

    private static final Logger log = LoggerFactory.getLogger(TenantFilterAspect.class);

    // Resolved on first repository call rather than injected, so building this aspect does
    // not drag the EntityManagerFactory into existence during startup.
    private final ObjectProvider<EntityManagerFactory> entityManagerFactory;

    public TenantFilterAspect(ObjectProvider<EntityManagerFactory> entityManagerFactory) {
        this.entityManagerFactory = entityManagerFactory;
    }

    @Around("execution(* com.moveinsync.pulse..*Repository+.*(..))")
    public Object scopeToTenant(ProceedingJoinPoint joinPoint) throws Throwable {
        String operation = joinPoint.getSignature().toShortString();
        String tenantId = TenantContextHolder.require(operation);

        EntityManagerFactory factory = entityManagerFactory.getObject();
        if (TransactionSynchronizationManager.hasResource(factory)) {
            // A transaction, or an outer repository call, already bound one.
            return proceedWithFilter(joinPoint, tenantId);
        }
        return proceedWithBoundEntityManager(factory, joinPoint, tenantId);
    }

    /** Binds a fresh EntityManager for the duration of the call so the filter and the query
     * share a session, without the COMMIT round trip a transaction would add. */
    private Object proceedWithBoundEntityManager(EntityManagerFactory factory, ProceedingJoinPoint joinPoint,
            String tenantId) throws Throwable {
        EntityManager entityManager = factory.createEntityManager();
        TransactionSynchronizationManager.bindResource(factory, new EntityManagerHolder(entityManager));
        try {
            return proceedWithFilter(joinPoint, tenantId);
        } finally {
            TransactionSynchronizationManager.unbindResource(factory);
            EntityManagerFactoryUtils.closeEntityManager(entityManager);
        }
    }

    private Object proceedWithFilter(ProceedingJoinPoint joinPoint, String tenantId) throws Throwable {
        EntityManager entityManager =
                EntityManagerFactoryUtils.getTransactionalEntityManager(entityManagerFactory.getObject());
        if (entityManager == null) {
            throw new IllegalStateException("no EntityManager bound to the current thread");
        }
        Session session = entityManager.unwrap(Session.class);
        boolean alreadyEnabled = session.getEnabledFilter(FILTER_NAME) != null;
        if (!alreadyEnabled) {
            session.enableFilter(FILTER_NAME).setParameter(FILTER_PARAM, tenantId);
            log.trace("tenantFilter enabled for {} as {}", joinPoint.getSignature().toShortString(), tenantId);
        }
        try {
            return joinPoint.proceed();
        } finally {
            // Only the call that enabled it disables it; nested repository calls leave it be.
            if (!alreadyEnabled) {
                session.disableFilter(FILTER_NAME);
            }
        }
    }
}
