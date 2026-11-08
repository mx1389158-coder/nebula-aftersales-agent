package com.nebula.audit;

import com.nebula.security.BusinessPrincipal;
import java.util.List;
import java.util.Map;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1/admin/audit-logs")
@PreAuthorize("hasRole('ADMIN')")
public class AuditController {
    private final AuditService audit;

    public AuditController(AuditService audit) { this.audit = audit; }

    @GetMapping
    List<Map<String, Object>> list(@AuthenticationPrincipal Jwt jwt,
                                   @RequestParam(defaultValue = "100") int limit) {
        return audit.list(BusinessPrincipal.from(jwt).tenantId(), limit);
    }
}
