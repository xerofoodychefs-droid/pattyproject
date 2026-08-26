# Phase 4 — Step 8A: PostgreSQL & FastAPI Production Architecture Inspection Report

**Project**: Patty Project UK  
**Phase**: Phase 4 — Step 8A (Pre-Migration Architecture Audit & Design)  
**Target Environment**: IONOS VPS L+ (Ubuntu 24.04 LTS, 6 vCPU, 8 GB RAM, 240 GB NVMe SSD)  
**Auditor**: Principal Database Engineer, Senior FastAPI Engineer & Production DevOps Engineer  
**Date**: 2026-08-26  
**Status**: Pre-Migration Audit Complete — Read-Only Architecture Blueprint  

---

## 1. Current Database Architecture

The Patty Project backend currently utilizes **SQLAlchemy 2.0 ORM** with a flexible dialect layer. 
- **Connection Configuration (`backend/app/core/database.py`)**:
  - `DATABASE_URL` dynamic resolution via `settings.DATABASE_URL`.
  - Automatic dialect switching: When `DATABASE_URL` starts with `sqlite`, sets `connect_args={"check_same_thread": False}`. When pointing to PostgreSQL, automatically activates enterprise connection pooling (`pool_pre_ping=True`, `pool_size=10`, `max_overflow=20`).
- **Schema & Migration Foundation**:
  - **Alembic** is fully configured (`backend/alembic.ini` and `backend/alembic/env.py`).
  - Production migrations: `ed7049002652_initial_postgresql_schema.py` (complete 26-table relational schema) and `c748291b5a10_loyalty_programme_and_milestones.py`.
- **Existing SQLite State & Verified Backup**:
  - Golden Reference Backup: `C:\Users\HP\Desktop\pattyproject_backups\patty_project_backup_2026-08-25_12-30-54.db` (SHA-256: `3e565aa8da292fc13675cac426d818f07a708fc123139367b7a4314327f4da95`).
  - Contains **19 populated application tables**, **46 orders**, **47 payment records**, **76 order items**, **66 order status histories**, and all customer/admin accounts.

---

## 2. SQLite Dependencies & PostgreSQL Compatibility Assessment

| Dimension | SQLite Handling | PostgreSQL Production Handling | Compatibility Status |
| :--- | :--- | :--- | :--- |
| **Primary Keys & UUIDs** | `VARCHAR(36)` / `VARCHAR(64)` strings | `VARCHAR(36)` / `VARCHAR(64)` strings | **100% Compatible** (no type mismatch). |
| **Boolean Values** | Integer storage (`0` / `1`) | Native `BOOLEAN` (`TRUE` / `FALSE`) | Requires boolean coercion during ETL (`bool(v)`). |
| **JSON Columns** | Serialized text strings | Native `JSONB` / `JSON` types | Requires deserialization / JSON parsing during ETL. |
| **Date & Timestamps** | ISO-8601 strings without native TZ | Native `TIMESTAMP WITH TIME ZONE` | Requires `datetime.fromisoformat()` UTC normalization. |
| **Decimal / Currency** | `FLOAT` / `REAL` | `FLOAT` / `NUMERIC(10,2)` | Float parsing with exact roundings. |
| **Foreign Keys** | Enforced conditionally via PRAGMA | Enforced natively by PostgreSQL engine | Topological table insertion order required. |
| **Concurrency & Locking** | Database-level file lock | Row-level multiversion concurrency (MVCC) | **Significant Performance & Stability Upgrade**. |

**Conclusion**: The SQLAlchemy models are **fully PostgreSQL-ready**. No schema or model code changes are necessary.

---

## 3. Model-by-Model Relational Schema Assessment

All 26 database models and tables have been audited for dependency-safe migration:

