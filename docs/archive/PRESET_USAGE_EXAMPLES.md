# Exemplos de Uso - Sistema de Presets

Este documento contém exemplos práticos de como usar o sistema de gestão de presets.

---

## 1. Criar Preset a Partir de Modelos Treinados

### Exemplo Básico

```bash
cd /Users/nelsonsilva/Documentos/gemini/projetos/NSP\ Plugin_dev_full_package

# Criar preset simples
python tools/create_preset_package.py \
    --name "My First Preset" \
    --models models/ \
    --output my_first_preset.nsppreset
```

### Exemplo Completo

```bash
# Criar preset com todas as opções
python tools/create_preset_package.py \
    --name "Nelson Silva Cinematic Look" \
    --author "Nelson Silva" \
    --email "nelson@nelsonsilva.photography" \
    --website "https://nelsonsilva.photography" \
    --instagram "@nelsonsilva.photography" \
    --description "Tons cinematográficos com cores quentes e alto contraste" \
    --category "Professional" \
    --tags "cinematic,warm,dramatic,wedding" \
    --models models/ \
    --previews path/to/preview_images/ \
    --license "commercial" \
    --price 29.99 \
    --version "1.2.0" \
    --num-samples 5234 \
    --output nelson_silva_cinematic.nsppreset \
    --verbose
```

---

## 2. Usar Preset Manager via Python

### Listar Presets

```python
from services.preset_manager import PresetManager

# Inicializar manager
manager = PresetManager()

# Listar todos os presets
presets = manager.list_presets(include_default=True)

for preset in presets:
    print(f"- {preset['name']} v{preset['version']}")
    print(f"  Autor: {preset['author']}")
    print(f"  Categoria: {preset['category']}")
    print(f"  ID: {preset['id']}")
    print()
```

### Instalar Preset

```python
from services.preset_manager import PresetManager

manager = PresetManager()

# Instalar preset
preset_id = manager.install_preset(
    nsppreset_path="path/to/preset.nsppreset",
    force=False  # True para reinstalar se já existir
)

print(f"Preset instalado: {preset_id}")
```

### Validar Preset Antes de Instalar

```python
from services.preset_manager import PresetManager

manager = PresetManager()

# Validar preset
result = manager.validate_preset("path/to/preset.nsppreset")

if result['valid']:
    print("✓ Preset válido!")
    manifest = result['manifest']
    print(f"Nome: {manifest['preset']['name']}")
    print(f"Versão: {manifest['preset']['version']}")
    print(f"Autor: {manifest['author']['name']}")
else:
    print("✗ Preset inválido:")
    for error in result['errors']:
        print(f"  - {error}")
```

### Gerir Preset Activo

```python
from services.preset_manager import PresetManager

manager = PresetManager()

# Obter preset activo
active = manager.get_active_preset()
if active:
    print(f"Preset activo: {active['preset']['name']}")
else:
    print("Nenhum preset activo")

# Definir preset activo
manager.set_active_preset("preset-id-aqui")
print("Preset activo actualizado")
```

### Exportar Preset

```python
from services.preset_manager import PresetManager
from pathlib import Path

manager = PresetManager()

# Exportar preset existente
output_path = manager.export_preset(
    preset_id="default-preset",
    output_path=Path("exported_preset.nsppreset"),
    use_current_models=False
)

print(f"Preset exportado para: {output_path}")
```

### Criar Package Programaticamente

```python
from services.preset_manager import PresetManager
from pathlib import Path

manager = PresetManager()

metadata = {
    "name": "Wedding Collection",
    "version": "1.0.0",
    "description": "Preset profissional para casamentos",
    "author_name": "João Silva",
    "author_email": "joao@example.com",
    "category": "Wedding",
    "tags": ["wedding", "romantic", "soft"],
    "license_type": "commercial",
    "price": 49.99
}

# Coletar imagens de preview
preview_images = list(Path("previews/").glob("*.jpg"))[:6]

# Criar package
output_path = manager.create_preset_package(
    models_dir=Path("models/"),
    metadata=metadata,
    previews=preview_images,
    output_path=Path("wedding_collection.nsppreset")
)

print(f"Package criado: {output_path}")
```

