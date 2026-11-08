package com.nebula.auth;

import com.nebula.security.BusinessPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/business/v1/admin/users")
@PreAuthorize("hasRole('ADMIN')")
public class UserAdminController {
    private final UserAdminService users;
    public UserAdminController(UserAdminService users) { this.users = users; }

    @GetMapping
    List<Map<String, Object>> list(@AuthenticationPrincipal Jwt jwt) {
        return users.list(BusinessPrincipal.from(jwt).tenantId());
    }

    @PatchMapping("/{id}")
    Map<String, Object> update(@PathVariable UUID id, @Valid @RequestBody UpdateRequest body,
            @AuthenticationPrincipal Jwt jwt, HttpServletRequest request) {
        return users.update(BusinessPrincipal.from(jwt), id, body.status(), body.role(), request);
    }

    public record UpdateRequest(String status, String role) {}
}
