package com.nebula.auth;

import java.util.UUID;

public record UserAccount(
        UUID id,
        String tenantId,
        String username,
        String email,
        String passwordHash,
        String displayName,
        String status,
        String role
) {}
