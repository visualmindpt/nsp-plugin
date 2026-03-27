# 🧪 Guia de Testes Rápido - NSP Plugin

Guia para testar as correções e melhorias implementadas.

---

## ✅ Checklist de Testes

### 1. Config Loader (2 min)
```bash
# Teste 1: Config funcional
python config_loader.py

# Output esperado:
# ✅ Project Root, Server URL, Models Dir, Classifier, Refiner
```

**Resultado esperado:**
```
NSP Plugin - Config Loader
==================================================
Project Root: /Users/.../NSP Plugin_dev_full_package
Server URL: http://127.0.0.1:5678
Models Dir: .../models
Classifier: .../models/best_preset_classifier_v2.pth
Refiner: .../models/best_refinement_model_v2.pth
Batch Size: 16
GPU Enabled: True
```

✅ **PASSOU** se mostrar todos os paths corretamente
❌ **FALHOU** se der erro ou paths incorretos

---

### 2. Modelos Consolidados (1 min)
```bash
# Teste 2: Verificar estrutura de modelos
ls -lh models/*.pth
ls -lh models/backup_*/*.pth
```

**Resultado esperado:**
```
models/
├── best_preset_classifier_v2.pth (361K)
├── best_refinement_model_v2.pth (385K)
├── clip_preset_model.pth (5.8M)
├── backup_v1/
│   ├── best_preset_classifier.pth
│   └── best_refinement_model.pth
└── backup_old_versions/
    ├── best_preset_classifier_old_*.pth
    └── best_refinement_model_old_*.pth
```

✅ **PASSOU** se modelos V2 estão em models/ e backups em subpastas
❌ **FALHOU** se modelos ainda na raiz ou falta algum

---

### 3. Servidor com Config Loader (3 min)
```bash
# Teste 3: Iniciar servidor
source venv/bin/activate
./start_server.sh
```

**No output, procurar por:**
```
✅ AI_PREDICTOR (V2) inicializado com sucesso.
   Classifier: best_preset_classifier_v2.pth
   Refiner: best_refinement_model_v2.pth
   Model Version: 2.0
```

✅ **PASSOU** se servidor inicia sem erros e modelos carregam
❌ **FALHOU** se erro ao carregar config ou modelos

**Manter servidor a correr para testes seguintes**

---

### 4. Endpoint /version (1 min)
```bash
# Teste 4: Testar endpoint /version
curl http://127.0.0.1:5678/version | jq .
```

**Resultado esperado:**
```json
{
  "server_version": "2.0.0",
  "api_version": "v2",
  "models": {
    "classifier": {
      "name": "best_preset_classifier_v2.pth",
      "version": "2.0",
      "loaded": true
    },
    "refiner": {
      "name": "best_refinement_model_v2.pth",
      "version": "2.0",
      "loaded": true
    }
  },
  "features": {
    "feedback_system": true,
    "incremental_training": true,
    ...
  }
}
```

✅ **PASSOU** se JSON válido e `loaded: true` em ambos modelos
❌ **FALHOU** se erro 404, JSON inválido ou `loaded: false`

---

### 5. Validador de Pré-Treino (2 min)
```bash
# Teste 5: Validar ambiente
python train/training_validator.py
```

**Resultado esperado:**
```
🔍 Iniciando validações de pré-treino...

==============================================================
📊 RESUMO DAS VALIDAÇÕES
==============================================================
✅ [N] INFORMAÇÕES:
   • Python 3.X.X ✓
   • PyTorch instalado ✓
   • GPU: [Nome GPU] ✓
   • config.json válido ✓
   ...

⚠️  [N] AVISOS encontrados:
   [Lista de avisos não-críticos]

✅ Todas as validações passaram! Pronto para treinar.
==============================================================
```

✅ **PASSOU** se 0 erros críticos
⚠️ **AVISOS OK** se apenas warnings (não-críticos)
❌ **FALHOU** se erros críticos (❌) listados

---

### 6. Progress Tracker (1 min)
```bash
# Teste 6: Testar progress tracker
python train/training_progress.py
```

**Resultado esperado:**
Deve mostrar simulação de treino com:
- Barras de progresso visuais
- Estimativas de tempo
- Métricas em tempo real
- Resumo final

✅ **PASSOU** se output visual aparece corretamente
❌ **FALHOU** se erros ou output incompleto

---

### 7. Plugin Lightroom - Validação de Versão (5 min)

**Pré-requisitos:**
- Servidor a correr (teste 3)
- Lightroom Classic aberto
- NSP Plugin instalado

**Passos:**
1. Abrir Lightroom Classic
2. Selecionar uma foto
3. `File > Plug-in Extras > AI Preset V2`

**No log do servidor, procurar:**
```
VERSION CHECK: Servidor v2.0.0, API v2, Modelos v2.0
✅ COMPATIBILITY: Servidor compatível com este plugin
```

**No Lightroom:**
- Se modelos NÃO carregados → deve mostrar erro: "Modelos AI não estão carregados"
- Se API incompatível → deve mostrar erro: "Versão da API incompatível"
- Se tudo OK → preset aplica normalmente

✅ **PASSOU** se validação funciona e mensagens são claras
❌ **FALHOU** se não valida ou erro genérico

