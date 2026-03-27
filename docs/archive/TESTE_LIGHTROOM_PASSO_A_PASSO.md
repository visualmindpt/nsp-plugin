# 🔧 Teste do Plugin - Passo a Passo NO LIGHTROOM

**Problema:** Menus aparecem mas nada acontece ao clicar

---

## ⚠️ IMPORTANTE: Processo de Reload

O Lightroom **NUNCA atualiza plugins automaticamente**. Tens que fazer reload manual!

---

## 📋 PASSO A PASSO (OBRIGATÓRIO)

### **1. FECHAR Lightroom Completamente**

- ⌘Q (Cmd+Q) para sair
- Aguardar 5 segundos
- Verificar que não há processo Lightroom no Activity Monitor

---

### **2. ABRIR Lightroom**

- Abrir normalmente
- Aguardar carregar completamente

---

### **3. REMOVER Plugin Antigo**

**File > Plug-in Manager** (ou ⌘,)

Na lista de plugins:
1. Encontrar "NSP Plugin"
2. **Clicar em "Remove"** (botão no canto inferior)
3. Confirmar remoção
4. **FECHAR o Plug-in Manager**

---

### **4. RE-ADICIONAR Plugin**

**File > Plug-in Manager** novamente

1. Clicar em **"Add"** (botão inferior esquerdo)
2. Navegar até:
   ```
   /Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin
   ```
3. Selecionar a **PASTA** `NSP-Plugin.lrplugin` (não entrar dentro dela)
4. Clicar "Add Plugin"
5. **VERIFICAR:** Status deve mostrar "**Enabled**"
6. **FECHAR o Plug-in Manager**

---

### **5. REINICIAR Lightroom NOVAMENTE**

- ⌘Q (Cmd+Q)
- Aguardar 5 segundos
- Abrir novamente

**Porquê?** Alguns módulos do Lightroom só carregam no startup.

---

### **6. TESTE 1: Menu Ultra Simples**

**ANTES de selecionar qualquer foto:**

1. Ir a **File > Plug-in Extras**
2. Procurar menu: **"⚡ TESTE ULTRA SIMPLES"**

**O QUE DEVE ACONTECER:**
- Deve aparecer um alerta com texto: "Se vês esta mensagem, o plugin ESTÁ A FUNCIONAR!"

**Se NÃO aparecer:**
- O menu não existe? → Plugin não foi carregado (voltar ao passo 3)
- O menu existe mas não faz nada? → Continuar para Teste 2

---

### **7. TESTE 2: Com Foto Selecionada**

1. **Selecionar 1 foto** na Library
2. Ir a **File > Plug-in Extras**
3. Clicar em **"🔧 TESTE DE CONEXÃO (DEBUG)"**

**O QUE DEVE ACONTECER:**
- Deve aparecer um modal com resultado do teste de conexão

**Resultados Possíveis:**

#### ✅ Sucesso
```
✅ TODOS OS TESTES PASSARAM!

• Plugin carregado: OK
• Fotos selecionadas: 1
• Servidor online: OK
• Resposta: {"status":"healthy"}
```
→ **PLUGIN ESTÁ FUNCIONAL!** Continuar para Teste 3.

#### ❌ Servidor Offline
```
❌ SERVIDOR NÃO ACESSÍVEL
Status HTTP: sem resposta
```
→ Iniciar servidor: `python services/server.py`

#### ⚠️ Nada Acontece
→ Continuar para secção de diagnóstico avançado abaixo

---

### **8. TESTE 3: Aplicar Preset**

**APENAS se Teste 2 passou!**

1. Selecionar 1 foto
2. **File > Plug-in Extras > AI Preset V2 – Foto Individual**
3. Aguardar modal de preview

**O QUE DEVE ACONTECER:**
- Modal com lista de ajustes sugeridos
- Sliders para rating (1-5 ⭐)
- Botões "Aplicar" / "Cancelar"

---

## 🐛 Se NADA Funciona (Diagnóstico Avançado)

### **Verificação 1: Plugin Manager**

No Plug-in Manager, com NSP Plugin selecionado:

**Verificar:**
- Status: **"Enabled"** (não "Disabled" ou "Not Loaded")
- Location: Deve apontar para `/Users/nelsonsilva/Documentos/.../NSP-Plugin.lrplugin`

**Se Status = "Not Loaded" ou mensagem de erro:**
- Há erro de sintaxe Lua
- Verificar: `luac -p NSP-Plugin.lrplugin/*.lua`

---

### **Verificação 2: Logs do Lightroom**

```bash
# Terminal
tail -f ~/Library/Logs/LrClassicLogs/*.log | grep -i "nsp"
```

**Clicar no menu enquanto tail está a correr.**

**Se aparecer algum erro:**
- Copiar mensagem de erro completa
- Pode indicar problema específico

**Se NÃO aparecer nada:**
- Plugin não está a executar de todo
- Problema na estrutura ou carregamento

---

### **Verificação 3: Info.lua Válido**

