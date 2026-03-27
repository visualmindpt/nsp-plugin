# Guia de Teste Passo-a-Passo - NSP Plugin Simplificado

## PREPARAÇÃO

### 1. Reiniciar Lightroom e Recarregar Plugin

```
a) Fechar Lightroom Classic completamente
b) Abrir Lightroom Classic
c) File > Plug-in Manager
d) Verificar que "NSP Plugin" está listado e ativado
e) Se necessário, clicar "Reload" ou "Remove" + "Add" novamente
f) Fechar Plug-in Manager
```

### 2. Verificar Localização dos Logs

**macOS:**
```bash
cd ~/Library/Logs/LrClassicLogs/
ls -la | grep NSPPlugin
```

**Ficheiros esperados:**
- `NSPPlugin.ApplyAIPresetV2.log`
- `NSPPlugin.CommonV2.log`
- `NSPPlugin.TestApplySettings.log`

**DICA:** Abrir uma janela Terminal e executar:
```bash
tail -f ~/Library/Logs/LrClassicLogs/NSPPlugin.*.log
```
Isto mostra os logs em tempo real enquanto testa!

---

## TESTE 1: TESTE HARDCODED (Isolar o SDK)

**Objetivo:** Confirmar que `photo:applyDevelopSettings()` funciona independentemente da predição AI.

### Passo 1: Preparar Foto de Teste

```
1. No Lightroom, selecionar UMA foto RAW
2. IMPORTANTE: Usar uma foto de TESTE (valores extremos serão aplicados!)
3. Anotar o estado atual da foto (exposure, temperatura, etc.)
```

### Passo 2: Executar Teste Hardcoded

```
1. File > Plug-in Extras > 🧪 TESTE APPLY SETTINGS (HARDCODED)
   OU
   Library > Plug-in Extras > 🧪 TESTE APPLY SETTINGS (HARDCODED)

2. Aguardar execução (1-2 segundos)

3. Observar diálogo de resultado
```

### Passo 3: Interpretar Resultado

#### ✅ RESULTADO ESPERADO: SUCESSO

**Diálogo mostra:**
```
Teste Concluído - SUCESSO

Settings hardcoded aplicados com SUCESSO!

A foto deve estar:
• Muito clara (+2 EV)
• Muito laranja (temp 8000K)
• Muito saturada

Se vê estas mudanças, o Lightroom SDK está a funcionar!
```

**Verificação visual da foto:**
- ✅ Foto ficou MUITO mais clara
- ✅ Foto ficou com tom LARANJA forte
- ✅ Cores muito saturadas e vibrantes

**No painel Develop do Lightroom, verificar:**
- Exposure: +2.0
- Contrast: +50
- Temp: 8000K
- Saturation: +50
- Hue (Red): +50
- Saturation (Red): +50

**Logs mostram:**
```
✅ TESTE PASSOU: Todos os settings foram aplicados corretamente!
   ✅ Exposure2012       | Esperado: 2.0      | Atual: 2.0
   ✅ Contrast2012       | Esperado: 50       | Atual: 50
   ✅ Temperature        | Esperado: 8000     | Atual: 8000
   ✅ Saturation         | Esperado: 50       | Atual: 50
   ✅ HueAdjustmentRed   | Esperado: 50       | Atual: 50
   ✅ SaturationAdjustmentRed | Esperado: 50  | Atual: 50
```

**Conclusão:** 🎉 Lightroom SDK funciona perfeitamente!

**Próximo passo:** Ir para TESTE 2 (predição AI real)

---

#### ❌ RESULTADO INESPERADO: FALHA

**Diálogo mostra:**
```
Teste Concluído - FALHA

ATENÇÃO: Alguns settings NÃO foram aplicados!

Isto indica um problema com:
1. Lightroom SDK (applyDevelopSettings não funciona)
2. Permissões do plugin
3. Tipo de ficheiro da foto

Consulte o log para detalhes.
```

**Verificação visual da foto:**
- ❌ Foto NÃO mudou
- ❌ OU mudou parcialmente (alguns settings aplicados, outros não)

