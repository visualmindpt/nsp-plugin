# Deployment em cPanel - License Server

## 🚨 Implicações de Usar Servidor Partilhado cPanel

### ❌ Limitações Críticas

1. **Sem acesso root/sudo**
   - Não podes instalar Python packages globalmente
   - Não podes usar systemd/supervisor para manter o servidor ativo
   - Não podes abrir portas customizadas (8080, etc)

2. **Python via CGI/FastCGI apenas**
   - FastAPI/Uvicorn requer processo persistente (não funciona em CGI)
   - Latência muito alta (cada request reinicia o processo)
   - Sem suporte para WebSockets ou long-polling

3. **Recursos partilhados**
   - CPU/RAM limitados e partilhados com outros users
   - Podem suspender teu processo se consumir muitos recursos
   - Database connections limitadas

4. **Segurança comprometida**
   - Outros users no mesmo servidor podem ver teus processos
   - Filesystem permissions partilhadas
   - Não controlas firewall/iptables

### ✅ Soluções Possíveis para cPanel

#### Opção 1: Reescrever para PHP (Recomendado para cPanel)

Como cPanel tem excelente suporte para PHP, podes reescrever o license server em PHP:

```php
<?php
// licensing/api/v1/activate.php

require_once '../vendor/autoload.php';
use Firebase\JWT\JWT;

header('Content-Type: application/json');

// Database connection
$db = new PDO('mysql:host=localhost;dbname=nsp_licenses', 'user', 'pass');

// Parse JSON request
$input = json_decode(file_get_contents('php://input'), true);
$license_key = $input['license_key'];
$machine_id = $input['machine_id'];

// Validate license
$stmt = $db->prepare("SELECT * FROM licenses WHERE license_key = ? AND status = 'active'");
$stmt->execute([$license_key]);
$license = $stmt->fetch(PDO::FETCH_ASSOC);

if (!$license) {
    http_response_code(404);
    echo json_encode(['error' => 'License not found']);
    exit;
}

// Check activation limit
$stmt = $db->prepare("SELECT COUNT(*) FROM activations WHERE license_id = ? AND deactivated_at IS NULL");
$stmt->execute([$license['id']]);
$active_count = $stmt->fetchColumn();

if ($active_count >= $license['max_activations']) {
    http_response_code(403);
    echo json_encode(['error' => 'Maximum activations reached']);
    exit;
}

// Create activation
$activation_id = bin2hex(random_bytes(16));
$stmt = $db->prepare("INSERT INTO activations (id, license_id, machine_id, activated_at) VALUES (?, ?, ?, NOW())");
$stmt->execute([$activation_id, $license['id'], $machine_id]);

// Generate JWT token
$secret_key = getenv('JWT_SECRET_KEY');
$payload = [
    'activation_id' => $activation_id,
    'license_id' => $license['id'],
    'machine_id' => $machine_id,
    'plan' => $license['plan'],
    'exp' => time() + (24 * 3600)
];

$token = JWT::encode($payload, $secret_key, 'HS256');

// Return response
echo json_encode([
    'success' => true,
    'token' => $token,
    'plan' => $license['plan'],
    'features' => get_features($license['plan'])
]);

function get_features($plan) {
    $features = [
        'trial' => ['lightgbm' => true, 'neural_network' => false, 'max_photos_per_batch' => 50],
        'personal' => ['lightgbm' => true, 'neural_network' => true, 'max_photos_per_batch' => 500],
        'professional' => ['lightgbm' => true, 'neural_network' => true, 'smart_culling' => true, 'max_photos_per_batch' => 5000],
        'studio' => ['lightgbm' => true, 'neural_network' => true, 'smart_culling' => true, 'max_photos_per_batch' => -1],
    ];
    return $features[$plan] ?? $features['trial'];
}
?>
```

**Estrutura de ficheiros no cPanel:**

```
public_html/
├── .htaccess          # URL rewriting
├── index.php          # Landing page
└── api/
    └── v1/
        ├── activate.php
        ├── validate.php
        ├── heartbeat.php
        ├── deactivate.php
        └── create.php    # Admin endpoint
```

**`.htaccess` para API routing:**

```apache
RewriteEngine On
RewriteBase /

# API endpoints
RewriteRule ^api/v1/licenses/activate$ api/v1/activate.php [L]
RewriteRule ^api/v1/licenses/validate$ api/v1/validate.php [L]
RewriteRule ^api/v1/licenses/heartbeat$ api/v1/heartbeat.php [L]
RewriteRule ^api/v1/licenses/deactivate$ api/v1/deactivate.php [L]
RewriteRule ^api/v1/licenses/create$ api/v1/create.php [L]
```

#### Opção 2: Python via Passenger (se disponível)

