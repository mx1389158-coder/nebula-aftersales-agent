#!/usr/bin/env bash
set -euo pipefail

: "${BIZ_DB_PASSWORD:=aftersales-biz-local}"
: "${AI_DB_PASSWORD:=aftersales-ai-local}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=biz_password="$BIZ_DB_PASSWORD" --set=ai_password="$AI_DB_PASSWORD" <<'EOSQL'
CREATE ROLE aftersales_biz LOGIN PASSWORD :'biz_password';
CREATE ROLE aftersales_ai LOGIN PASSWORD :'ai_password';
CREATE SCHEMA biz AUTHORIZATION aftersales_biz;
CREATE SCHEMA ai AUTHORIZATION aftersales_ai;
GRANT CONNECT ON DATABASE aftersales TO aftersales_biz, aftersales_ai;
EOSQL
