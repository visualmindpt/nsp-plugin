# 🚨 CAPTURAR O ERRO DO LIGHTROOM

**Situação:** Plugin mostra erro UMA VEZ, depois nada funciona mais.

---

## 🎯 OBJETIVO

Capturar a mensagem de erro EXATA para identificar o problema.

---

## 📋 MÉTODO 1: Logs do Lightroom (PREFERIDO)

### **Passo 1: Localizar Logs**

```bash
# Verificar onde estão os logs
ls -lt ~/Library/Logs/Adobe/Lightroom/ 2>/dev/null | head -5
ls -lt ~/Library/Logs/LrClassicLogs/ 2>/dev/null | head -5

# Se nada aparecer, procurar em todas as localizações
find ~/Library/Logs -name "*Lightroom*" -o -name "*lightroom*" 2>/dev/null
```

### **Passo 2: Monitorizar Logs EM TEMPO REAL**

Abrir **2 terminais lado a lado**:

**Terminal 1: Logs Gerais**
```bash
tail -f ~/Library/Logs/Adobe/Lightroom/*.log 2>/dev/null
```

**Terminal 2: Logs do Plugin**
```bash
tail -f ~/Library/Logs/LrClassicLogs/*.log 2>/dev/null | grep -i "nsp\|error\|fatal"
```

### **Passo 3: Forçar o Erro**

1. Posicionar terminais e Lightroom **lado a lado** (ver os 3 simultaneamente)
2. **⌘Q** (Fechar Lightroom)
3. Aguardar 5 segundos
4. Reabrir Lightroom
5. **OBSERVAR TERMINAIS** enquanto Lightroom carrega
6. Quando Lightroom abrir, clicar: **File > Plug-in Extras > 🟢 TESTE MÍNIMO**
7. **COPIAR IMEDIATAMENTE** qualquer mensagem que aparecer nos terminais

### **Passo 4: Se Erro Aparecer no Lightroom**

Se aparecer um popup de erro no Lightroom:
1. **NÃO FECHAR** o popup
2. **Ler TODA a mensagem**
3. Tirar **SCREENSHOT** (⌘⇧4)
4. Copiar texto manualmente se possível

---

## 📋 MÉTODO 2: Console.app (macOS)

Se logs não mostrarem nada:

1. Abrir **Console.app** (Applications > Utilities > Console)
2. No lado esquerdo: **System Reports**
3. Clicar em **Clear** para limpar
4. No Lightroom: Tentar executar o plugin
5. Voltar ao Console.app
6. Procurar por mensagens novas
7. Filtrar por: "Lightroom" ou "NSP"

---

## 📋 MÉTODO 3: Forçar Erro de Propósito

Vou criar um ficheiro que **deliberadamente** gera um erro controlado:

```bash
cd "/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin"

# Criar teste com erro proposital
cat > TestError.lua << 'EOF'
local LrDialogs = import 'LrDialogs'
local LrLogger = import 'LrLogger'

local logger = LrLogger('TestError')
logger:enable("logfile")

local function main()
    logger:info("========================================")
    logger:info("TESTE DE ERRO - Iniciando...")
    logger:info("========================================")

    -- Tentar várias operações para ver qual falha

    -- 1. Teste básico
    logger:info("1. Teste básico de dialog...")
    local ok1 = pcall(function()
        LrDialogs.message("TESTE 1", "Dialog básico funciona", "info")
    end)
    logger:info("   Resultado: " .. (ok1 and "OK" or "FALHOU"))

    -- 2. Teste de require JSON
    logger:info("2. Teste de require JSON...")
    local ok2, JSON = pcall(require, 'json')
    logger:info("   Resultado: " .. (ok2 and "OK" or "FALHOU - " .. tostring(JSON)))

    if ok2 then
        logger:info("   JSON.encode existe: " .. tostring(JSON.encode ~= nil))
        logger:info("   JSON.decode existe: " .. tostring(JSON.decode ~= nil))
    end

    -- 3. Teste de require Common_V2
    logger:info("3. Teste de require Common_V2...")
    local ok3, Common = pcall(require, 'Common_V2')
    logger:info("   Resultado: " .. (ok3 and "OK" or "FALHOU - " .. tostring(Common)))

    -- Mostrar resultado final
    local message = string.format(
        "RESULTADOS DOS TESTES:\n\n" ..
        "1. Dialog básico: %s\n" ..
        "2. JSON require: %s\n" ..
        "3. Common_V2 require: %s\n\n" ..
        "Ver logs para detalhes!",
        ok1 and "✅" or "❌",
        ok2 and "✅" or "❌",
        ok3 and "✅" or "❌"
    )

    LrDialogs.message("TESTE DE ERRO - Resultados", message, "info")

    logger:info("========================================")
    logger:info("TESTE DE ERRO - Concluído")
    logger:info("========================================")
end

return main
EOF
```

