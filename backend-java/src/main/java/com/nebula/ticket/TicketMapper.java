package com.nebula.ticket;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface TicketMapper {
    @Select("""
            SELECT id, ticket_no, tenant_id, user_id, device_id, summary, contact,
                   agent_context::text AS agent_context, status, assignee_id, version,
                   created_at, updated_at
            FROM biz.tickets WHERE id = #{id} AND tenant_id = #{tenantId}
            """)
    TicketRow findById(@Param("tenantId") String tenantId, @Param("id") UUID id);

    @Select("""
            SELECT id, ticket_no, tenant_id, user_id, device_id, summary, contact,
                   agent_context::text AS agent_context, status, assignee_id, version,
                   created_at, updated_at
            FROM biz.tickets WHERE tenant_id = #{tenantId} AND user_id = #{userId}
            ORDER BY updated_at DESC
            """)
    List<TicketRow> listForUser(@Param("tenantId") String tenantId, @Param("userId") UUID userId);

    @Select("""
            SELECT id, ticket_no, tenant_id, user_id, device_id, summary, contact,
                   agent_context::text AS agent_context, status, assignee_id, version,
                   created_at, updated_at
            FROM biz.tickets WHERE tenant_id = #{tenantId} ORDER BY updated_at DESC LIMIT 200
            """)
    List<TicketRow> listForStaff(String tenantId);

    @Select("""
            SELECT event_type, from_status, to_status, payload, actor_id, created_at
            FROM biz.ticket_events WHERE ticket_id = #{ticketId} ORDER BY created_at
            """)
    List<Map<String, Object>> events(UUID ticketId);

    @Insert("""
            INSERT INTO biz.tickets(id, ticket_no, tenant_id, user_id, device_id, summary, contact,
              agent_context)
            VALUES(#{id}, #{ticketNo}, #{tenantId}, #{userId}, #{deviceId}, #{summary}, #{contact},
              CAST(#{agentContext} AS jsonb))
            """)
    int insert(@Param("id") UUID id, @Param("ticketNo") String ticketNo,
               @Param("tenantId") String tenantId, @Param("userId") UUID userId,
               @Param("deviceId") UUID deviceId, @Param("summary") String summary,
               @Param("contact") String contact, @Param("agentContext") String agentContext);

    @Update("""
            UPDATE biz.tickets SET status = #{target}::varchar, assignee_id = #{assigneeId},
              version = version + 1, updated_at = now()
            WHERE id = #{id} AND tenant_id = #{tenantId} AND version = #{version}
            """)
    int updateStatus(@Param("id") UUID id, @Param("tenantId") String tenantId,
                     @Param("target") String target, @Param("assigneeId") UUID assigneeId,
                     @Param("version") long version);

    @Insert("""
            INSERT INTO biz.ticket_events(id, ticket_id, actor_id, event_type, from_status, to_status, payload)
            VALUES(#{id}, #{ticketId}, #{actorId}, #{eventType}, #{fromStatus}, #{toStatus},
              CAST(#{payload} AS jsonb))
            """)
    int insertEvent(@Param("id") UUID id, @Param("ticketId") UUID ticketId,
                    @Param("actorId") UUID actorId, @Param("eventType") String eventType,
                    @Param("fromStatus") String fromStatus, @Param("toStatus") String toStatus,
                    @Param("payload") String payload);

    @Select("""
            SELECT request_hash, resource_id FROM biz.idempotency_records
            WHERE user_id = #{userId} AND operation = #{operation} AND idempotency_key = #{key}
            """)
    IdempotencyRow findIdempotency(@Param("userId") UUID userId,
                                   @Param("operation") String operation, @Param("key") String key);

    @Insert("""
            INSERT INTO biz.idempotency_records(id, user_id, operation, idempotency_key,
              request_hash, resource_id)
            VALUES(#{id}, #{userId}, #{operation}, #{key}, #{requestHash}, #{resourceId})
            ON CONFLICT (user_id, operation, idempotency_key) DO NOTHING
            """)
    int insertIdempotency(@Param("id") UUID id, @Param("userId") UUID userId,
                          @Param("operation") String operation, @Param("key") String key,
                          @Param("requestHash") String requestHash, @Param("resourceId") UUID resourceId);
}