```
[ Tier 1: Core Identities & Independent Tables ]
  ├── users (UUID PK, unique email, password_hash, role)
  ├── branches (VARCHAR PK, coordinates, opening_hours JSON)
  ├── categories (VARCHAR PK, slug, sort_order)
  ├── coupons (VARCHAR PK, code, discount_type, min_subtotal)
  ├── offer_settings (VARCHAR PK, active banner config)
  ├── printers (VARCHAR PK, branch association)
  └── loyalty_program_config (VARCHAR PK, points ratio, rules)

[ Tier 2: User-Dependent & Child Entities ]
  ├── user_auth_identities (FK -> users.id)
  ├── auth_sessions (FK -> users.id, refresh_token_hash, session metadata)
  ├── auth_consumed_jtis (FK -> users.id, jti replay tracking)
  ├── customer_addresses (FK -> users.id)
  ├── customer_cards (FK -> users.id)
  ├── loyalty_accounts (FK -> users.id, 1:1 invariant)
  ├── branch_users (FK -> users.id, FK -> branches.id)
  ├── collection_slots (FK -> branches.id)
  ├── products (FK -> categories.id)
  └── loyalty_milestones & loyalty_campaigns

[ Tier 3: Product-Dependent Entities ]
  ├── product_modifiers (FK -> products.id)
  └── inventory (FK -> products.id, FK -> branches.id)

[ Tier 4: Transactional & Order Pipelines ]
  ├── orders (FK -> users.id, FK -> branches.id, delivery_address JSON)
  ├── order_items (FK -> orders.id, FK -> products.id, selected_modifiers JSON)
  ├── order_status_history (FK -> orders.id, FK -> users.id)
  ├── payments (FK -> orders.id, raw_response JSON)
  ├── payment_events (FK -> payments.id, payload JSON)
  ├── loyalty_transactions (FK -> loyalty_accounts.id, FK -> orders.id)
  ├── print_jobs (FK -> orders.id, FK -> printers.id)
  └── audit_logs (diff_json JSON)
```

---

## 4. FastAPI Startup & Lifecycle Safety Audit

- **`backend/app/main.py` & `backend/app/db/seed.py` Analysis**:
  - `on_startup` calls `settings.validate_production_configuration()` and `seed_db()`.
  - **Production Guard Active**: When `ENVIRONMENT=production` (`settings.is_production` is `True`):
    - `Base.metadata.create_all(bind=engine)` is **SKIPPED** (Alembic manages DDL migrations).
    - Hardcoded development passwords and default sample seeding are **COMPLETELY DISABLED**.
    - If `admin@pattyproject.co.uk` already exists in PostgreSQL (post-migration), `seed_db()` safely exits without modifying any records.
  - **Verdict**: FastAPI startup is **100% safe for production PostgreSQL deployment**.

---

## 5. Environment Variable Inventory

| Variable Name | Required In Production | Purpose & Masked Baseline |
| :--- | :---: | :--- |
| `ENVIRONMENT` | **YES** | Set to `production`. |
| `PROJECT_NAME` | Optional | Set to `Patty Project UK`. |
| `API_V1_STR` | Optional | Defaults to `/api/v1`. |
| `SECRET_KEY` | **YES (CRITICAL)** | Cryptographically random 64-character secret key (`[MASKED]`). |
| `DATABASE_URL` | **YES (CRITICAL)** | `postgresql://patty_user:[MASKED]@patty_postgres:5432/patty_production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | `15` (short-lived access tokens). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Optional | `7` (persistent refresh window). |
| `BACKEND_CORS_ORIGINS` | **YES** | Strict domain origins (e.g. `https://pattyproject.co.uk`). |
| `PAYMENT_PROVIDER` | **YES** | `mock` (until client payment API credentials provided). |
| `GOOGLE_CLIENT_ID` | Optional | Production Google OAuth Client ID (`[MASKED]`). |
| `POSTGRES_DB` | **YES (Docker)** | `patty_production`. |
| `POSTGRES_USER` | **YES (Docker)** | `patty_user`. |
| `POSTGRES_PASSWORD` | **YES (Docker)** | Strong random database password (`[MASKED]`). |

---

## 6. Payment Architecture Assessment

- **Current Implementation**:
  - Clean abstraction in `backend/app/services/payment_service.py` with `BasePaymentGateway` interface and `MockPaymentGateway`.
  - Finite State Machine: `PENDING` -> `AUTHORIZED` -> `CAPTURED` / `PAID` -> `REFUNDED`.
  - Multi-key lookup, idempotent webhook handling via `PaymentEvent`, and safe transaction isolation.
- **Client Payment API Integration Boundary**:
  - The future client payment API will seamlessly implement the `BasePaymentGateway` interface (`create_payment_session`, `verify_payment_status`, `refund_payment`) without changing the frontend checkout UX or backend order pipeline.

---

## 7. Authentication & Session Preservation

- **Session Invariants**:
  - `auth_sessions` stores `refresh_token_hash`, `user_id`, `expires_at`, `is_revoked`, `ip_address`, `user_agent`.
  - `auth_consumed_jtis` stores blacklisted/consumed token IDs.
  - `User.password_hash` stores cryptographically secure Argon2id / bcrypt hashes.
- **Zero Logout Migration**:
  - Because all password hashes, session records, and active refresh tokens are migrated row-for-row into PostgreSQL, **active user and admin sessions will remain valid without forcing users to log in again**.

