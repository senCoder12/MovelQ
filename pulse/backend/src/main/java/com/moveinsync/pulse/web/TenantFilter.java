package com.moveinsync.pulse.web;

import java.io.IOException;

import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Resolves the tenant from X-Tenant-Id into the request-scoped {@link TenantContext} for
 * every /api/** call. Requests without the header are rejected -- there is no "no tenant"
 * mode once you're past health checks. */
@Component
public class TenantFilter extends OncePerRequestFilter {

    private static final String TENANT_HEADER = "X-Tenant-Id";

    private final ObjectProvider<TenantContext> tenantContext;
    private final ObjectMapper objectMapper;

    public TenantFilter(ObjectProvider<TenantContext> tenantContext, ObjectMapper objectMapper) {
        this.tenantContext = tenantContext;
        this.objectMapper = objectMapper;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return !path.startsWith("/api/") || path.equals("/api/health");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String tenantId = request.getHeader(TENANT_HEADER);
        if (tenantId == null || tenantId.isBlank()) {
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            objectMapper.writeValue(response.getWriter(),
                    new Error(HttpServletResponse.SC_BAD_REQUEST, "missing required header: " + TENANT_HEADER));
            return;
        }
        tenantContext.getObject().setTenantId(tenantId);
        try {
            chain.doFilter(request, response);
        } finally {
            // Request threads are pooled. Leaving the tenant set would hand the next
            // request on this thread the previous caller's scope.
            tenantContext.getObject().clear();
        }
    }

    private record Error(int status, String message) {
    }
}
