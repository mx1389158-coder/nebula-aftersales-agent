ALTER TABLE biz.tickets
    ADD COLUMN agent_context JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE biz.audit_logs
    ADD COLUMN trace_id VARCHAR(80);

CREATE INDEX ix_audit_request ON biz.audit_logs(tenant_id, request_id, trace_id);
