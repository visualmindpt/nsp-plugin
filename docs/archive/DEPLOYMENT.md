# 🚀 NSP Plugin - Deployment Guide

## Deployment em Produção com Docker

Este guia cobre o deployment production-ready do NSP Plugin usando Docker e Docker Compose.

---

## 📋 Pré-requisitos

- **Docker** >= 20.10
- **Docker Compose** >= 2.0
- **Modelos treinados** em `models/`
- **4GB RAM mínimo** (8GB recomendado)
- **2 CPU cores mínimo** (4 recomendado)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                    Lightroom Plugin                 │
│                        (Lua)                        │
└────────────────────┬────────────────────────────────┘
                     │ HTTP API
                     ▼
┌─────────────────────────────────────────────────────┐
│                   NSP Plugin API                    │
│              (Python/FastAPI/PyTorch)               │
│  - Parallel Feature Extraction                      │
│  - Model Inference                                  │
│  - Batch Processing                                 │
│  - Caching Layer                                    │
└─────────────────────────────────────────────────────┘
                     │
                     ├──► Prometheus (metrics)
                     ├──► Grafana (dashboards)
                     └──► Redis (cache)
```

---

## 🚀 Quick Start

### 1. Deploy Básico (apenas API)

```bash
./scripts/deploy.sh
```

Isto vai:
- ✅ Verificar se modelos existem
- ✅ Build da imagem Docker
- ✅ Iniciar API server
- ✅ Health check automático

**Endpoints disponíveis:**
- API: `http://localhost:5001`
- Health: `http://localhost:5001/health`
- Docs: `http://localhost:5001/docs`

### 2. Deploy com Monitoring

```bash
./scripts/deploy.sh monitoring
```

Adiciona:
- ✅ Prometheus (métricas)
- ✅ Grafana (dashboards)

**Endpoints adicionais:**
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

### 3. Deploy com Cache

```bash
./scripts/deploy.sh cache
```

Adiciona:
- ✅ Redis (cache de predições)

### 4. Deploy Full Stack

```bash
./scripts/deploy.sh full
```

Todos os serviços ativos!

---

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```bash
# Server
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
MAX_WORKERS=4           # Número de workers uvicorn
SERVER_PORT=5001        # Porta da API

# Features
ENABLE_MONITORING=true  # Ativar métricas
ENABLE_CACHE=true       # Ativar cache Redis
CACHE_TTL=3600         # TTL do cache (segundos)

# Performance
BATCH_SIZE=16          # Batch size para inferência
MAX_BATCH_SIZE=100     # Máximo de imagens por batch request
```

### Resource Limits

Editar em `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Máximo de CPUs
      memory: 4G       # Máxima RAM
    reservations:
      cpus: '1.0'      # Mínimo garantido
      memory: 2G       # Mínima RAM garantida
```

---

## 📊 Monitoring & Observability

### Métricas Disponíveis

**API Metrics (Prometheus):**
- `nsp_api_requests_total` - Total de requests
- `nsp_api_latency_seconds` - Latência por endpoint
- `nsp_model_inference_duration` - Tempo de inferência
- `nsp_cache_hit_ratio` - Taxa de cache hits
- `nsp_batch_size` - Tamanho de batches processados

### Grafana Dashboards

Pré-configurados:
1. **API Overview** - Requests, latência, errors
2. **Model Performance** - Inference time, throughput
3. **Cache Statistics** - Hit rate, memory usage
4. **System Resources** - CPU, RAM, disk

---

## 🔍 Operações

### Ver logs em tempo real

```bash
docker-compose logs -f api
```

### Ver status dos containers

```bash
docker-compose ps
```

### Restart do servidor

```bash
docker-compose restart api
```

### Stop completo

```bash
docker-compose down
```

### Stop com limpeza de volumes

```bash
docker-compose down -v
```

### Atualizar código

```bash
# 1. Pull novo código
git pull

# 2. Rebuild e restart
docker-compose build api
docker-compose up -d api
```

---

## 🧪 Health Checks

### API Health Endpoint

```bash
curl http://localhost:5001/health
```

**Response esperada:**
```json
{
  "status": "healthy",
  "version": "2.0",
  "models_loaded": true,
  "uptime_seconds": 1234
}
```

### Docker Health Status

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Deve mostrar `healthy` para o container `nsp-plugin-api`.

---

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs de erro
docker-compose logs api

# Verificar se porta está em uso
lsof -i :5001

# Tentar start manual para debug
docker-compose run --rm api bash
```

### Models not found

```bash
# Verificar se modelos existem
ls -la models/

# Re-treinar se necessário
python train/train_models_v2.py
```

### Out of Memory

Reduzir workers em `docker-compose.yml`:

```yaml
environment:
  - MAX_WORKERS=2  # Reduzir de 4 para 2
```

Ou aumentar limite de memória:

```yaml
deploy:
  resources:
    limits:
      memory: 8G  # Aumentar de 4G para 8G
```

### High Latency

1. Verificar métricas no Grafana
2. Ativar Redis cache se não ativo
3. Aumentar batch size
4. Escalar horizontalmente (múltiplos containers)

---

## 📈 Scaling

### Horizontal Scaling (Load Balancer)

```bash
# Scale to 3 replicas
docker-compose up -d --scale api=3

# Nginx como load balancer
# (ver docs/nginx-lb.conf para config)
```

### Vertical Scaling

```yaml
# Aumentar recursos
deploy:
  resources:
    limits:
      cpus: '4.0'    # Mais CPUs
      memory: 16G    # Mais RAM
```

---

## 🔒 Segurança

### Production Checklist

- [ ] Trocar passwords padrão (Grafana)
- [ ] Configurar HTTPS/SSL
- [ ] Limitar acesso por IP/firewall
- [ ] Configurar rate limiting
- [ ] Ativar authentication na API
- [ ] Logs para sistema externo (ELK, Datadog)
- [ ] Backups automáticos dos modelos

### Rate Limiting

Configurar no Nginx ou usar SlowAPI no FastAPI (já integrado).

---

## 📦 Backup & Recovery

### Backup dos Modelos

```bash
# Backup manual
tar -czf models-backup-$(date +%Y%m%d).tar.gz models/

# Backup automático (cron)
0 2 * * * tar -czf /backups/models-$(date +\%Y\%m\%d).tar.gz /app/models/
```

### Recovery

```bash
# Restaurar modelos
tar -xzf models-backup-20251121.tar.gz -C .

# Restart do serviço
docker-compose restart api
```

---

## 🌐 Production Deployment (Cloud)

### AWS (ECS/Fargate)

```bash
# 1. Push image to ECR
docker tag nsp-plugin:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/nsp-plugin:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/nsp-plugin:latest

# 2. Deploy via Terraform/CloudFormation
# (ver docs/aws-deployment.md)
```

### Google Cloud (Cloud Run)

```bash
# 1. Build and push
gcloud builds submit --tag gcr.io/<project-id>/nsp-plugin

# 2. Deploy
gcloud run deploy nsp-plugin \
  --image gcr.io/<project-id>/nsp-plugin \
  --platform managed \
  --region us-central1 \
  --memory 4Gi \
  --cpu 2
```

### Docker Swarm

```bash
# Deploy stack
docker stack deploy -c docker-compose.yml nsp-plugin
```

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Ver docs/kubernetes.md para detalhes
```

---

## 📞 Support

**Issues:** https://github.com/nsp-plugin/issues
**Docs:** https://nsp-plugin.docs.com
**Email:** support@nsp-plugin.com

---

## 📄 License

© 2025 NSP Plugin. All rights reserved.
