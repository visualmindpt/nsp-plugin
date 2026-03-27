# Payment Integration Examples

Este diretório contém ficheiros de exemplo para integrar o NSP Plugin License Server com Stripe e criar uma página de checkout profissional.

## 📁 Ficheiros Incluídos

### `pricing.html`
Página de pricing moderna e responsiva com 3 planos (Personal, Professional, Studio).

**Tecnologias:**
- HTML5 + Tailwind CSS (via CDN)
- Design responsivo (mobile-first)
- Cards de pricing com call-to-action

**Como usar:**
```bash
# 1. Copiar para teu servidor cPanel
cp pricing.html ~/public_html/pricing.html

# 2. Aceder via browser
https://vilearn.ai/pricing.html
```

### `checkout.php`
Script PHP que cria uma Stripe Checkout Session e redireciona o utilizador.

**Requisitos:**
- PHP 7.4+ (cPanel normalmente tem)
- Stripe PHP SDK
- Variável de ambiente `STRIPE_SECRET_KEY`

**Como usar:**
```bash
# 1. Instalar Stripe SDK no cPanel
cd ~/public_html
composer require stripe/stripe-php

# 2. Copiar ficheiro
cp checkout.php ~/public_html/checkout.php

# 3. Configurar variável de ambiente
# No cPanel: File Manager → Edit .htaccess → Adicionar:
# SetEnv STRIPE_SECRET_KEY sk_test_xxxxxxxxxxxxxxx

# 4. Testar
https://vilearn.ai/checkout.php?plan=professional
```

## 🔄 Fluxo Completo de Pagamento

```
1. User visita pricing.html
   ↓
2. Clica "Get Professional"
   ↓
3. Redireciona para checkout.php?plan=professional
   ↓
4. PHP cria Stripe Checkout Session
   ↓
5. User redireccionado para Stripe (pagamento seguro)
   ↓
6. User preenche dados do cartão
   ↓
7. Stripe processa pagamento
   ↓
8. Stripe webhook → License Server (FastAPI)
   ↓
9. License Server cria licença na database
   ↓
10. SendGrid envia email com license key
    ↓
11. User recebe: VELA-XXXX-XXXX-XXXX-XXXX
```

## ⚙️ Setup Passo a Passo

### 1. Configurar Stripe

```bash
# Criar conta em stripe.com
# Dashboard → API Keys

# Modo Test (desenvolvimento):
Publishable Key: pk_test_xxxxx
Secret Key: sk_test_xxxxx

# Modo Live (produção):
Publishable Key: pk_live_xxxxx
Secret Key: sk_live_xxxxx
```

### 2. Configurar Webhook no Stripe

```bash
# Stripe Dashboard → Developers → Webhooks → Add endpoint

URL: https://license.vilearn.ai/webhook/stripe
Events to send:
  ✓ checkout.session.completed

# Copiar Webhook Secret
whsec_xxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. Configurar License Server

```bash
# Criar ficheiro .env no servidor
cd ~/nsp-license-server
cp .env.example .env

# Editar .env:
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
SENDGRID_API_KEY=SG.xxxxx
DATABASE_URL=postgresql://user:pass@localhost/nsp_licenses
```

### 4. Deploy License Server

**Opção A: Railway (Recomendado)**
```bash
# 1. Push code to GitHub
git add .
git commit -m "Add Stripe integration"
git push

# 2. Railway Dashboard
# - New Project → Deploy from GitHub
# - Select repo: NSP Plugin_dev_full_package
# - Root directory: /licensing
# - Add PostgreSQL database
# - Set environment variables (Stripe, SendGrid)
# - Deploy!

# 3. Custom domain
# - Settings → Domains → Add domain
# - license.vilearn.ai → CNAME to railway.app
```

**Opção B: Render (Free Tier)**
```bash
# Similar ao Railway
# Limitação: Server "dorme" após 15min inativo (cold start)
```

### 5. Upload para cPanel

```bash
# Via File Manager ou FTP:
public_html/
  ├── index.html          # Landing page
  ├── pricing.html        # Pricing page (exemplo)
  ├── checkout.php        # Stripe checkout (exemplo)
  ├── success.html        # Thank you page
  └── .htaccess           # Stripe API key config

# Configurar .htaccess:
SetEnv STRIPE_SECRET_KEY sk_live_xxxxx
```

## 🧪 Testar Integração

### Test Mode (Stripe)

```bash
# Usar cartões de teste do Stripe:

Cartão aprovado:
  Número: 4242 4242 4242 4242
  CVV: Qualquer 3 dígitos
  Data: Qualquer data futura

Cartão recusado:
  Número: 4000 0000 0000 0002

# Testar checkout:
https://vilearn.ai/checkout.php?plan=professional

# Verificar webhook recebido:
# Stripe Dashboard → Developers → Webhooks → Recent deliveries
```

### Validar Email

```bash
# Após pagamento, verificar:
# 1. Email recebido com license key
# 2. License key no formato: VELA-XXXX-XXXX-XXXX-XXXX
# 3. Database tem nova entrada:

SELECT * FROM licenses WHERE email = 'test@example.com';

# Resultado esperado:
# license_key: VELA-87B1-D22D-AD04-331E
# plan: professional
# status: active
# max_activations: 3
```

## 🎨 Personalizar Design

### Cores
```css
/* Mudar cor primária (azul) para outra: */
/* pricing.html - Procurar e substituir: */

bg-blue-600  → bg-purple-600
text-blue-600 → text-purple-600
border-blue-600 → border-purple-600
```

### Preços
```html
<!-- pricing.html - Editar: -->
<span class="text-5xl font-bold text-gray-900">€79</span>

<!-- checkout.php - Editar: -->
'amount' => 7900,  // €79.00 em cêntimos
```

### Features
```html
<!-- Adicionar/remover features em pricing.html: -->
<li class="flex items-start">
    <svg class="w-5 h-5 text-green-500 mt-1 mr-2">...</svg>
    <span>Tua nova feature</span>
</li>
```

## 📧 Email Templates

O email enviado ao user está definido em `server.py` → função `send_license_email()`.

**Para personalizar:**
```python
# server.py linha ~546

html_content = f"""
<html>
<body style="...">
    <!-- Teu HTML customizado aqui -->
    <h2>Bem-vindo ao NSP Plugin!</h2>
    <p>A tua license key: {license_key}</p>
</body>
</html>
"""
```

## 🔒 Segurança

### IMPORTANTE - Proteção de Chaves

```bash
# ❌ NUNCA fazer:
# - Commit .env para git
# - Hardcode de API keys no código
# - Partilhar secret keys publicamente

# ✅ Sempre fazer:
# - Usar variáveis de ambiente
# - Diferentes keys para test/live
# - Verificar webhook signatures (já implementado)
# - HTTPS obrigatório em produção
```

### Validação de Webhook

```python
# server.py já implementa validação de signature:

event = stripe.Webhook.construct_event(
    payload,
    sig_header,
    STRIPE_WEBHOOK_SECRET  # ← Valida que request veio do Stripe
)

# Sem esta validação, qualquer um poderia criar licenses grátis!
```

## 💰 Custos de Processamento

### Stripe
```
Cartões europeus: 1.4% + €0.25
Cartões não-europeus: 2.9% + €0.25
Multibanco/MB WAY: 1.4% + €0.25

Exemplo (Professional €149):
  Valor bruto: €149.00
  Taxa Stripe: €2.09 + €0.25 = €2.34
  Recebes: €146.66
```

### SendGrid
```
Free tier: 100 emails/dia (suficiente para começar)
Paid tier: €15/mês = 40,000 emails/mês
```

### Railway/Render
```
Railway: $5 crédito grátis/mês → ~100 users
Render: Grátis (com cold starts)
```

## 🚀 Go Live Checklist

### Antes de Lançar:

- [ ] Stripe em modo **Live** (não Test)
- [ ] Webhook configurado em produção
- [ ] License server deployed (Railway/Render)
- [ ] SSL/HTTPS ativo (vilearn.ai)
- [ ] SendGrid configurado e testado
- [ ] Email recebido e não vai para spam
- [ ] Database backups configurados
- [ ] Test purchase completo (cartão real)
- [ ] Verificar license activation funciona
- [ ] Página de pricing no ar
- [ ] FAQ e documentação prontos
- [ ] Suporte email configurado (support@vilearn.ai)

### Pós-Lançamento:

- [ ] Monitoring configurado (UptimeRobot)
- [ ] Analytics (Google Analytics/Plausible)
- [ ] Refund policy documentada
- [ ] Terms of Service
- [ ] Privacy Policy (GDPR compliance)

## 📞 Suporte

Se encontrares problemas:

1. **Webhook não recebido:**
   - Verificar Stripe Dashboard → Webhooks → Recent deliveries
   - Confirmar URL: https://license.vilearn.ai/webhook/stripe
   - Verificar logs do server

2. **Email não chega:**
   - Verificar logs SendGrid
   - Confirmar FROM_EMAIL verificado
   - Verificar spam folder

3. **Checkout falha:**
   - Verificar STRIPE_SECRET_KEY correto
   - Confirmar test/live mode consistente
   - Ver console browser para erros JS

4. **License não ativa:**
   - Confirmar database tem entrada
   - Verificar license_key formato correto
   - Testar endpoint `/api/v1/licenses/activate`

## 🎯 Próximos Passos

1. Personalizar design da pricing page
2. Configurar Stripe em modo test
3. Testar checkout flow completo
4. Deploy license server (Railway)
5. Configurar webhook produção
6. Beta testing com 5-10 users
7. Switch para Stripe Live mode
8. 🚀 Launch!

---

**Boa sorte com o lançamento! 🎉**
