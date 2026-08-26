#!/bin/sh
set -e

# ==============================================================================
# Patty Project UK — PostgreSQL Container App User Initialization Script
# Executed automatically by PostgreSQL container entrypoint upon initial initdb.
# ==============================================================================

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_APP_USER:-patty_app}') THEN
            CREATE USER ${POSTGRES_APP_USER:-patty_app} WITH ENCRYPTED PASSWORD '${POSTGRES_APP_PASSWORD}';
        ELSE
            ALTER USER ${POSTGRES_APP_USER:-patty_app} WITH ENCRYPTED PASSWORD '${POSTGRES_APP_PASSWORD}';
        END IF;
    END
    \$\$;
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB:-patty_db} TO ${POSTGRES_APP_USER:-patty_app};
    GRANT ALL ON SCHEMA public TO ${POSTGRES_APP_USER:-patty_app};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${POSTGRES_APP_USER:-patty_app};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${POSTGRES_APP_USER:-patty_app};
EOSQL