**Logs mostram:**
```
❌ TESTE FALHOU: Alguns settings NÃO foram aplicados!
   ❌ Exposure2012       | Esperado: 2.0      | Atual: 0.0
   ❌ Contrast2012       | Esperado: 50       | Atual: 0
   ...
```

**Diagnóstico:**

1. **Verificar tipo de ficheiro:**
   - Foto é RAW ou JPG?
   - Foto é "virtual copy"?
   - Foto está read-only?

2. **Tentar com outra foto:**
   - Selecionar uma foto RAW diferente
   - Repetir teste

3. **Verificar permissões:**
   - Plug-in Manager > NSP Plugin > Status
   - Verificar se há avisos de permissões

4. **Reportar problema:**
   - Anotar tipo de ficheiro
   - Anotar versão do Lightroom
   - Anexar logs completos

**IMPORTANTE:** Se este teste falhar, NÃO adianta testar predição AI!
O problema está no Lightroom SDK ou permissões.

---

## TESTE 2: PREDIÇÃO AI REAL (Fluxo Completo)

**Pré-requisito:** TESTE 1 deve ter passado com sucesso!

**Objetivo:** Confirmar que predições AI são aplicadas corretamente.

### Passo 1: Preparar Servidor

```
1. Abrir Terminal
2. Navegar para diretório do servidor:
   cd ~/Documentos/gemini/projetos/nsp_ai_model_v2/

3. Iniciar servidor:
   ./start_server.sh

4. Aguardar mensagem:
   "✅ Servidor NSP AI V2 pronto na porta 5678"
```

**OU usar o menu do plugin:**
```
File > Plug-in Extras > 🚀 Iniciar Servidor AI
```

### Passo 2: Selecionar Foto e Resetar

```
1. No Lightroom, selecionar UMA foto
2. IMPORTANTE: Resetar develop settings primeiro!
   - Painel Develop > Settings > Reset
   - Isto garante que foto está em estado "neutro"
3. Anotar estado inicial (todos valores devem estar em 0)
```

### Passo 3: Aplicar Preset AI

```
1. File > Plug-in Extras > AI Preset V2 - Foto Individual
   OU
   Library > Plug-in Extras > AI Preset V2 - Foto Individual

2. Aguardar execução (5-10 segundos dependendo do servidor)

3. Observar:
   - NÃO aparece diálogo de preview (foi removido!)
   - Aparece apenas confirmação: "✅ Preset AI aplicado!"
```

### Passo 4: Verificar Aplicação

**Verificação visual:**
- Foto deve ter mudado visivelmente
- Ajustes de exposição, cor, contraste aplicados

**No painel Develop:**
- Verificar que valores NÃO estão todos em 0
- Deve haver mudanças em vários sliders

**Exemplos esperados:**
```
Exposure: -0.5 ou +1.2 (algum valor não-zero)
Contrast: +15 ou -20
Temperature: 5800K ou 6500K (não 5500K padrão)
Saturation: +10 ou -5
etc.
```

### Passo 5: Analisar Logs Detalhados

**Abrir log:**
```bash
tail -200 ~/Library/Logs/LrClassicLogs/NSPPlugin.ApplyAIPresetV2.log
```

**Procurar secções específicas:**

#### 5.1. Verificar Predição Recebida

```
✅ Predição recebida com sucesso:
   → Preset ID: 2
   → Confiança: 0.87
   → Prediction DB ID: 123
   → Número de sliders recebidos: 38
```

**Verificar:**
- ✅ Preset ID recebido (0, 1, 2, 3)
- ✅ Confiança > 0.5
- ✅ Número de sliders = 38 (modelo atual)

#### 5.2. Verificar Sliders Recebidos do Servidor