---

## 8. Docker Architecture & Private Networking Design

```
[ Nginx Reverse Proxy (Host OS: 194.164.120.249) ]
         │ (HTTP Proxy -> http://127.0.0.1:8000)
         ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Docker Private Bridge Network: `patty_network` (Internal Only)          │
│                                                                        │
│   ┌───────────────────────────┐         ┌───────────────────────────┐  │
│   │     patty_fastapi         │         │      patty_postgres       │  │
│   │  (FastAPI Backend App)    │         │  (PostgreSQL 16 Database) │  │
│   │                           │  TCP    │                           │  │
│   │  Ports Bound:             │  5432   │  Ports Bound:             │  │
│   │  127.0.0.1:8000:8000      ├────────►│  NONE (NO HOST BINDING)   │  │
│   │  (Localhost Ingress Only) │         │  (Accessible ONLY via     │  │
│   │                           │         │   patty_network)          │  │
│   └───────────────────────────┘         └─────────────┬─────────────┘  │
└───────────────────────────────────────────────────────┼────────────────┘
                                                        ▼
                                          [ Named Volume: postgres_data ]
                                          (/var/lib/docker/volumes/...)
```

### Key Security & Operational Directives
1. **PostgreSQL Container (`patty_postgres`)**:
   - Image: `postgres:16-alpine`.
   - **`ports:` section MUST BE COMPLETELY OMITTED**. PostgreSQL is reachable exclusively by the `patty_fastapi` container on the private Docker bridge network.
   - Storage: Persistent named volume `postgres_data`.
   - Health check: `pg_isready -U patty_user -d patty_production`.
2. **FastAPI Container (`patty_fastapi`)**:
   - Built from production multi-stage Dockerfile.
   - Executes as unprivileged non-root user (`USER appuser`, UID 10001).
   - Port mapping: `127.0.0.1:8000:8000` (Localhost loopback only, blocked from external network by UFW).
   - Health check: `curl -f http://127.0.0.1:8000/api/v1/health || exit 1`.
   - Resource limits: Max 1.5 GB RAM, 2 vCPU.

---

## 9. PostgreSQL Version Recommendation

- **Recommended Version**: **PostgreSQL 16 LTS** (`postgres:16-alpine`).
- **Rationale**:
  - Official active support through November 2028.
  - Enhanced query parallelism, faster JSONB subscripting, and robust memory optimization.
  - Full compatibility with `psycopg2-binary`, SQLAlchemy 2.0, and async pgpool drivers.

---

## 10. Data Migration Strategy (Zero Data Loss)

### Migration Pipeline
```
[ Verified SQLite Golden Backup ]
             │
             ▼ (Transactional Python ETL: migrate_sqlite_to_postgres.py)
[ Stage 1: Schema Initialization via Alembic ] (ed7049002652 -> c748291b5a10)
             │
             ▼ (Topological Insertion with Special Type Coercion)
[ Stage 2: Data Transfer across 26 Tables in Single Transaction ]
             │
             ▼ (Post-ETL Verification)
[ Stage 3: Deep Integrity Audit & Row Count Reconciliations ]
             │
             ▼
[ PostgreSQL Production Database Ready ]
```

### Special Type Handlers in ETL
- **Booleans**: Integer values `0`/`1` converted to `False`/`True`.
- **JSON Fields**: Text strings parsed into native Python dicts/lists for JSONB columns.
- **Timestamps**: Text strings normalized to UTC-aware datetime objects.
- **Sequences**: Auto-increment sequence pointers synced post-insertion (`setval`).

---

## 11. Data Integrity & Verification Strategy

Following migration, automated verification checks:
1. **Row Count Parity**: 1:1 table row counts against the SQLite golden backup (e.g. exactly 46 orders, 47 payments, 76 order items, 66 status histories).
2. **Financial Parity**: Sum of order subtotals, VAT amounts, and payment totals between SQLite and PostgreSQL must match to £0.0001 precision.
3. **Foreign Key Invariant Check**: Zero orphaned records across all relationships.
4. **Authentication Check**: Verification of password hash decryptability and session lookup.

---

## 12. Backup Strategy

```
A. SQLite Backup: Permanently preserved at C:\Users\HP\Desktop\pattyproject_backups\.
B. Pre-Migration Baseline: Database schema snapshot created prior to data load.
C. Post-Migration Snapshot: Full pg_dump immediately following verified migration.
D. Production Automated Backups: Daily automated backup via scripts/backup_postgresql.sh
   (rotates daily, compressed with gzip, retained for 30 days).
```

