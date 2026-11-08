package com.nebula.audit;

import tools.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class AuditService {
    private final AuditMapper audit;
    private final ObjectMapper objectMapper;

    public AuditService(AuditMapper audit, ObjectMapper objectMapper) {
        this.audit = audit;
        this.objectMapper = objectMapper;
    }

    public void record(String tenantId, UUID actorId, String action, String resourceType,
                       UUID resourceId, String requestId, String traceId,
                       Map<String, Object> payload) {
        try {
            audit.insert(UUID.randomUUID(), tenantId, actorId, action, resourceType, resourceId,
                    requestId, traceId, objectMapper.writeValueAsString(payload));
        } catch (RuntimeException exception) {
            throw new IllegalArgumentException("审计数据无法序列化", exception);
        }
    }

    public java.util.List<Map<String, Object>> list(String tenantId, int limit) {
        return audit.list(tenantId, Math.max(1, Math.min(limit, 500)));
    }
}
