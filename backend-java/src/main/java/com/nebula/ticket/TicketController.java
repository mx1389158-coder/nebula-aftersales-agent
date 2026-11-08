package com.nebula.ticket;

import com.nebula.security.BusinessPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1/tickets")
public class TicketController {
    private final TicketService tickets;

    public TicketController(TicketService tickets) { this.tickets = tickets; }

    @GetMapping
    List<Map<String, Object>> list(@AuthenticationPrincipal Jwt jwt) {
        return tickets.list(BusinessPrincipal.from(jwt));
    }

    @GetMapping("/{id}")
    Map<String, Object> get(@PathVariable UUID id, @AuthenticationPrincipal Jwt jwt) {
        return tickets.get(BusinessPrincipal.from(jwt), id);
    }

    @GetMapping("/idempotency/{key}")
    Map<String, Object> byIdempotencyKey(@PathVariable String key,
            @AuthenticationPrincipal Jwt jwt) {
        return tickets.findByIdempotency(BusinessPrincipal.from(jwt), key);
    }

    @PostMapping
    Map<String, Object> create(@Valid @RequestBody CreateRequest body,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @AuthenticationPrincipal Jwt jwt, HttpServletRequest request) {
        return tickets.create(BusinessPrincipal.from(jwt), body.deviceId(), body.summary(),
                body.contact(), body.agentContext(), idempotencyKey, request);
    }

    @PatchMapping("/{id}/status")
    Map<String, Object> updateStatus(@PathVariable UUID id, @Valid @RequestBody StatusRequest body,
            @AuthenticationPrincipal Jwt jwt, HttpServletRequest request) {
        return tickets.updateStatus(BusinessPrincipal.from(jwt), id, body.status(), body.version(),
                body.note(), request);
    }

    public record CreateRequest(UUID deviceId,
            @NotBlank @Size(max = 4000) String summary,
            @NotBlank @Size(max = 120) String contact,
            Map<String, Object> agentContext) {}
    public record StatusRequest(@NotNull TicketStatus status, long version,
                                @Size(max = 1000) String note) {}
}
