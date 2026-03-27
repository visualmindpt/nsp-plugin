# Sistema de Gestão de Presets - NSP Plugin

**Data:** 14 de Novembro de 2025
**Estado:** ✅ Implementado e Testado

---

## Resumo Executivo

Implementação completa do sistema de gestão de presets para o NSP Plugin, conforme especificação do `PRESET_MARKETPLACE.md`. O sistema permite criar, instalar, gerir e exportar presets (pacotes de modelos ML + configurações) em formato `.nsppreset`.

---

## Componentes Implementados

### 1. **services/preset_package.py**
Classe responsável por criar e extrair packages `.nsppreset` (formato ZIP).

**Funcionalidades:**
- Criar package a partir de diretório
- Extrair package para diretório
- Validar estrutura e integridade (SHA256)
- Verificar path traversal e segurança
- Limite de tamanho (100MB)

**Classes:**
- `PresetPackage`: Classe principal para gestão de packages
- `PresetPackageError`: Excepção para erros de package
- `create_preview_images()`: Função para criar previews optimizados

**Ficheiros obrigatórios no package:**
```
manifest.json
models/
  - classifier.pth
  - refinement.pth
  - preset_centers.json
  - scaler_stat.pkl
  - scaler_deep.pkl
  - scaler_deltas.pkl
  - delta_columns.json
previews/
  - thumbnail.jpg (400x400)
  - hero.jpg (1920x1080)
signature.sha256
```

---

### 2. **services/preset_manager.py**
Gestor principal de presets com todas as operações CRUD.

**Funcionalidades:**
- `list_presets()`: Lista todos os presets instalados
- `get_preset(preset_id)`: Obtém detalhes de um preset
- `install_preset(nsppreset_path)`: Instala preset .nsppreset
- `uninstall_preset(preset_id)`: Remove preset instalado
- `export_preset(preset_id, output_path)`: Exporta preset como .nsppreset
- `create_preset_package()`: Cria package a partir de modelos
- `validate_preset(nsppreset_path)`: Valida integridade de package
- `get_active_preset()`: Obtém preset actualmente activo
- `set_active_preset(preset_id)`: Define preset activo
- `ensure_default_preset_exists()`: Garante que preset default existe

**Classes:**
- `PresetManager`: Gestor principal
- `PresetNotFoundError`: Excepção para preset não encontrado
- `PresetAlreadyInstalledError`: Excepção para preset já instalado

**Estrutura de Pastas:**
```
presets/
├── default/              # Preset default do sistema
│   ├── manifest.json
│   ├── models/
│   ├── previews/
│   └── docs/
├── installed/            # Presets instalados
│   └── {preset_id}/
│       ├── manifest.json
│       ├── models/
│       ├── previews/
│       └── docs/
└── active_preset.json    # Configuração do preset activo
```

---

### 3. **services/server.py - Endpoints REST**
API REST para gestão de presets integrada no servidor FastAPI.

**Endpoints Implementados:**

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/presets` | Lista todos os presets instalados |
| GET | `/api/presets/{id}` | Obtém detalhes de preset específico |
| POST | `/api/presets/install` | Upload e instala ficheiro .nsppreset |
| DELETE | `/api/presets/{id}` | Remove preset instalado |
| GET | `/api/presets/active` | Obtém preset actualmente activo |
| PUT | `/api/presets/active` | Define preset activo |
| POST | `/api/presets/export` | Exporta preset como .nsppreset |

**Rate Limits:**
- Listagem: 30 req/min
- Detalhes: 30 req/min
- Instalação: 5 req/min
- Remoção: 10 req/min
- Export: 5 req/min

**Inicialização Automática:**
- PresetManager inicializado no startup do servidor
- Preset default criado automaticamente se não existir

---

### 4. **tools/create_preset_package.py**
Script CLI para criar packages .nsppreset a partir de modelos treinados.

**Uso:**
```bash
python tools/create_preset_package.py \
    --name "Nelson Silva Cinematic" \
    --author "Nelson Silva" \
    --email "nelson@example.com" \
    --models models/ \
    --previews previews/ \
    --output nelson_silva_cinematic.nsppreset
