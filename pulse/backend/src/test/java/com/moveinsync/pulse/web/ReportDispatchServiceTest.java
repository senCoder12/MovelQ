package com.moveinsync.pulse.web;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.moveinsync.pulse.config.DispatchProperties;
import com.moveinsync.pulse.report.DispatchApiRequest;
import com.moveinsync.pulse.report.DispatchApiResponse;
import com.moveinsync.pulse.report.LeadershipPack;
import com.moveinsync.pulse.report.LeadershipPack.DateRange;
import com.moveinsync.pulse.report.LeadershipPack.Footer;
import com.moveinsync.pulse.report.LeadershipPack.Scope;
import com.moveinsync.pulse.report.LeadershipPackService;
import com.moveinsync.pulse.report.PreviewRequest;
import com.moveinsync.pulse.report.PreviewResponse;
import com.moveinsync.pulse.report.RecipientsResponse;
import com.moveinsync.pulse.report.ReportDispatchRepository;
import com.moveinsync.pulse.report.ReportDispatchService;
import com.moveinsync.pulse.report.ReportRecipient;
import com.moveinsync.pulse.report.ReportRecipientRepository;
import com.moveinsync.pulse.report.dispatch.DispatchRequest;
import com.moveinsync.pulse.report.dispatch.DispatchResult;
import com.moveinsync.pulse.report.dispatch.DispatchStatus;
import com.moveinsync.pulse.report.dispatch.ReportTransport;
import com.moveinsync.pulse.report.render.LeadershipPackRenderer;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

/** In the {@code web} package so it can call TenantContext.setTenantId --
 * see the same note on ActionDraftServiceTest. */
@ExtendWith(MockitoExtension.class)
class ReportDispatchServiceTest {

    @Mock
    private LeadershipPackService leadershipPackService;
    @Mock
    private ReportRecipientRepository recipientRepository;
    @Mock
    private ReportDispatchRepository dispatchRepository;

    private final LeadershipPackRenderer renderer = new LeadershipPackRenderer();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DispatchProperties dispatchProperties = new DispatchProperties("logged", "pulse-reports@example.com");

    /** Counts calls so tests can assert the transport is never invoked twice
     * for what should be a single logical dispatch (the duplicate path). */
    private static final class CountingTransport implements ReportTransport {
        final AtomicInteger calls = new AtomicInteger();

        @Override
        public DispatchResult send(DispatchRequest request) {
            calls.incrementAndGet();
            return new DispatchResult(DispatchStatus.SUCCESS, "logged", Instant.now(), null, null);
        }

        @Override
        public String name() {
            return "logged";
        }
    }

    private static LeadershipPack samplePack() {
        return new LeadershipPack("July 2026", new Scope("catalyst", List.of("HQ"), 100,
                new DateRange("2026-07-01", "2026-07-31")), "headline", "summary", List.of(), List.of(),
                new Footer(100, 0, 0.0, List.of()));
    }

    private static ReportRecipient recipient(String id, String tenantId, String role, boolean isDefault) {
        return new ReportRecipient(id, tenantId, "Test " + role, role + "@" + tenantId + ".example.com", role,
                isDefault);
    }

    private ReportDispatchService serviceForTenant(String tenantId, ReportTransport transport) {
        TenantContext tenantContext = new TenantContext();
        tenantContext.setTenantId(tenantId);
        return new ReportDispatchService(leadershipPackService, renderer, recipientRepository, dispatchRepository,
                transport, dispatchProperties, tenantContext, objectMapper);
    }

    @Test
    void recipientsIncludesTheActiveTransportName() {
        when(recipientRepository.findByTenantIdOrderByRoleAscNameAsc("catalyst"))
                .thenReturn(List.of(recipient("rcpt_catalyst_transport_head", "catalyst", "transport_head", true)));

        RecipientsResponse response = serviceForTenant("catalyst", new CountingTransport()).recipients();

        assertThat(response.transport()).isEqualTo("logged");
        assertThat(response.recipients()).hasSize(1);
        assertThat(response.recipients().get(0).recipientId()).isEqualTo("rcpt_catalyst_transport_head");
    }

    @Test
    void previewRendersWithoutPersistingOrCallingTheTransport() {
        when(recipientRepository.findByTenantIdAndRecipientIdIn("catalyst", List.of("rcpt_catalyst_transport_head")))
                .thenReturn(List.of(recipient("rcpt_catalyst_transport_head", "catalyst", "transport_head", true)));
        when(leadershipPackService.assemble("2026-07")).thenReturn(samplePack());
        CountingTransport transport = new CountingTransport();

        PreviewResponse preview = serviceForTenant("catalyst", transport)
                .preview(new PreviewRequest("2026-07", List.of("rcpt_catalyst_transport_head")));

        assertThat(preview.subject()).isEqualTo("Catalyst mobility operations — July 2026");
        assertThat(transport.calls.get()).isZero();
    }