Alguns hosts cPanel suportam Python via Phusion Passenger:

```python
# passenger_wsgi.py
import sys
import os

INTERP = os.path.join(os.environ['HOME'], 'venv', 'bin', 'python')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

from server import app as application
```

**Limitações:**
- Nem todos os hosts cPanel têm Passenger
- Ainda terás limites de recursos
- Performance inferior a VPS dedicado

#### Opção 3: Hosting Híbrido (Recomendado para começar)

**Melhor abordagem para fase inicial:**

1. **cPanel**: Hospeda landing page + checkout (PHP)
2. **Railway/Render (free tier)**: Hospeda license server (Python FastAPI)

```
User → vilearn.ai (cPanel)
       ↓
       Stripe Checkout
       ↓
       Webhook → license.vilearn.ai (Railway - FastAPI)
       ↓
       Cria licença + Email ao user
```

**Vantagens:**
- Landing page em cPanel (tens controlo total)
- License server em ambiente adequado (Railway free tier = $5/mês de crédito grátis)
- Fácil upgrade quando crescer

---

## 💳 Sistema de Pagamento Recomendado

### **Stripe (Recomendado) 🏆**

**Por quê Stripe?**
- ✅ Aceita cartões internacionais + SEPA + Multibanco + MB WAY
- ✅ Webhooks automáticos (pagamento → ativação)
- ✅ Excelente API e documentação
- ✅ Suporte para subscriptions (se quiseres modelo recorrente)
- ✅ Baixa taxa: 1.4% + €0.25 (cartões europeus)
- ✅ Dashboard completo com analytics
- ✅ Compliance automático com PSD2/SCA (Strong Customer Authentication)

**Alternativas:**
- **Paddle**: Melhor para SaaS (eles gerem VAT), mas taxa mais alta (5% + €0.50)
- **PayPal**: Conhecido mas interface antiga, taxas altas (3.4% + €0.35)
- **Gumroad**: Muito simples mas taxa 10% (não recomendado)

---

## 🔄 Automação Completa: Pagamento → Ativação

### Arquitetura do Sistema

```
┌────────────────────────────────────────────────────────────┐
│ 1. User visita vilearn.ai/pricing                         │
│    → Clica "Buy Professional" (€149)                       │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ 2. Stripe Checkout Session                                │
│    → User preenche cartão/email                           │
│    → Stripe processa pagamento                            │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ 3. Stripe Webhook: checkout.session.completed             │
│    POST https://license.vilearn.ai/webhook/stripe          │
│    Body: {                                                 │
│      customer_email: "user@example.com",                   │
│      product_id: "professional",                           │
│      amount_paid: 14900  // cents                          │
│    }                                                       │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ 4. License Server (FastAPI)                               │
│    → Valida webhook signature (segurança)                  │
│    → Cria licença: VELA-XXXX-XXXX-XXXX-XXXX               │
│    → Guarda em database                                    │
│    → Envia email ao user com license key                  │
└────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────┐
│ 5. Email ao User (SendGrid/Mailgun)                       │
│                                                            │
│    Subject: Your NSP Plugin License Key                    │
│                                                            │
│    Hi user@example.com,                                    │
│                                                            │
│    Thanks for purchasing NSP Plugin Professional!         │
│                                                            │
│    Your license key: VELA-87B1-D22D-AD04-331E             │
│                                                            │
│    To activate:                                            │
│    1. Open Lightroom Classic                               │
│    2. File → Plug-in Manager → NSP Plugin                 │
│    3. Enter your license key                               │
│                                                            │
│    Need help? Reply to this email.                         │
└────────────────────────────────────────────────────────────┘
```

---

## 💻 Implementação - Integração Stripe

### Passo 1: Setup Stripe

```bash
# Criar conta em stripe.com
# Dashboard → API Keys
# Copiar:
# - Publishable Key: pk_live_xxxxx
# - Secret Key: sk_live_xxxxx
# - Webhook Secret: whsec_xxxxx
```

### Passo 2: Adicionar Webhook Endpoint ao Server

