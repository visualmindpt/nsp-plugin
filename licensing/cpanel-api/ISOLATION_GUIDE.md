# Guia de Isolamento - Sistema de Licenciamento vs Backend Existente

## 🎯 Objetivo

Garantir que o **novo sistema de licenciamento** não interfere com o **backend existente de extração** que já está no cPanel.

---

## 📂 Separação Física de Diretórios

### Backend Existente (Não Tocar!)
```
public_html/
└── backend_extracao/          # ❌ NÃO MODIFICAR
    ├── config/
    ├── api/
    └── ... (estrutura existente)
```

### Novo Sistema de Licenciamento (Isolado)
```
public_html/
└── api/
    └── license/               # ✅ NOVO - Completamente separado
        ├── v1/
        │   ├── activate.php
        │   ├── validate.php
        │   └── ...
        ├── config/
        │   └── config.php     # Config isolado
        ├── lib/
        └── logs/
```

**URLs Resultantes:**
- Backend Extração: `https://plugin.nelsonsilvaphotography.com/backend_extracao/...`
- Sistema Licenças: `https://plugin.nelsonsilvaphotography.com/api/license/...`

✅ **Zero conflito de paths**

---

## 🗄️ Separação de Databases

### Database Existente (Não Tocar!)
```
Database: nelsonsi_extracao (ou similar)
Tables: (as que já existem no backend_extracao)
User: nelsonsi_extracao_user
```

### Nova Database de Licenças (Isolada)
```
Database: nelsonsi_nsp_licenses  # ✅ Nome único
Tables: licenses, activations, heartbeats, rate_limits, audit_log
User: nelsonsi_nsp_user          # ✅ User separado
```

**Criação:**
```sql
-- Via cPanel > MySQL® Databases

CREATE DATABASE nelsonsi_nsp_licenses;  -- Nome DIFERENTE!

CREATE USER 'nelsonsi_nsp_user'@'localhost'
IDENTIFIED BY 'STRONG_PASSWORD_DIFERENTE';

GRANT ALL PRIVILEGES ON nelsonsi_nsp_licenses.*
TO 'nelsonsi_nsp_user'@'localhost';

FLUSH PRIVILEGES;
```

✅ **Zero conflito de databases**

---

## 🔧 Configuração Isolada

### Backend Existente
```php
// backend_extracao/config/config.php
// Configuração existente - NÃO MODIFICAR
```

### Sistema Licenças
```php
// api/license/config/config.php
<?php
// Prevent direct access
defined('NSP_LICENSE_SERVER') or die('Access denied');

// Database - DIFERENTES do backend existente
define('DB_HOST', 'localhost');
define('DB_NAME', 'nelsonsi_nsp_licenses');  // ✅ Nome único
define('DB_USER', 'nelsonsi_nsp_user');      // ✅ User diferente
define('DB_PASS', 'PASSWORD_DIFERENTE');     // ✅ Password diferente

// JWT Secret - ÚNICO para licenças
define('JWT_SECRET_KEY', 'UNIQUE_JWT_KEY_FOR_LICENSES_ONLY');

// Admin Key - ÚNICO para licenças
define('ADMIN_API_KEY', 'UNIQUE_ADMIN_KEY_FOR_LICENSES_ONLY');

// Log file - SEPARADO
define('LOG_FILE', __DIR__ . '/../logs/license_server.log');

// Prefixo único para evitar conflitos de sessão/cache
define('APP_PREFIX', 'NSP_LICENSE_');
?>
```

✅ **Zero conflito de configuração**

---

## 🌐 Separação de Endpoints

### Backend Existente
```
POST /backend_extracao/api/extract
POST /backend_extracao/api/process
GET  /backend_extracao/api/status
... (endpoints existentes)
```

### Sistema Licenças (Novos endpoints)
```
GET  /api/license/health
POST /api/license/v1/activate
POST /api/license/v1/validate
POST /api/license/v1/heartbeat
POST /api/license/v1/deactivate
POST /api/license/v1/create (admin)
```

**Namespace diferente:** `/api/license/*` vs `/backend_extracao/*`

✅ **Zero conflito de rotas**

---

## 🔒 Isolamento de Segurança

### API Keys Separadas

**Backend Existente:**
```env
BACKEND_API_KEY=existing_key_do_not_touch
```

