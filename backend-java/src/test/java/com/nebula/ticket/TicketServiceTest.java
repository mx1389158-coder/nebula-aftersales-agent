package com.nebula.ticket;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;

import com.nebula.audit.AuditService;
import com.nebula.common.BusinessException;
import com.nebula.product.CatalogMapper;
import com.nebula.security.BusinessPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

class TicketServiceTest {
    private TicketMapper tickets;
    private TicketService service;
    private HttpServletRequest request;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        tickets = mock(TicketMapper.class);
        request = mock(HttpServletRequest.class);
        objectMapper = mock(ObjectMapper.class);
        service = new TicketService(tickets, mock(CatalogMapper.class), mock(AuditService.class),
                objectMapper);
    }

    @Test
    void rejectsIllegalStatusTransitionBeforeWriting() {
        UUID ticketId = UUID.randomUUID();
        BusinessPrincipal support = principal(UUID.randomUUID(), "SUPPORT");
        when(tickets.findById("demo", ticketId)).thenReturn(row(ticketId, support.userId(), TicketStatus.CREATED));

        assertThatThrownBy(() -> service.updateStatus(
                support, ticketId, TicketStatus.RESOLVED, 0, null, request))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("不允许");
        verify(tickets, never()).updateStatus(
                ticketId, "demo", TicketStatus.RESOLVED.name(), support.userId(), 0);
    }

    @Test
    void reportsOptimisticLockConflict() {
        UUID ticketId = UUID.randomUUID();
        BusinessPrincipal support = principal(UUID.randomUUID(), "SUPPORT");
        when(tickets.findById("demo", ticketId)).thenReturn(row(ticketId, support.userId(), TicketStatus.CREATED));
        when(tickets.updateStatus(ticketId, "demo", "ASSIGNED", support.userId(), 3)).thenReturn(0);

        assertThatThrownBy(() -> service.updateStatus(
                support, ticketId, TicketStatus.ASSIGNED, 3, null, request))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("刷新后重试");
    }

    @Test
    void hidesAnotherUsersTicket() {
        UUID ticketId = UUID.randomUUID();
        BusinessPrincipal user = principal(UUID.randomUUID(), "USER");
        when(tickets.findById("demo", ticketId))
                .thenReturn(row(ticketId, UUID.randomUUID(), TicketStatus.CREATED));

        assertThatThrownBy(() -> service.get(user, ticketId))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("无权访问");
    }

    @Test
    void rejectsIdempotencyKeyReusedWithDifferentPayload() {
        BusinessPrincipal user = principal(UUID.randomUUID(), "USER");
        when(objectMapper.writeValueAsString(any())).thenReturn("canonical-request");
        when(tickets.findIdempotency(user.userId(), "CREATE_TICKET", "same-key"))
                .thenReturn(new IdempotencyRow("different-hash", UUID.randomUUID()));

        assertThatThrownBy(() -> service.create(
                user, null, "summary", "13800000000", "same-key", request))
                .isInstanceOf(BusinessException.class)
                .hasMessageContaining("请求内容不同");
        verify(tickets, never()).insertIdempotency(any(), any(), any(), any(), any(), any());
    }

    private BusinessPrincipal principal(UUID id, String role) {
        return new BusinessPrincipal(id, "demo", List.of(role), "tester");
    }

    private TicketRow row(UUID id, UUID owner, TicketStatus status) {
        OffsetDateTime now = OffsetDateTime.now();
        return new TicketRow(id, "T-1", "demo", owner, null, "summary", "13800000000",
                status, null, 0, now, now);
    }
}