```python
# server.py - Adicionar este endpoint

import stripe
import hmac
import hashlib

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler.
    Automatically creates license when payment succeeds.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        # Verify webhook signature (CRITICAL for security)
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Extract customer info
        customer_email = session["customer_details"]["email"]
        metadata = session.get("metadata", {})
        plan = metadata.get("plan", "personal")

        # Generate license
        license_key = generate_license_key()

        # Determine max_activations based on plan
        max_activations = {
            "trial": 1,
            "personal": 2,
            "professional": 3,
            "studio": 10
        }.get(plan, 2)

        # Create license in database
        license_obj = License(
            license_key=license_key,
            email=customer_email,
            plan=plan,
            max_activations=max_activations,
            expires_at=None,  # Perpetual license
            license_metadata={
                "stripe_session_id": session["id"],
                "stripe_customer_id": session.get("customer"),
                "amount_paid": session["amount_total"],
                "currency": session["currency"]
            }
        )

        db.add(license_obj)
        db.commit()

        logger.info(f"Created license {license_key} for {customer_email} via Stripe (plan: {plan})")

        # Send email with license key
        send_license_email(customer_email, license_key, plan)

        return {"status": "success"}

    return {"status": "ignored"}


def send_license_email(email: str, license_key: str, plan: str):
    """Send license key via email using SendGrid."""
    import sendgrid
    from sendgrid.helpers.mail import Mail, Email, To, Content

    sg = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))

    from_email = Email("noreply@vilearn.ai")
    to_email = To(email)
    subject = f"Your NSP Plugin {plan.title()} License Key"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Welcome to NSP Plugin {plan.title()}! 🎉</h2>

        <p>Thank you for your purchase. Your license key is:</p>

        <div style="background: #f5f5f5; padding: 20px; border-radius: 5px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 2px; margin: 20px 0;">
            {license_key}
        </div>

        <h3>How to Activate:</h3>
        <ol>
            <li>Open Adobe Lightroom Classic</li>
            <li>Go to <strong>File → Plug-in Manager</strong></li>
            <li>Select <strong>NSP Plugin</strong></li>
            <li>Click <strong>Activate License</strong></li>
            <li>Enter your license key: <code>{license_key}</code></li>
        </ol>

        <h3>Your Plan Includes:</h3>
        <ul>
            <li>✅ LightGBM AI Selection</li>
            <li>✅ Neural Network Rating</li>
            <li>✅ Smart Culling Algorithm</li>
            <li>✅ {get_feature_set(plan)['max_photos_per_batch']} photos per batch</li>
            <li>✅ Activate on {get_max_activations(plan)} computers</li>
        </ul>

        <p><strong>Need help?</strong> Reply to this email or visit our documentation at <a href="https://docs.vilearn.ai">docs.vilearn.ai</a></p>

        <hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">

        <p style="color: #666; font-size: 12px;">
            This license is registered to: {email}<br>
            Plan: {plan.title()}<br>
            Purchase date: {datetime.utcnow().strftime('%Y-%m-%d')}
        </p>
    </body>
    </html>
    """

    content = Content("text/html", html_content)
    mail = Mail(from_email, to_email, subject, content)

    response = sg.client.mail.send.post(request_body=mail.get())

    if response.status_code >= 400:
        logger.error(f"Failed to send email to {email}: {response.body}")
    else:
        logger.info(f"License email sent to {email}")

def get_max_activations(plan: str) -> int:
    return {"trial": 1, "personal": 2, "professional": 3, "studio": 10}.get(plan, 2)
```

### Passo 3: Criar Checkout Page (PHP no cPanel)

```php
<?php
// public_html/checkout.php

require_once 'vendor/autoload.php';
\Stripe\Stripe::setApiKey(getenv('STRIPE_SECRET_KEY'));

// Get plan from URL: checkout.php?plan=professional
$plan = $_GET['plan'] ?? 'personal';

$prices = [
    'personal' => ['amount' => 7900, 'name' => 'Personal', 'activations' => 2],
    'professional' => ['amount' => 14900, 'name' => 'Professional', 'activations' => 3],
    'studio' => ['amount' => 49900, 'name' => 'Studio', 'activations' => 10],
];

if (!isset($prices[$plan])) {
    die('Invalid plan');
}

$price_info = $prices[$plan];

// Create Stripe Checkout Session
$session = \Stripe\Checkout\Session::create([
    'payment_method_types' => ['card'],
    'line_items' => [[
        'price_data' => [
            'currency' => 'eur',
            'product_data' => [
                'name' => "NSP Plugin - {$price_info['name']} License",
                'description' => "Activate on {$price_info['activations']} computers. Perpetual license.",
            ],
            'unit_amount' => $price_info['amount'],
        ],
        'quantity' => 1,
    ]],
    'mode' => 'payment',
    'success_url' => 'https://vilearn.ai/success',
    'cancel_url' => 'https://vilearn.ai/pricing',
    'customer_email' => $_GET['email'] ?? null,
    'metadata' => [
        'plan' => $plan,
    ],
]);

// Redirect to Stripe Checkout
header("Location: " . $session->url);
exit;
?>
```

### Passo 4: Configurar Webhook no Stripe Dashboard

```
1. Stripe Dashboard → Developers → Webhooks
2. Add endpoint: https://license.vilearn.ai/webhook/stripe
3. Select events: checkout.session.completed
4. Copiar Webhook Secret: whsec_xxxxx
5. Adicionar a .env: STRIPE_WEBHOOK_SECRET=whsec_xxxxx
```

