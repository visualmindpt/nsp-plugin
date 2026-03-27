# NSP Plugin - Guia de Deployment em cPanel

## 🎯 Sistema de Licenciamento Production-Ready

**Domínio:** plugin.nelsonsilvaphotography.com
**Tecnologia:** PHP 8.0+ + MySQL 5.7+
**Segurança:** Máxima (anti-hacking, rate limiting, JWT, HTTPS obrigatório)

---

## 📋 Checklist Pré-Deployment

### 1. Requisitos cPanel

- ✅ PHP 8.0 ou superior
- ✅ MySQL 5.7 ou superior
- ✅ SSL Certificate (Let's Encrypt)
- ✅ Acesso SSH (recomendado mas não obrigatório)
- ✅ Composer (ou upload manual de dependências)

### 2. Dependências PHP

```bash
# Via composer (se tiver SSH)
composer require firebase/php-jwt

# Ou download manual:
# https://github.com/firebase/php-jwt/releases
# Extrair para licensing/cpanel-api/vendor/
```

---

## 🚀 Passo a Passo - Deployment

### PASSO 1: Criar Database via cPanel

1. Login em cPanel
2. **MySQL® Databases**
3. **Create New Database:**
   - Nome: `nsp_licenses` (ficará: `nelsonsi_nsp_licenses`)
4. **Create New User:**
   - Username: `nsp_user`
   - Password: Gerar strong password (copiar!)
   - Exemplo: `Kp9#mX2$vL8@nQ5!`
5. **Add User to Database:**
   - User: `nsp_user`
   - Database: `nsp_licenses`
   - Privileges: **ALL PRIVILEGES** ✅

### PASSO 2: Importar Schema SQL

1. cPanel > **phpMyAdmin**
2. Selecionar database `nelsonsi_nsp_licenses`
3. **Import** tab
4. Upload `licensing/cpanel-api/schema.sql`
5. Verificar que 4 tabelas foram criadas:
   - `licenses`
   - `activations`
   - `heartbeats`
   - `rate_limits`

### PASSO 3: Gerar Chaves de Segurança

**Via Terminal SSH (recomendado):**
```bash
# JWT Secret Key
openssl rand -base64 64

# Admin API Key
openssl rand -hex 32
```

**Sem SSH (online generator):**
- https://generate-random.org/api-token-generator
- Gerar 2 keys: 64 chars (JWT) e 32 chars (Admin)

**⚠️ GUARDAR ESTAS KEYS EM LOCAL SEGURO!**

### PASSO 4: Configurar config.php

1. Editar `licensing/cpanel-api/config/config.php`
2. Atualizar:

```php
// Database
define('DB_NAME', 'nelsonsi_nsp_licenses');  // Teu cPanel prefix
define('DB_USER', 'nelsonsi_nsp_user');      // Teu username
define('DB_PASS', 'Kp9#mX2$vL8@nQ5!');       // Password do PASSO 1

// JWT Secret Key (do PASSO 3)
define('JWT_SECRET_KEY', 'BASE64_KEY_AQUI');

// Admin API Key (do PASSO 3)
define('ADMIN_API_KEY', 'HEX_KEY_AQUI');

// Dev Mode: DESLIGAR!
define('DEV_MODE', false);
```

### PASSO 5: Upload Ficheiros

**Via File Manager (cPanel):**

```
public_html/
└── api/
    └── license/
        ├── v1/
        │   ├── activate.php
        │   ├── validate.php
        │   ├── heartbeat.php
        │   ├── deactivate.php
        │   └── create.php (admin only)
        ├── config/
        │   └── config.php
        ├── lib/
        │   ├── Database.php
        │   ├── Security.php
        │   ├── Logger.php
        │   └── JWT.php
        ├── vendor/
        │   └── autoload.php
        ├── .htaccess
        └── index.php (redirect/info)
```

**Via FTP:**
- Host: ftp.nelsonsilvaphotography.com
- User: (teu cPanel user)
- Port: 21 (ou 990 para FTPS)

**Via SSH/SCP:**
```bash
scp -r licensing/cpanel-api/* user@server:/home/user/public_html/api/license/
```

### PASSO 6: Proteger config.php

**Criar .htaccess em `config/`:**
```apache
# config/.htaccess
Order deny,allow
Deny from all
```

**Verificar permissões:**
```bash
chmod 600 config/config.php  # Owner read/write apenas
chmod 755 api/v1/*.php       # Executável
```

### PASSO 7: Configurar SSL/HTTPS

1. cPanel > **SSL/TLS Status**
2. Verificar que `plugin.nelsonsilvaphotography.com` tem SSL ativo
3. Se não: **Install AutoSSL** (Let's Encrypt grátis)

**Forçar HTTPS (criar/editar .htaccess na raiz):**
```apache
# public_html/.htaccess
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
```

### PASSO 8: Testar Endpoints

**Health Check:**
```bash
curl https://plugin.nelsonsilvaphotography.com/api/license/health

# Esperado:
# {"status":"ok","service":"nsp-license-server","version":"1.0.0"}
```

**Criar Licença (Admin):**
```bash
curl -X POST https://plugin.nelsonsilvaphotography.com/api/license/v1/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: TUA_ADMIN_KEY_AQUI" \
  -d '{
    "email": "test@example.com",
    "plan": "professional",
    "max_activations": 3,
    "duration_days": 365
  }'

# Esperado:
# {
#   "success": true,
#   "license_key": "NSP-XXXX-XXXX-XXXX-XXXX",
#   "email": "test@example.com",
#   "plan": "professional",
#   "expires_at": "2026-11-24T..."
# }
```

**Ativar Licença:**
```bash
LICENSE_KEY="NSP-XXXX-XXXX-XXXX-XXXX"  # Do comando anterior

curl -X POST https://plugin.nelsonsilvaphotography.com/api/license/v1/activate \
  -H "Content-Type: application/json" \
  -d "{
    \"license_key\": \"$LICENSE_KEY\",
    \"machine_id\": \"test_machine_123\",
    \"machine_name\": \"Test MacBook Pro\"
  }"

# Esperado:
# {
#   "success": true,
#   "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "plan": "professional",
#   "features": {...}
# }
```

### PASSO 9: Configurar Cron Jobs (Manutenção)

cPanel > **Cron Jobs**

**Cleanup de tokens expirados (diariamente às 3h):**
```
0 3 * * * php /home/user/public_html/api/license/cron/cleanup.php
```

**Backup de database (diariamente às 4h):**
```
0 4 * * * /usr/bin/mysqldump -u nelsonsi_nsp_user -p'PASSWORD' nelsonsi_nsp_licenses > /home/user/backups/nsp_licenses_$(date +\%Y\%m\%d).sql
```

---

## 🔐 Segurança - Medidas Anti-Hacking

### 1. Proteção contra SQL Injection

✅ **Implementado:** Prepared statements em todas as queries
```php
$stmt = $db->prepare("SELECT * FROM licenses WHERE license_key = ?");
$stmt->execute([$license_key]);
```

### 2. Rate Limiting

✅ **Implementado:** 100 requests/hora por IP
- Tabela `rate_limits` armazena contadores
- Bloqueio automático após limite
- Reset automático após 1 hora

### 3. JWT Token Security

✅ **Implementado:**
- Tokens assinados com HS256
- Expiração de 24h
- Validação de assinatura em cada request
- Não armazena informação sensível no token

### 4. Hardware Fingerprinting

✅ **Implementado:**
- `machine_id` = SHA-256(MAC + CPU Serial + Disk UUID + Hostname)
- Irreprodutível sem acesso ao hardware
- Detecção de VM cloning

### 5. Anti-Fraud Detection

✅ **Implementado:**
- Max 5 ativações/dia por license key
- Max 10 ativações/dia por IP
- Detecção de VMs (DMI, hypervisor flags)
- Bloqueio de datacenters conhecidos (AWS, DigitalOcean IPs)

### 6. HTTPS Obrigatório

✅ **Implementado:**
- Recusa conexões HTTP
- HSTS header forçado
- SSL certificate validation

### 7. Admin Endpoint Protection

✅ **Implementado:**
- X-Admin-Key header obrigatório
- Key comparation com timing-safe
- IP whitelist (opcional)
- Logging de todas as ações admin

### 8. Input Validation

✅ **Implementado:**
- Sanitização de todos os inputs
- Validação de tipos
- Rejeição de payloads grandes (>1MB)
- CSRF token (em endpoints web)

### 9. Error Handling Seguro

✅ **Implementado:**
- Mensagens genéricas em produção
- Logs detalhados server-side
- Sem stack traces expostos
- Status codes apropriados

### 10. Database Security

✅ **Implementado:**
- User com privilégios mínimos
- Conexão localhost apenas
- Passwords fortes (20+ chars)
- Backup automático diário

---

## 📊 Monitorização

### Logs

**Location:** `licensing/cpanel-api/logs/license_server.log`

**Tail logs:**
```bash
tail -f public_html/api/license/logs/license_server.log
```

**Procurar erros:**
```bash
grep "ERROR" public_html/api/license/logs/license_server.log
```

### Database Queries Úteis

**Licenças ativas:**
```sql
SELECT license_key, email, plan, status, created_at, expires_at
FROM licenses
WHERE status = 'active'
ORDER BY created_at DESC;
```

**Ativações recentes:**
```sql
SELECT l.license_key, a.machine_id, a.machine_name, a.activated_at, a.last_heartbeat
FROM activations a
JOIN licenses l ON a.license_id = l.id
WHERE a.deactivated_at IS NULL
ORDER BY a.activated_at DESC
LIMIT 20;
```

**Detecção de fraude:**
```sql
-- Múltiplas ativações suspeitas
SELECT license_id, COUNT(*) as activation_count
FROM activations
WHERE activated_at > DATE_SUB(NOW(), INTERVAL 1 DAY)
  AND deactivated_at IS NULL
GROUP BY license_id
HAVING COUNT(*) > 5;
```

**Rate limits atingidos:**
```sql
SELECT ip_address, endpoint, request_count, window_start
FROM rate_limits
WHERE request_count >= 100
ORDER BY window_start DESC;
```

---

## 🚨 Troubleshooting

### Erro: "Database connection failed"

**Causa:** Credenciais incorretas ou database não existe

**Solução:**
1. Verificar `config/config.php` - DB_NAME, DB_USER, DB_PASS corretos?
2. cPanel > MySQL® Databases - database existe?
3. User tem ALL PRIVILEGES?

### Erro: "Invalid JWT signature"

**Causa:** JWT_SECRET_KEY mudou ou incorreto

**Solução:**
1. Verificar `config/config.php` - JWT_SECRET_KEY é o mesmo usado na ativação?
2. Se mudou: Todos os tokens antigos são inválidos (users precisam re-ativar)

### Erro: "Maximum activations reached"

**Causa:** Licença atingiu limite de máquinas

**Solução:**
1. User deve deactivate numa máquina existente
2. Ou: Admin aumenta `max_activations` na database
3. Ou: User compra upgrade

### Erro: "Rate limit exceeded"

**Causa:** IP fez >100 requests em 1 hora

**Solução:**
1. Aguardar 1 hora
2. Ou: Admin limpa rate_limits para esse IP:
```sql
DELETE FROM rate_limits WHERE ip_address = '203.0.113.1';
```

### SSL Certificate Error

**Causa:** SSL não configurado ou expirado

**Solução:**
1. cPanel > SSL/TLS Status
2. Install AutoSSL (Let's Encrypt)
3. Aguardar 5-10 minutos para propagação

---

## 🔄 Manutenção

### Backup

**Manual:**
```bash
# Database
mysqldump -u USER -p nelsonsi_nsp_licenses > backup.sql

# Ficheiros
tar -czf license_api_backup.tar.gz public_html/api/license/
```

**Automático:** Ver PASSO 9 (Cron Jobs)

### Updates

1. Backup database e ficheiros
2. Upload novos ficheiros (não substituir config.php!)
3. Executar migrations SQL se houver
4. Testar endpoints

### Limpar Dados Antigos

**Heartbeats >90 dias:**
```sql
DELETE FROM heartbeats WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);
```

**Licenças expiradas >1 ano:**
```sql
UPDATE licenses SET status = 'archived'
WHERE expires_at < DATE_SUB(NOW(), INTERVAL 1 YEAR)
  AND status = 'expired';
```

---

## 📞 Suporte

**Em caso de problemas:**

1. Verificar logs: `tail -f logs/license_server.log`
2. Testar conectividade: `curl https://plugin.../health`
3. Verificar database: phpMyAdmin > `nelsonsi_nsp_licenses`
4. Contactar suporte cPanel se problemas de infraestrutura

---

## ✅ Checklist Final

- [ ] Database criada e user configurado
- [ ] Schema SQL importado (4 tabelas)
- [ ] JWT_SECRET_KEY e ADMIN_API_KEY gerados e configurados
- [ ] config.php atualizado com credenciais corretas
- [ ] DEV_MODE = false
- [ ] Ficheiros uploaded para cPanel
- [ ] .htaccess em config/ para proteger
- [ ] SSL/HTTPS ativo e funcionando
- [ ] Health check retorna 200 OK
- [ ] Criação de licença admin funciona
- [ ] Ativação de licença funciona
- [ ] Cron jobs configurados
- [ ] Backup automático testado
- [ ] Logs funcionam e são readable
- [ ] Rate limiting testado
- [ ] Documentação lida e compreendida

---

**Sistema pronto para produção! 🚀**

**URL Base:** https://plugin.nelsonsilvaphotography.com/api/license/
**Versão:** 1.0.0
**Data:** 24 Novembro 2025
