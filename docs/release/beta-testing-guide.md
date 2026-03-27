# 🧪 NSP Plugin - Guia de Beta Testing

**Versão:** 2.0 Beta
**Data:** 24 Novembro 2025
**Audiência:** Beta Testers, Early Adopters, Fotógrafos

---

## 📋 Sumário Executivo

Este documento guia beta testers através do processo de teste do NSP Plugin V2, um sistema de aplicação automática de presets no Adobe Lightroom Classic usando inteligência artificial.

### Objetivos do Beta Testing
1. Validar funcionalidade em diferentes ambientes
2. Identificar bugs e issues críticos
3. Avaliar usabilidade e UX
4. Coletar feedback para melhorias
5. Testar performance com catálogos reais

---

## 🎯 Quem Deve Participar

### Perfil Ideal do Beta Tester
- ✅ Fotógrafo profissional ou entusiasta sério
- ✅ Utilizador regular do Adobe Lightroom Classic
- ✅ Processa 100+ fotos por semana
- ✅ Confortável com tecnologia e novos softwares
- ✅ Disponível para dar feedback detalhado
- ✅ Sistema: macOS 10.14+ ou Windows 10+

### O Que Esperamos de Si
- ⏰ **Tempo:** 2-4 horas/semana por 2-4 semanas
- 💬 **Feedback:** Reportar bugs e sugestões
- 📊 **Dados:** Partilhar estatísticas de uso (opcional, anonimizado)
- 🤝 **Comunicação:** Responder a questionários e surveys

---

## 🚀 Instalação

### Pré-Requisitos
- Adobe Lightroom Classic (versão 10+)
- Python 3.8 ou superior
- 8GB+ RAM (16GB recomendado)
- 5GB espaço livre em disco
- macOS 10.14+ ou Windows 10+

### Instalação Rápida

**macOS/Linux:**
```bash
cd path/to/NSP\ Plugin_dev_full_package
chmod +x install/setup.sh
./install/setup.sh
```

**Windows:**
```cmd
cd path\to\NSP Plugin_dev_full_package
install\setup.bat
```

### Instalação Manual

Ver `GUIA_TESTES_RAPIDO.md` para instruções detalhadas.

---

## 📝 Plano de Testes

### Fase 1: Teste Básico (Semana 1)

**Objetivo:** Validar funcionalidade core

#### Teste 1.1: Single Photo
1. Selecionar 1 foto no Lightroom
2. `File > Plug-in Extras > AI Preset V2`
3. Observar aplicação do preset

**Critérios de Sucesso:**
- ✅ Plugin aplica preset em <5 segundos
- ✅ Ajustes visíveis na foto
- ✅ Sem erros ou crashes

**Reportar:**
- Tempo de processamento
- Qualidade do resultado (1-5 estrelas)
- Screenshots antes/depois

#### Teste 1.2: Small Batch (10-20 fotos)
1. Selecionar 10-20 fotos
2. `File > Plug-in Extras > AI Preset V2`
3. Observar progress bar

**Critérios de Sucesso:**
- ✅ Progress bar mostra percentagem e ETA
- ✅ Lightroom não bloqueia
- ✅ Estatísticas finais corretas

**Reportar:**
- Número de fotos processadas
- Tempo total
- Falhas (se houver)

#### Teste 1.3: Medium Batch (50-100 fotos)
1. Selecionar 50-100 fotos
2. Aplicar AI Preset V2
3. Monitorar performance

**Critérios de Sucesso:**
- ✅ Processa sem erros
- ✅ ETA razoavelmente preciso
- ✅ Memória RAM não excede 4GB

**Reportar:**
- Performance geral
- Uso de memória/CPU (Activity Monitor/Task Manager)
- Quaisquer slowdowns

---

### Fase 2: Teste de Usabilidade (Semana 2)

**Objetivo:** Avaliar experiência do utilizador

#### Teste 2.1: Workflow Real
Use o plugin no seu workflow normal durante 3-5 sessões de edição.

**Avaliar:**
- 📊 **Velocidade:** Economiza tempo vs edição manual?
- 🎨 **Qualidade:** Presets são bons pontos de partida?
- 🔄 **Consistência:** Resultados similares em fotos parecidas?
- 💡 **Intuitividade:** Interface é clara e fácil de usar?

**Questionário:**
1. O plugin integra-se bem no seu workflow? (1-5)
2. Economiza tempo? Quantos minutos por sessão?
3. Confia nos ajustes sugeridos? (1-5)
4. O que mudaria na interface?

#### Teste 2.2: Feedback System
1. Usar preset AI
2. Fazer ajustes manuais
3. `File > Plug-in Extras > NSP – Feedback Rápido`
4. Submeter feedback

**Avaliar:**
- ✅ Processo de feedback é rápido?
- ✅ Tags sugeridas são relevantes?
- ✅ Diálogo é intuitivo?

---

### Fase 3: Teste de Stress (Semana 3)

**Objetivo:** Validar robustez e limites

#### Teste 3.1: Large Batch (200-500 fotos)
1. Selecionar 200-500 fotos
2. Aplicar AI Preset V2
3. Monitorar sistema

