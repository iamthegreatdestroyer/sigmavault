# SigmaVault Port Assignments (36000 Series)

**Purpose:** Port configuration for SigmaVault (ΣVAULT) project.

**Port Series:** 36000-36999 (exclusive range)

**Last Updated:** December 18, 2025

---

## 🎯 Port Allocation Summary

| Port Range | Category | Description |
|------------|----------|-------------|
| 36000-36099 | Application | Vault UI, Admin Console |
| 36080-36099 | API | Storage, Crypto, Sync |
| 36500-36599 | Cache | Redis |
| 36900-36999 | Observability | Prometheus, Grafana |

---

## 🔐 Application & API Tier (36000-36099)

| Port | Service | Description | Config |
|------|---------|-------------|--------|
| **36080** | Vault API | Main encrypted storage API | `docker-compose.yml` |

---

## 🔄 Cache & Messaging (36500-36599)

| Port | Service | Internal | Description | Config |
|------|---------|----------|-------------|--------|
| **36500** | Redis | 6379 | Cache and pub/sub | `docker-compose.yml` |

---

## 📈 Observability (36900-36999)

| Port | Service | Internal | Description | Config |
|------|---------|----------|-------------|--------|
| **36900** | Prometheus | 9090 | Metrics collection | `docker-compose.yml` |
| **36910** | Grafana | 3000 | Dashboards | `docker-compose.yml` |

---

## 🌐 Quick Access

| Service | URL |
|---------|-----|
| Vault API | http://localhost:36080 |
| Grafana | http://localhost:36910 |
| Redis | localhost:36500 |

---

## 🔗 Cross-Project Reference

For complete port allocations across all projects in the ecosystem, see the **MASTER_PORT_ASSIGNMENTS.md** in the NEURECTOMY project:
- **DOPPELGANGER-STUDIO:** 10000-10999
- **NEURECTOMY:** 16000-16999
- **SigmaLang:** 26000-26999
- **SigmaVault:** 36000-36999 ✓
- **Ryot LLM:** 46000-46999

---

## 🚀 Getting Started

```bash
# Start all services
docker-compose up -d

# Run in development mode
docker-compose --profile dev up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

**Version:** 1.0
**Status:** Active and maintained