```

**Argumentos:**
- `--name`: Nome do preset (obrigatório)
- `--models`: Diretório com modelos (obrigatório)
- `--output`: Ficheiro .nsppreset a criar (obrigatório)
- `--author`: Nome do autor (default: Unknown)
- `--email`: Email do autor
- `--website`: Website do autor
- `--description`: Descrição do preset
- `--category`: Categoria (Professional, Wedding, Portrait, etc.)
- `--tags`: Tags separadas por vírgula
- `--previews`: Diretório com imagens para previews
- `--license`: Tipo de licença (free, commercial, single-user)
- `--price`: Preço em EUR
- `--version`: Versão do preset (default: 1.0.0)
- `--verbose`: Modo verbose

---

### 5. **NSP-Plugin.lrplugin/PresetManager.lua**
Interface Lua para gestão de presets no Lightroom.

**Funções de API:**
```lua
local PresetManager = require 'PresetManager'

-- Listar presets instalados
local presets, error = PresetManager.listPresets()

-- Obter detalhes de preset
local preset, error = PresetManager.getPresetDetail(presetId)

-- Obter preset activo
local activePreset, error = PresetManager.getActivePreset()

-- Definir preset activo
local success, error = PresetManager.setActivePreset(presetId)

-- Aplicar preset a foto
local success, error = PresetManager.applyPresetById(presetId, photo)
```

**Funções de UI:**
```lua
-- Mostrar interface de gestão de presets
PresetManager.showPresetPicker()

-- Mostrar lista simples de presets
PresetManager.showPresetListSimple()
```

---

### 6. **Preset Default**
Preset padrão criado automaticamente com os modelos base do sistema.

**Localização:** `/presets/default/`

**Características:**
- ID: `default-preset`
- Nome: NSP Default Preset
- Versão: 1.0.0
- Categoria: Default
- Licença: Free
- Sempre disponível e não pode ser removido

---

## Formato manifest.json

Conforme especificação do PRESET_MARKETPLACE.md:

```json
{
  "format_version": "1.0.0",
  "preset": {
    "id": "uuid",
    "name": "Nome do Preset",
    "version": "1.0.0",
    "description": "Descrição...",
    "tags": ["tag1", "tag2"],
    "category": "Professional"
  },
  "author": {
    "name": "Nome do Autor",
    "email": "email@example.com",
    "website": "https://...",
    "verified": false
  },
  "models": {
    "format": "pytorch",
    "version": "2.2.0",
    "architecture": "V2",
    "trained_on": "2025-11-14",
    "num_samples": 260,
    "metrics": {}
  },
  "compatibility": {
    "min_plugin_version": "2.0.0",
    "lightroom_versions": ["Classic 14.0+"]
  },
  "pricing": {
    "type": "free",
    "price": 0.0,
    "currency": "EUR"
  },
  "stats": {
    "downloads": 0,
    "rating": 0.0,
    "reviews": 0,
    "created_at": "2025-11-14T22:12:33.321336Z",
    "updated_at": "2025-11-14T22:12:33.321339Z"
  }
}
```

---

## Segurança

### Validações Implementadas:
- ✅ Validação de estrutura do package antes de extrair
- ✅ Verificação de path traversal (evita `../` maliciosos)
- ✅ Validação de tipos de ficheiros
- ✅ Limite de tamanho do package (100MB)
- ✅ Verificação de integridade com SHA256
- ✅ Validação do manifest.json (schema)
- ✅ Rate limiting nos endpoints da API

### Path Traversal Prevention:
```python
for member in zipf.namelist():
    member_path = Path(member)
    if member_path.is_absolute() or '..' in member_path.parts:
        raise PresetPackageError(f"Path traversal detectado: {member}")
```

---

## Testes

### Script de Testes: `tools/test_preset_system.py`

**Testes Implementados:**
1. ✅ Listar Presets
2. ✅ Obter Detalhes de Preset
3. ✅ Preset Activo
4. ✅ Criar Package .nsppreset
5. ✅ Instalar/Desinstalar Preset
6. ✅ Exportar Preset

**Resultado:**
```
Resultados: 6/6 testes passaram
```

**Executar testes:**
```bash
python tools/test_preset_system.py
```

---

## Fluxos de Trabalho

### 1. Criar Novo Preset
```bash
# 1. Treinar modelos
python train/train_models_v2.py

