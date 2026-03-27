# NSP Control Center V2

Dashboard web moderno para monitorização e gestão do NSP Plugin Lightroom.

## 🎯 Funcionalidades

### Dashboard Principal
- ✅ Estado do servidor em tempo real
- ✅ Métricas de uso (predições, tempo médio, etc.)
- ✅ Gráficos de distribuição de presets
- ✅ Logs em tempo real
- ✅ Controlo de servidor (start/stop)

### Treino e Modelos
- ✅ Visualização de métricas de treino
- ✅ Comparação de modelos (V1 vs V2)
- ✅ Gráficos de MAE por slider
- ✅ Histórico de treinos
- ✅ Iniciar novo treino

### Configurações
- ✅ Gestão de hiperparâmetros
- ✅ Configuração de caminhos
- ✅ Preferências de UI
- ✅ Gestão de presets

### Feedback e Active Learning
- ✅ Visualização de feedback recebido
- ✅ Estatísticas de correções
- ✅ Ativação de re-treino automático
- ✅ Threshold de confiança

## 🏗️ Arquitetura

```
┌─────────────────────────────────────┐
│     NSP Control Center V2 (Web)    │
│     http://localhost:5000/dashboard │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│     FastAPI Server (Backend)        │
│     API Endpoints + WebSocket       │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│     Services Layer                  │
│  - Inference Engine                 │
│  - Training Manager                 │
│  - Feedback Collector               │
│  - Model Manager                    │
└─────────────────────────────────────┘
```

## 🚀 Tecnologias

### Backend
- FastAPI (Python)
- WebSocket para real-time
- SQLite para logs e métricas
- Server-Sent Events (SSE)

### Frontend
- HTML5 + CSS3 + Vanilla JS (sem dependências!)
- Chart.js para gráficos
- Tailwind CSS (via CDN) para styling
- Fetch API para comunicação

## 📦 Estrutura de Ficheiros

```
control-center-v2/
├── README.md
├── static/
│   ├── index.html              # Dashboard principal
│   ├── css/
│   │   └── dashboard.css       # Estilos customizados
│   └── js/
│       ├── dashboard.js        # Lógica principal
│       ├── charts.js           # Gráficos e visualizações
│       └── api.js              # Cliente API
└── backend/
    └── dashboard_api.py        # Endpoints para o dashboard
```

## 🎨 Interface

### Dashboard Principal (/)
- Card: Estado do Servidor (🟢/🔴)
- Card: Métricas em Tempo Real
  - Total de predições hoje
  - Tempo médio de resposta
  - Taxa de sucesso
- Gráfico: Distribuição de Presets (últimas 100 predições)
- Gráfico: Predições por Hora (últimas 24h)
- Log Stream: Logs em tempo real

### Treino (/training)
- Card: Último Treino
  - Data e hora
  - Épocas completadas
  - MAE final
- Card: Modelos Disponíveis
  - Classificador V2
  - Refinador V2
  - Modelo V1 (legacy)
- Gráfico: MAE por Slider (top 10)
- Gráfico: Loss vs. Epoch
- Botão: "Iniciar Novo Treino"

### Configurações (/settings)
- Tab: Servidor
  - URL do servidor
  - Porta
  - Auto-start
- Tab: Treino
  - Número de presets
  - Rating mínimo
  - Épocas classificador
  - Épocas refinador
  - Batch size
  - Patience
- Tab: Feedback
  - Threshold de confiança
  - Active learning ativado
  - Intervalo de re-treino

### Feedback (/feedback)
- Card: Estatísticas
  - Total de feedbacks
  - Feedbacks positivos vs. negativos
  - Taxa de correção média
- Tabela: Últimos Feedbacks
  - Timestamp
  - Foto
  - Preset original
  - Correção aplicada
  - Confiança
- Gráfico: Feedbacks por Dia

## 🔌 API Endpoints

### Dashboard
- `GET /api/dashboard/status` - Estado do servidor
- `GET /api/dashboard/metrics` - Métricas em tempo real
- `GET /api/dashboard/predictions/recent` - Últimas predições
- `GET /api/dashboard/logs` - Logs recentes
- `WebSocket /ws/logs` - Stream de logs em tempo real

### Treino
- `GET /api/training/status` - Estado do treino atual
- `GET /api/training/history` - Histórico de treinos
- `GET /api/training/metrics` - Métricas do último treino
- `POST /api/training/start` - Iniciar novo treino
- `POST /api/training/stop` - Parar treino atual

### Configurações
- `GET /api/settings` - Obter todas as configurações
- `PUT /api/settings` - Atualizar configurações
- `POST /api/settings/reset` - Reset para padrão

### Feedback
- `GET /api/feedback/stats` - Estatísticas de feedback
- `GET /api/feedback/recent` - Feedbacks recentes
- `POST /api/feedback/process` - Processar feedback manual

## 🎯 Como Usar

### 1. Iniciar o Servidor
```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate
python services/server.py
```

### 2. Aceder ao Dashboard
Abrir no browser:
```
http://localhost:5000/dashboard
```

### 3. Navegar
- Dashboard Principal: Visão geral e estado
- Treino: Gerir modelos e treinos
- Configurações: Ajustar parâmetros
- Feedback: Monitorizar correções

## 📊 Métricas Disponíveis

### Servidor
- Status (online/offline)
- Uptime
- Número de pedidos
- Erros/minuto
- Memória usada

### Predições
- Total hoje
- Tempo médio
- Taxa de sucesso
- Distribuição de presets
- Confiança média

### Treino
- MAE por slider
- Loss por época
- Tempo de treino
- Dataset size
- Validação accuracy

### Feedback
- Total de feedbacks
- Taxa de correção
- Presets mais corrigidos
- Sliders com maior erro

## 🎨 Paleta de Cores

```css
--primary: #3B82F6    /* Blue */
--success: #10B981    /* Green */
--warning: #F59E0B    /* Orange */
--danger: #EF4444     /* Red */
--dark: #1F2937       /* Dark Gray */
--light: #F3F4F6      /* Light Gray */
```

## 🔒 Segurança

- Dashboard acessível apenas em localhost por padrão
- Sem autenticação necessária (uso local)
- CORS configurado para localhost
- Rate limiting nos endpoints

## 🐛 Troubleshooting

### Dashboard não carrega
**Solução:** Verificar se o servidor está a correr em http://localhost:5000

### Gráficos não aparecem
**Solução:** Verificar console do browser para erros de CDN

### WebSocket desconecta
**Solução:** Verificar firewall e configurações de rede

## 📈 Roadmap

### v2.1 (próximo)
- [ ] Autenticação opcional
- [ ] Exportar relatórios PDF
- [ ] Comparação de modelos lado-a-lado
- [ ] Notificações push

### v2.2 (futuro)
- [ ] Multi-utilizador
- [ ] Histórico de alterações
- [ ] A/B testing de modelos
- [ ] API pública documentada

## 📞 Suporte

Para issues ou sugestões, verificar logs em:
- Servidor: Console onde o `server.py` está a correr
- Browser: DevTools > Console

---

**Desenvolvido por Nelson Silva**
**Data: 13 de Novembro de 2025**
