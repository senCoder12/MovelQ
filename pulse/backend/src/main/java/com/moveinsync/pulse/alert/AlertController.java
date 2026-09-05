package com.moveinsync.pulse.alert;

import java.util.List;

import com.moveinsync.pulse.alert.dto.AcknowledgeRequest;
import com.moveinsync.pulse.alert.dto.AlertDeliveryView;
import com.moveinsync.pulse.alert.dto.AlertView;
import com.moveinsync.pulse.alert.dto.MuteRequest;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Alerts: what a scan decided, and the two things a human can do about
 * one -- acknowledge it, or mute the (rule, entity) it came from. Nothing
 * here ever sends anything; see AlertDelivery's class docstring. */
@RestController
@RequestMapping("/api/alerts")
public class AlertController {

    private final AlertService alertService;

    public AlertController(AlertService alertService) {
        this.alertService = alertService;
    }

    @GetMapping
    public List<AlertView> list(@RequestParam(required = false) String status,
            @RequestParam(required = false) String persona) {
        return alertService.list(status, persona);
    }

    @PostMapping("/{id}/acknowledge")
    public AlertView acknowledge(@PathVariable String id, @RequestBody(required = false) AcknowledgeRequest request) {
        return alertService.acknowledge(id, request == null ? AcknowledgeRequest.empty() : request);
    }

    @PostMapping("/{id}/mute")
    public AlertView mute(@PathVariable String id, @Valid @RequestBody MuteRequest request) {
        return alertService.mute(id, request);
    }

    @GetMapping("/{id}/delivery")
    public AlertDeliveryView delivery(@PathVariable String id) {
        return alertService.getDelivery(id);
    }
}
