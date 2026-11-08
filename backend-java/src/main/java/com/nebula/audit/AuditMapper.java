package com.nebula.audit;

import java.util.UUID;
import java.util.List;
import java.util.Map;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AuditMapper {
    @Insert("""
            INSERT INTO biz.audit_logs(id, tenant_id, actor_id, action, resource_type,
              resource_id, request_id, trace_id, payload)
            VALUES(#{id}, #{tenantId}, #{actorId}, #{action}, #{resourceType}, #{resourceId},
              #{requestId}, #{traceId}, CAST(#{payload} AS jsonb))
            """)
    int insert(@Param("id") UUID id, @Param("tenantId") String tenantId,
               @Param("actorId") UUID actorId, @Param("action") String action,
               @Param("resourceType") String resourceType, @Param("resourceId") UUID resourceId,
               @Param("requestId") String requestId, @Param("traceId") String traceId,
               @Param("payload") String payload);

    @org.apache.ibatis.annotations.Select("""
            SELECT id, actor_id, action, resource_type, resource_id, request_id, trace_id,
                   payload, created_at
            FROM biz.audit_logs WHERE tenant_id = #{tenantId}
            ORDER BY created_at DESC LIMIT #{limit}
            """)
    List<Map<String, Object>> list(@Param("tenantId") String tenantId, @Param("limit") int limit);
}