```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"

# Verificar sintaxe
luac -p Info.lua

# Ver estrutura
cat Info.lua | grep -A 5 "LrExportMenuItems"
```

**Deve mostrar:**
```lua
LrExportMenuItems = {
    {
        title = "⚡ TESTE ULTRA SIMPLES",
        file = "TestSimple.lua",
    },
    ...
}
```

---

### **Verificação 4: Permissões**

```bash
ls -la NSP-Plugin.lrplugin/*.lua

# Todos devem ter:
# -rwxr-xr-x (executáveis e legíveis)
```

**Se não tiver, corrigir:**
```bash
chmod -R 755 NSP-Plugin.lrplugin
```

---

### **Verificação 5: Estrutura de Pastas**

```bash
tree -L 2 NSP-Plugin.lrplugin

# Deve mostrar:
NSP-Plugin.lrplugin/
├── Info.lua              ← CRÍTICO
├── TestSimple.lua        ← NOVO
├── TestConnection.lua    ← NOVO
├── ApplyAIPresetV2.lua
├── Common_V2.lua
└── ...
```

**Se Info.lua NÃO está na raiz:**
- Plugin não vai carregar
- Mover para raiz

---

## 🔍 Teste de Última Instância

Se **NADA** funciona até aqui, fazer este teste:

### **Criar Plugin Dummy Mínimo**

```bash
# Criar pasta nova
mkdir -p ~/Desktop/TestPlugin.lrplugin

# Criar Info.lua
cat > ~/Desktop/TestPlugin.lrplugin/Info.lua << 'EOF'
return {
    LrSdkVersion = 14.5,
    LrPluginName = "Test Plugin",
    LrToolkitIdentifier = "com.test.plugin",
    LrExportMenuItems = {
        {
            title = "TEST MENU",
            file = "test.lua",
        },
    },
}
EOF

# Criar test.lua
cat > ~/Desktop/TestPlugin.lrplugin/test.lua << 'EOF'
local LrDialogs = import 'LrDialogs'
local function main()
    LrDialogs.message("TEST", "IT WORKS!", "info")
end
return main
EOF
```

**Testar:**
1. Lightroom > Plug-in Manager
2. Add > `~/Desktop/TestPlugin.lrplugin`
3. Reiniciar Lightroom
4. File > Plug-in Extras > TEST MENU

**Se este plugin dummy funciona MAS o NSP não:**
- Problema específico no código do NSP
- Provavelmente em Common_V2.lua ou imports

**Se este plugin dummy TAMBÉM não funciona:**
- Problema no Lightroom ou configuração do sistema
- Reinstalar Lightroom pode ser necessário

---

## 📊 Matriz de Decisão

| Sintoma | Causa Provável | Solução |
|---------|----------------|---------|
| Menu não aparece | Plugin não carregado | Passos 1-5 |
| Menu aparece mas não faz nada | Plugin não recarregado | Passo 5 (reiniciar LR) |
| Teste Ultra Simples falha | Problema estrutural | Verificação 3-5 |
| Teste Conexão falha | Servidor offline | Iniciar servidor |
| Todos os testes passam mas preset não funciona | Problema nos modelos | Verificar `./diagnostico.sh` |

---

## 🎯 Checklist Final

Execute TODOS estes passos ANTES de reportar problema:

- [ ] Lightroom FECHADO e REABERTO
- [ ] Plugin REMOVIDO e RE-ADICIONADO
- [ ] Lightroom REINICIADO após adicionar
- [ ] Status no Plug-in Manager = "Enabled"
- [ ] `./diagnostico.sh` mostra 0 problemas
- [ ] Servidor a correr: `python services/server.py`
- [ ] Teste Ultra Simples executado (Passo 6)
- [ ] Teste Conexão executado (Passo 7)
- [ ] Logs monitorizados durante teste

---

## 📸 Screenshots Úteis

**Onde está o Plug-in Manager:**
```
Lightroom Classic 14.5
  File
    ├─ Plug-in Manager...  ← AQUI
    └─ Plug-in Extras
        ├─ ⚡ TESTE ULTRA SIMPLES     ← Deve aparecer
        ├─ 🔧 TESTE DE CONEXÃO        ← Deve aparecer
        └─ AI Preset V2 ...           ← Deve aparecer
```

**Como deve estar o Plug-in Manager:**
```
┌────────────────────────────────────┐
│ Lightroom Plug-in Manager          │
├────────────────────────────────────┤
│ Plug-ins:                          │
│  [✓] NSP Plugin        ← Enabled   │
│      Version: 0.6.0                │
│      Status: Enabled   ← IMPORTANTE│
│      /Users/.../NSP-Plugin.lrplugin│
├────────────────────────────────────┤
│  [Add] [Remove] [Reload]           │
└────────────────────────────────────┘
```

---

**Desenvolvido por:** Nelson Silva
**Data:** 13 de Novembro de 2025
**Versão:** Diagnostic v2.0
