# NSP Plugin - Plano de Comercialização e Proteção

Estratégia completa para transformar o NSP Plugin num produto comercial seguro e protegido contra pirataria.

---

## 1. Estratégia de Proteção Multi-Camada

### 1.1 Camadas de Proteção

```
┌─────────────────────────────────────────────────────────┐
│ CAMADA 1: Licenciamento Online                         │
│ - Validação de licença via servidor                    │
│ - Hardware fingerprinting                               │
│ - Limite de ativações (2-3 máquinas)                   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 2: Modelos ML Encriptados                       │
│ - Modelos assinados com RSA-2048                       │
│ - Encriptação AES-256 dos artefactos                   │
│ - Chave de desencriptação via licença                  │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 3: Code Obfuscation                             │
│ - Python bytecode compilation (.pyc)                   │
│ - Lua code minification                                │
│ - String obfuscation de endpoints críticos             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 4: Runtime Verification                         │
│ - Heartbeat checks a cada 24h                          │
│ - Validação de integridade dos modelos                 │
│ - Anti-debugging checks                                │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Sistema de Licenciamento

### 2.1 Tipos de Licença

| Tipo | Duração | Ativações | Preço Sugerido |
|------|---------|-----------|----------------|
| **Trial** | 14 dias | 1 máquina | Grátis |
| **Personal** | Perpétuo | 2 máquinas | €79 |
| **Professional** | Perpétuo | 3 máquinas | €149 |
| **Studio** | Perpétuo | 10 máquinas | €499 |
| **Subscription** | 1 ano (renovável) | 2 máquinas | €29/ano |

### 2.2 Modelo de Negócio Recomendado

**Hybrid Model**: Perpétuo + Subscription

- **Venda inicial**: Licença perpétua (€79-€149)
- **Atualizações major**: Upgrade pago (50% desconto)
- **Atualizações minor**: Grátis para licenças ativas
- **Support**: 1 ano incluído, renovação €29/ano

**Vantagens**:
- Receita inicial significativa
- Receita recorrente de suporte/updates
- Flexibilidade para clientes

---

## 3. Arquitetura Técnica

### 3.1 License Server (FastAPI)

```
┌─────────────────────────────────────────────────────────┐
│                    License Server                        │
│                 (license.vilearn.ai)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  /api/v1/licenses/activate                              │
│  /api/v1/licenses/validate                              │
│  /api/v1/licenses/deactivate                            │
│  /api/v1/licenses/heartbeat                             │
│  /api/v1/models/download (encrypted)                    │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ Database: PostgreSQL                                    │
│ - licenses (id, key, email, plan, activations_used)    │
│ - activations (id, license_id, machine_id, last_seen)  │
│ - heartbeats (id, activation_id, timestamp)            │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Hardware Fingerprinting

```python
def generate_machine_id():
    """
    Gera ID único da máquina baseado em:
    - MAC address (primary network interface)
    - CPU serial (macOS: IOPlatformSerialNumber)
    - Disk UUID (boot volume)
    - Hostname

    Resultado: SHA-256 hash → ID irreprodutível
    """
    components = [
        get_mac_address(),
        get_cpu_serial(),
        get_disk_uuid(),
        get_hostname()
    ]

    fingerprint = "|".join(sorted(components))
    machine_id = hashlib.sha256(fingerprint.encode()).hexdigest()

    return machine_id[:32]  # Primeiros 128 bits
```

### 3.3 Fluxo de Ativação

```
1. User compra licença → recebe LICENSE_KEY por email

2. Instalação inicial:
   Plugin/Server → gera machine_id
                → POST /activate {key, machine_id}
                → Server valida:
                    ✓ Licença existe?
                    ✓ Ainda tem slots disponíveis?
                    ✓ Não expirou?
                → Retorna: encrypted_token (JWT)

3. Runtime:
   Plugin → valida token localmente (validade 24h)
          → se expirado: POST /heartbeat {token}
          → Server atualiza last_seen
          → Retorna: novo token (renovação)

4. Modelos ML:
   Server → desencripta modelos com chave derivada da licença
          → serve via /models/download (autenticado)
```

### 3.4 License File Format (.velkey)