---

## 13. Health-Check Strategy

1. **PostgreSQL**:
   - `docker exec patty_postgres pg_isready -U patty_user -d patty_production`
2. **FastAPI**:
   - Dedicated endpoint `GET /api/v1/health` verifying database pool connectivity.
3. **Host Nginx**:
   - `curl -I http://127.0.0.1/` (Frontend SPA) and `curl -I http://127.0.0.1/api/v1/health` (Reverse Proxy).

---

## 14. Resource Allocation Planning (8 GB RAM / 6 vCPU Host)

| Service | CPU Limit | Memory Reservation | Memory Hard Limit | Storage Footprint |
| :--- | :---: | :---: | :---: | :---: |
| **PostgreSQL 16** | 2.0 vCPU | 1.0 GiB | 2.5 GiB | ~500 MB data (scales to 100 GB+) |
| **FastAPI Backend** | 2.0 vCPU | 512 MiB | 1.5 GiB | ~200 MB container image |
| **Host Nginx** | 1.0 vCPU | 128 MiB | 512 MiB | ~50 MB static assets |
| **OS, Cache & Buffers** | 1.0 vCPU | 2.0 GiB | Remaining (~3.5 GiB) | Host NVMe (227 GB free) |
| **Swap Buffer** | N/A | 4.0 GiB | 4.0 GiB | `/swapfile` on NVMe |

---

## 15. Production Rollback Strategy

If any failure occurs during Phase 4 Step 8B deployment:
1. **Immediate Halt**: `sudo docker compose down`.
2. **PostgreSQL Preservation**: Named volume `postgres_data` preserved for diagnostic inspection.
3. **SQLite Preserved**: `patty_project.db` and external backups remain 100% intact.
4. **Configuration Reversion**: Set `DATABASE_URL=sqlite:///patty_project.db` to immediately restore local operation.

---

## 16. Component Status & Migration Matrix

| Component | Current State | Target State | Migration Required | Risk Level |
| :--- | :--- | :--- | :--- | :---: |
| **Database Engine** | SQLite 3 | PostgreSQL 16 (Docker) | YES (Topological ETL) | Low (Reversible) |
| **Database Network** | Local file | Private Docker bridge | YES (Docker network) | Low |
| **FastAPI Backend** | Local Python process | Docker container (non-root) | YES (Container build) | Low |
| **Nginx Reverse Proxy** | Static SPA active | Static SPA + `/api/v1/` proxy | YES (Upstream binding) | Low |
| **User & Admin Sessions** | SQLite `auth_sessions` | PostgreSQL `auth_sessions` | YES (Exact preservation) | Low |
| **Payment Ledger** | SQLite `payments` (47 records) | PostgreSQL `payments` | YES (Exact parity) | Low |
| **Customer Orders** | SQLite `orders` (46 orders) | PostgreSQL `orders` | YES (Exact parity) | Low |
| **Loyalty Points** | SQLite `loyalty_accounts` | PostgreSQL `loyalty_accounts` | YES (Exact parity) | Low |

---

## 17. Production Blockers & Exact Next-Step Sequence

### Blockers for Step 8B
- **0 Blockers**. The architecture, ETL utility, Alembic migrations, and safety parameters are fully designed and ready.

### Next Step Sequence (Phase 4 Step 8B)
1. Generate production environment configuration (`.env.production`) with strong generated secrets.
2. Build FastAPI production container image.
3. Start PostgreSQL container on private `patty_network` (no host ports).
4. Run Alembic migrations against PostgreSQL.
5. Execute `migrate_sqlite_to_postgres.py` transactional ETL.
6. Verify row-count, foreign-key, and financial parity.
7. Start FastAPI container connected to PostgreSQL.
8. Validate end-to-end HTTP `/api/v1/` communication through Nginx.

---

## 18. CHANGES ACTUALLY MADE

> [!IMPORTANT]
> **EXPLICIT NON-MODIFICATION STATEMENT**:
> - **SQLite database was NOT modified**.
> - **SQLite backup was NOT modified**.
> - **PostgreSQL was NOT installed**.
> - **PostgreSQL data was NOT created**.
> - **FastAPI production container was NOT deployed**.
> - **Docker Compose production stack was NOT deployed**.
> - **Application source code was NOT modified**.
> - **Authentication logic was NOT modified**.
> - **Payment logic was NOT modified**.
> - **Customer workflows were NOT modified**.
> - **Admin workflows were NOT modified**.
> - **No production data was migrated**.
> - **No users were logged out**.
> - **No system reboot occurred**.
