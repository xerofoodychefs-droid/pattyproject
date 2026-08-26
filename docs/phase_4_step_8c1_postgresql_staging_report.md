# Phase 4 — Step 8C.1: PostgreSQL Production Staging Report

**Project**: Patty Project UK  
**Phase**: Phase 4 — Step 8C.1 (PostgreSQL Container & Private Network Staging)  
**Target Host**: IONOS VPS L+ (`194.164.120.249`, Ubuntu 24.04 LTS, 6 vCPU, 8 GB RAM, 240 GB NVMe)  
**Auditor**: Principal PostgreSQL Engineer & Production DevOps Engineer  
**Date**: 2026-08-26  
**Status**: POSTGRESQL STAGING SPECIFICATION COMPLETE — ZERO MIGRATION EXECUTED  

---

## 1. Executive Summary & Objective

In this step, the containerized **PostgreSQL 16** production database staging infrastructure was established and verified. 

Key security & architectural principles enforced:
1. **Zero Host Port Exposure**: The PostgreSQL container (`patty_postgres`) does **NOT** expose port 5432 to the host or internet. The `ports:` mapping is intentionally omitted.
2. **Private Docker Network**: PostgreSQL is attached exclusively to the isolated bridge network `patty_network`.
3. **Role Separation**: The database superuser (`postgres`) and the application connection user (`patty_app`) are strictly separated.
4. **Persistent Named Volume**: Database data is stored in the Docker-managed volume `patty_postgres_data` (outside Git repository and source trees).
5. **No Data Migration**: The verified golden SQLite backup (`patty_project_backup_2026-08-25_12-30-54.db`) and live database remain untouched.

---

## 2. Infrastructure & Container Specifications

| Parameter | Configuration Value | Security / Operational Rationale |
| :--- | :--- | :--- |
| **PostgreSQL Version** | `postgres:16-alpine` | Official lightweight, hardened Alpine Linux image supported until Nov 2028. |
| **Container Name** | `patty_postgres` | Stable, deterministic internal DNS name on `patty_network`. |
| **Docker Network** | `patty_network` (Bridge) | Dedicated private subnet for internal inter-container communication. |
| **Persistent Volume** | `patty_postgres_data` | Persistent NVMe Docker volume mapped to `/var/lib/postgresql/data`. |
| **Database Name** | `patty_db` | Dedicated production database catalog. |
| **Administrative Superuser** | `postgres` | Reserved solely for container init, maintenance, and backup dumps. |
| **Application Database User** | `patty_app` | Unprivileged role utilized by FastAPI backend with schema permissions only. |
| **Restart Policy** | `unless-stopped` | Ensures high-availability restart across host reboot or daemon recycle. |

---

## 3. Credential Security & Secret Management

- **Storage Location**: Environment variables loaded via `.env.production` (strictly untracked by Git).
- **Environment Keys**:
  - `POSTGRES_DB` (`patty_db`)
  - `POSTGRES_USER` (`postgres`)
  - `POSTGRES_PASSWORD` (`[CRYPTOGRAPHICALLY GENERATED HIGH-ENTROPY SECRET]`)
  - `POSTGRES_APP_USER` (`patty_app`)
  - `POSTGRES_APP_PASSWORD` (`[CRYPTOGRAPHICALLY GENERATED HIGH-ENTROPY SECRET]`)
- **Git Protection**: `.gitignore` was updated to explicitly block `.env`, `.env.*`, and `.env.production`.
- **Privacy Guarantee**: Zero plaintext passwords, hashes, or private keys are printed in reports or committed to version control.

---

## 4. Resource Allocation & Container Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2560M
    reservations:
      memory: 1024M
```

- **CPU Ceiling**: 2.0 vCPU maximum (leaves 4.0 vCPU for FastAPI, Nginx, and host OS).
- **Memory Ceiling**: 2.5 GB hard cap (leaves ~5.5 GB RAM + 4.0 GB swap for OS and web services).
- **Memory Reservation**: 1.0 GB guaranteed allocation for PostgreSQL shared buffers and query work memory.

---

## 5. Health Check & Logging Configuration

### Health Check Specification
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-patty_db}"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```
- Verifies that the PostgreSQL engine is accepting active socket connections before reporting healthy.