---

## 3. Usar API REST

### Listar Presets

```bash
# GET /api/presets
curl http://localhost:8321/api/presets
```

**Resposta:**
```json
{
  "presets": [
    {
      "id": "default-preset",
      "name": "NSP Default Preset",
      "version": "1.0.0",
      "description": "Preset padrão do NSP Plugin",
      "author": "NSP Plugin",
      "category": "Default",
      "tags": ["default", "base"],
      "is_default": true,
      "installed_at": "2025-11-14T22:12:33.321336Z",
      "path": "/path/to/presets/default"
    }
  ],
  "total": 1
}
```

### Obter Detalhes de Preset

```bash
# GET /api/presets/{id}
curl http://localhost:8321/api/presets/default-preset
```

### Instalar Preset (Upload)

```bash
# POST /api/presets/install
curl -X POST http://localhost:8321/api/presets/install \
  -F "file=@my_preset.nsppreset" \
  -F "force=false"
```

**Resposta:**
```json
{
  "success": true,
  "message": "Preset instalado com sucesso: abc123",
  "preset_id": "abc123"
}
```

### Remover Preset

```bash
# DELETE /api/presets/{id}
curl -X DELETE http://localhost:8321/api/presets/abc123
```

### Obter Preset Activo

```bash
# GET /api/presets/active
curl http://localhost:8321/api/presets/active
```

### Definir Preset Activo

```bash
# PUT /api/presets/active
curl -X PUT http://localhost:8321/api/presets/active \
  -H "Content-Type: application/json" \
  -d '{"preset_id": "default-preset"}'
```

### Exportar Preset

```bash
# POST /api/presets/export
curl -X POST http://localhost:8321/api/presets/export \
  -H "Content-Type: application/json" \
  -d '{
    "preset_id": "default-preset",
    "output_filename": "my_export.nsppreset",
    "use_current_models": false
  }'
```

**Resposta:**
```json
{
  "success": true,
  "message": "Preset exportado com sucesso",
  "download_url": "/downloads/exports/my_export.nsppreset"
}
```

---

## 4. Usar no Lightroom (Lua)

### Listar e Escolher Preset

```lua
local PresetManager = require 'PresetManager'

-- Mostrar interface de escolha de preset
PresetManager.showPresetPicker()
```

### Aplicar Preset Programaticamente

```lua
local PresetManager = require 'PresetManager'
local LrApplication = import 'LrApplication'

-- Obter foto seleccionada
local catalog = LrApplication.activeCatalog()
local targetPhoto = catalog:getTargetPhoto()

if targetPhoto then
    -- Aplicar preset específico
    local success, error = PresetManager.applyPresetById(
        "default-preset",
        targetPhoto
    )

    if success then
        LrDialogs.message("Sucesso", "Preset aplicado!")
    else
        LrDialogs.message("Erro", error, "critical")
    end
end
```

### Listar Presets Disponíveis

```lua
local PresetManager = require 'PresetManager'

-- Obter lista de presets
local presets, error = PresetManager.listPresets()

if presets then
    for _, preset in ipairs(presets) do
        local logger = import 'LrLogger'('MyScript')
        logger:info(string.format(
            "Preset: %s v%s (ID: %s)",
            preset.name,
            preset.version,
            preset.id
        ))
    end
else
    LrDialogs.message("Erro", error, "critical")
end
```

### Definir Preset Activo

```lua
local PresetManager = require 'PresetManager'

-- Definir preset activo
local success, error = PresetManager.setActivePreset("default-preset")

if success then
    LrDialogs.message("Sucesso", "Preset activo definido")
else
    LrDialogs.message("Erro", error, "critical")
end
```

---

## 5. Testes e Validação

### Executar Testes Completos

```bash
# Executar suite de testes
python tools/test_preset_system.py
```