**Sistema Licenças:**
```env
LICENSE_ADMIN_KEY=new_unique_key_for_licenses_only
LICENSE_JWT_SECRET=new_unique_jwt_secret_for_licenses
```

### Rate Limiting Separado

**Backend Existente:**
- Tem seu próprio sistema (se houver)

**Sistema Licenças:**
- Tabela `rate_limits` própria
- IP tracking independente
- Não afeta rate limiting do backend existente

### Logs Separados

**Backend Existente:**
```
backend_extracao/logs/extracacao.log
```

**Sistema Licenças:**
```
api/license/logs/license_server.log
```

✅ **Zero conflito de segurança**

---

## 📦 Dependências PHP

### Verificar Versão PHP (Ambos Usam)

```bash
# Via cPanel > Select PHP Version
# Escolher PHP 8.0 ou superior
# Aplicar para TODO o domínio
```

Ambos os sistemas podem usar a mesma versão PHP sem conflitos.

### Composer Dependencies

**Backend Existente:**
```
backend_extracao/vendor/
(dependências existentes)
```

**Sistema Licenças:**
```
api/license/vendor/
└── firebase/
    └── php-jwt/  # Única dependência necessária
```

**Instalação isolada:**
```bash
cd public_html/api/license
composer require firebase/php-jwt

# Ou download manual:
# https://github.com/firebase/php-jwt/releases
# Extrair para api/license/vendor/
```

✅ **Zero conflito de dependências**

---

## 🛡️ .htaccess Isolado

### Backend Existente
```apache
# backend_extracao/.htaccess
# Configuração existente - NÃO MODIFICAR
```

### Sistema Licenças
```apache
# api/license/.htaccess
<IfModule mod_rewrite.c>
    RewriteEngine On

    # Force HTTPS
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

    # Protect config directory
    RewriteRule ^config/ - [F,L]

    # Protect logs directory
    RewriteRule ^logs/ - [F,L]

    # API routing
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^v1/(.*)$ v1/$1.php [L,QSA]
</IfModule>

# Disable directory listing
Options -Indexes

# Protect sensitive files
<FilesMatch "^\.">
    Order allow,deny
    Deny from all
</FilesMatch>
```

**Proteção adicional para config:**
```apache
# api/license/config/.htaccess
Order deny,allow
Deny from all
```

✅ **Cada sistema tem seu .htaccess isolado**

---

## 🔄 Integração Sem Conflitos

### O Sistema de Licenças Não Precisa Comunicar com Backend Extração

**Separação completa:**
- Backend Extração: Processa dados, extrai informações
- Sistema Licenças: Valida licenças, controla features

**Comunicação (se necessária no futuro):**
```php
// backend_extracao pode chamar sistema de licenças via HTTP
$license_api = 'https://plugin.nelsonsilvaphotography.com/api/license';
$response = file_get_contents($license_api . '/v1/validate', ...);
// Mas NÃO é necessário para funcionamento básico
```

### NSP Plugin Lightroom Pode Usar Ambos

**Plugin Lightroom pode ter 2 URLs diferentes:**
```lua
-- NSP-Plugin.lrplugin/Config.lua

-- Backend de Extração (existente)
EXTRACTION_API = "https://plugin.nelsonsilvaphotography.com/backend_extracao"

-- Sistema de Licenças (novo)
LICENSE_API = "https://plugin.nelsonsilvaphotography.com/api/license"

-- Usar conforme necessário, sem conflitos
```

✅ **Ambos podem coexistir perfeitamente**

---

## 📋 Checklist de Não-Interferência

Antes de fazer deployment do sistema de licenças:

### Diretórios
- [ ] Novo sistema em `public_html/api/license/` (não em `backend_extracao/`)
- [ ] Nenhum ficheiro modificado em `backend_extracao/`

### Database
- [ ] Nova database: `nelsonsi_nsp_licenses`
- [ ] Novo user: `nelsonsi_nsp_user`
- [ ] Database existente (`nelsonsi_extracao`?) intocada

### Configuração
- [ ] `api/license/config/config.php` com credenciais ÚNICAS
- [ ] `backend_extracao/config/config.php` inalterado
- [ ] JWT_SECRET_KEY diferente
- [ ] ADMIN_API_KEY diferente

### Endpoints
- [ ] Sistema licenças: `/api/license/*`
- [ ] Backend existente: `/backend_extracao/*`
- [ ] Zero sobreposição de rotas