---

## 🔍 Testes Exploratórios

### Teste A: Portabilidade
**Objetivo:** Verificar que projeto funciona em outro diretório

```bash
# 1. Copiar projeto para outro local
cp -r "NSP Plugin_dev_full_package" ~/Desktop/test_nsp

# 2. Ir para novo local
cd ~/Desktop/test_nsp

# 3. Tentar iniciar servidor
source venv/bin/activate
./start_server.sh
```

✅ **PASSOU** se servidor inicia sem erros
❌ **FALHOU** se erros de paths hardcoded

---

### Teste B: Config Customização
**Objetivo:** Verificar que mudanças em config.json funcionam

```bash
# 1. Editar config.json
vim config.json
# Mudar: "port": 5678 → "port": 5679

# 2. Reiniciar servidor
./stop_server.sh
./start_server.sh

# 3. Testar novo port
curl http://127.0.0.1:5679/version
```

✅ **PASSOU** se servidor usa novo port
❌ **FALHOU** se ignora config.json

---

### Teste C: Fallback de Modelos
**Objetivo:** Verificar comportamento quando modelos faltam

```bash
# 1. Renomear modelo temporariamente
mv models/best_preset_classifier_v2.pth models/classifier_backup.pth

# 2. Reiniciar servidor
./start_server.sh

# 3. Verificar log
# Deve mostrar:
# ⚠️ Ficheiros do modelo AI (V2) em falta
# Ficheiros em falta: [lista]

# 4. Restaurar
mv models/classifier_backup.pth models/best_preset_classifier_v2.pth
```

✅ **PASSOU** se servidor detecta e informa ficheiros em falta
❌ **FALHOU** se crashou ou não informou claramente

---

## 📊 Scorecard de Testes

| Teste | Tempo | Resultado | Notas |
|-------|-------|-----------|-------|
| 1. Config Loader | 2 min | ⬜ | |
| 2. Modelos | 1 min | ⬜ | |
| 3. Servidor | 3 min | ⬜ | |
| 4. Endpoint /version | 1 min | ⬜ | |
| 5. Validator | 2 min | ⬜ | |
| 6. Progress Tracker | 1 min | ⬜ | |
| 7. Plugin Validação | 5 min | ⬜ | |
| **TOTAL** | **15 min** | **⬜** | |

**Legenda:**
- ✅ Passou
- ⚠️ Passou com avisos
- ❌ Falhou
- ⬜ Não testado

---

## 🐛 Troubleshooting

### Problema: Config loader dá erro
**Sintoma:** `FileNotFoundError: config.json`
**Solução:**
```bash
# Verificar se config.json existe
ls -l config.json

# Se não existe, copiar exemplo (se houver) ou recriar
```

---

### Problema: Servidor não encontra modelos
**Sintoma:** `Ficheiros do modelo AI (V2) em falta`
**Solução:**
```bash
# Verificar modelos
ls -l models/*.pth

# Se faltam, podem estar em backup
ls -l models/backup_*/*.pth

# Restaurar se necessário
cp models/backup_*/best_*.pth models/
```

---

### Problema: GPU não detectada
**Sintoma:** `GPU CUDA não disponível`
**Solução:**
```bash
# Verificar CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Se False, verificar drivers NVIDIA
nvidia-smi

# Treino continuará em CPU (mais lento mas funcional)
```

---

### Problema: Plugin não valida versão
**Sintoma:** Erro genérico no plugin
**Solução:**
1. Verificar se servidor está a correr: `curl http://127.0.0.1:5678/health`
2. Verificar logs do Lightroom: `~/Library/Logs/LrClassicLogs/NSPPlugin.*.log`
3. Verificar se Common_V2.lua tem as novas funções `check_server_version()` e `validate_server_compatibility()`

---

## ✅ Critérios de Aceitação

Para considerar as correções como **TOTALMENTE FUNCIONAIS**, devem passar:

### Obrigatórios (100% pass rate)
- ✅ Teste 1: Config Loader
- ✅ Teste 2: Modelos Consolidados
- ✅ Teste 3: Servidor com Config
- ✅ Teste 4: Endpoint /version

### Recomendados (80% pass rate)
- ⚠️ Teste 5: Validator (warnings OK)
- ✅ Teste 6: Progress Tracker
- ✅ Teste 7: Plugin Validação

### Exploratórios (desejável)
- ✅ Teste A: Portabilidade
- ✅ Teste B: Config Customização
- ✅ Teste C: Fallback de Modelos

---

## 📝 Report de Testes

Após completar os testes, preencher:

**Data:** _______________
**Testador:** _______________
**Ambiente:**
- OS: _______________
- Python: _______________
- GPU: _______________

**Resultados:**
- Testes passados: _____ / 7
- Testes com avisos: _____
- Testes falhados: _____

**Observações:**
```
[Escrever aqui quaisquer problemas encontrados ou sugestões]
```

**Conclusão:**
- [ ] ✅ Tudo funcional - pronto para uso
- [ ] ⚠️ Funcional com ressalvas - notas acima
- [ ] ❌ Não funcional - correções necessárias

---

*Boa sorte com os testes! 🚀*
