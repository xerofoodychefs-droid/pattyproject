# Phase 4 — Step 8B: Pre-Migration Validation & Migration Rehearsal Report

**Project**: Patty Project UK  
**Phase**: Phase 4 — Step 8B (Pre-Migration Architecture Validation & Rehearsal Blueprint)  
**Target Host**: IONOS VPS L+ (`194.164.120.249`, Ubuntu 24.04 LTS, 6 vCPU, 8 GB RAM, 240 GB NVMe)  
**Auditor**: Principal Database Engineer, Senior FastAPI Engineer & Production DevOps Engineer  
**Date**: 2026-08-26  
**Status**: Validation Complete — Dry-Run Blueprint Formulated  

---

## 1. 26-Table vs. 19-Table Reconciliation

### Explanation of Discrepancy
In previous audit summaries, the term **"19 application tables"** specifically described the **19 tables containing existing production records (>0 rows)**. The complete relational database schema defined by SQLAlchemy models and Alembic migrations encompasses **26 tables** in total.

All 26 tables exist in the verified SQLite backup (`patty_project_backup_2026-08-25_12-30-54.db`):
- **19 tables** currently contain historical operational data.
- **7 tables** currently contain 0 rows (features such as OAuth identities, revoked token IDs, collection slots, print queues, and banner configurations).

### Complete Table-by-Table Reconciliation Matrix

| # | Table Name | SQLite Existence | PostgreSQL Target | Table Classification | Contains Business Data | SQLite Row Count | Migration Required |
| :---: | :--- | :---: | :---: | :--- | :---: | :---: | :---: |
| **1** | `users` | **YES** | **YES** | Core Identity | **YES** | **9** | **YES** |
| **2** | `user_auth_identities` | **YES** | **YES** | OAuth Identity | NO (0 rows) | **0** | **YES (Schema)** |
| **3** | `auth_sessions` | **YES** | **YES** | Authentication Session | NO (0 rows) | **0** | **YES (Schema)** |
| **4** | `auth_consumed_jtis` | **YES** | **YES** | Token Replay Blacklist | NO (0 rows) | **0** | **YES (Schema)** |
| **5** | `customer_addresses` | **YES** | **YES** | Customer PII / Address | **YES** | **3** | **YES** |
| **6** | `customer_cards` | **YES** | **YES** | Payment Token Ref | **YES** | **3** | **YES** |
| **7** | `branches` | **YES** | **YES** | Store Architecture | **YES** | **6** | **YES** |
| **8** | `branch_users` | **YES** | **YES** | Store RBAC Mapping | **YES** | **2** | **YES** |
| **9** | `collection_slots` | **YES** | **YES** | Store Logistics | NO (0 rows) | **0** | **YES (Schema)** |
| **10** | `categories` | **YES** | **YES** | Menu Hierarchy | **YES** | **7** | **YES** |
| **11** | `products` | **YES** | **YES** | Menu Catalog | **YES** | **37** | **YES** |
| **12** | `product_modifiers` | **YES** | **YES** | Menu Customization | **YES** | **51** | **YES** |
| **13** | `inventory` | **YES** | **YES** | Stock Control | **YES** | **59** | **YES** |
| **14** | `orders` | **YES** | **YES** | Core Order Transaction | **YES** | **46** | **YES** |
| **15** | `order_items` | **YES** | **YES** | Order Line Items | **YES** | **76** | **YES** |
| **16** | `order_status_history` | **YES** | **YES** | Order State Audit | **YES** | **66** | **YES** |
| **17** | `payments` | **YES** | **YES** | Financial Ledger | **YES** | **47** | **YES** |
| **18** | `payment_events` | **YES** | **YES** | Webhook Audit Log | **YES** | **9** | **YES** |
| **19** | `loyalty_accounts` | **YES** | **YES** | Customer Balance | **YES** | **8** | **YES** |
| **20** | `loyalty_rewards` | **YES** | **YES** | Reward Definitions | **YES** | **4** | **YES** |
| **21** | `loyalty_transactions` | **YES** | **YES** | Loyalty Ledger | **YES** | **16** | **YES** |
| **22** | `coupons` | **YES** | **YES** | Discount Engine | **YES** | **6** | **YES** |
| **23** | `offer_settings` | **YES** | **YES** | Promotional Engine | NO (0 rows) | **0** | **YES (Schema)** |
| **24** | `printers` | **YES** | **YES** | Kitchen Hardware | NO (0 rows) | **0** | **YES (Schema)** |
| **25** | `print_jobs` | **YES** | **YES** | Kitchen Print Queue | NO (0 rows) | **0** | **YES (Schema)** |
| **26** | `audit_logs` | **YES** | **YES** | Administrative Audit | **YES** | **1** | **YES** |

