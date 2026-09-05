package com.moveinsync.pulse.web;

import com.moveinsync.pulse.report.LeadershipPack;
import com.moveinsync.pulse.report.LeadershipPackService;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Serves the leadership pack -- a one-click monthly report a transport &
 * facilities head can forward to leadership unedited. Tenant-filtered like
 * every other endpoint. */
@RestController
@RequestMapping("/api")
public class ReportController {

    private final LeadershipPackService leadershipPackService;

    public ReportController(LeadershipPackService leadershipPackService) {
        this.leadershipPackService = leadershipPackService;
    }

    @GetMapping("/reports/leadership")
    public LeadershipPack leadership(@RequestParam(defaultValue = "2026-07") String period) {
        try {
            return leadershipPackService.assemble(period);
        } catch (RestClientException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "agent unavailable", ex);
        }
    }
}
