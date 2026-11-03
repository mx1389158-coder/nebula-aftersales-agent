package com.nebula.ticket;

import java.util.UUID;

public record IdempotencyRow(String requestHash, UUID resourceId) {}