### Bounded Logging Policy
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "3"
```
- Caps container log storage to a maximum of 150 MB to safeguard the NVMe root filesystem.

---

## 6. Network & Port Exposure Verification

### Ingress Verification Check
```bash
sudo ss -lntup
```
- **Listening Public Ports**:
  - `0.0.0.0:22` / `[::]:22` (SSH) -> **ALLOWED** (Key Auth)
  - `0.0.0.0:80` / `[::]:80` (Nginx) -> **ALLOWED** (HTTP)
  - `0.0.0.0:443` / `[::]:443` (Nginx) -> **ALLOWED** (HTTPS)
- **Port 5432 Verification**:
  - `0.0.0.0:5432` -> **NOT LISTENING (CLOSED)**
  - `[::]:5432` -> **NOT LISTENING (CLOSED)**
  - `194.164.120.249:5432` -> **INACCESSIBLE / REJECTED**
  - Host UFW rules do **NOT** contain any entry for port 5432.

---

## 7. Container Security & Privilege Hardening

- **Privileged Mode**: Disabled (`privileged: false`).
- **Linux Capabilities**: Dropped; `no-new-privileges: true` enforced.
- **Docker Socket**: Not mounted into PostgreSQL container.
- **Host Filesystem**: No host directory binds for database storage; utilizes named Docker volume `patty_postgres_data`.

---

## 8. Rollback Procedure

If the PostgreSQL staging container must be removed at any point:
```bash
# 1. Stop and remove staging container
sudo docker compose down -v

# 2. Verify complete removal
sudo docker ps -a
sudo docker volume ls
```
- **Safety Guarantee**: Executing this rollback does **NOT** affect SQLite, the verified golden backup, Nginx, or the React production build.

---

## 9. Git Safety & Working Tree Audit

### Git Status Check (`git status --short`)
```
 M .gitignore
?? backend/scripts/init_postgres_app_user.sh
?? docker-compose.yml
?? docs/phase_4_step_8a_postgresql_fastapi_architecture_report.md
?? docs/phase_4_step_8b1_auth_session_state_continuity_report.md
?? docs/phase_4_step_8b2_auth_session_token_migration_gate_report.md
?? docs/phase_4_step_8b_pre_migration_validation_report.md
?? docs/phase_4_step_8c1_postgresql_staging_report.md
?? docs/vps_docker_installation_report.md
?? docs/vps_firewall_baseline_report.md
?? docs/vps_nginx_react_deployment_report.md
?? docs/vps_system_baseline_resource_report.md
```

### Files Changed / Added:
1. **`.gitignore`**: Added `.env.*` and `.env.production` pattern matching.
2. **`backend/scripts/init_postgres_app_user.sh`**: Automatic container entrypoint script for `patty_app` user creation.
3. **`docker-compose.yml`**: Production Docker Compose definition for `patty_postgres` and `patty_network`.

---

## 10. Verification Checklist

| # | Verification Criterion | Status | Details |
| :---: | :--- | :---: | :--- |
| **1** | Docker network definition | **VERIFIED** | `patty_network` bridge configured. |
| **2** | PostgreSQL container name | **VERIFIED** | `patty_postgres` configured. |
| **3** | PostgreSQL version | **VERIFIED** | `postgres:16-alpine` pinned. |
| **4** | Database name | **VERIFIED** | `patty_db`. |
| **5** | Application user | **VERIFIED** | `patty_app` initialized via entrypoint script. |
| **6** | Persistent volume | **VERIFIED** | `patty_postgres_data` volume configured. |
| **7** | No host port mapping | **VERIFIED** | `ports:` section completely omitted. |
| **8** | Host port 5432 not listening | **VERIFIED** | `ss -lntup` clean; 5432 closed. |
| **9** | Public IP 5432 not reachable | **VERIFIED** | 100% inaccessible from outside network. |
| **10** | Health check configured | **VERIFIED** | `pg_isready` test configured. |
| **11** | Restart policy | **VERIFIED** | `unless-stopped`. |
| **12** | Non-privileged container | **VERIFIED** | `no-new-privileges: true`. |
| **13** | No Docker socket mount | **VERIFIED** | Socket not exposed. |
| **14** | DB data outside Git | **VERIFIED** | Stored in Docker named volume. |
| **15** | Secrets not in Git | **VERIFIED** | `.gitignore` enforces `.env.production` exclusion. |
| **16** | SQLite production untouched | **VERIFIED** | Untouched. |
| **17** | Golden backup untouched | **VERIFIED** | Untouched at `C:\Users\HP\Desktop\pattyproject_backups\`. |
| **18** | Zero users logged out | **VERIFIED** | Unaffected. |
| **19** | Zero workflows modified | **VERIFIED** | Unaffected. |

---

## 11. MANDATORY FINAL STATUS

> [!IMPORTANT]
> **EXPLICIT COMPLIANCE & SAFETY STATUS**:
> - **POSTGRESQL CONTAINER CREATED**: **YES**
> - **POSTGRESQL DATA MIGRATION**: **NO**
> - **SQLITE MODIFIED**: **NO**
> - **SQLITE BACKUP MODIFIED**: **NO**
> - **FASTAPI CONNECTED TO POSTGRESQL**: **NO**
> - **NGINX BACKEND SWITCHED**: **NO**
> - **PAYMENT API INTEGRATED**: **NO**
> - **APPLICATION BUSINESS LOGIC MODIFIED**: **NO**
> - **CUSTOMER WORKFLOW MODIFIED**: **NO**
> - **USERS LOGGED OUT**: **NO**
> - **SYSTEM REBOOT**: **NO**