```json
{
  "version": "1.0",
  "license_key": "VELA-XXXX-XXXX-XXXX-XXXX",
  "email": "customer@example.com",
  "plan": "professional",
  "issued_at": "2025-01-09T12:00:00Z",
  "expires_at": null,
  "max_activations": 3,
  "features": {
    "lightgbm": true,
    "neural_network": true,
    "smart_culling": true,
    "auto_profiling": true
  },
  "signature": "RSA-SHA256 signature (base64)"
}
```

**Assinatura RSA**:
```python
# Server-side (private key)
private_key = load_private_key("license_signing_key.pem")
payload = json.dumps(license_data, sort_keys=True)
signature = private_key.sign(payload.encode(), padding.PSS(...))

# Client-side (public key embedded)
public_key = load_public_key("embedded_public_key.pem")
public_key.verify(signature, payload.encode(), ...)
```

---

## 4. Proteção dos Modelos ML

### 4.1 Encriptação AES-256

```python
# Build time (encrypt models)
from cryptography.fernet import Fernet

# Chave derivada da master key + license_key
def derive_model_key(master_key: bytes, license_key: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"nsp_model_salt_v1",
        iterations=100000,
    )
    combined = master_key + license_key.encode()
    return base64.urlsafe_b64encode(kdf.derive(combined))

# Encriptar modelo
model_bytes = open("slider_exposure.txt", "rb").read()
fernet = Fernet(model_key)
encrypted = fernet.encrypt(model_bytes)

# Guardar modelo encriptado
open("slider_exposure.enc", "wb").write(encrypted)
```

```python
# Runtime (decrypt models)
def load_encrypted_model(model_path: Path, license_key: str):
    encrypted_data = model_path.read_bytes()

    # Derivar chave da licença
    model_key = derive_model_key(MASTER_KEY, license_key)
    fernet = Fernet(model_key)

    try:
        decrypted = fernet.decrypt(encrypted_data)
    except InvalidToken:
        raise LicenseError("Licença inválida ou modelo corrompido")

    # Carregar modelo desencriptado em memória
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(decrypted)
    temp_file.close()

    model = lgb.Booster(model_file=temp_file.name)
    os.unlink(temp_file.name)  # Apagar temp file

    return model
```

### 4.2 Model Integrity Verification

```python
# Hash SHA-256 de cada modelo (signed manifest)
{
  "models": {
    "slider_exposure.enc": {
      "sha256": "abc123...",
      "size": 123456,
      "version": "2.1.0"
    }
  },
  "signature": "RSA signature of entire manifest"
}

# Runtime: verificar integridade antes de desencriptar
def verify_model_integrity(model_path: Path):
    manifest = load_signed_manifest()

    expected_hash = manifest["models"][model_path.name]["sha256"]
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()

    if expected_hash != actual_hash:
        raise IntegrityError("Modelo foi modificado ou corrompido")
```

---

## 5. Proteção do Código

### 5.1 Python Code Protection

**Opção 1: PyInstaller + Obfuscation**
```bash
# Compile Python to standalone binary
pyinstaller --onefile \
            --hidden-import=lightgbm \
            --hidden-import=torch \
            --add-data "models:models" \
            --key="encryption_key_here" \
            services/server.py

# Resultado: Single binary (server.exe / server.app)
# - Bytecode encriptado
# - Sem .py files expostos
# - Dificulta reverse engineering
```

**Opção 2: Cython Compilation**
```bash
# Compilar Python crítico para C extension
cython services/licensing.py --embed
gcc -Os -I /usr/include/python3.9 \
    -o licensing.so \
    services/licensing.c \
    -lpython3.9

# Resultado: licensing.so (binary)
# - Impossível reverter para Python
# - Performance boost
```

**Opção 3: PyArmor (Recommended)**
```bash
# Professional obfuscation tool
pip install pyarmor

pyarmor pack \
    --with-license \
    --license-key "VELA-..." \
    --platform darwin.x86_64 \
    services/server.py

# Resultado: Obfuscated + license-locked binary
```

### 5.2 Lua Code Protection (Limitado)

**Lightroom SDK limitation**: Lua code tem de ser legível pelo SDK.

**Estratégias**:
1. **Minification**: Remover comments, whitespace, renomear vars
2. **String obfuscation**: Ofuscar endpoints críticos
3. **Logic no backend**: Mover lógica crítica para Python server

