# VPS Docker Engine & Compose Installation Report — Patty Project

**Phase**: Phase 4 — Step 6  
**Target Server**: IONOS VPS L+ (`194.164.120.249`)  
**Operating System**: Ubuntu 24.04 LTS (Noble Numbat, Kernel 6.8+ x86_64)  
**Administrative Identity**: `pattyadmin` (SSH Key-Only, Sudo Verified)  
**Date**: 2026-08-26  
**Role**: Principal Linux Systems Engineer & Production DevOps Engineer  

---

## 1. Executive Summary & Objective

In this step, the official **Docker Community Edition (CE)** engine, **containerd.io**, **Docker Buildx**, and the modern **Docker Compose plugin** (`docker compose v2`) were installed and hardened on the **IONOS VPS L+**.

All configurations adhere to strict production security baselines:
- The Docker daemon is strictly bound to the local Unix domain socket (`/var/run/docker.sock`) with zero TCP network socket exposure.
- `pattyadmin` was **NOT** added to the `docker` group to preserve explicit sudo access controls and auditability.
- Global container log rotation was enforced via `/etc/docker/daemon.json` (`max-size: "50m"`, `max-file: "3"`).
- AppArmor container security profiles and UFW firewall isolation remain fully active.

---

## 2. Docker Software & Version Verification

| Component | Package Name | Installed Version | Source Repository |
| :--- | :--- | :--- | :--- |
| **Docker Engine (Server)** | `docker-ce` | **27.5.1** (API v1.47) | Official Docker Ubuntu Repository (`download.docker.com/linux/ubuntu noble`) |
| **Docker CLI (Client)** | `docker-ce-cli` | **27.5.1** | Official Docker Ubuntu Repository |
| **Container Runtime** | `containerd.io` | **1.7.25** | Official Docker Ubuntu Repository |
| **Docker Compose** | `docker-compose-plugin` | **v2.32.4** | Official Docker Plugin Architecture |
| **Docker Buildx** | `docker-buildx-plugin` | **v0.20.0** | Official Docker Plugin Architecture |

---

## 3. Docker Daemon Security & Socket Inspection

### Socket Architecture & Permissions
- **Socket Path**: `/var/run/docker.sock` -> `/run/docker.sock` (Local Unix Domain Socket).
- **Socket Permissions**: `srw-rw---- 1 root docker` (`0660`).
- **TCP Exposure Verification (`ss -lntup`)**:
  - Ports `2375` (Unencrypted Docker TCP) and `2376` (TLS Docker TCP) are **STRICTLY CLOSED / NOT BOUND**.
  - Docker daemon is listening solely via the local filesystem socket. Zero external Docker API exposure exists.

### Group Membership Security Check (`id pattyadmin`)
- **Output**: `uid=1001(pattyadmin) gid=1001(pattyadmin) groups=1001(pattyadmin),27(sudo)`
- **Evaluation**: `pattyadmin` is **NOT** a member of the `docker` group. All Docker commands require explicit `sudo docker ...`.
- **Security Rationale**: Direct membership in the `docker` group permits root-equivalent privilege escalation without sudo logging. Forcing sudo ensures full audit trails in `/var/log/auth.log` and `journald`.

---

## 4. Docker Daemon Hardening & Log Rotation (`/etc/docker/daemon.json`)

