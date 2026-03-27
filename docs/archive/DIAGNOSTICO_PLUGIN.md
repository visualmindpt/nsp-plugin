# 🔧 Diagnóstico do Plugin - Passo a Passo

**Problema Reportado:** Plugin não abre modais, não aplica alterações, sem erros no servidor nem no plugin.

---

## 🎯 Checklist de Diagnóstico

Execute TODOS os passos na ordem:

### ✅ **PASSO 1: Verificar Servidor**

```bash
# Verificar se servidor está a correr
lsof -i :5000

# Se nada aparecer, iniciar servidor:
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
source venv/bin/activate
python services/server.py

# Deve aparecer:
# INFO - ✅ AI_PREDICTOR (V2) inicializado com sucesso.
# INFO - Application startup complete.
# INFO - Uvicorn running on http://127.0.0.1:5000
```

**Testar servidor manualmente:**
```bash
curl http://localhost:5000/health
# Deve retornar: {"status":"healthy"}
```

---

### ✅ **PASSO 2: Verificar Localização do Plugin**

```bash
# Onde está instalado?
ls -la ~/Library/Application\ Support/Adobe/Lightroom/Modules/
# OU
ls -la "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"

# O plugin deve estar numa destas localizações
```

**Ações:**
1. Se o plugin estiver em duas localizações → APAGAR a cópia antiga
2. Manter apenas 1 cópia

---

### ✅ **PASSO 3: Recarregar Plugin no Lightroom**

**IMPORTANTE:** Lightroom NÃO recarrega plugins automaticamente!

1. Abrir Lightroom Classic
2. **File > Plug-in Manager** (ou Cmd+,)
3. Encontrar "NSP Plugin" na lista
4. Clicar em **"Remove"** (sim, remover!)
5. Clicar em **"Add"**
6. Navegar até: `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin`
7. Clicar "Add Plugin"
8. **Verificar:** Status deve mostrar "Enabled"

**Screenshot de onde deve estar:**
```
File > Plug-in Manager
├─ [✓] NSP Plugin
│   Status: Enabled
│   Version: 0.6.0
│   File: /Users/nelsonsilva/.../NSP-Plugin.lrplugin
```

---

### ✅ **PASSO 4: Testar Script de Diagnóstico**

Criei um script de teste: **TestConnection.lua**

**Como usar:**
1. Selecionar 1 foto no Lightroom
2. **File > Plug-in Extras > 🔧 TESTE DE CONEXÃO (DEBUG)**
3. Aguardar modal aparecer

**Resultados Possíveis:**

#### ✅ **Cenário 1: Tudo OK**
```
✅ TODOS OS TESTES PASSARAM!

• Plugin carregado: OK
• Fotos selecionadas: 1
• Servidor online: OK
• Resposta: {"status":"healthy"}
```
**Ação:** Plugin está funcional! O problema é noutro lado.

#### ❌ **Cenário 2: Servidor Offline**
```
❌ SERVIDOR NÃO ACESSÍVEL

Status HTTP: sem resposta
URL testado: http://127.0.0.1:5000/health

Por favor, verifique:
1. Servidor está a correr?
2. Porta 5000 está livre?
3. Firewall está a bloquear?
```
**Ação:** Iniciar servidor (ver Passo 1)

#### ❌ **Cenário 3: Nada Acontece**
**Sintomas:** Clicar no menu não abre nada, sem erros

**Possíveis Causas:**
1. Plugin não carregado corretamente
2. Ficheiro .lua com erro de sintaxe
3. Lightroom não vê o menu

**Ações:**
```bash
# Verificar sintaxe de todos os ficheiros
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"
luac -p Info.lua
luac -p TestConnection.lua
luac -p ApplyAIPresetV2.lua
luac -p Common_V2.lua

# Todos devem retornar sem erros
```

---

### ✅ **PASSO 5: Verificar Logs do Lightroom**

Os logs do Lightroom estão em:
```bash
~/Library/Logs/Adobe/Lightroom/
```