```lua
-- Original
local SERVER_URL = "http://127.0.0.1:5678"
local LICENSE_KEY = Common.load_config().license_key

-- Obfuscated
local _0x1a2b = {[1]="h",[2]="t",[3]="t",[4]="p",...}
local _0x3c4d = table.concat(_0x1a2b)
local _0x5e6f = require('Common').load_config()['\108\105\099\101\110\115\101']
```

**Tool**: LuaObfuscator
```bash
npm install -g luaobfuscator
luaobfuscator Main.lua -o Main.obfuscated.lua
```

---

## 6. Distribuição Segura

### 6.1 Canais de Distribuição

**Opção A: Direct Download (Controlo Total)**
```
Website: shop.vilearn.ai
  ↓ Purchase (Stripe/Paddle)
  ↓ Email com license key
  ↓ Download link (signed .dmg/.pkg)
  ↓ Instalação
  ↓ Ativação com license key
```

**Vantagens**:
- Controlo total sobre distribuição
- Melhor margem (sem comissões)
- Analytics completo

**Desvantagens**:
- Marketing próprio necessário
- Suporte técnico total

---

**Opção B: Adobe Exchange Marketplace**
```
Adobe Exchange
  ↓ Plugin listing (free/paid)
  ↓ Adobe handles payments (30% comissão)
  ↓ User downloads via Creative Cloud
  ↓ Ativação via Adobe ID
```

**Vantagens**:
- Exposição a milhões de users Lightroom
- Adobe badge de confiança
- Payment processing incluído

**Desvantagens**:
- 30% comissão
- Guidelines restritivas
- Menos controlo

---

**Opção C: Hybrid (Recomendado)**
- Adobe Exchange: Free trial (14 dias)
- Website próprio: Full version paga
- Maximiza exposição + margens

### 6.2 Package Signing (macOS)

```bash
# Developer ID Certificate (Apple)
# Necessário para distribuição fora da App Store

# 1. Sign application bundle
codesign --deep --force \
         --sign "Developer ID Application: ViLearnStyle (TEAMID)" \
         --options runtime \
         --timestamp \
         "NSP Plugin.app"

# 2. Create installer package
productbuild --component "NSP Plugin.app" /Applications \
             --sign "Developer ID Installer: ViLearnStyle (TEAMID)" \
             NSPPlugin_Installer.pkg

# 3. Notarize with Apple
xcrun notarytool submit NSPPlugin_Installer.pkg \
                        --apple-id "dev@vilearn.ai" \
                        --password "@keychain:AC_PASSWORD" \
                        --team-id TEAMID

# 4. Staple notarization ticket
xcrun stapler staple NSPPlugin_Installer.pkg
```

**Resultado**: Instalador confiável, sem avisos do macOS Gatekeeper.

### 6.3 Update Mechanism

```python
# Auto-update via Sparkle framework (macOS)
# appcast.xml (signed)
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
    <channel>
        <title>NSP Plugin Updates</title>
        <item>
            <title>Version 2.2.0</title>
            <sparkle:version>2.2.0</sparkle:version>
            <sparkle:minimumSystemVersion>10.15</sparkle:minimumSystemVersion>
            <pubDate>Fri, 10 Jan 2025 10:00:00 +0000</pubDate>
            <enclosure url="https://updates.vilearn.ai/NSPPlugin-2.2.0.dmg"
                       sparkle:edSignature="..."
                       length="45678901"
                       type="application/octet-stream" />
            <sparkle:releaseNotesLink>https://vilearn.ai/changelog</sparkle:releaseNotesLink>
        </item>
    </channel>
</rss>
```

---

## 7. Anti-Pirataria Ativa

### 7.1 Heartbeat System

```python
# Client-side (executa a cada 24h)
async def heartbeat_check():
    """
    Valida licença periodicamente.
    Se offline > 7 dias → degraded mode (apenas trial features).
    """
    try:
        response = await http.post(
            f"{LICENSE_SERVER}/heartbeat",
            json={"token": current_token},
            timeout=10
        )

        if response.status == 200:
            new_token = response.json()["token"]
            save_token(new_token)
            last_heartbeat = datetime.now()
        else:
            # Licença revogada ou expirada
            enter_grace_period()

    except NetworkError:
        # Offline - permitir grace period de 7 dias
        days_offline = (datetime.now() - last_heartbeat).days
        if days_offline > 7:
            enter_degraded_mode()
```

### 7.2 License Revocation