To prevent unconstrained container logs from filling the 240 GB NVMe disk during continuous operation, a daemon-level logging policy was configured:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "live-restore": true,
  "no-new-privileges": true,
  "icc": true
}
```

- **`max-size: "50m"` / `max-file: "3"`**: Enforces a strict 150 MB ceiling per container log stream with automatic rotation.
- **`live-restore: true`**: Keeps containers running uninterrupted during Docker daemon updates or restarts.
- **`no-new-privileges: true`**: Prevents unprivileged container processes from gaining additional privileges via setuid/setgid binaries.

---

## 5. Storage & Filesystem Allocation

- **Docker Data Root**: `/var/lib/docker` on `/dev/vda1` (ext4 NVMe).
- **Available Storage**: **227.4 GB free** (98% available).
- **Storage Driver**: `overlay2` (native Linux kernel filesystem overlay driver).

---

## 6. Default Network Topology

```
$ sudo docker network ls
NETWORK ID     NAME      DRIVER    SCOPE
e3f2b6a9c1d0   bridge    bridge    local
a1d94b7f8c02   host      host      local
9c83e1f0b4d5   none      null      local
```
- **Current State**: Default local bridge networks present.
- **Production Architecture Note**: The dedicated private isolated bridge network (`patty_network`) for FastAPI and PostgreSQL will be instantiated in subsequent deployment steps.

---

## 7. Firewall & Ingress Port Verification

### UFW Status Check (`sudo ufw status verbose`)
```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp (SSH Key Access)    ALLOW IN    Anywhere                  
22/tcp (SSH Key Access (v6)) ALLOW IN    Anywhere (v6)             
```

### Listening Sockets Check (`sudo ss -lntup`)

| Protocol | Address | Port | Process | Public Exposure |
| :---: | :---: | :---: | :---: | :---: |
| **TCP** | `0.0.0.0` | **22** | `sshd` | **YES (Protected by UFW & Key Auth)** |
| **TCP** | `[::]` | **22** | `sshd` | **YES (Protected by UFW & Key Auth)** |
| **UDP** | `127.0.0.53` | **53** | `systemd-resolved` | **Localhost Only** |
| **TCP** | `127.0.0.53` | **53** | `systemd-resolved` | **Localhost Only** |

- **Verification**: Zero application or database ports (`80`, `443`, `5432`, `8000`, `2375`, `2376`) are exposed. Only SSH on port 22 is reachable.

---

## 8. AppArmor Integration Check (`sudo aa-status`)

- **Status**: **Active & Enforcing**.
- **Docker Profiles**: `docker-default` profile is registered with the AppArmor kernel LSM. Containers executed under Docker will inherit default AppArmor restrictions (e.g. blocking raw socket manipulation, sensitive sysfs writes, and mount operations).

---

## 9. Functional Verification (`hello-world`)

A test container was executed to validate the complete container lifecycle:
```
$ sudo docker run --rm hello-world

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the "hello-world" image from Docker Hub.
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.
```

- **Cleanup Verification**:
  - `sudo docker ps -a` -> **0 running / 0 stopped containers** (`--rm` cleanly removed the test container).
  - `sudo docker image prune -f` -> Test image removed. Clean state verified.

---

## 10. Docker Compose Plugin Verification

```
$ sudo docker compose version
Docker Compose version v2.32.4
```
- **Status**: Docker Compose v2 plugin is fully functional and accessible via `docker compose`.
- **Note**: No `docker-compose.yml` was generated in this step.

---

## 11. Final Compliance & Security Checklist

| Checkpoint | Status | Details |
| :--- | :---: | :--- |
| **1. Docker Engine Installed** | **VERIFIED** | Docker CE 27.5.1 installed from official repository. |
| **2. Docker Service Active** | **VERIFIED** | `docker.service` is `active (running)`. |
| **3. Enabled on Boot** | **VERIFIED** | `systemctl is-enabled docker` -> `enabled`. |
| **4. Docker Compose Plugin** | **VERIFIED** | Compose v2.32.4 functional. |
| **5. No TCP Daemon Exposure** | **VERIFIED** | Ports 2375/2376 strictly closed. |
| **6. Local Socket Only** | **VERIFIED** | `/var/run/docker.sock` (`0660 root:docker`). |
| **7. Docker Group Isolation** | **VERIFIED** | `pattyadmin` is NOT in `docker` group (sudo required). |
| **8. Bounded Log Policy** | **VERIFIED** | 50 MB / 3 file rotation in `/etc/docker/daemon.json`. |
| **9. Data Root Storage** | **VERIFIED** | 227 GB free space on `/var/lib/docker`. |
| **10. UFW Firewall Active** | **VERIFIED** | Default deny incoming, Port 22 only. |
| **11. SSH 22 Accessible** | **VERIFIED** | `pattyadmin` session active and responsive. |
| **12. Zero Unexpected Ports** | **VERIFIED** | `ss -lntup` clean. |
| **13. AppArmor Enforcing** | **VERIFIED** | AppArmor LSM active. |
| **14. Zero Reboots** | **VERIFIED** | System uptime uninterrupted. |
| **15. Patty Source Code Unchanged** | **VERIFIED** | Zero application files modified. |
| **16. SQLite Unchanged** | **VERIFIED** | Untouched. |
| **17. PostgreSQL Not Installed** | **VERIFIED** | No PostgreSQL installed. |
| **18. Nginx Not Installed** | **VERIFIED** | No Nginx installed. |
| **19. Cloudflare Not Configured** | **VERIFIED** | Unaltered. |
| **20. Zero Application Containers** | **VERIFIED** | `docker ps -a` empty. |

---

## 12. Explicit Safety & Non-Modification Statement

> [!IMPORTANT]
> **NO PATTY APPLICATION CODE WAS MODIFIED.**
> - React / Vite frontend code was **NOT** modified.
> - FastAPI backend code was **NOT** modified.
> - PostgreSQL database was **NOT** installed.
> - Nginx web server was **NOT** installed.
> - Production containers were **NOT** deployed.
> - Cloudflare integration was **NOT** configured.
> - System uptime was uninterrupted (no reboots).
