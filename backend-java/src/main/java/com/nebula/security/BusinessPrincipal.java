package com.nebula.security;

import java.util.List;
import java.util.UUID;
import org.springframework.security.oauth2.jwt.Jwt;

public record BusinessPrincipal(UUID userId, String tenantId, List<String> roles, String token) {
    public static BusinessPrincipal from(Jwt jwt) {
        List<String> roles = jwt.getClaimAsStringList("roles");
        if (roles == null || roles.isEmpty()) {
            String role = jwt.getClaimAsString("role");
            roles = role == null ? List.of("USER") : List.of(role.toUpperCase());
        }
        return new BusinessPrincipal(
                UUID.fromString(jwt.getSubject()), jwt.getClaimAsString("tenant_id"), roles,
                jwt.getTokenValue());
    }

    public boolean hasRole(String role) {
        return roles.stream().anyMatch(item -> item.equalsIgnoreCase(role));
    }
}