**Reportar:**
- ✅ Completa sem crashes?
- ✅ Tempo total
- ✅ Taxa de sucesso (% fotos processadas)
- ❌ Erros encontrados

#### Teste 3.2: Diferentes Tipos de Fotos
Testar com:
- 📷 Retratos
- 🌄 Paisagens
- 🌃 Noturnas
- 🏢 Arquitetura
- 🎉 Eventos
- 📸 Macros

**Avaliar:**
Qualidade dos presets para cada tipo (1-5)

#### Teste 3.3: Edge Cases
- Foto muito escura/clara
- Preto e branco
- Panorama (resolução alta)
- Foto já editada vs RAW
- Diferentes câmaras/marcas

**Reportar:**
Como o sistema lida com casos extremos?

---

### Fase 4: Teste de Longo Prazo (Semana 4)

**Objetivo:** Validar estabilidade e valor a longo prazo

#### Teste 4.1: Uso Continuado
Use o plugin como parte do workflow normal durante toda a semana.

**Métricas:**
- Total de fotos processadas
- Tempo economizado estimado
- % de presets usados sem ajustes
- % que requeriram ajustes mínimos
- % que foram completamente refeitos

#### Teste 4.2: Survey Final
Preencher questionário detalhado sobre experiência geral.

---

## 🐛 Como Reportar Bugs

### Informação Necessária

#### Bug Report Template
```markdown
**Título:** [Descrição breve]

**Severidade:** Crítico / Alta / Média / Baixa

**Descrição:**
[O que aconteceu vs o que deveria acontecer]

**Passos para Reproduzir:**
1. [Passo 1]
2. [Passo 2]
3. [...]

**Ambiente:**
- OS: macOS 12.6 / Windows 11
- Lightroom Classic: v12.5
- Python: 3.10.5
- NSP Plugin: 2.0 Beta

**Screenshots/Logs:**
[Anexar se possível]

**Frequência:**
Sempre / Frequente / Ocasional / Uma vez

**Workaround:**
[Se encontrou algum]
```

### Canais de Comunicação

#### Email
[Seu email de contacto beta]

#### Issue Tracker
[Link para GitHub Issues se aplicável]

#### Slack/Discord
[Link para comunidade beta se existir]

---

## 📊 Métricas e KPIs

### O Que Medimos

#### Performance
- ⏱️ Tempo médio de processamento por foto
- 📈 Throughput (fotos/minuto)
- 💾 Uso de memória
- 🔥 Uso de CPU/GPU

#### Qualidade
- ⭐ Rating médio dos presets (1-5)
- ✅ Taxa de aceitação (% usados sem alterações)
- 🔧 Taxa de ajuste (% com ajustes mínimos)
- ❌ Taxa de rejeição (% completamente refeitos)

#### Usabilidade
- ⏰ Tempo para primeira aplicação bem-sucedida
- 🤔 Número de questões/confusões reportadas
- 📖 Necessidade de consultar documentação
- 😊 NPS (Net Promoter Score)

---

## 🎁 Incentivos para Beta Testers

### O Que Recebe

1. **Acesso Antecipado** - Use features antes do release público
2. **Licença Gratuita** - Versão completa gratuita quando lançar
3. **Suporte Prioritário** - Resposta rápida a questões
4. **Influência** - Seu feedback molda o produto final
5. **Reconhecimento** - Crédito como beta tester (opcional)

### Top Contributors

Beta testers com mais contribuições receberão:
- 🏆 **Beta Tester Badge** no perfil
- 🎁 **Swag** (se aplicável)
- 📢 **Feature** nas redes sociais
- 💰 **Desconto** em produtos futuros

---

## 📅 Timeline

| Semana | Foco | Deliverables |
|--------|------|--------------|
| **1** | Setup + Testes Básicos | Validar instalação, testes core |
| **2** | Usabilidade | Feedback de UX, workflow integration |
| **3** | Stress Testing | Large batches, edge cases |
| **4** | Long-term | Survey final, métricas completas |

**Data Início:** [Data de início do beta]
**Data Fim:** [Data estimada de conclusão]
**Release Público:** [Data estimada]

---

## ❓ FAQ

### Como atualizo para novas versões beta?
Execute `git pull` (se clonou repo) ou substitua ficheiros manualmente.

### Os meus dados são enviados para algum lugar?
Apenas se ativar telemetria (opt-in). Feedback é sempre anónimo.

### Posso usar em projetos comerciais?
Sim, sem restrições durante beta.

### E se encontrar um bug crítico?
Reporte imediatamente via email com tag [CRÍTICO].

### Posso partilhar o plugin com outros?
Não durante beta privado. Apenas beta testers aprovados.

---

## 🙏 Agradecimentos

Obrigado por participar no beta testing do NSP Plugin! Seu feedback é fundamental para criar uma ferramenta que fotógrafos adoram usar.

**Juntos estamos a construir o futuro da edição fotográfica!** 🚀📸

---

## 📞 Contactos

**Beta Program Manager:** [Nome]
**Email:** [Email]
**Support:** [Canal de suporte]
**Documentation:** Ver `MELHORIAS_COMPLETAS_FINAL.md`

---

*Documento versão 1.0 - 24 Novembro 2025*