Depois adicionar ao Info.lua e testar.

---

## 📋 MÉTODO 4: Criar Plugin de Teste Separado

Criar um plugin **completamente novo** e minimalista:

```bash
cd ~/Desktop

# Criar plugin teste
mkdir -p TestPlugin.lrplugin

# Info.lua
cat > TestPlugin.lrplugin/Info.lua << 'EOF'
return {
    LrSdkVersion = 14.5,
    LrPluginName = "Test Plugin",
    LrToolkitIdentifier = "com.test.minimal",
    VERSION = { major=1, minor=0, revision=0 },
    LrExportMenuItems = {
        {
            title = "TEST - Show Alert",
            file = "test.lua",
        },
    },
}
EOF

# test.lua
cat > TestPlugin.lrplugin/test.lua << 'EOF'
local LrDialogs = import 'LrDialogs'
local function main()
    LrDialogs.message("TEST", "This is a test plugin!\n\nIf you see this, Lightroom plugins work on your system.", "info")
end
return main
EOF

echo "✅ Plugin de teste criado em ~/Desktop/TestPlugin.lrplugin"
```

**Testar:**
1. Lightroom > Plug-in Manager
2. Add > `~/Desktop/TestPlugin.lrplugin`
3. File > Plug-in Extras > TEST - Show Alert

**Se este funciona MAS o NSP não:**
- Problema específico no código do NSP
- Provavelmente no Common_V2.lua ou imports

**Se este TAMBÉM não funciona:**
- Problema no Lightroom ou sistema
- Pode precisar reinstalar Lightroom

---

## 🔍 ERROS COMUNS E MENSAGENS

### Erro: "module 'json' not found"
**Causa:** json.lua não está no diretório do plugin
**Solução:** Verificar que json.lua existe em NSP-Plugin.lrplugin/

### Erro: "attempt to call a nil value"
**Causa:** Função ou módulo não existe
**Solução:** Verificar imports e requires

### Erro: "FATAL: Módulo JSON não foi carregado corretamente"
**Causa:** json.lua não retorna encode/decode
**Solução:** Verificar conteúdo de json.lua

### Erro: Lightroom crash completo (sem mensagem)
**Causa:** Erro grave de memória ou loop infinito
**Solução:** Verificar código não tem loops no top-level

---

## 📊 Checklist de Informação para Reportar

Quando conseguires capturar o erro, reporta:

- [ ] Mensagem de erro EXATA (copiar texto ou screenshot)
- [ ] Quando apareceu (ao carregar plugin? ao clicar menu?)
- [ ] Output de `tail logs/*.log`
- [ ] Qual teste estavas a executar (TESTE MÍNIMO, TESTE ULTRA SIMPLES, etc.)
- [ ] Versão do Lightroom (Help > System Info)
- [ ] Versão do macOS (⌘ > About This Mac)
- [ ] Output de `./diagnostico.sh`

---

## 🎯 PRÓXIMOS PASSOS

Dependendo do erro encontrado:

### Se erro for "module 'json' not found":
→ Corrigir path de json.lua

### Se erro for "module 'Common_V2' not found":
→ Problema de estrutura de pastas

### Se erro for no Common_V2.lua (linha específica):
→ Corrigir essa linha específica

### Se erro for "attempt to call a nil value":
→ Identificar qual função está nil

---

**OBJETIVO:** Obter mensagem EXATA tipo:
```
Error in module Common_V2.lua:18: attempt to call field 'encode' (a nil value)
```

Com isto consigo corrigir **imediatamente**.

---

**Desenvolvido por:** Nelson Silva
**Data:** 13 de Novembro de 2025
