package com.moveinsync.pulse.web;

import java.util.List;

import com.moveinsync.pulse.report.DispatchApiRequest;
import com.moveinsync.pulse.report.DispatchApiResponse;
import com.moveinsync.pulse.report.DispatchView;
import com.moveinsync.pulse.report.LeadershipPack;
import com.moveinsync.pulse.report.LeadershipPackService;
import com.moveinsync.pulse.report.PreviewRequest;
import com.moveinsync.pulse.report.PreviewResponse;
import com.moveinsync.pulse.report.RecipientsResponse;
import com.moveinsync.pulse.report.ReportDispatchService;

import jakarta.validation.Valid;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Serves the leadership pack -- a one-click monthly report a transport &
 * facilities head can forward to leadership unedited -- and its send flow:
 * who can receive it, a no-persist preview of exactly what they would see,
 * the dispatch itself, and its history. Tenant-filtered like every other
 * endpoint. */
@RestController
@RequestMapping("/api")
public class ReportController {

    private final LeadershipPackService leadershipPackService;
    private final ReportDispatchService reportDispatchService;

    public ReportController(LeadershipPackService leadershipPackService, ReportDispatchService reportDispatchService) {
        this.leadershipPackService = leadershipPackService;
        this.reportDispatchService = reportDispatchService;
    }

    @GetMapping("/reports/leadership")
    public LeadershipPack leadership(@RequestParam(defaultValue = "2026-07") String period) {
        try {
            return leadershipPackService.assemble(period);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }

    @GetMapping("/reports/leadership/recipients")
    public RecipientsResponse recipients() {
        return reportDispatchService.recipients();
    }

    @PostMapping("/reports/leadership/preview")
    public PreviewResponse preview(@RequestBody PreviewRequest request) {
        try {
            return reportDispatchService.preview(request);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }

    @PostMapping("/reports/leadership/dispatch")
    public DispatchApiResponse dispatch(@Valid @RequestBody DispatchApiRequest request) {
        try {
            return reportDispatchService.dispatch(request);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }

    @GetMapping("/reports/dispatches")
    public List<DispatchView> dispatches(@RequestParam(required = false) String period) {
        return reportDispatchService.history(period);
    }
}
