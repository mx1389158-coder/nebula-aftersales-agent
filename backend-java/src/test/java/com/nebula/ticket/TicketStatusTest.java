package com.nebula.ticket;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class TicketStatusTest {
    @Test
    void allowsDocumentedHappyPath() {
        assertThat(TicketStatus.CREATED.canTransitionTo(TicketStatus.ASSIGNED)).isTrue();
        assertThat(TicketStatus.ASSIGNED.canTransitionTo(TicketStatus.PROCESSING)).isTrue();
        assertThat(TicketStatus.PROCESSING.canTransitionTo(TicketStatus.RESOLVED)).isTrue();
        assertThat(TicketStatus.RESOLVED.canTransitionTo(TicketStatus.CLOSED)).isTrue();
    }

    @Test
    void rejectsSkippingRequiredStates() {
        assertThat(TicketStatus.CREATED.canTransitionTo(TicketStatus.RESOLVED)).isFalse();
        assertThat(TicketStatus.PROCESSING.canTransitionTo(TicketStatus.CREATED)).isFalse();
    }

    @Test
    void supportsExplicitReopen() {
        assertThat(TicketStatus.CLOSED.canTransitionTo(TicketStatus.PROCESSING)).isTrue();
    }
}