```
━━━ SLIDERS RECEBIDOS DO SERVIDOR (ANTES DO MAPEAMENTO) ━━━
   [01] Python: exposure                   = 1.2
   [02] Python: contrast                   = 15
   [03] Python: highlights                 = -30
   [04] Python: shadows                    = 25
   [05] Python: temp                       = 5800
   [06] Python: tint                       = 5
   [07] Python: saturation                 = 10
   [08] Python: vibrance                   = 15
   [09] Python: red_hue                    = -10
   [10] Python: red_saturation             = 20
   ...
   [38] Python: grain                      = 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Verificar:**
- ✅ 38 sliders listados
- ✅ Nomes corretos (exposure, contrast, temp, etc.)
- ✅ Valores parecem razoáveis

#### 5.3. Verificar Mapeamento

```
build_develop_settings: SAÍDA
   → Total sliders recebidos: 38
   → Total sliders mapeados: 38
   → Total sliders NÃO mapeados: 0
✅ Todos os sliders foram mapeados com sucesso!
```

**Verificar:**
- ✅ Total mapeados = Total recebidos (38 = 38)
- ✅ Total NÃO mapeados = 0
- ✅ Mensagem de sucesso presente

**⚠️ SE houver sliders não mapeados:**
```
⚠️  ATENÇÃO: 3 sliders NÃO foram mapeados:
      [1] orange_hue
      [2] orange_saturation
      [3] orange_luminance
   → Estes sliders foram IGNORADOS e NÃO serão aplicados!
```

**Ação:** Estes sliders precisam ser adicionados ao `DEVELOP_MAPPING` em `Common_V2.lua`

#### 5.4. Verificar Settings Finais

```
━━━ DEVELOP SETTINGS FINAIS (PARA APLICAR AO LIGHTROOM) ━━━
   [01] Lightroom: Exposure2012                           = 1.2
   [02] Lightroom: Contrast2012                           = 15
   [03] Lightroom: Highlights2012                         = -30
   [04] Lightroom: Shadows2012                            = 25
   [05] Lightroom: Temperature                            = 5800
   [06] Lightroom: Tint                                   = 5
   [07] Lightroom: Saturation                             = 10
   [08] Lightroom: Vibrance                               = 15
   [09] Lightroom: HueAdjustmentRed                       = -10
   [10] Lightroom: SaturationAdjustmentRed                = 20
   ...
   [38] Lightroom: GrainAmount                            = 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Verificar:**
- ✅ 38 settings listados
- ✅ Nomes Lightroom corretos (Exposure2012, Temperature, etc.)
- ✅ Valores coincidem com sliders Python

#### 5.5. Verificar Aplicação

```
🎯 PRESTES A APLICAR DEVELOP SETTINGS À FOTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Total de settings a aplicar: 38

📋 LISTA COMPLETA DE TODOS OS SETTINGS:
   [01] Exposure2012                        = 1.2
   [02] Contrast2012                        = 15
   ...

🚀 A chamar photo:applyDevelopSettings() agora...
✅ photo:applyDevelopSettings() executado com sucesso!
```

**Verificar:**
- ✅ Total de settings = 38
- ✅ Execução bem-sucedida

#### 5.6. Verificar Confirmação Pós-Aplicação

```
🔍 VERIFICAÇÃO PÓS-APLICAÇÃO:
   ✅ Exposure2012       | Esperado: 1.2      | Atual: 1.2
   ✅ Contrast2012       | Esperado: 15       | Atual: 15
   ✅ Temperature        | Esperado: 5800     | Atual: 5800
   ✅ Saturation         | Esperado: 10       | Atual: 10
   ✅ HueAdjustmentRed   | Esperado: -10      | Atual: -10
   ✅ SaturationAdjustmentRed | Esperado: 20  | Atual: 20
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Verificar:**
- ✅ Todos os settings críticos têm ✅
- ✅ Valores esperados = Valores atuais

**⚠️ SE houver ❌:**
```
   ❌ Exposure2012       | Esperado: 1.2      | Atual: 0.0
