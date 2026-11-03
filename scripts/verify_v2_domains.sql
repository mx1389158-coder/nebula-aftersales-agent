\pset tuples_only on
\pset format unaligned

SELECT n.nspname, r.rolname
FROM pg_namespace AS n
JOIN pg_roles AS r ON r.oid = n.nspowner
WHERE n.nspname IN ('biz', 'ai')
ORDER BY n.nspname;

SELECT
    has_schema_privilege('aftersales_ai', 'biz', 'USAGE') AS ai_can_use_biz,
    has_schema_privilege('aftersales_biz', 'ai', 'USAGE') AS biz_can_use_ai;

SELECT
    (SELECT count(*) FROM biz.tickets) AS biz_tickets,
    (SELECT count(*) FROM ai.tickets) AS legacy_ai_tickets,
    (SELECT count(*) FROM ai.users) AS ai_identity_projections;
