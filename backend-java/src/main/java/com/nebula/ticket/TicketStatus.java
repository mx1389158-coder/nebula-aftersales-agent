package com.nebula.ticket;

import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

public enum TicketStatus {
    CREATED, ASSIGNED, PROCESSING, RESOLVED, CLOSED;

    private static final Map<TicketStatus, Set<TicketStatus>> TRANSITIONS = Map.of(
            CREATED, EnumSet.of(ASSIGNED, CLOSED),
            ASSIGNED, EnumSet.of(PROCESSING, CREATED, CLOSED),
            PROCESSING, EnumSet.of(RESOLVED, ASSIGNED),
            RESOLVED, EnumSet.of(CLOSED, PROCESSING),
            CLOSED, EnumSet.of(PROCESSING));

    public boolean canTransitionTo(TicketStatus target) {
        return this == target || TRANSITIONS.getOrDefault(this, Set.of()).contains(target);
    }
}