```

**Diagnóstico:**
- Settings NÃO foram aplicados
- Possível clamping de valores
- Problema com tipo de dados

---

## INTERPRETAÇÃO DE RESULTADOS

### ✅ CENÁRIO 1: Tudo Funciona Perfeitamente

**Sintomas:**
- Teste hardcoded passa
- Predição AI aplica settings
- Logs mostram 38/38 mapeados
- Verificação pós-aplicação: todos ✅
- Foto muda visivelmente

**Conclusão:** 🎉 Plugin está a funcionar 100%!

**Próximo passo:** Testar em múltiplas fotos, afinar modelo AI

---

### ⚠️ CENÁRIO 2: Teste Hardcoded Passa, AI Não Aplica

**Sintomas:**
- Teste hardcoded: ✅ SUCESSO
- Predição AI: foto NÃO muda
- Logs mostram sliders recebidos
- Mas settings não são aplicados

**Diagnóstico:** Problema no parsing/mapeamento

**Verificar nos logs:**

1. **Sliders não mapeados:**
   ```
   ⚠️  ATENÇÃO: 10 sliders NÃO foram mapeados:
         [1] some_slider_name
   ```
   **Solução:** Adicionar mapeamentos em `Common_V2.lua`

2. **Settings vazios:**
   ```
   ❌ CRÍTICO: Nenhum slider foi mapeado! settings está VAZIO!
   ```
   **Solução:** Verificar nomes dos sliders do servidor

3. **Valores iguais a 0:**
   ```
   [01] Lightroom: Exposure2012 = 0
   [02] Lightroom: Contrast2012 = 0
   ...
   ```
   **Solução:** Servidor está a retornar zeros, verificar modelo AI

---

### ❌ CENÁRIO 3: Teste Hardcoded Falha

**Sintomas:**
- Teste hardcoded: ❌ FALHA
- Foto não muda com valores extremos
- Predição AI também não funciona

**Diagnóstico:** Problema no Lightroom SDK ou permissões

**Soluções:**

1. **Testar com foto diferente:**
   - Usar RAW em vez de JPG
   - Não usar virtual copy
   - Verificar que foto não está read-only

2. **Verificar plugin:**
   - Recarregar plugin
   - Remover e adicionar novamente
   - Verificar versão do Lightroom (mínimo: SDK 14.5)

3. **Verificar logs de erro:**
   - Procurar mensagens de erro
   - Verificar stack traces

---

## RESUMO: CHECKLIST DE VERIFICAÇÃO

### ✅ Pré-Teste
- [ ] Lightroom reiniciado
- [ ] Plugin recarregado
- [ ] Logs acessíveis (`tail -f` em execução)
- [ ] Foto de teste selecionada

### ✅ Teste Hardcoded
- [ ] Executado
- [ ] Resultado: SUCESSO ou FALHA
- [ ] Foto mudou visivelmente (se sucesso)
- [ ] Logs verificados

### ✅ Teste Predição AI
- [ ] Servidor iniciado e online
- [ ] Foto resetada para estado neutro
- [ ] Preset AI aplicado
- [ ] Foto mudou visivelmente
- [ ] Logs completos analisados:
  - [ ] 38 sliders recebidos
  - [ ] 38/38 mapeados (0 não mapeados)
  - [ ] 38 settings aplicados
  - [ ] Verificação pós-aplicação: todos ✅

### ✅ Diagnóstico (se houver problemas)
- [ ] Tipo de problema identificado
- [ ] Logs relevantes extraídos
- [ ] Soluções tentadas
- [ ] Resultado reportado

---

## COMANDOS ÚTEIS

### Verificar Logs em Tempo Real
```bash
tail -f ~/Library/Logs/LrClassicLogs/NSPPlugin.*.log
```

### Limpar Logs Antigos
```bash
rm ~/Library/Logs/LrClassicLogs/NSPPlugin.*.log
```

### Extrair Secção Específica do Log
```bash
grep -A 50 "PRESTES A APLICAR DEVELOP SETTINGS" ~/Library/Logs/LrClassicLogs/NSPPlugin.ApplyAIPresetV2.log
```

### Procurar Erros
```bash
grep "❌\|ERROR\|FALHA\|CRÍTICO" ~/Library/Logs/LrClassicLogs/NSPPlugin.*.log
```

### Contar Sliders Mapeados
```bash
grep "Total sliders mapeados:" ~/Library/Logs/LrClassicLogs/NSPPlugin.CommonV2.log | tail -1
```

---

**Boa sorte com os testes! 🚀**
