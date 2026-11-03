package com.nebula.ticket;

import tools.jackson.databind.ObjectMapper;
import com.nebula.audit.AuditService;
import com.nebula.common.BusinessException;
import com.nebula.common.RequestIdFilter;
import com.nebula.product.CatalogMapper;
import com.nebula.security.BusinessPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TicketService {
    private static final String CREATE_OPERATION = "CREATE_TICKET";
    private final TicketMapper tickets;
    private final CatalogMapper catalog;
    private final AuditService audit;
    private final ObjectMapper objectMapper;

    public TicketService(TicketMapper tickets, CatalogMapper catalog, AuditService audit,
                         ObjectMapper objectMapper) {
        this.tickets = tickets;
        this.catalog = catalog;
        this.audit = audit;
        this.objectMapper = objectMapper;
    }

    public List<Map<String, Object>> list(BusinessPrincipal principal) {
        List<TicketRow> rows = principal.hasRole("ADMIN") || principal.hasRole("SUPPORT")
                ? tickets.listForStaff(principal.tenantId())
                : tickets.listForUser(principal.tenantId(), principal.userId());
        return rows.stream().map(row -> view(row, false)).toList();
    }

    public Map<String, Object> get(BusinessPrincipal principal, UUID id) {
        TicketRow row = requireVisible(principal, id);
        return view(row, true);
    }

    @Transactional
    public Map<String, Object> create(BusinessPrincipal principal, UUID deviceId, String summary,
                                      String contact, String idempotencyKey, HttpServletRequest request) {
        if (idempotencyKey == null || idempotencyKey.length() < 8 || idempotencyKey.length() > 120) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "IDEMPOTENCY_KEY_REQUIRED",
                    "创建工单必须提供 8–120 字符的 Idempotency-Key");
        }
        if (deviceId != null) {
            Map<String, Object> device = catalog.getDevice(principal.tenantId(), deviceId);
            if (device == null || !principal.userId().equals(device.get("owner_id"))) {
                throw new BusinessException(HttpStatus.NOT_FOUND, "DEVICE_NOT_OWNED", "设备不存在或不属于当前用户");
            }
        }
        String requestHash = hash(Map.of(
                "device_id", deviceId == null ? "" : deviceId.toString(),
                "summary", summary.trim(), "contact", contact.trim()));
        IdempotencyRow existing = tickets.findIdempotency(principal.userId(), CREATE_OPERATION, idempotencyKey);
        if (existing != null) return existing(principal, existing, requestHash);

        UUID ticketId = UUID.randomUUID();
        String ticketNo = "T" + DateTimeFormatter.ofPattern("yyyyMMddHHmmss")
                .withZone(ZoneOffset.UTC).format(java.time.Instant.now())
                + ticketId.toString().substring(0, 4).toUpperCase();
        if (tickets.insertIdempotency(UUID.randomUUID(), principal.userId(), CREATE_OPERATION,
                idempotencyKey, requestHash, ticketId) == 0) {
            IdempotencyRow raced = tickets.findIdempotency(principal.userId(), CREATE_OPERATION, idempotencyKey);
            if (raced == null) {
                throw new BusinessException(HttpStatus.CONFLICT, "IDEMPOTENCY_RACE",
                        "幂等请求正在处理中，请稍后按相同键查询");
            }
            return existing(principal, raced, requestHash);
        }
        tickets.insert(ticketId, ticketNo, principal.tenantId(), principal.userId(), deviceId,
                summary.trim(), contact.trim());
        tickets.insertEvent(UUID.randomUUID(), ticketId, principal.userId(), "CREATED",
                null, TicketStatus.CREATED.name(), json(Map.of("source", "api")));
        audit.record(principal.tenantId(), principal.userId(), "TICKET_CREATED", "ticket",
                ticketId, requestId(request), Map.of("idempotency_key", idempotencyKey));
        Map<String, Object> response = get(principal, ticketId);
        response.put("deduplicated", false);
        return response;
    }

    @Transactional
    public Map<String, Object> updateStatus(BusinessPrincipal principal, UUID id, TicketStatus target,
                                            long version, String note, HttpServletRequest request) {
        if (!principal.hasRole("SUPPORT") && !principal.hasRole("ADMIN")) {
            throw new BusinessException(HttpStatus.FORBIDDEN, "STAFF_ROLE_REQUIRED", "需要售后或管理员权限");
        }
        TicketRow current = requireVisible(principal, id);
        if (!current.status().canTransitionTo(target)) {
            throw new BusinessException(HttpStatus.CONFLICT, "INVALID_STATUS_TRANSITION",
                    "不允许从 " + current.status() + " 转换到 " + target);
        }
        UUID assignee = target == TicketStatus.ASSIGNED || target == TicketStatus.PROCESSING
                ? principal.userId() : current.assigneeId();
        if (tickets.updateStatus(id, principal.tenantId(), target.name(), assignee, version) != 1) {
            throw new BusinessException(HttpStatus.CONFLICT, "OPTIMISTIC_LOCK_CONFLICT",
                    "工单已被其他售后人员更新，请刷新后重试");
        }
        tickets.insertEvent(UUID.randomUUID(), id, principal.userId(), "STATUS_CHANGED",
                current.status().name(), target.name(), json(Map.of("note", note == null ? "" : note)));
        audit.record(principal.tenantId(), principal.userId(), "TICKET_STATUS_CHANGED", "ticket",
                id, requestId(request), Map.of("from", current.status(), "to", target));
        return get(principal, id);
    }

    private Map<String, Object> existing(BusinessPrincipal principal, IdempotencyRow row, String hash) {
        if (!row.requestHash().equals(hash)) {
            throw new BusinessException(HttpStatus.CONFLICT, "IDEMPOTENCY_KEY_REUSED",
                    "相同幂等键对应的请求内容不同");
        }
        Map<String, Object> response = get(principal, row.resourceId());
        response.put("deduplicated", true);
        return response;
    }

    private TicketRow requireVisible(BusinessPrincipal principal, UUID id) {
        TicketRow row = tickets.findById(principal.tenantId(), id);
        if (row == null || (!principal.hasRole("ADMIN") && !principal.hasRole("SUPPORT")
                && !principal.userId().equals(row.userId()))) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "TICKET_NOT_FOUND", "工单不存在或无权访问");
        }
        return row;
    }

    private Map<String, Object> view(TicketRow row, boolean includeEvents) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("id", row.id()); value.put("ticket_no", row.ticketNo());
        value.put("user_id", row.userId()); value.put("device_id", row.deviceId());
        value.put("summary", row.summary()); value.put("contact", row.contact());
        value.put("status", row.status()); value.put("assignee_id", row.assigneeId());
        value.put("version", row.version()); value.put("created_at", row.createdAt());
        value.put("updated_at", row.updatedAt());
        if (includeEvents) value.put("events", tickets.events(row.id()));
        return value;
    }

    private String requestId(HttpServletRequest request) {
        Object value = request.getAttribute(RequestIdFilter.ATTRIBUTE);
        return value == null ? null : value.toString();
    }

    private String json(Map<String, ?> value) {
        try { return objectMapper.writeValueAsString(value); }
        catch (RuntimeException exception) { throw new IllegalArgumentException(exception); }
    }

    private String hash(Map<String, ?> value) {
        try {
            byte[] canonical = objectMapper.writeValueAsString(value).getBytes(StandardCharsets.UTF_8);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(canonical));
        } catch (RuntimeException | NoSuchAlgorithmException exception) {
            throw new IllegalStateException("无法计算请求摘要", exception);
        }
    }
}