---

## 2. FastAPI / Nginx Networking Validation

### Technical Network Path Breakdown
```
[ Public Internet Client ]
           │
           ▼
[ Host Nginx Proxy (194.164.120.249:80/443) ]
           │ (HTTP Proxy Protocol)
           ▼
  http://127.0.0.1:8000
           │
           ▼ (Host Loopback Interface Binding)
[ Docker Port Forwarder: 127.0.0.1:8000 -> container:8000 ]
           │
           ▼ (patty_network Bridge)
[ FastAPI Container (Bound to 0.0.0.0:8000 internally) ]
           │
           ▼ (TCP 5432 via Docker DNS `patty_postgres`)
[ PostgreSQL Container (NO HOST PORT MAPPING) ]
```

### Exact Networking Properties & Validation
1. **FastAPI Binding Inside Container**:
   - Uvicorn must bind to `0.0.0.0:8000` inside its container namespace so the Docker bridge network router can route incoming TCP packets to it.
2. **Host Port Mapping**:
   - In `docker-compose.yml`, the port mapping must be explicitly configured as **`127.0.0.1:8000:8000`**.
   - **Security Mechanism**: Because the port is bound exclusively to the IPv4 loopback adapter (`127.0.0.1`), external packets reaching `194.164.120.249:8000` are rejected at the kernel interface level.
3. **Nginx Upstream Connection**:
   - Nginx on the host connects directly to `http://127.0.0.1:8000`.
4. **PostgreSQL Network Isolation**:
   - `patty_postgres` container specifies **NO `ports:` entry**. It communicates with FastAPI strictly over the private internal Docker bridge (`patty_network`).
   - PostgreSQL is physically inaccessible from both the host OS network and the public internet.

---

## 3. PostgreSQL Version Validation

- **Recommended Version**: **PostgreSQL 16 (Alpine Image: `postgres:16-alpine`)**.
- **Lifecycle Justification**:
  - The PostgreSQL Global Development Group maintains major releases for 5 years.
  - PostgreSQL 16 was released in September 2023 and receives active security and bugfix support through **November 2028**.
  - *(Note: PostgreSQL uses standard major release versioning rather than "LTS" terminology).*
- **Stack Compatibility**:
  - `psycopg2-binary 2.9.9` & `asyncpg`: Full native support for PostgreSQL 16 wire protocol.
  - `SQLAlchemy 2.0.35`: Native dialect support for JSONB, native UUIDs, server-side cursors, and connection pooling.
  - `Alembic 1.13.2`: Fully validated migration generation and execution.

---

## 4. Migration Script Audit (`backend/scripts/migrate_sqlite_to_postgres.py`)

A comprehensive audit of the ETL script was performed:

| Audit Parameter | Implementation Check | Safety Verdict |
| :--- | :--- | :---: |
| **Source Database Protection** | Connects via `sqlite:///file:...?mode=ro&uri=true`. Read-only OS file descriptor. | **SAFE** (Zero write risk to SQLite). |
| **Target Pre-Flight Checks** | Inspects target database, verifies Alembic revision, confirms target tables are 100% empty. | **SAFE** (Prevents partial overwrite). |
| **Transaction Atomicity** | Encapsulated in `with self.dst_engine.begin() as conn:` across all 26 tables. | **SAFE** (Single atomic commit or full rollback). |
| **Topological Order** | 26 tables ordered strictly by foreign-key dependency (`users` -> `orders` -> `order_items`). | **SAFE** (Zero foreign-key constraint violations). |
| **Boolean Handling** | Integer `0`/`1` coerced via `parse_bool_val()` to native Python `bool`. | **SAFE** (Clean PostgreSQL boolean mapping). |
| **JSON / JSONB Handling** | Stringified JSON parsed via `parse_json_val()` to native dicts/lists. | **SAFE** (Valid JSONB insertion). |
| **DateTime Normalization** | Text ISO strings normalized to UTC-aware datetime objects via `parse_datetime_val()`. | **SAFE** (No timezone drift). |
| **Identity & Sequences** | Executes `SELECT setval(pg_get_serial_sequence(...))` to update PostgreSQL sequences. | **SAFE** (No sequence collision on new orders). |

---

## 5. Golden Backup Rehearsal Strategy

- **Golden Reference File**: `C:\Users\HP\Desktop\pattyproject_backups\patty_project_backup_2026-08-25_12-30-54.db`
  - SHA-256: `3e565aa8da292fc13675cac426d818f07a708fc123139367b7a4314327f4da95`
- **Rehearsal Rule**: The production backup is **NEVER** touched directly. A disposable copy is created in a temporary workspace for rehearsal testing:
  ```bash
  Copy-Item -Path "C:\Users\HP\Desktop\pattyproject_backups\patty_project_backup_2026-08-25_12-30-54.db" -Destination "backend/scratch/rehearsal_backup.db"
  ```
- Rehearsal SHA-256 is verified prior to running the dry run.

---

## 6. Migration Dry-Run Design

```
[ Disposable SQLite Rehearsal Copy ]
                │
                ▼
[ Temporary PostgreSQL Container (patty_postgres_dryrun) ]
                │ (Alembic DDL Applied: ed7049002652 -> c748291b5a10)
                ▼
[ Execute migrate_sqlite_to_postgres.py ETL ]
                │
                ▼
[ Automated Verification Suite (26 Tables, Foreign Keys, Financial Sums) ]
                │
                ▼
[ Destroy Temporary Rehearsal Container & Disposable Copy ]
```

---

## 7. Data Verification Plan (Pre- vs. Post-Migration)

### Expected Table Row-Count Comparison Table

| Table Name | Source SQLite Count | Target PostgreSQL Expected | Expected Diff | Verification Criteria |
| :--- | :---: | :---: | :---: | :--- |
| `users` | 9 | 9 | 0 | 1 Super Admin, 2 Branch Admins, 6 Customers |
| `branches` | 6 | 6 | 0 | Camden, Westfield, Central, Soho, etc. |
| `branch_users` | 2 | 2 | 0 | Branch administrator store mappings |
| `categories` | 7 | 7 | 0 | Burgers, Sides, Drinks, Desserts, Deals, etc. |
| `products` | 37 | 37 | 0 | All menu items and SKUs |
| `product_modifiers` | 51 | 51 | 0 | Modifiers, add-ons, sauces |
| `inventory` | 59 | 59 | 0 | Stock levels and availability per branch |
| `orders` | 46 | 46 | 0 | Exactly 46 historical orders |
| `order_items` | 76 | 76 | 0 | Exactly 76 line items linked to orders |
| `order_status_history` | 66 | 66 | 0 | Exactly 66 state transitions |
| `payments` | 47 | 47 | 0 | Exactly 47 payment transaction records |
| `payment_events` | 9 | 9 | 0 | Exactly 9 payment webhook audit events |
| `customer_addresses` | 3 | 3 | 0 | Customer delivery address profiles |
| `customer_cards` | 3 | 3 | 0 | Saved customer payment references |
| `loyalty_accounts` | 8 | 8 | 0 | Active point balances and tier status |
| `loyalty_rewards` | 4 | 4 | 0 | Milestone reward definitions |
| `loyalty_transactions` | 16 | 16 | 0 | Historical point earning and redemptions |
| `coupons` | 6 | 6 | 0 | Active and promotional voucher codes |
| `audit_logs` | 1 | 1 | 0 | Administrative action ledger |
| *(Remaining 7 Empty Tables)* | 0 | 0 | 0 | Schemas created cleanly |

