# NSP Plugin - Licensing System

Sistema completo de licenciamento production-ready para o NSP Plugin.

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                     NSP Plugin (Client)                       │
│                                                                │
│  ┌──────────────────┐                                        │
│  │ LicenseClient    │  →  Machine ID generation              │
│  │                  │  →  Token caching (offline mode)       │
│  │                  │  →  Heartbeat every 24h                │
│  └────────┬─────────┘                                        │
│           │ HTTPS                                             │
└───────────┼───────────────────────────────────────────────────┘
            │
            ↓
┌───────────┴───────────────────────────────────────────────────┐
│                   License Server (FastAPI)                     │
│                                                                │
│  Endpoints:                                                   │
│  • POST /api/v1/licenses/activate                            │
│  • POST /api/v1/licenses/validate                            │
│  • POST /api/v1/licenses/heartbeat                           │
│  • POST /api/v1/licenses/deactivate                          │
│  • POST /api/v1/licenses/create (admin)                      │
│                                                                │
│  Database: PostgreSQL                                         │
│  • licenses (keys, plans, expiration)                        │
│  • activations (machine_id, last_heartbeat)                  │
│  • heartbeats (analytics)                                     │
└───────────────────────────────────────────────────────────────┘
```

---

## Instalação

### Dependências

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose[cryptography] passlib[bcrypt] requests cryptography
```

### License Server Setup

1. **PostgreSQL Setup**

```bash
# macOS (Homebrew)
brew install postgresql
brew services start postgresql

# Create database
createdb nsp_licensing
```

2. **Environment Variables**

```bash
export DATABASE_URL="postgresql://localhost/nsp_licensing"
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ADMIN_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

3. **Start Server**

```bash
cd licensing
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

4. **Verify**

```bash
curl http://localhost:8080/health
# {"status":"ok","service":"nsp-license-server","version":"1.0.0"}
```

---

## Uso

### Admin: Criar Licença

```bash
curl -X POST http://localhost:8080/api/v1/licenses/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: admin_secret_key_change_me" \
  -d '{
    "email": "customer@example.com",
    "plan": "professional",
    "max_activations": 3,
    "duration_days": 365
  }'

# Response:
# {
#   "success": true,
#   "license_key": "VELA-A1B2-C3D4-E5F6-G7H8",
#   "email": "customer@example.com",
#   "plan": "professional",
#   "expires_at": "2026-01-09T12:00:00Z"
# }
```

### Client: Ativar Licença

```python
from licensing.client import LicenseClient

client = LicenseClient(license_server="http://localhost:8080")

# Activate
result = client.activate("VELA-A1B2-C3D4-E5F6-G7H8")
print(f"Plan: {result['plan']}")
print(f"Features: {result['features']}")

# Validate (uses cached token if < 24h old)
validation = client.validate()
print(f"Valid: {validation['valid']}")
print(f"Offline mode: {validation.get('offline', False)}")

# Heartbeat (refresh token)
client.heartbeat(plugin_version="2.0.0")

# Deactivate
client.deactivate()
```

### CLI Tool

```bash
# Show machine ID
python licensing/client.py machine-id
# Machine ID: abc123def456...

# Activate
python licensing/client.py activate VELA-A1B2-C3D4-E5F6-G7H8 --server http://localhost:8080
# ✅ License activated successfully!

# Validate
python licensing/client.py validate --server http://localhost:8080
# ✅ License valid!

# Heartbeat
python licensing/client.py heartbeat --server http://localhost:8080
# ✅ Heartbeat sent

# Deactivate
python licensing/client.py deactivate --server http://localhost:8080
# ✅ License deactivated
```

---

## Planos e Features

| Plan | Preço | Ativações | LightGBM | Neural Net | Smart Culling | Auto-Profiling | Max Batch |
|------|-------|-----------|----------|------------|---------------|----------------|-----------|
| Trial | Grátis | 1 | ✅ | ❌ | ❌ | ❌ | 50 |
| Personal | €79 | 2 | ✅ | ✅ | ✅ | ❌ | 500 |
| Professional | €149 | 3 | ✅ | ✅ | ✅ | ✅ | 5000 |
| Studio | €499 | 10 | ✅ | ✅ | ✅ | ✅ | Unlimited |

