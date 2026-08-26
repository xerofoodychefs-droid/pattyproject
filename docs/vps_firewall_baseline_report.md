# VPS Firewall Baseline Report — Patty Project

**Phase**: Phase 4 — Step 4  
**Target Host**: IONOS VPS L+ (Ubuntu 24.04 LTS)  
**Public IP**: `194.164.120.249`  
**Administrative Identity**: `pattyadmin` (SSH Key Authentication Verified, Sudo Verified)  
**Date**: 2026-08-26  
**Role**: Principal Linux Security Engineer & Production DevOps Engineer  

---

## 1. Executive Summary & Objective

In this step, a hardened host firewall baseline was established on the **IONOS VPS L+** server prior to the installation of Docker, PostgreSQL, Nginx, or any application container deployments.

The firewall policy operates on a **Strict Default-Deny Model**, ensuring that only explicitly authorized network traffic can reach the server. All inbound ports are dropped by default, while outbound connectivity is permitted for operating system package management and system time synchronization.

---

## 2. Step-by-Step Firewall Configuration Execution

### Step 1: Pre-Configuration State Inspection
- **Previous UFW Status**: `inactive` (Standard fresh Ubuntu 24.04 cloud-init state).
- **Previous iptables/nftables**: Default empty acceptance chains (`INPUT ACCEPT`, `FORWARD ACCEPT`, `OUTPUT ACCEPT`).
- **Initial Listening Ports**:
  - `0.0.0.0:22` (TCP) — `sshd` (OpenSSH Daemon)
  - `[::]:22` (TCP) — `sshd` (OpenSSH Daemon IPv6)
  - `127.0.0.53:53` (UDP/TCP) — `systemd-resolved` (Local DNS Stub Resolver)
  - `127.0.0.54:53` (UDP/TCP) — `systemd-resolved` (Local DNS Stub Resolver)
- **Active Network Interface**: `eth0` / `ens6` with assigned public IPv4 `194.164.120.249` and allocated `/64` IPv6 prefix.

### Step 2: Ingress Port Requirement Determination
- **Mandatory Inbound**:
  - **TCP 22 (SSH)**: Required for ongoing remote administration via the verified `pattyadmin` user with Ed25519/RSA public key authentication.
- **Future Inbound (Reserved for Nginx Step)**:
  - **TCP 80 (HTTP)** / **TCP 443 (HTTPS)**: Will be opened during the Nginx reverse proxy installation step.
- **Strictly Blocked & Isolated**:
  - **TCP 5432 (PostgreSQL)**: Blocked. Will run in an internal Docker network (`patty_network`) with zero public/host port mappings.
  - **TCP 8000 (FastAPI)**: Blocked from external interfaces. Accessible only via localhost (`127.0.0.1:8000`) or Docker internal network.
  - **TCP 2375 / 2376 (Docker Daemon)**: Blocked. Docker socket is restricted strictly to local `/var/run/docker.sock`.

### Step 3: UFW Policy Hardening & Dual-Stack IPv6 Configuration
1. **Dual-Stack Configuration**:
   - Inspected `/etc/default/ufw` to verify `IPV6=yes`.
   - Ensures all UFW rules apply symmetrically to `ip6tables` and `nftables` IPv6 chains, preventing IPv6 ingress bypass attacks.
2. **Default Traffic Policies**:
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw default deny routed
   ```
3. **SSH Rule Definition**:
   ```bash
   sudo ufw allow 22/tcp comment 'SSH Key Access'
   ```
4. **Anti-Lockout Verification**:
   - Verified active terminal session as `pattyadmin`.
   - Verified `sudo whoami` evaluated to `root`.
   - Applied rule and enabled firewall:
   ```bash
   sudo ufw --force enable
   ```

---

## 3. Post-Hardening Firewall Verification (`ufw status verbose`)

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

---

## 4. Post-Hardening Listening Sockets (`ss -lntup`)

| Protocol | Local Address | Port | Process | Scope | Publicly Exposed? |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **TCP** | `0.0.0.0` | **22** | `sshd` | Global IPv4 | **YES (Protected by UFW & Key Auth)** |
| **TCP** | `[::]` | **22** | `sshd` | Global IPv6 | **YES (Protected by UFW & Key Auth)** |
| **UDP** | `127.0.0.53%lo` | **53** | `systemd-resolved` | Localhost Only | **NO (Loopback Only)** |
| **UDP** | `127.0.0.54%lo` | **53** | `systemd-resolved` | Localhost Only | **NO (Loopback Only)** |
| **TCP** | `127.0.0.53%lo` | **53** | `systemd-resolved` | Localhost Only | **NO (Loopback Only)** |
| **TCP** | `127.0.0.54%lo` | **53** | `systemd-resolved` | Localhost Only | **NO (Loopback Only)** |

**Assessment**: Zero unexpected public services are listening or reachable. Only the OpenSSH daemon on port 22 is exposed to inbound traffic, protected by key-only authentication and UFW packet filtering.

---

## 5. IONOS Cloud Panel vs. Host OS Firewall Boundaries

- **Host Firewall (UFW / nftables)**:
  - Manages internal packet processing directly inside the Linux kernel on the VPS.
  - Active and enforcing default-deny ingress.
- **Provider Firewall (IONOS Cloud Panel)**:
  - External network hypervisor filter operated by IONOS.
  - Acts as an upstream perimeter filter. Can be configured via the IONOS Cloud Panel console to mirror ports 22, 80, and 443 if provider-level redundancy is desired.

---

## 6. Final Audit & Safety Verification Checklist

| Verification Item | Status | Details |
| :--- | :---: | :--- |
| **1. Previous Firewall State** | **VERIFIED** | Initially `inactive` with default ACCEPT policy. |
| **2. Final UFW Status** | **ACTIVE** | `active`, default deny incoming, default allow outgoing, default deny routed. |
| **3. IPv4 Firewall Status** | **ACTIVE** | Rule `22/tcp ALLOW IN Anywhere` active. |
| **4. IPv6 Firewall Status** | **ACTIVE** | Rule `22/tcp (v6) ALLOW IN Anywhere (v6)` active (`IPV6=yes`). |
| **5. Allowed Inbound Ports** | **TCP 22** | Port 22 only. Ports 80 and 443 remain closed until Nginx setup. |
| **6. Denied Inbound Behavior** | **DROP / DENY** | All unsolicited inbound connection requests are dropped. |
| **7. Listening Services** | **MINIMAL** | `sshd` on port 22; `systemd-resolved` on 127.0.0.53/54:53. |
| **8. Unexpected Exposed Ports** | **NONE** | 0 unexpected listening ports. |
| **9. SSH Accessibility** | **CONFIRMED** | `pattyadmin` session remained connected and functional. |
| **10. Application Files Unchanged** | **CONFIRMED** | 0 application source code files modified. |
| **11. No Staging of Services** | **CONFIRMED** | Docker, PostgreSQL, and Nginx were **NOT** installed. |
| **12. Zero Reboots** | **CONFIRMED** | Host uptime uninterrupted; no reboots triggered. |

---

## 7. Next Step Readiness

The host OS firewall baseline is securely established. The server is ready for:
- **Phase 4 — Step 5**: Fail2ban intrusion prevention configuration for SSH.
- **Phase 4 — Step 6**: Virtual memory & 4 GB swapfile configuration.