# 2. Criar package
python tools/create_preset_package.py \
    --name "My Preset" \
    --models models/ \
    --output my_preset.nsppreset

# 3. Validar package
python -c "from services.preset_manager import PresetManager; \
    pm = PresetManager(); \
    print(pm.validate_preset('my_preset.nsppreset'))"
```

### 2. Instalar Preset

**Via API:**
```bash
curl -X POST http://localhost:8321/api/presets/install \
  -F "file=@my_preset.nsppreset"
```

**Via Python:**
```python
from services.preset_manager import PresetManager

manager = PresetManager()
preset_id = manager.install_preset('my_preset.nsppreset')
print(f"Preset instalado: {preset_id}")
```

### 3. Usar Preset no Lightroom

```lua
local PresetManager = require 'PresetManager'

-- Listar presets
local presets = PresetManager.listPresets()

-- Definir como activo
PresetManager.setActivePreset(preset_id)

-- Aplicar a foto
PresetManager.applyPresetById(preset_id, photo)
```

---

## Estrutura de Ficheiros Criados

```
/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/
├── presets/                              # ✅ NOVO
│   ├── default/                          # ✅ NOVO
│   │   ├── manifest.json
│   │   ├── models/
│   │   │   ├── classifier.pth
│   │   │   ├── refinement.pth
│   │   │   ├── preset_centers.json
│   │   │   ├── scaler_stat.pkl
│   │   │   ├── scaler_deep.pkl
│   │   │   ├── scaler_deltas.pkl
│   │   │   └── delta_columns.json
│   │   ├── previews/
│   │   └── docs/
│   │       ├── README.md
│   │       └── LICENSE.txt
│   ├── installed/                        # ✅ NOVO
│   └── active_preset.json                # ✅ NOVO
├── services/
│   ├── preset_package.py                 # ✅ NOVO
│   ├── preset_manager.py                 # ✅ NOVO
│   └── server.py                         # ✅ ACTUALIZADO (endpoints)
├── tools/
│   ├── create_preset_package.py          # ✅ NOVO
│   ├── create_default_preset.py          # ✅ NOVO
│   └── test_preset_system.py             # ✅ NOVO
└── NSP-Plugin.lrplugin/
    └── PresetManager.lua                 # ✅ NOVO
```

---

## Próximos Passos (Futuro)

### Fase 2: Marketplace Online
- Backend marketplace
- Frontend loja
- Sistema de pagamentos (Stripe)
- Rating e reviews
- Sistema de licenciamento

### Fase 3: Comunidade
- Fóruns
- Tutoriais
- Competições
- Featured creators

### Melhorias Técnicas
- Compressão adicional de modelos
- Versionamento de presets
- Sistema de updates automáticos
- Backup/restore de presets
- Importação em batch

---

## Troubleshooting

### Preset default não criado
```bash
python tools/create_default_preset.py
```

### Erro ao instalar preset
1. Verificar tamanho do ficheiro (< 100MB)
2. Validar estrutura: `PresetManager.validate_preset(path)`
3. Verificar logs do servidor

### Preset não aparece no Lightroom
1. Verificar se servidor está a correr
2. Testar endpoint: `GET /api/presets`
3. Verificar logs do plugin Lua

---

## Documentação Adicional

- **Especificação:** `PRESET_MARKETPLACE.md`
- **Formato Package:** Secção "Formato do Preset Package"
- **API REST:** Secção "Endpoints Implementados"
- **Testes:** `tools/test_preset_system.py`

---

## Conclusão

✅ Sistema de gestão de presets **totalmente funcional e testado**

**Funcionalidades Principais:**
- Criar packages .nsppreset
- Instalar/desinstalar presets
- Exportar presets
- Gerir preset activo
- API REST completa
- Interface Lua para Lightroom
- Validação e segurança
- Testes automáticos (6/6 passed)

**Pronto para:**
- Utilização em produção
- Criação de presets personalizados
- Partilha de presets entre utilizadores
- Integração com marketplace (futuro)

---

**Implementado por:** Backend Master
**Data:** 14 de Novembro de 2025