```python
# Server-side: revogar licença (chargeback, refund, abuse)
def revoke_license(license_key: str, reason: str):
    db.execute(
        "UPDATE licenses SET status = 'revoked', revoked_at = NOW(), revoke_reason = ? WHERE key = ?",
        (reason, license_key)
    )

    # Notificar todas as ativações
    activations = db.query("SELECT * FROM activations WHERE license_id = ?", license_id)
    for activation in activations:
        send_push_notification(activation.device_token, "License revoked")
```

### 7.3 Abuse Detection

```python
# Detectar ativações suspeitas
def detect_activation_abuse(license_key: str):
    activations = get_activations(license_key)

    # Flag 1: Muitas ativações em curto período
    recent_activations = [a for a in activations if a.created_at > now() - timedelta(hours=24)]
    if len(recent_activations) > 5:
        flag_for_review(license_key, "Excessive activations")

    # Flag 2: Padrão de IPs suspeito (VPN hopping, datacenter IPs)
    ips = [a.ip_address for a in activations]
    if detect_vpn_pattern(ips) or detect_datacenter_ips(ips):
        flag_for_review(license_key, "Suspicious IP pattern")

    # Flag 3: Machine IDs muito similares (VM cloning)
    machine_ids = [a.machine_id for a in activations]
    if detect_cloned_fingerprints(machine_ids):
        flag_for_review(license_key, "Possible VM cloning")
```

---

## 8. Infraestrutura de Produção

### 8.1 License Server Stack

```yaml
# Kubernetes deployment (license-server)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: license-server
spec:
  replicas: 3  # High availability
  template:
    spec:
      containers:
      - name: license-api
        image: vilearn/license-server:2.1
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        - name: RSA_PRIVATE_KEY
          valueFrom:
            secretKeyRef:
              name: signing-keys
              key: private
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: license-server
spec:
  type: LoadBalancer
  ports:
  - port: 443
    targetPort: 8000
```

### 8.2 Database Schema (PostgreSQL)

```sql
-- Licenses table
CREATE TABLE licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key VARCHAR(32) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    plan VARCHAR(50) NOT NULL, -- trial, personal, professional, studio
    status VARCHAR(20) DEFAULT 'active', -- active, expired, revoked
    max_activations INTEGER NOT NULL DEFAULT 2,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoke_reason TEXT,
    metadata JSONB, -- {purchase_id, stripe_customer_id, ...}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Activations table
CREATE TABLE activations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id UUID NOT NULL REFERENCES licenses(id),
    machine_id VARCHAR(64) NOT NULL,
    machine_name VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ,
    deactivated_at TIMESTAMPTZ,
    UNIQUE(license_id, machine_id)
);

-- Heartbeats table (analytics + abuse detection)
CREATE TABLE heartbeats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activation_id UUID NOT NULL REFERENCES activations(id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET,
    plugin_version VARCHAR(20)
);

-- Indexes
CREATE INDEX idx_licenses_email ON licenses(email);
CREATE INDEX idx_licenses_key ON licenses(license_key);
CREATE INDEX idx_activations_license ON activations(license_id);
CREATE INDEX idx_heartbeats_activation ON heartbeats(activation_id);
CREATE INDEX idx_heartbeats_timestamp ON heartbeats(timestamp DESC);
```

### 8.3 Custos Estimados (AWS/DigitalOcean)

| Componente | Especificação | Custo/mês |
|------------|---------------|-----------|
| License Server | 2x t3.small (2GB RAM) | $30 |
| PostgreSQL RDS | db.t3.micro | $25 |
| CloudFront CDN | Model downloads (1TB/mês) | $85 |
| S3 Storage | Encrypted models (10GB) | $1 |
| Route53 DNS | Hosted zone | $1 |
| SSL Certificate | AWS ACM | Grátis |
| **Total** | | **~$142/mês** |

**Escalabilidade**: Até 10,000 users ativos com esta stack.

---

## 9. Compliance Legal

### 9.1 Termos de Serviço (ToS)

Elementos críticos:
- **Propriedade intelectual**: Modelos ML são propriedade da ViLearnStyle
- **Uso permitido**: Personal/commercial use conforme licença
- **Uso proibido**: Reverse engineering, redistribuição, rental
- **Limitação de responsabilidade**: Software "as-is", sem garantias
- **Término**: Violação resulta em revogação imediata

### 9.2 GDPR Compliance (EU)