### Validar Preset Individual

```python
from services.preset_manager import PresetManager

manager = PresetManager()
result = manager.validate_preset("my_preset.nsppreset")

if not result['valid']:
    print("Erros encontrados:")
    for error in result['errors']:
        print(f"  - {error}")
```

### Verificar Integridade de Package

```python
from services.preset_package import PresetPackage

# Carregar package
package = PresetPackage("my_preset.nsppreset")

# Validar estrutura
try:
    package.validate_structure()
    print("✓ Package válido")
except Exception as e:
    print(f"✗ Package inválido: {e}")

# Verificar assinatura
signature = package.calculate_signature()
print(f"SHA256: {signature}")
```

---

## 6. Workflows Comuns

### Workflow: Criar e Partilhar Preset

```bash
# 1. Treinar modelos com os seus dados
python train/train_models_v2.py --catalog "Lightroom Catalog.lrcat" --min-rating 3

# 2. Criar previews (exportar algumas fotos processadas)
# (Fazer manualmente no Lightroom)

# 3. Criar package
python tools/create_preset_package.py \
    --name "My Style" \
    --author "Your Name" \
    --models models/ \
    --previews previews/ \
    --output my_style.nsppreset

# 4. Testar localmente
python -c "from services.preset_manager import PresetManager; \
    pm = PresetManager(); \
    pid = pm.install_preset('my_style.nsppreset'); \
    print(f'Instalado: {pid}')"

# 5. Partilhar ficheiro .nsppreset
```

### Workflow: Actualizar Preset Existente

```python
from services.preset_manager import PresetManager
from pathlib import Path

manager = PresetManager()

# 1. Exportar preset actual
current = manager.export_preset(
    preset_id="my-preset-id",
    output_path=Path("backup.nsppreset")
)
print(f"Backup criado: {current}")

# 2. Treinar novos modelos
# (executar treino)

# 3. Criar nova versão do preset
new_version = manager.create_preset_package(
    models_dir=Path("models/"),
    metadata={
        "name": "My Style",
        "version": "2.0.0",  # Incrementar versão
        # ... outros metadados
    },
    previews=None,
    output_path=Path("my_style_v2.nsppreset")
)

# 4. Instalar nova versão
manager.install_preset(new_version, force=True)
```

---

## 7. Troubleshooting

### Erro: "Preset já instalado"

```python
# Opção 1: Forçar reinstalação
manager.install_preset(path, force=True)

# Opção 2: Remover e reinstalar
manager.uninstall_preset(preset_id)
manager.install_preset(path)
```

### Erro: "Package excede tamanho máximo"

```bash
# Verificar tamanho
ls -lh my_preset.nsppreset

# Se > 100MB, optimizar modelos ou reduzir previews
```

### Preset não aparece na API

```python
# Verificar se foi instalado
manager = PresetManager()
presets = manager.list_presets()
print(f"Total de presets: {len(presets)}")

# Verificar diretório
import os
os.listdir("presets/installed/")
```

---

## 8. Dicas e Boas Práticas

### Nomes de Preset
- Use nomes descritivos: "Cinematic Wedding" em vez de "Preset1"
- Inclua estilo ou caso de uso no nome
- Versões semânticas: 1.0.0, 1.1.0, 2.0.0

### Tags
- Use tags específicas: "wedding", "portrait", "landscape"
- Máximo 5-7 tags relevantes
- Evite tags genéricas como "good" ou "best"

### Previews
- Inclua pelo menos 3 exemplos before/after
- Use imagens de alta qualidade
- Mostre diferentes cenários/condições de luz

### Versionamento
- Versão MAJOR.MINOR.PATCH
- MAJOR: Mudanças incompatíveis
- MINOR: Novas funcionalidades compatíveis
- PATCH: Bug fixes

### Documentação
- Inclua README.md detalhado
- Explique quando usar o preset
- Liste limitações conhecidas

---

Implementado por Backend Master - 14 de Novembro de 2025
