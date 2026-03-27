# Como Recarregar o Plugin no Lightroom

## ✅ Problema Resolvido

Os ficheiros de feedback foram corrigidos. Agora precis as de recarregar o plugin no Lightroom.

---

## 🔄 Passos para Recarregar

### Método 1: Recarregar Plugin (Recomendado)

1. **Abrir Lightroom**

2. **Ir para File → Plug-in Manager**
   - No Mac: `Lightroom Classic → Plug-in Manager...`
   - Atalho: `Cmd + Option + Shift + ,`

3. **Selecionar "NSP Plugin" na lista**

4. **Clicar no botão "Reload Plugin"** (no canto inferior direito)

5. **Verificar que não há erros**
   - Se aparecerem erros, copiar e enviar para debug

6. **Clicar "Done"**

---

### Método 2: Remover e Adicionar (Se Reload não funcionar)

1. **Ir para File → Plug-in Manager**

2. **Selecionar "NSP Plugin"**

3. **Clicar "Remove"**

4. **Clicar "Add"**

5. **Navegar para:**
   ```
   /Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/NSP-Plugin.lrplugin
   ```

6. **Selecionar a pasta e clicar "Select Folder"**

7. **Verificar que carrega sem erros**

8. **Clicar "Done"**

---

### Método 3: Reiniciar Lightroom (Última opção)

Se os métodos anteriores não funcionarem:

1. **Fechar Lightroom completamente** (`Cmd + Q`)

2. **Aguardar 5 segundos**

3. **Abrir Lightroom novamente**

4. **Verificar File → Plug-in Manager** para confirmar que carregou sem erros

---

## ✅ Como Verificar que Funcionou

Após recarregar, verifica que os seguintes menus aparecem sem erros:

- ✅ **Library → Plug-in Extras:**
  - NSP – Get AI Edit
  - NSP – Enviar Feedback (Diálogo)
  - NSP – Marcar como BOA
  - NSP – Marcar como PRECISA CORREÇÃO

Se todos aparecerem, **está tudo OK**!

---

## ⚠️ Se Ainda Houver Erros

Se continuares a ver erros após recarregar:

1. **Ir para File → Plug-in Manager**

2. **Selecionar "NSP Plugin"**

3. **Clicar em "Status"** (no canto inferior direito)

4. **Copiar TODOS os erros** que aparecerem

5. **Enviar os erros** para análise

---

## 🎯 Alterações Feitas

**Versão atualizada:** v0.5.0

**Correções:**
- ✅ Main.lua: Proteção contra erros ao carregar ImplicitFeedback
- ✅ FeedbackGood.lua: Versão simplificada funcional
- ✅ FeedbackNeedsCorrection.lua: Versão simplificada funcional
- ✅ FeedbackUI.lua: Interface completa de feedback
- ✅ Info.lua: Versão incrementada para forçar recarga

**Nota:** As funcionalidades de feedback estão em modo "placeholder" - mostram mensagens mas ainda não enviam dados para o servidor. Isto será implementado na próxima fase.

---

## 📝 Testar Funcionalidade Básica

Após recarregar:

1. **Selecionar 1 foto no Lightroom**

2. **Library → Plug-in Extras → NSP – Get AI Edit**

3. **Verificar que aplica edições AI** (deve funcionar normalmente)

4. **Testar menu de feedback:**
   - Library → Plug-in Extras → NSP – Marcar como BOA
   - Deve aparecer uma mensagem de confirmação

Se tudo isto funcionar, **plugin está operacional**! 🎉