    @Test
    void dispatchPersistsAndCallsTheTransportExactlyOnce() {
        when(recipientRepository.findByTenantIdAndRecipientIdIn("catalyst", List.of("rcpt_catalyst_transport_head")))
                .thenReturn(List.of(recipient("rcpt_catalyst_transport_head", "catalyst", "transport_head", true)));
        when(leadershipPackService.assemble("2026-07")).thenReturn(samplePack());
        when(dispatchRepository.findFirstByTenantIdAndPeriodAndContentHashAndStatusAndDispatchedAtAfterOrderByDispatchedAtDesc(
                org.mockito.ArgumentMatchers.eq("catalyst"), org.mockito.ArgumentMatchers.eq("2026-07"),
                org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.eq("SUCCESS"),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(Optional.empty());
        CountingTransport transport = new CountingTransport();

        DispatchApiResponse response = serviceForTenant("catalyst", transport)
                .dispatch(new DispatchApiRequest("2026-07", List.of("rcpt_catalyst_transport_head"), null, null));

        assertThat(response.duplicate()).isFalse();
        assertThat(response.dispatch().status()).isEqualTo("SUCCESS");
        assertThat(response.dispatch().recipients()).hasSize(1);
        assertThat(transport.calls.get()).isEqualTo(1);
    }

    /** A FAILED dispatch (e.g. SMTP down) must never block a retry of the
     * same content -- nothing was actually sent, so there is nothing for a
     * later identical attempt to duplicate. The idempotency lookup only
     * ever searches for a prior SUCCESS with the same content_hash. */
    @Test
    void aPriorFailedDispatchDoesNotBlockARetryOfIdenticalContent() {
        when(recipientRepository.findByTenantIdAndRecipientIdIn("catalyst", List.of("rcpt_catalyst_transport_head")))
                .thenReturn(List.of(recipient("rcpt_catalyst_transport_head", "catalyst", "transport_head", true)));
        when(leadershipPackService.assemble("2026-07")).thenReturn(samplePack());
        when(dispatchRepository.findFirstByTenantIdAndPeriodAndContentHashAndStatusAndDispatchedAtAfterOrderByDispatchedAtDesc(
                org.mockito.ArgumentMatchers.eq("catalyst"), org.mockito.ArgumentMatchers.eq("2026-07"),
                org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.eq("SUCCESS"),
                org.mockito.ArgumentMatchers.any()))
                .thenReturn(Optional.empty());

        ReportTransport failingThenSucceeding = new ReportTransport() {
            private int calls;

            @Override
            public DispatchResult send(DispatchRequest request) {
                calls++;
                return calls == 1
                        ? new DispatchResult(DispatchStatus.FAILED, "smtp", Instant.now(), null, "connection refused")
                        : new DispatchResult(DispatchStatus.SUCCESS, "smtp", Instant.now(), "mid", null);
            }

            @Override
            public String name() {
                return "smtp";
            }
        };
        ReportDispatchService service = serviceForTenant("catalyst", failingThenSucceeding);
        DispatchApiRequest request = new DispatchApiRequest("2026-07", List.of("rcpt_catalyst_transport_head"), null, null);

        DispatchApiResponse first = service.dispatch(request);
        assertThat(first.dispatch().status()).isEqualTo("FAILED");
        assertThat(first.duplicate()).isFalse();

        DispatchApiResponse retry = service.dispatch(request);
        assertThat(retry.duplicate()).isFalse();
        assertThat(retry.dispatch().status()).isEqualTo("SUCCESS");
    }

    @Test
    void dispatchRejectsAnEmptyRecipientList() {
        ReportDispatchService service = serviceForTenant("catalyst", new CountingTransport());

        assertThatThrownBy(() -> service.dispatch(new DispatchApiRequest("2026-07", List.of(), null, null)))
                .isInstanceOf(ResponseStatusException.class);
    }

    @Test
    void dispatchRejectsAnUnknownRecipientId() {
        when(recipientRepository.findByTenantIdAndRecipientIdIn("catalyst", List.of("rcpt_missing")))
                .thenReturn(List.of());
        ReportDispatchService service = serviceForTenant("catalyst", new CountingTransport());

        assertThatThrownBy(() -> service.dispatch(new DispatchApiRequest("2026-07", List.of("rcpt_missing"), null, null)))
                .isInstanceOf(ResponseStatusException.class);
    }
}
