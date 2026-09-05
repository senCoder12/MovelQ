package com.moveinsync.pulse.report;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.config.DispatchProperties;
import com.moveinsync.pulse.report.dispatch.DispatchRequest;
import com.moveinsync.pulse.report.dispatch.DispatchResult;
import com.moveinsync.pulse.report.dispatch.DispatchStatus;
import com.moveinsync.pulse.report.dispatch.ReportTransport;
import com.moveinsync.pulse.report.render.LeadershipPackRenderer;
import com.moveinsync.pulse.report.render.RenderedReport;
import com.moveinsync.pulse.web.TenantContext;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * Renders, persists and (once) transmits the leadership pack. This is the
 * only class that ever calls ReportTransport -- everything up to that call
 * is the valuable, inspectable part (who it goes to, what they see, the
 * immutable record); the send itself is one interface call at the very end.
 *
 * Idempotency: a dispatch for the same (tenant, period, content_hash) within
 * the last hour is returned as-is with duplicate=true rather than sent
 * again. The window is deliberately short -- a person re-running the exact
 * same send an hour later has probably decided they meant it.
 */
@Service
public class ReportDispatchService {

    private static final String REPORT_ID = "leadership_pack";
    /** No user/auth model exists anywhere in this app yet -- see the same
     * placeholder in ActionDraftService.DECIDED_BY. */
    private static final String DISPATCHED_BY = "operator";
    private static final long DUPLICATE_WINDOW_MINUTES = 60;

    private final LeadershipPackService leadershipPackService;
    private final LeadershipPackRenderer renderer;
    private final ReportRecipientRepository recipientRepository;
    private final ReportDispatchRepository dispatchRepository;
    private final ReportTransport transport;
    private final DispatchProperties dispatchProperties;
    private final TenantContext tenantContext;
    private final ObjectMapper objectMapper;

    public ReportDispatchService(LeadershipPackService leadershipPackService, LeadershipPackRenderer renderer,
            ReportRecipientRepository recipientRepository, ReportDispatchRepository dispatchRepository,
            ReportTransport transport, DispatchProperties dispatchProperties, TenantContext tenantContext,
            ObjectMapper objectMapper) {
        this.leadershipPackService = leadershipPackService;
        this.renderer = renderer;
        this.recipientRepository = recipientRepository;
        this.dispatchRepository = dispatchRepository;
        this.transport = transport;
        this.dispatchProperties = dispatchProperties;
        this.tenantContext = tenantContext;
        this.objectMapper = objectMapper;
    }

    public RecipientsResponse recipients() {
        List<RecipientView> views = recipientRepository
                .findByTenantIdOrderByRoleAscNameAsc(tenantContext.tenantId())
                .stream().map(RecipientView::of).toList();
        return new RecipientsResponse(views, transport.name());
    }

    /** Renders but never persists -- the drawer's Step 2 calls this on every
     * recipient-selection or subject change, so it must stay side-effect
     * free. `recipientIds` is validated the same as dispatch's (an unknown
     * id is still a 400 here), even though the render itself does not vary
     * by recipient today -- see the module docstring's "out of scope" note
     * on per-recipient personalisation. */
    public PreviewResponse preview(PreviewRequest request) {
        resolveRecipients(request.recipientIds());
        RenderedReport rendered = renderer.render(leadershipPackService.assemble(request.period()));
        return new PreviewResponse(rendered.subject(), rendered.bodyHtml(), rendered.bodyText());
    }

    public DispatchApiResponse dispatch(DispatchApiRequest request) {
        String tenantId = tenantContext.tenantId();
        List<ReportRecipient> recipients = resolveRecipients(request.recipientIds());

        RenderedReport rendered = renderer.render(leadershipPackService.assemble(request.period()));
        String subject = hasText(request.subject()) ? request.subject() : rendered.subject();
        String contentHash = sha256(subject + " " + rendered.bodyHtml());

        Instant cutoff = Instant.now().minus(DUPLICATE_WINDOW_MINUTES, ChronoUnit.MINUTES);
        Optional<ReportDispatch> existing = dispatchRepository
                .findFirstByTenantIdAndPeriodAndContentHashAndStatusAndDispatchedAtAfterOrderByDispatchedAtDesc(
                        tenantId, request.period(), contentHash, DispatchStatus.SUCCESS.name(), cutoff);
        if (existing.isPresent()) {
            return new DispatchApiResponse(toView(existing.get()), true);
        }

        List<DispatchRecipientView> recipientViews = recipients.stream().map(DispatchRecipientView::of).toList();
        DispatchRequest transportRequest = new DispatchRequest(
                tenantId,
                REPORT_ID,
                recipientViews.stream().map(DispatchRecipientView::toTransportRecipient).toList(),
                subject,
                rendered.bodyHtml(),
                rendered.bodyText(),
                List.of(),
                dispatchProperties.fromAddress());
        DispatchResult result = transport.send(transportRequest);

        ReportDispatch entity = new ReportDispatch(
                "disp_" + UUID.randomUUID(),
                tenantId,
                REPORT_ID,
                request.period(),
                toJson(recipientViews),
                subject,
                rendered.bodyHtml(),
                rendered.bodyText(),
                result.transport(),
                result.status().name(),
                result.dispatchedAt(),
                DISPATCHED_BY,
                result.providerMessageId(),
                result.error(),
                contentHash);
        dispatchRepository.save(entity);
        return new DispatchApiResponse(toView(entity), false);
    }

    public List<DispatchView> history(String period) {
        String tenantId = tenantContext.tenantId();
        List<ReportDispatch> dispatches = (period == null || period.isBlank())
                ? dispatchRepository.findByTenantIdOrderByDispatchedAtDesc(tenantId)
                : dispatchRepository.findByTenantIdAndPeriodOrderByDispatchedAtDesc(tenantId, period);
        return dispatches.stream().map(this::toView).toList();
    }

    private List<ReportRecipient> resolveRecipients(List<String> recipientIds) {
        if (recipientIds == null || recipientIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "recipient_ids must not be empty");
        }
        String tenantId = tenantContext.tenantId();
        List<ReportRecipient> found = recipientRepository.findByTenantIdAndRecipientIdIn(tenantId, recipientIds);
        if (found.size() != Set.copyOf(recipientIds).size()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "one or more recipient_ids are unknown for this tenant");
        }
        return found;
    }

    private DispatchView toView(ReportDispatch dispatch) {
        return new DispatchView(
                dispatch.dispatchId(),
                dispatch.reportId(),
                dispatch.period(),
                fromJson(dispatch.recipientsJson()),
                dispatch.subject(),
                dispatch.bodyHtml(),
                dispatch.bodyText(),
                dispatch.transport(),
                dispatch.status(),
                dispatch.dispatchedAt(),
                dispatch.dispatchedBy(),
                dispatch.providerMessageId(),
                dispatch.errorSummary(),
                dispatch.contentHash());
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to serialize dispatch recipients", ex);
        }
    }

    private List<DispatchRecipientView> fromJson(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<DispatchRecipientView>>() {
            });
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("failed to deserialize dispatch recipients", ex);
        }
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException ex) {
            // SHA-256 is guaranteed available on every JDK distribution.
            throw new IllegalStateException(ex);
        }
    }
}