**Ver logs em tempo real:**
```bash
# Abrir terminal
tail -f ~/Library/Logs/Adobe/Lightroom/*.log

# Ou ver ficheiro específico do plugin:
tail -f ~/Library/Logs/LrClassicLogs/NSPPlugin*.log
```

**O que procurar:**
- Mensagens de erro ao carregar plugin
- Stack traces
- "module not found"
- "syntax error"

---

### ✅ **PASSO 6: Verificar Permissões**

```bash
# Verificar permissões do plugin
ls -la "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"

# Todos os ficheiros devem ter permissão de leitura (r)
# Exemplo: -rw-r--r--

# Se não tiver, corrigir:
chmod -R 755 "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"
```

---

### ✅ **PASSO 7: Testar Menu Alternativo**

Se o menu não aparecer em **File > Plug-in Extras**, tentar:

**Library > Plug-in Extras**

O plugin está registado em AMBOS os locais.

---

### ✅ **PASSO 8: Verificar Versão do Lightroom**

```bash
# Abrir Lightroom
# Help > System Info
# Procurar: "Version: X.X.X"

# Plugin requer: Lightroom Classic 14.5+
```

Se versão < 14.5 → Atualizar Lightroom

---

## 🐛 Problemas Comuns e Soluções

### Problema 1: "Nada acontece ao clicar no menu"

**Causa:** Plugin não está a ser carregado

**Solução:**
1. Remover e re-adicionar plugin (Passo 3)
2. Verificar logs (Passo 5)
3. Verificar sintaxe Lua (Passo 4 - Cenário 3)

---

### Problema 2: "Menu não aparece"

**Causa:** Info.lua não foi lido corretamente

**Solução:**
```bash
# Verificar sintaxe
luac -p NSP-Plugin.lrplugin/Info.lua

# Reiniciar Lightroom completamente:
# Quit Lightroom (Cmd+Q)
# Aguardar 5 segundos
# Abrir novamente
```

---

### Problema 3: "Erro: module 'Common_V2' not found"

**Causa:** Ficheiro Common_V2.lua não está no lugar certo

**Solução:**
```bash
# Verificar se existe
ls -la NSP-Plugin.lrplugin/Common_V2.lua

# Se não existir, há um problema de instalação
```

---

### Problema 4: "Servidor retorna erro 503"

**Causa:** Modelos AI não carregados

**Solução:**
```bash
# Verificar se modelos existem
ls -la models/*.pth

# Deve haver:
# best_preset_classifier.pth
# best_refinement_model.pth

# Se não existir, treinar modelos primeiro
```

---

### Problema 5: "Plugin funciona mas não aplica ajustes"

**Causa:** Servidor processa mas não retorna JSON correto

**Solução:**
1. Verificar logs do servidor (terminal onde corre)
2. Testar endpoint manualmente:
```bash
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/caminho/para/foto.jpg",
    "exif": {"iso": 100, "width": 6000, "height": 4000}
  }'
```

---

## 📊 Matriz de Diagnóstico

| Sintoma | Causa Provável | Solução |
|---------|----------------|---------|
| Menu não aparece | Plugin não carregado | Passo 3 |
| Menu aparece mas não faz nada | Erro de sintaxe Lua | Passo 4 - Cenário 3 |
| Modal abre mas dá erro | Servidor offline | Passo 1 |
| Servidor retorna 503 | Modelos não carregados | Treinar modelos |
| Sem logs no servidor | Plugin não faz requests | Verificar Common_V2.lua |
| Fotos não selecionadas | User error | Selecionar foto antes |

---

## 🔍 Comando de Diagnóstico Completo

Execute este comando para diagnóstico automático:

```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"

echo "🔍 DIAGNÓSTICO NSP PLUGIN"
echo "========================"
echo ""

echo "1. Verificar sintaxe Lua..."
luac -p NSP-Plugin.lrplugin/Info.lua && echo "✅ Info.lua OK" || echo "❌ Info.lua ERRO"
luac -p NSP-Plugin.lrplugin/TestConnection.lua && echo "✅ TestConnection.lua OK" || echo "❌ TestConnection.lua ERRO"
luac -p NSP-Plugin.lrplugin/Common_V2.lua && echo "✅ Common_V2.lua OK" || echo "❌ Common_V2.lua ERRO"
luac -p NSP-Plugin.lrplugin/ApplyAIPresetV2.lua && echo "✅ ApplyAIPresetV2.lua OK" || echo "❌ ApplyAIPresetV2.lua ERRO"
echo ""

echo "2. Verificar servidor..."
if lsof -i :5000 > /dev/null 2>&1; then
    echo "✅ Porta 5000 em uso (servidor provavelmente a correr)"
    curl -s http://localhost:5000/health > /dev/null 2>&1 && echo "✅ Servidor responde a /health" || echo "❌ Servidor não responde"
else
    echo "❌ Porta 5000 LIVRE (servidor NÃO está a correr)"
    echo "   Execute: python services/server.py"
fi
echo ""

echo "3. Verificar modelos..."
if [ -f "models/best_preset_classifier.pth" ]; then
    echo "✅ Classificador existe"
else
    echo "❌ Classificador NÃO existe (treinar modelos primeiro)"
fi

if [ -f "models/best_refinement_model.pth" ]; then
    echo "✅ Refinador existe"
else
    echo "❌ Refinador NÃO existe (treinar modelos primeiro)"
fi
echo ""

echo "4. Verificar permissões..."
ls -la NSP-Plugin.lrplugin/Info.lua | grep "r--r--r--" > /dev/null && echo "✅ Permissões OK" || echo "⚠️  Permissões podem estar incorretas"
echo ""

echo "========================"
echo "✅ Diagnóstico concluído"
echo ""
echo "PRÓXIMO PASSO:"
echo "1. Se tudo OK → Testar no Lightroom: File > Plug-in Extras > 🔧 TESTE DE CONEXÃO"
echo "2. Se servidor offline → python services/server.py"
echo "3. Se modelos não existem → python train_ui.py"
```

---

## 🎯 Workflow de Resolução

```
START
  ↓
[Executar diagnóstico completo] ←────────┐
  ↓                                       │
[Todos os testes OK?] ─── NÃO ──→ [Corrigir problemas]
  ↓ SIM                                   │
[Remover + Re-adicionar plugin] ─────────┘
  ↓
[Reiniciar Lightroom]
  ↓
[Testar: 🔧 TESTE DE CONEXÃO]
  ↓
[Funcionou?] ─── SIM ──→ [✅ RESOLVIDO!]
  ↓ NÃO
[Ver logs do Lightroom]
  ↓
[Reportar erro com logs]
```

---

## 📝 Checklist Rápida

Execute esta checklist antes de qualquer teste:

- [ ] Servidor está a correr (`python services/server.py`)
- [ ] Servidor responde a `curl http://localhost:5000/health`
- [ ] Plugin foi REMOVIDO e RE-ADICIONADO no Lightroom
- [ ] Lightroom foi REINICIADO após adicionar plugin
- [ ] Pelo menos 1 foto está SELECIONADA
- [ ] Todos os ficheiros .lua têm sintaxe válida (`luac -p`)
- [ ] Logs do Lightroom estão acessíveis e monitorizados

---

## 🆘 Se Nada Funcionar

**Último recurso: Reset completo**

```bash
# 1. Fechar Lightroom
# 2. Remover plugin completamente
rm -rf ~/Library/Application\ Support/Adobe/Lightroom/Modules/NSP-Plugin.lrplugin

# 3. Limpar caches do Lightroom
rm -rf ~/Library/Caches/Adobe/Lightroom/

# 4. Verificar integridade do plugin
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package"
luac -p NSP-Plugin.lrplugin/*.lua

# 5. Reiniciar Lightroom
# 6. Adicionar plugin novamente via Plug-in Manager
# 7. Testar com 🔧 TESTE DE CONEXÃO
```

---

**Desenvolvido por:** Nelson Silva
**Data:** 13 de Novembro de 2025
**Versão:** NSP Plugin V2.1 Diagnostic