---

## 📧 Setup Email (SendGrid)

### Por quê SendGrid?
- ✅ 100 emails/dia grátis (suficiente para começar)
- ✅ Excelente deliverability (não vai para spam)
- ✅ API simples
- ✅ Templates profissionais

### Setup:

```bash
# 1. Criar conta em sendgrid.com
# 2. Verify sender identity: noreply@vilearn.ai
# 3. Create API Key
# 4. Adicionar a .env

pip install sendgrid
```

**Alternativas:**
- **Mailgun**: 5000 emails grátis/mês
- **Amazon SES**: €0.10 por 1000 emails (super barato mas setup complexo)
- **SMTP do cPanel**: Grátis mas vai para spam

---

## 🚀 Deployment Recomendado (Fase Inicial)

### Opção A: Railway (Recomendado)

**Por quê Railway?**
- ✅ $5 de crédito grátis/mês (suficiente para 100-1000 users)
- ✅ Deploy direto do GitHub
- ✅ PostgreSQL incluído
- ✅ SSL automático
- ✅ Logs e monitoring

```bash
# 1. Criar conta em railway.app
# 2. New Project → Deploy from GitHub
# 3. Selecionar: NSP Plugin_dev_full_package/licensing
# 4. Adicionar PostgreSQL database
# 5. Set environment variables:
#    DATABASE_URL (auto)
#    SECRET_KEY
#    STRIPE_SECRET_KEY
#    STRIPE_WEBHOOK_SECRET
#    SENDGRID_API_KEY
# 6. Deploy!
```

### Opção B: Render (Free Tier)

```bash
# Similar ao Railway mas totalmente grátis
# Limitação: server "dorme" após 15min inativo
# Primeiro request demora 30s (cold start)
```

### Opção C: DigitalOcean App Platform

```bash
# $5/mês mas com CPU dedicado
# Melhor performance
# Recomendado quando tiveres 50+ users
```

---

## 💰 Custos Mensais Estimados

### Fase 1 (0-100 users):

```
Railway:         $0 (free tier $5 crédito)
SendGrid:        $0 (100 emails/dia grátis)
Stripe:          1.4% + €0.25 por transação
Domain:          €12/ano
SSL:             Grátis (Railway/Render incluem)
─────────────────────────────────────────────
TOTAL:           ~€0/mês + taxas Stripe
```

### Fase 2 (100-1000 users):

```
Railway Pro:     $20/mês
SendGrid:        $0 ou $15/mês (se > 100 emails/dia)
Stripe:          1.4% + €0.25 por transação
─────────────────────────────────────────────
TOTAL:           $20-35/mês + taxas Stripe
```

### Fase 3 (1000+ users):

```
DigitalOcean:    $12/mês (VPS)
PostgreSQL:      $15/mês (managed)
SendGrid:        $15/mês
Monitoring:      $10/mês (opcional)
─────────────────────────────────────────────
TOTAL:           $52/mês + taxas Stripe
```

---

## ✅ Checklist de Implementação

### Semana 1: Setup Básico
- [ ] Criar conta Stripe (modo test)
- [ ] Criar conta SendGrid
- [ ] Criar conta Railway/Render
- [ ] Deploy license server
- [ ] Testar webhook Stripe → License creation

### Semana 2: Landing Page
- [ ] Design página de pricing (Tailwind CSS)
- [ ] Botões "Buy Now" → Stripe Checkout
- [ ] Página de sucesso (instruções de ativação)
- [ ] FAQ e documentação

### Semana 3: Testes
- [ ] Test checkout flow completo
- [ ] Verificar email delivery
- [ ] Testar ativação no plugin
- [ ] Beta testing com 5-10 users

### Semana 4: Launch
- [ ] Stripe modo live (verificação de identidade)
- [ ] Domínio customizado (vilearn.ai)
- [ ] SSL configurado
- [ ] Monitoring e alertas
- [ ] Anunciar lançamento

---

## 🎯 Recomendação Final

**Para começar AGORA com cPanel:**

1. **Landing page + Checkout** → cPanel (PHP)
2. **License Server** → Railway free tier (Python FastAPI)
3. **Pagamentos** → Stripe
4. **Emails** → SendGrid free tier

**Fluxo:**
```
vilearn.ai (cPanel)
    ↓
Stripe Checkout
    ↓
license.vilearn.ai (Railway)
    ↓
Email automático com license key
```

**Upgrade path (quando tiveres €100+ MRR):**
- Migrar tudo para VPS dedicado (DigitalOcean €12/mês)
- PostgreSQL managed database
- Monitoring profissional (Datadog)

**Queres que implemente a integração Stripe + webhook handler completo?**
