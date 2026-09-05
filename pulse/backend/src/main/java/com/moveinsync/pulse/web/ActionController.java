package com.moveinsync.pulse.web;

import java.util.List;

import com.moveinsync.pulse.action.ActionDraftService;
import com.moveinsync.pulse.action.dto.ActionDraftResponse;
import com.moveinsync.pulse.action.dto.ApproveRequest;
import com.moveinsync.pulse.action.dto.DraftRequest;
import com.moveinsync.pulse.action.dto.RejectRequest;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Action drafting and approval -- the "act" third of sense-reason-act. The
 * agent only ever drafts (POST /insights/{id}/actions); a human approves or
 * rejects one action at a time; nothing here ever sends anything, see
 * ActionDraftService's class docstring. */
@RestController
@RequestMapping("/api")
public class ActionController {

    private final ActionDraftService actionDraftService;

    public ActionController(ActionDraftService actionDraftService) {
        this.actionDraftService = actionDraftService;
    }

    @GetMapping("/insights/{id}/actions")
    public List<ActionDraftResponse> listForInsight(@PathVariable String id) {
        return actionDraftService.listForInsight(id);
    }

    @PostMapping("/insights/{id}/actions")
    public ActionDraftResponse draft(@PathVariable String id, @Valid @RequestBody DraftRequest request) {
        return actionDraftService.draft(id, request.type());
    }

    @PostMapping("/actions/{id}/approve")
    public ActionDraftResponse approve(@PathVariable String id,
            @RequestBody(required = false) ApproveRequest request) {
        return actionDraftService.approve(id, request == null ? ApproveRequest.empty() : request);
    }

    @PostMapping("/actions/{id}/reject")
    public ActionDraftResponse reject(@PathVariable String id, @Valid @RequestBody RejectRequest request) {
        return actionDraftService.reject(id, request);
    }

    @GetMapping("/actions")
    public List<ActionDraftResponse> audit(@RequestParam(required = false) String status) {
        return actionDraftService.audit(status);
    }
}