- **Consentimento**: Opt-in para analytics/marketing
- **Data minimization**: Apenas email + machine_id necessários
- **Right to erasure**: Endpoint `/gdpr/delete-my-data`
- **Data portability**: Endpoint `/gdpr/export-my-data`
- **Privacy policy**: Transparente sobre data collection

### 9.3 Software License Agreement (EULA)

```
ViLearnStyle NSP Plugin - End User License Agreement

1. GRANT OF LICENSE
   ViLearnStyle grants you a non-exclusive, non-transferable license to use
   the NSP Plugin software ("Software") on up to [N] computers, subject to
   the terms of this Agreement.

2. RESTRICTIONS
   You may NOT:
   - Reverse engineer, decompile, or disassemble the Software
   - Rent, lease, or lend the Software
   - Remove or alter any copyright notices
   - Use the Software for any illegal purpose

3. OWNERSHIP
   The Software, including all machine learning models, algorithms, and
   documentation, is the intellectual property of ViLearnStyle.

4. TERMINATION
   This license is effective until terminated. Your rights will terminate
   automatically if you fail to comply with any term of this Agreement.

5. WARRANTY DISCLAIMER
   THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.

6. LIMITATION OF LIABILITY
   IN NO EVENT SHALL VILEARNSTYLE BE LIABLE FOR ANY DAMAGES ARISING FROM
   THE USE OR INABILITY TO USE THE SOFTWARE.
```

---

## 10. Roadmap de Lançamento

### Fase 1: MVP Licensing (Mês 1-2)
- [ ] Implementar sistema de licenciamento básico
- [ ] Hardware fingerprinting
- [ ] License server (FastAPI + PostgreSQL)
- [ ] Modelo encryption (AES-256)
- [ ] Testing com 10 beta users

### Fase 2: Proteção Avançada (Mês 3)
- [ ] Code obfuscation (PyArmor)
- [ ] Model integrity verification
- [ ] Heartbeat system
- [ ] Abuse detection algorithms
- [ ] Legal docs (ToS, EULA, Privacy Policy)

### Fase 3: Distribuição (Mês 4)
- [ ] Website + checkout (Stripe/Paddle)
- [ ] Installer signing (Apple Developer ID)
- [ ] Auto-update mechanism
- [ ] Adobe Exchange submission
- [ ] Marketing materials

### Fase 4: Lançamento (Mês 5)
- [ ] Public beta (100 users)
- [ ] Monitor abuse patterns
- [ ] Customer support system
- [ ] Analytics dashboard
- [ ] Official launch

---

## 11. Custos Totais de Lançamento

| Categoria | Item | Custo |
|-----------|------|-------|
| **Infraestrutura** | License server (6 meses) | $852 |
| **Desenvolvimento** | Licensing system (80h @ $50/h) | $4,000 |
| **Legal** | ToS/EULA/Privacy Policy (lawyer) | $2,000 |
| **Apple** | Developer ID Certificate (1 ano) | $99 |
| **Marketing** | Website + landing page | $1,500 |
| **Pagamentos** | Stripe/Paddle setup | $0 |
| **Total** | | **~$8,451** |

**Break-even**: 113 licenças @ $75/cada

---

## 12. Projeção de Receitas (Ano 1)

**Pressupostos conservadores**:
- 500 downloads/mês (Adobe Exchange exposure)
- 5% conversion rate (trial → paid)
- $79 preço médio
- 15% churn anual

| Mês | Downloads | Sales | MRR | ARR |
|-----|-----------|-------|-----|-----|
| 1-2 | 100 | 5 | $395 | - |
| 3-4 | 300 | 15 | $1,580 | - |
| 5-6 | 500 | 25 | $3,950 | - |
| 7-12 | 500 | 25/mês | $11,850 | $47,400 |

**Ano 1 Total**: ~$47,400 receita bruta
**Após custos**: ~$39,000 lucro líquido

---

## Conclusão

O NSP Plugin pode ser transformado num produto comercial viável com:

✅ **Proteção Multi-Camada**: Licenciamento + Encryption + Obfuscation
✅ **Infraestrutura Escalável**: License server robusto e monitorizado
✅ **Anti-Pirataria Ativa**: Heartbeats, revocation, abuse detection
✅ **Distribuição Profissional**: Signed installers, auto-updates
✅ **Compliance Legal**: ToS, EULA, GDPR-ready

**Próximo passo**: Implementar sistema de licenciamento (Fase 1).
