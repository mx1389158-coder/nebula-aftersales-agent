package com.nebula.audit;

import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AuditMapper {
    @Insert("""
            INSERT INTO biz.audit_logs(id, tenant_id, actor_id, action, resource_type,
              resource_id, request_id, payload)
            VALUES(#{id}, #{tenantId}, #{actorId}, #{action}, #{resourceType}, #{resourceId},
              #{requestId}, CAST(#{payload} AS jsonb))
            """)
    int insert(@Param("id") UUID id, @Param("tenantId") String tenantId,
               @Param("actorId") UUID actorId, @Param("action") String action,
               @Param("resourceType") String resourceType, @Param("resourceId") UUID resourceId,
               @Param("requestId") String requestId, @Param("payload") String payload);
}