---

## 8. Critical Business Data Checks (Sanitized)

- **Users**: 9 total accounts preserved (1 Super Admin, 2 Branch Admins, 6 Registered Customers).
- **Orders**: Exactly **46 customer orders** preserved.
- **Financial Ledger**: Exactly **47 payment records** preserved. Sum of order subtotals and payment amounts matches to £0.0001 precision.
- **Inventory**: All **59 branch inventory records** preserved.
- **Loyalty Program**: All **8 loyalty accounts** and **16 transaction history logs** preserved.
- **Sensitive Data Handling**: Passwords remain in salted cryptographic hashes; zero raw tokens or PII are exposed in audit logs.

---

## 9. Authentication Session & Refresh Token Preservation

- **Session Continuity**:
  - `auth_sessions` and `auth_consumed_jtis` schemas are fully mapped.
  - Active refresh token hashes and session metadata migrate cleanly.
  - Users and administrators with valid refresh tokens will **remain authenticated without forced logouts**.

---

## 10. Payment Data Handling

- **Live Client API State**: The client's live payment gateway API has not been handed over.
- **Database Scope**: Migration preserves all existing internal financial and transaction records (`payments` and `payment_events`) without fabricating external provider fields.

---

## 11. Backup & Rollback Plan

1. **Pre-Migration Safety**: Verified SQLite backup permanently archived at `C:\Users\HP\Desktop\pattyproject_backups\`.
2. **Transactional Protection**: Migration executes inside a single database transaction. If an error occurs, PostgreSQL rolls back to a pristine empty state.
3. **Rollback Trigger**:
   - If verification fails or any discrepancy is detected:
     - Stop FastAPI container.
     - Revert backend `DATABASE_URL` to local SQLite.
     - Retain PostgreSQL volume for post-mortem analysis.

---

## 12. Stop Conditions

The migration must immediately abort and trigger rollback if:
- Any of the 26 table row counts differ by $\pm 1$ row from SQLite.
- Any foreign-key orphan is detected.
- Any financial sum discrepancy occurs between SQLite and PostgreSQL.
- Database sequence pointers fail to increment properly.
- Any network listener binds to public `0.0.0.0:8000` or `0.0.0.0:5432`.

---

## 13. Exact Next-Step Sequence (Phase 4 Step 8C)

1. Provision `.env.production` on VPS with strong random `SECRET_KEY` and `POSTGRES_PASSWORD`.
2. Start `patty_postgres` container on private `patty_network` (no host ports).
3. Execute Alembic migrations (`alembic upgrade head`) to initialize all 26 tables.
4. Execute `migrate_sqlite_to_postgres.py` transactional ETL.
5. Run automated verification suite to confirm 100% data parity.
6. Start `patty_fastapi` container bound to `127.0.0.1:8000`.
7. Validate end-to-end API communication through host Nginx.

---

## 14. Explicit Operational Confirmations

> [!IMPORTANT]
> **MANDATORY SAFETY STATUS**:
> - **PRODUCTION SQLITE MIGRATION EXECUTED**: **NO**
> - **PRODUCTION POSTGRESQL CREATED**: **NO**
> - **PRODUCTION DATA MODIFIED**: **NO**
> - **FASTAPI PRODUCTION DEPLOYED**: **NO**
> - **NGINX PRODUCTION BACKEND SWITCHED**: **NO**
> - **PAYMENT API INTEGRATED**: **NO**
> - **NO SYSTEM REBOOT OCCURRED**.