---

## Proteção de Modelos ML

### Encriptar Modelos

```python
from licensing.client import encrypt_model
from pathlib import Path

# Encriptar todos os modelos com master key
master_key = "MASTER-KEY-FOR-ENCRYPTION"  # Keep secret!

for model_file in Path("models").glob("slider_*.txt"):
    encrypt_model(model_file, master_key)
    # Output: slider_exposure.txt.enc
```

### Desencriptar no Runtime

```python
from licensing.client import decrypt_model, LicenseClient

# Get user's license key
client = LicenseClient()
license_key = client.get_cached_plan()  # From token

# Decrypt model in memory (never save to disk)
encrypted_path = Path("models/slider_exposure.txt.enc")
model_bytes = decrypt_model(encrypted_path, license_key)

# Load into LightGBM from bytes
import tempfile
import lightgbm as lgb

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(model_bytes)
    tmp.flush()
    model = lgb.Booster(model_file=tmp.name)
os.unlink(tmp.name)
```

---

## Hardware Fingerprinting

O sistema gera um `machine_id` único baseado em:

### macOS
- **MAC Address**: Primary network interface
- **IOPlatformSerialNumber**: CPU serial
- **Volume UUID**: Boot disk UUID
- **Hostname**: Computer name

### Windows
- **MAC Address**: Primary network interface
- **Machine GUID**: From WMIC
- **Hostname**: Computer name

### Linux
- **MAC Address**: Primary network interface
- **Machine ID**: From `/etc/machine-id`
- **Hostname**: Computer name

**Resultado**: SHA-256 hash (primeiros 128 bits) = ID irreprodutível

**Nota**: Mudanças de hardware major (motherboard, boot disk) podem gerar novo ID.

---

## Offline Mode & Grace Period

### Offline Mode
- Token válido por **24 horas** sem conectividade
- Após 24h: Heartbeat requerido para renovar token
- Se offline > 7 dias: **Degraded mode** (apenas trial features)

### Grace Period
```python
# Client-side logic
days_offline = (datetime.now() - last_heartbeat).days

if days_offline > 7:
    # Enter degraded mode
    features = {
        "lightgbm": True,
        "neural_network": False,  # Disable premium features
        "smart_culling": False,
        "auto_profiling": False,
        "max_photos_per_batch": 50  # Trial limit
    }
```

---

## Deployment em Produção

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: nsp_licensing
      POSTGRES_USER: nsp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  license-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql://nsp:${DB_PASSWORD}@postgres/nsp_licensing
      SECRET_KEY: ${SECRET_KEY}
      ADMIN_KEY: ${ADMIN_KEY}
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Kubernetes Deployment

Ver `docs/COMMERCIALIZATION_PLAN.md` secção 8.1

### Custos Estimados

- **DigitalOcean**: $142/mês (até 10,000 users)
- **AWS**: $150-200/mês (similar)

---

## Monitorização & Analytics

### Admin Dashboard

```bash
curl -H "X-Admin-Key: admin_secret_key_change_me" \
  http://localhost:8080/api/v1/admin/stats

# {
#   "total_licenses": 1234,
#   "active_licenses": 987,
#   "total_activations": 1543,
#   "heartbeats_24h": 892
# }
```

### Queries Úteis (PostgreSQL)

```sql
-- Licenças ativas por plano
SELECT plan, COUNT(*)
FROM licenses
WHERE status = 'active'
GROUP BY plan;

-- Activações por dia (últimos 30 dias)
SELECT DATE(activated_at) as date, COUNT(*)
FROM activations
WHERE activated_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(activated_at)
ORDER BY date;

-- Heartbeats por hora (últimas 24h)
SELECT DATE_TRUNC('hour', timestamp) as hour, COUNT(*)
FROM heartbeats
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Detecção de abuso (múltiplas ativações recentes)
SELECT license_id, COUNT(*) as activation_count
FROM activations
WHERE activated_at > NOW() - INTERVAL '1 day'
  AND deactivated_at IS NULL
GROUP BY license_id
HAVING COUNT(*) > 5;
```

