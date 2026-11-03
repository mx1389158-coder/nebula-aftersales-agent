CREATE TABLE biz.users (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    username VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DISABLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, username),
    UNIQUE (tenant_id, email)
);

CREATE TABLE biz.user_roles (
    user_id UUID NOT NULL REFERENCES biz.users(id) ON DELETE CASCADE,
    role_code VARCHAR(32) NOT NULL CHECK (role_code IN ('USER', 'SUPPORT', 'ADMIN')),
    PRIMARY KEY (user_id, role_code)
);

CREATE TABLE biz.products (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    product_code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    category VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, product_code)
);

CREATE TABLE biz.product_models (
    id UUID PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES biz.products(id),
    model_code VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    UNIQUE (product_id, model_code)
);

CREATE TABLE biz.firmwares (
    id UUID PRIMARY KEY,
    model_id UUID NOT NULL REFERENCES biz.product_models(id),
    version VARCHAR(40) NOT NULL,
    released_at DATE NOT NULL,
    UNIQUE (model_id, version)
);

CREATE TABLE biz.devices (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    owner_id UUID NOT NULL REFERENCES biz.users(id),
    model_id UUID NOT NULL REFERENCES biz.product_models(id),
    firmware_id UUID NOT NULL REFERENCES biz.firmwares(id),
    serial_no VARCHAR(100) NOT NULL,
    nickname VARCHAR(120),
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, serial_no)
);

CREATE TABLE biz.tickets (
    id UUID PRIMARY KEY,
    ticket_no VARCHAR(32) NOT NULL UNIQUE,
    tenant_id VARCHAR(64) NOT NULL,
    user_id UUID NOT NULL REFERENCES biz.users(id),
    device_id UUID REFERENCES biz.devices(id),
    summary TEXT NOT NULL,
    contact VARCHAR(120) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'CREATED'
        CHECK (status IN ('CREATED', 'ASSIGNED', 'PROCESSING', 'RESOLVED', 'CLOSED')),
    assignee_id UUID REFERENCES biz.users(id),
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE biz.ticket_events (
    id UUID PRIMARY KEY,
    ticket_id UUID NOT NULL REFERENCES biz.tickets(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES biz.users(id),
    event_type VARCHAR(48) NOT NULL,
    from_status VARCHAR(24),
    to_status VARCHAR(24),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE biz.idempotency_records (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES biz.users(id),
    operation VARCHAR(80) NOT NULL,
    idempotency_key VARCHAR(120) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    resource_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, operation, idempotency_key)
);

CREATE TABLE biz.audit_logs (
    id UUID PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    actor_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(60) NOT NULL,
    resource_id UUID,
    request_id VARCHAR(80),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_devices_owner ON biz.devices(tenant_id, owner_id);
CREATE INDEX ix_tickets_user ON biz.tickets(tenant_id, user_id, updated_at DESC);
CREATE INDEX ix_tickets_status ON biz.tickets(tenant_id, status, updated_at DESC);
CREATE INDEX ix_ticket_events_ticket ON biz.ticket_events(ticket_id, created_at);
CREATE INDEX ix_audit_actor ON biz.audit_logs(tenant_id, actor_id, created_at DESC);
