package com.nebula.ticket;

import java.time.OffsetDateTime;
import java.util.UUID;

public record TicketRow(
        UUID id,
        String ticketNo,
        String tenantId,
        UUID userId,
        UUID deviceId,
        String summary,
        String contact,
        TicketStatus status,
        UUID assigneeId,
        long version,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {}
