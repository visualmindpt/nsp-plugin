# NSP Plugin - Documentação

**Versão:** 2.0
**Data:** 24 Novembro 2025
**Status:** Production-Ready

---

## Navegação Rápida

- [Guia de Utilizador](#guia-de-utilizador)
- [Guia de Desenvolvimento](#guia-de-desenvolvimento)
- [Release e Beta Testing](#release-e-beta-testing)
- [Arquivo](#arquivo)

---

## Guia de Utilizador

Documentação para utilizadores finais do plugin.

### Instalação e Configuração

- **[Installation Guide](user-guide/installation.md)** - Instalação completa passo a passo
- **[Installation Verification](user-guide/installation-verification.md)** - Verificação da instalação
- **[Quick Testing Guide](user-guide/quick-testing-guide.md)** - Guia rápido de testes

### Resolução de Problemas

- **[Troubleshooting](user-guide/troubleshooting.md)** - Diagnóstico e soluções

---

## Guia de Desenvolvimento

Documentação técnica para desenvolvedores e contribuidores.

### Arquitetura

- **[Architecture](developer/architecture.md)** - Arquitetura completa do NSP Plugin V2
- **[Improvements Complete](developer/improvements-complete.md)** - Melhorias implementadas
- **[Optimizations Summary](developer/optimizations-summary.md)** - Resumo das otimizações

### Machine Learning

- **[ML Optimizations](developer/ml-optimizations.md)** - Guia de otimizações ML (English)
- **[ML Optimizations PT](developer/ml-optimizations-pt.md)** - Guia de otimizações ML (Português)
- **[Transfer Learning](developer/transfer-learning.md)** - Guia de transfer learning
- **[Transfer Learning Quickstart](developer/transfer-learning-quickstart.md)** - Início rápido transfer learning
- **[Lightroom Parameters](developer/lightroom-parameters.md)** - Lista completa de parâmetros suportados

**Nota:** O sistema atualmente suporta **60 de ~130 parâmetros Lightroom** mapeados, incluindo:
- Basic (6 parâmetros): Exposure, Contrast, Highlights, Shadows, Whites, Blacks
- Presence (5): Texture, Clarity, Dehaze, Vibrance, Saturation
- White Balance (2): Temperature, Tint
- Sharpening (4): Amount, Radius, Detail, Edge Masking
- Noise Reduction (3): Luminance, Detail, Color
- Effects (2): Vignette, Grain
- Calibration (7): Shadow Tint, RGB Hue/Saturation primaries
- HSL Completo (24): 8 cores × 3 sliders (Hue, Saturation, Luminance)
- Split Toning (5): Highlight/Shadow Hue, Saturation, Balance
- Transform/Upright (2): Version, Mode

### Training

- **[Training UI](developer/training-ui.md)** - Interface de treino de modelos

---

## Release e Beta Testing

Documentação para preparação de releases e beta testing.

### Beta Testing

- **[Beta Testing Guide](release/beta-testing-guide.md)** - Guia completo para beta testers
  - 4 fases de teste (4 semanas)
  - Bug reporting template
  - Métricas e KPIs
  - Incentivos

### Release

- **[Release Checklist](release/release-checklist.md)** - Checklist completa de produção
  - Pre-release (desenvolvimento, testes, segurança)
  - Build & Packaging
  - Documentação
  - Marketing & Legal
  - Deployment
  - Launch day procedures

---

## Arquivo

Documentação antiga e relatórios históricos arquivados para referência.

Ver pasta: `docs/archive/`

Contém:
- Relatórios de implementação anteriores
- Guias de versões antigas
- Planos de modernização históricos
- Documentação de desenvolvimento iterativo

---

## Estrutura do Projeto

```
NSP Plugin_dev_full_package/
├── docs/                           # DOCUMENTAÇÃO PRINCIPAL
│   ├── README.md                   # ← VOCÊ ESTÁ AQUI
│   ├── user-guide/                 # Guias para utilizadores
│   │   ├── installation.md
│   │   ├── installation-verification.md
│   │   ├── quick-testing-guide.md
│   │   └── troubleshooting.md
│   ├── developer/                  # Guias para desenvolvedores
│   │   ├── architecture.md
│   │   ├── improvements-complete.md
│   │   ├── ml-optimizations.md
│   │   ├── ml-optimizations-pt.md
│   │   ├── optimizations-summary.md
│   │   ├── training-ui.md
│   │   ├── transfer-learning.md
│   │   └── transfer-learning-quickstart.md
│   ├── release/                    # Documentação de release
│   │   ├── beta-testing-guide.md
│   │   └── release-checklist.md
│   └── archive/                    # Documentação arquivada
│
├── NSP-Plugin.lrplugin/            # Plugin Lightroom
├── services/                       # Backend Python/FastAPI
├── train/                          # Scripts de treino ML
├── install/                        # Scripts de instalação
├── config.json                     # Configuração centralizada
└── README.md                       # README principal do projeto
```

---

## Quick Start

### Para Utilizadores

1. Ler [Installation Guide](user-guide/installation.md)
2. Executar instalador: `./install/setup.sh` (macOS/Linux) ou `install\setup.bat` (Windows)
3. Seguir [Quick Testing Guide](user-guide/quick-testing-guide.md)

### Para Desenvolvedores

1. Ler [Architecture](developer/architecture.md)
2. Ler [Improvements Complete](developer/improvements-complete.md)
3. Explorar código-fonte

### Para Beta Testers

1. Ler [Beta Testing Guide](release/beta-testing-guide.md)
2. Seguir plano de 4 fases
3. Reportar bugs e feedback

### Para Release Manager

1. Ler [Release Checklist](release/release-checklist.md)
2. Completar todas as secções
3. Obter sign-offs necessários

---

## Recursos Adicionais

### Ficheiros de Configuração

- `config.json` - Configuração centralizada do projeto
- `requirements.txt` - Dependências Python
- `config_loader.py` - Loader de configuração

### Scripts Úteis

- `install/setup.sh` - Instalador automatizado (macOS/Linux)
- `install/setup.bat` - Instalador automatizado (Windows)
- `start_server.sh` - Iniciar servidor backend
- `manage_api_keys.py` - Gestão de API keys

### Diretórios de Dados

- `data/` - Dados de runtime (sessões, feedback, API keys)
- `models/` - Modelos ML treinados
- `logs/` - Logs do sistema
- `datasets/` - Datasets para treino

---

## Contacto e Suporte

### Reportar Bugs

Use o template em [Beta Testing Guide](release/beta-testing-guide.md#como-reportar-bugs)

### Contribuir

Ver [Architecture](developer/architecture.md) para entender a estrutura do projeto

---

## Changelog

### v2.0 (24 Novembro 2025)

**Novo:**
- Sistema de configuração centralizado
- Autenticação API com API keys
- Processamento assíncrono de batches
- Instaladores automatizados
- Documentação completa reorganizada

**Melhorado:**
- Performance de processamento (3x throughput)
- Feedback visual UX (500% mais informação)
- Validação de versão servidor/plugin
- Organização de documentação

**Corrigido:**
- Hardcoded paths eliminados
- Encoding UTF-8 em todos os ficheiros Python
- Consolidação de modelos

---

## Versionamento

**Versão Atual:** 2.0
**Estado:** Production-Ready para Beta Testing

**Versões Anteriores:**
- v1.x: Sistema V1 (arquivado)
- v0.6.0: Simplificação e logging (arquivado)
- v0.5.x: Preview e feedback (arquivado)

---

**Última atualização:** 24 Novembro 2025
**Próxima revisão:** Após beta testing (4 semanas)