### Logs
- [ ] Logs licenças: `api/license/logs/`
- [ ] Logs backend: `backend_extracao/logs/`
- [ ] Ficheiros separados

### Segurança
- [ ] `.htaccess` separados
- [ ] API keys diferentes
- [ ] Rate limiting independente

### Testing
- [ ] Backend existente continua funcional
- [ ] Todos os endpoints existentes respondem normalmente
- [ ] Sistema licenças funciona isoladamente

---

## 🧪 Teste de Não-Interferência

### 1. Antes de Instalar Sistema Licenças

```bash
# Testar backend existente
curl https://plugin.nelsonsilvaphotography.com/backend_extracao/api/health
# Deve responder normalmente

# Anotar resposta
```

### 2. Depois de Instalar Sistema Licenças

```bash
# Testar backend existente (deve ser idêntico)
curl https://plugin.nelsonsilvaphotography.com/backend_extracao/api/health
# Deve responder EXATAMENTE igual

# Testar novo sistema licenças
curl https://plugin.nelsonsilvaphotography.com/api/license/health
# Deve responder 200 OK

# Ambos funcionam em paralelo ✅
```

### 3. Teste de Performance

```bash
# Monitorar que sistema licenças não afeta performance do backend
# Via cPanel > Metrics > Resource Usage

# Antes e depois devem ser similares
```

---

## 🚨 Sinais de Interferência (e Como Resolver)

### ❌ PROBLEMA: Backend existente deixou de funcionar

**Diagnóstico:**
```bash
# Verificar se ficheiros foram modificados
diff -r backend_extracao/ backup_backend_extracao/

# Verificar logs
tail -f backend_extracao/logs/*.log
```

**Solução:**
- Restaurar backup de `backend_extracao/`
- Verificar que `api/license/` não toca em nada fora do seu diretório

### ❌ PROBLEMA: Conflito de database

**Diagnóstico:**
```sql
-- Via phpMyAdmin
SHOW TABLES;
-- Verificar que não há sobreposição de nomes
```

**Solução:**
- Usar databases completamente separadas
- Diferentes users com privilégios isolados

### ❌ PROBLEMA: Conflito de sessões PHP

**Diagnóstico:**
```php
// Verificar se ambos usam session_start()
// com mesmo session_name()
```

**Solução:**
```php
// api/license/lib/Security.php
session_name('NSP_LICENSE_SESSION');  // Nome único
session_start();
```

---

## ✅ Deployment Seguro

### Ordem Recomendada

1. ✅ **Backup completo do cPanel**
   - Backup do `backend_extracao/` atual
   - Backup de todas as databases
   - Via cPanel > Backup Wizard

2. ✅ **Criar nova database isolada**
   - Nome: `nelsonsi_nsp_licenses`
   - User novo: `nelsonsi_nsp_user`
   - Sem tocar na database existente

3. ✅ **Upload sistema licenças**
   - Para: `public_html/api/license/`
   - NÃO modificar nada em `backend_extracao/`

4. ✅ **Importar schema.sql**
   - Apenas na nova database
   - Via phpMyAdmin

5. ✅ **Configurar config.php**
   - Apenas `api/license/config/config.php`
   - Credenciais únicas

6. ✅ **Testar ambos sistemas**
   - Backend existente primeiro
   - Sistema licenças depois
   - Ambos devem funcionar em paralelo

7. ✅ **Monitorar por 24h**
   - Logs de ambos
   - Performance do servidor
   - Zero interferência esperada

---

## 📞 Rollback Plan

Se algo correr mal:

### Rollback Rápido
```bash
# Via cPanel > File Manager
# Apagar pasta: public_html/api/license/

# Via phpMyAdmin
DROP DATABASE nelsonsi_nsp_licenses;
DROP USER 'nelsonsi_nsp_user'@'localhost';

# Backend existente permanece intocado ✅
```

**Tempo:** 2 minutos
**Risco:** Zero (sistema licenças é completamente isolado)

---

## 🎯 Conclusão

**Sistema de Licenciamento é 100% isolado e independente:**

✅ Diretórios separados
✅ Databases separadas
✅ Configurações separadas
✅ Endpoints diferentes
✅ Logs separados
✅ API keys únicas
✅ Zero modificações no backend existente

**Pode ser instalado, testado e removido sem NUNCA afetar o backend de extração existente.**

---

**Data:** 24 Novembro 2025
**Versão:** 1.0.0
