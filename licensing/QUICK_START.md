# Licensing System - Quick Start Guide

Guia rápido para testar o sistema de licenciamento localmente.

---

## Setup Rápido (5 minutos)

### 1. Instalar Dependências

```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate

pip install fastapi uvicorn sqlalchemy psycopg2-binary python-jose[cryptography] passlib[bcrypt] cryptography
```

### 2. Iniciar PostgreSQL

```bash
# macOS (Homebrew)
brew install postgresql
brew services start postgresql

# Criar database
createdb nsp_licensing
```

### 3. Configurar Environment

```bash
export DATABASE_URL="postgresql://localhost/nsp_licensing"
export SECRET_KEY="dev_secret_key_$(openssl rand -hex 16)"
export ADMIN_KEY="dev_admin_key_$(openssl rand -hex 16)"

echo "Admin Key: $ADMIN_KEY"  # Guardar para usar depois
```

### 4. Iniciar License Server

```bash
cd licensing
python server.py

# Servidor arranca em http://localhost:8080
# Ctrl+C para parar
```

### 5. Testar (Novo Terminal)

```bash
source venv/bin/activate
cd licensing

# Ver machine ID
python client.py machine-id
# Machine ID: abc123def456...

# Criar licença de teste (Admin)
curl -X POST http://localhost:8080/api/v1/licenses/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -d '{
    "email": "test@example.com",
    "plan": "professional",
    "max_activations": 3,
    "duration_days": 365
  }'

# Copiar o license_key da resposta
# Exemplo: VELA-A1B2-C3D4-E5F6-G7H8

# Ativar
python client.py activate VELA-A1B2-C3D4-E5F6-G7H8 --server http://localhost:8080
# ✅ License activated successfully!

# Validar
python client.py validate --server http://localhost:8080
# ✅ License valid!

# Heartbeat
python client.py heartbeat --server http://localhost:8080
# ✅ Heartbeat sent

# Deactivate
python client.py deactivate --server http://localhost:8080
# ✅ License deactivated
```

---

## Testar Offline Mode

```bash
# 1. Ativar licença
python client.py activate VELA-... --server http://localhost:8080

# 2. Parar license server (Ctrl+C no terminal do servidor)

# 3. Validar (usa token cached)
python client.py validate --server http://localhost:8080
# ✅ License valid!
# Offline mode: True

# 4. Simular token expirado
# (editar ~/.nsp/license/token.json, mudar "saved_at" para 3 dias atrás)

# 5. Validar novamente
python client.py validate --server http://localhost:8080
# ❌ Validation failed: License validation required. Please connect to the internet.

# 6. Reiniciar servidor e tentar novamente
python server.py  # Novo terminal
python client.py validate --server http://localhost:8080
# ✅ License valid!
```

---

## Testar Model Encryption

```bash
# 1. Encriptar modelo de teste
python3 << EOF
from pathlib import Path
from licensing.client import encrypt_model

# Criar modelo dummy
test_model = Path("test_model.txt")
test_model.write_text("model_data_here")

# Encriptar
encrypt_model(test_model, "VELA-TEST-KEY")
print(f"✅ Encrypted: {test_model}.enc")
EOF

# 2. Desencriptar
python3 << EOF
from pathlib import Path
from licensing.client import decrypt_model

encrypted = Path("test_model.txt.enc")
decrypted = decrypt_model(encrypted, "VELA-TEST-KEY")
print(f"✅ Decrypted: {decrypted.decode()}")
EOF

# 3. Testar com key errada (deve falhar)
python3 << EOF
from pathlib import Path
from licensing.client import decrypt_model, LicenseError

try:
    decrypt_model(Path("test_model.txt.enc"), "WRONG-KEY")
except LicenseError as e:
    print(f"✅ Correctly rejected wrong key: {e}")
EOF
```

---

## Testar Admin Endpoints

```bash
# Criar múltiplas licenças
for i in {1..5}; do
  curl -X POST http://localhost:8080/api/v1/licenses/create \
    -H "Content-Type: application/json" \
    -H "X-Admin-Key: $ADMIN_KEY" \
    -d "{
      \"email\": \"user$i@example.com\",
      \"plan\": \"personal\",
      \"max_activations\": 2
    }"
done

# Ver stats
curl -H "X-Admin-Key: $ADMIN_KEY" \
  http://localhost:8080/api/v1/admin/stats | jq

# {
#   "total_licenses": 6,
#   "active_licenses": 6,
#   "total_activations": 1,
#   "heartbeats_24h": 2
# }
```

---

## Testar Limite de Ativações