---

## Anti-Pirataria

### Detecção de Ativações Suspeitas

O sistema automaticamente detecta e flag:

1. **Excessive Activations**: > 5 ativações em 24h
2. **VPN Hopping**: IPs de VPNs conhecidas ou datacenters
3. **VM Cloning**: Machine IDs muito similares (Hamming distance < 3)

### Revogação de Licença

```python
# Server-side (admin endpoint)
db.execute(
    "UPDATE licenses SET status = 'revoked', revoked_at = NOW(), revoke_reason = ? WHERE key = ?",
    ("Chargeback - fraud", "VELA-A1B2-C3D4-E5F6-G7H8")
)
```

Próximo heartbeat: Cliente recebe status 403 e entra em modo degraded.

---

## Integração com NSP Plugin

### services/server.py

```python
from licensing.client import LicenseClient, LicenseError

# Startup
LICENSE_CLIENT = None

@app.on_event("startup")
def startup_event():
    global LICENSE_CLIENT
    LICENSE_CLIENT = LicenseClient(license_server="https://license.vilearn.ai")

    try:
        validation = LICENSE_CLIENT.validate()
        logger.info(f"License valid: {validation['plan']}")

        # Load features
        features = LICENSE_CLIENT.get_cached_features()

        # Conditionally load models
        if features.get("neural_network"):
            load_nn_model()
        if features.get("smart_culling"):
            load_culling_model()

    except LicenseError as e:
        logger.error(f"License validation failed: {e}")
        # Load only trial features
```

### Background Heartbeat

```python
from apscheduler.schedulers.background import BackgroundScheduler

def send_heartbeat():
    if LICENSE_CLIENT:
        LICENSE_CLIENT.heartbeat(plugin_version="2.0.0")

scheduler = BackgroundScheduler()
scheduler.add_job(send_heartbeat, 'interval', hours=24)
scheduler.start()
```

---

## Security Best Practices

### Server-Side
- ✅ Use HTTPS em produção (Let's Encrypt)
- ✅ Rotate SECRET_KEY periodicamente
- ✅ Rate limit endpoints (slowapi)
- ✅ Monitor for abuse patterns
- ✅ Backup database diariamente

### Client-Side
- ✅ Never hardcode license keys
- ✅ Encrypt token cache file
- ✅ Validate server SSL certificate
- ✅ Handle offline mode gracefully
- ✅ Obfuscate API endpoints

---

## Troubleshooting

### "License validation required. Please connect to the internet."

**Causa**: Token expirado (> 24h offline) e sem conectividade.

**Solução**: Conectar à internet e executar heartbeat.

### "Maximum activations (N) reached"

**Causa**: Licença já ativa em N máquinas.

**Solução**: Deactivar numa das máquinas existentes ou comprar upgrade.

### "License revoked: [reason]"

**Causa**: Licença foi revogada por admin (chargeback, abuso, etc).

**Solução**: Contactar suporte.

### "Failed to decrypt model. Invalid license key."

**Causa**: Modelos encriptados com key diferente.

**Solução**: Verificar que MASTER_KEY usada na encriptação é a correta.

---

## Roadmap

### v1.1 (Q1 2025)
- [ ] Web dashboard para users (self-service activation)
- [ ] Email notifications (expiring licenses)
- [ ] Subscription auto-renewal (Stripe integration)

### v1.2 (Q2 2025)
- [ ] Offline license files (.velkey)
- [ ] Air-gapped activation (manual validation)
- [ ] Multi-tenant support

### v2.0 (Q3 2025)
- [ ] Usage-based licensing (pay-per-photo)
- [ ] Team licenses (shared pools)
- [ ] SSO integration (OAuth)

---

## Support

- **Documentation**: `docs/COMMERCIALIZATION_PLAN.md`
- **Issues**: GitHub Issues
- **Email**: support@vilearn.ai

---

**License**: Proprietary - ViLearnStyle AI Systems