```bash
# 1. Criar licença com max_activations=2
LICENSE_KEY=$(curl -s -X POST http://localhost:8080/api/v1/licenses/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -d '{
    "email": "limit-test@example.com",
    "plan": "personal",
    "max_activations": 2
  }' | jq -r '.license_key')

echo "License key: $LICENSE_KEY"

# 2. Ativar em 2 "máquinas" (simular com machine_id diferente)
# Máquina 1 (real machine ID)
python client.py activate $LICENSE_KEY --server http://localhost:8080

# Máquina 2 (simular via API diretamente)
curl -X POST http://localhost:8080/api/v1/licenses/activate \
  -H "Content-Type: application/json" \
  -d "{
    \"license_key\": \"$LICENSE_KEY\",
    \"machine_id\": \"fake_machine_id_2\",
    \"machine_name\": \"Test Machine 2\"
  }"

# 3. Tentar ativar 3ª máquina (deve falhar)
curl -X POST http://localhost:8080/api/v1/licenses/activate \
  -H "Content-Type: application/json" \
  -d "{
    \"license_key\": \"$LICENSE_KEY\",
    \"machine_id\": \"fake_machine_id_3\",
    \"machine_name\": \"Test Machine 3\"
  }"

# Response: {"detail":"Maximum activations (2) reached..."}
```

---

## Integração com NSP Plugin (Demo)

```python
# Adicionar em services/server.py

from licensing.client import LicenseClient, LicenseError

# Global
LICENSE_CLIENT = None
LICENSED_FEATURES = {}

@app.on_event("startup")
def startup_event():
    global LICENSE_CLIENT, LICENSED_FEATURES

    # Tentar validar licença
    LICENSE_CLIENT = LicenseClient(license_server="http://localhost:8080")

    try:
        validation = LICENSE_CLIENT.validate()

        if validation['valid']:
            LICENSED_FEATURES = validation['features']
            logger.info(f"✅ License valid - Plan: {validation['plan']}")
            logger.info(f"Features: {LICENSED_FEATURES}")
        else:
            logger.warning("⚠️  License invalid - degraded mode")
            LICENSED_FEATURES = {
                "lightgbm": True,
                "neural_network": False,
                "smart_culling": False,
                "auto_profiling": False,
                "max_photos_per_batch": 50
            }

    except LicenseError as e:
        logger.error(f"❌ License validation failed: {e}")
        LICENSED_FEATURES = {}  # Trial mode

    # Carregar modelos baseado em features
    if LICENSED_FEATURES.get("neural_network"):
        logger.info("Loading Neural Network model...")
        # load_nn_model()

    if LICENSED_FEATURES.get("smart_culling"):
        logger.info("Loading Smart Culling model...")
        # CULLING_ENGINE = CullingEngine()


# Endpoint que respeita features
@app.post("/predict")
def predict(payload: PredictRequest):
    # Verificar batch size limit
    max_batch = LICENSED_FEATURES.get("max_photos_per_batch", 50)

    # Verificar se pode usar neural network
    if payload.model == "nn" and not LICENSED_FEATURES.get("neural_network"):
        raise HTTPException(
            status_code=403,
            detail="Neural Network model requires Professional license or higher"
        )

    # Continue normal flow...
```

---

## Queries Úteis (PostgreSQL)

```bash
# Conectar ao DB
psql nsp_licensing

# Ver todas as licenças
SELECT license_key, email, plan, status, max_activations
FROM licenses;

# Ver ativações
SELECT l.license_key, a.machine_id, a.machine_name, a.last_heartbeat
FROM activations a
JOIN licenses l ON a.license_id = l.id
WHERE a.deactivated_at IS NULL;

# Ver heartbeats recentes
SELECT a.machine_name, h.timestamp, h.plugin_version
FROM heartbeats h
JOIN activations a ON h.activation_id = a.id
ORDER BY h.timestamp DESC
LIMIT 10;

# Revogar licença
UPDATE licenses
SET status = 'revoked', revoked_at = NOW(), revoke_reason = 'Test revocation'
WHERE license_key = 'VELA-...';
```

---

## Troubleshooting

### "Connection refused" ao ativar

**Solução**: Verificar que license server está a correr:
```bash
curl http://localhost:8080/health
```

### "Database connection error"

**Solução**: Verificar PostgreSQL:
```bash
brew services list | grep postgresql
# Se stopped: brew services start postgresql
```

### "Invalid or expired token"

**Solução**: Apagar token cache e re-ativar:
```bash
rm -rf ~/.nsp/license/token.json
python client.py activate VELA-... --server http://localhost:8080
```

---

## Próximos Passos

1. ✅ Testar licensing system localmente
2. ✅ Integrar com NSP Plugin
3. ⏭️  Deploy license server em produção (DigitalOcean/AWS)
4. ⏭️  Encriptar modelos ML reais
5. ⏭️  Obfuscar código Python (PyArmor)
6. ⏭️  Criar website + checkout (Stripe)
7. ⏭️  Beta testing (10-20 users)
8. ⏭️  Launch! 🚀

---

**Support**: Ver `licensing/README.md` para documentação completa
