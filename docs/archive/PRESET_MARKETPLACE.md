# 🎨 NSP Preset Marketplace - Arquitetura Completa

**Data:** 13 de Novembro de 2025
**Versão:** 1.0.0
**Estado:** 📐 Design & Especificação

---

## 🎯 Visão do Produto

### Conceito
**"Mercado de Estéticas Fotográficas Inteligentes"**

Permitir que fotógrafos profissionais **monetizem o seu estilo visual** através de presets dinâmicos baseados em AI, que se adaptam automaticamente a cada foto.

### Casos de Uso

#### 1. Criador de Preset (Fotógrafo Pro)
```
Nelson Silva Photography treinou 5000 fotos → "Nelson Silva Cinematic Look"
Exporta preset → Publica no marketplace → Vende por €29.99
```

#### 2. Comprador (Fotógrafo Amador/Semi-Pro)
```
Compra "Nelson Silva Cinematic Look"
Importa para Lightroom → Aplica em 1 clique
Todas as fotos ficam com a estética Nelson Silva
```

#### 3. Comunidade
```
Preset gratuitos partilhados pela comunidade
Ratings e reviews
Top presets do mês
```

---

## 📦 Formato do Preset Package

### Estrutura: `.nsppreset` (ZIP comprimido)

```
nelson_silva_cinematic.nsppreset/
├── manifest.json                    # Metadata do preset
├── models/
│   ├── classifier.pth               # Modelo de classificação
│   ├── refinement.pth               # Modelo de refinamento
│   ├── preset_centers.json          # Centros dos presets
│   ├── scaler_stat.pkl              # Scaler estatístico
│   ├── scaler_deep.pkl              # Scaler deep features
│   ├── scaler_deltas.pkl            # Scaler deltas
│   └── delta_columns.json           # Nomes das colunas
├── previews/
│   ├── thumbnail.jpg                # Thumbnail 400x400
│   ├── hero.jpg                     # Hero image 1920x1080
│   ├── before_01.jpg                # Exemplo antes/depois
│   ├── after_01.jpg
│   ├── before_02.jpg
│   ├── after_02.jpg
│   ├── before_03.jpg
│   └── after_03.jpg
├── samples/
│   └── sample_xmp_01.xmp            # Exemplos de XMP gerados
├── docs/
│   ├── README.md                    # Descrição detalhada
│   └── LICENSE.txt                  # Termos de uso
├── signature.sha256                 # Hash de integridade
└── certificate.json                 # Assinatura digital (futuro)
```

### manifest.json

```json
{
  "format_version": "1.0.0",
  "preset": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Nelson Silva Cinematic Look",
    "slug": "nelson-silva-cinematic",
    "version": "1.2.0",
    "description": "Tons cinematográficos com cores quentes, alto contraste e look profissional de cinema. Ideal para retratos, casamentos e fotografia lifestyle.",
    "tags": [
      "cinematic",
      "warm",
      "high-contrast",
      "wedding",
      "portrait",
      "lifestyle",
      "professional"
    ],
    "category": "Professional",
    "style_keywords": [
      "moody",
      "dramatic",
      "film-like"
    ]
  },
  "author": {
    "name": "Nelson Silva",
    "email": "nelson@nelsonsilva.photography",
    "website": "https://nelsonsilva.photography",
    "instagram": "@nelsonsilva.photography",
    "verified": true
  },
  "technical": {
    "num_presets": 4,
    "trained_images": 5234,
    "training_duration_hours": 12.5,
    "model_size_mb": 45.2,
    "compatible_version": ">=0.6.0",
    "requires_gpu": false,
    "avg_inference_time_ms": 350
  },
  "pricing": {
    "type": "commercial",
    "price": 29.99,
    "currency": "EUR",
    "license": "single-user",
    "trial_available": true,
    "trial_images": 10
  },
  "stats": {
    "downloads": 1247,
    "rating": 4.8,
    "reviews": 89,
    "created_at": "2025-11-13T15:00:00Z",
    "updated_at": "2025-11-15T10:30:00Z"
  },
  "compatibility": {
    "lightroom_versions": ["Classic 14.0+", "CC"],
    "raw_formats": ["CR2", "NEF", "ARW", "DNG"],
    "platforms": ["macOS", "Windows"]
  },
  "preview_images": [
    "previews/thumbnail.jpg",
    "previews/hero.jpg",
    "previews/before_01.jpg",
    "previews/after_01.jpg",
    "previews/before_02.jpg",
    "previews/after_02.jpg",
    "previews/before_03.jpg",
    "previews/after_03.jpg"
  ],
  "changelog": [
    {
      "version": "1.2.0",
      "date": "2025-11-15",
      "changes": [
        "Melhorado contraste em sombras",
        "Ajustado temperatura para tons mais quentes",
        "Corrigido bug em fotos com ISO alto"
      ]
    },
    {
      "version": "1.1.0",
      "date": "2025-11-14",
      "changes": ["Versão inicial pública"]
    }
  ]
}
```

---

## 🏗️ Arquitetura do Sistema

### Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    NSP Preset Marketplace                     │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐        ┌────▼────┐
   │  Export │         │ Import  │        │  Store  │
   │ System  │         │ System  │        │   API   │
   └────┬────┘         └────┬────┘        └────┬────┘
        │                   │                   │
        │                   │                   │
   ┌────▼─────────────────┬─▼──────────────────▼────┐
   │    Preset Manager UI (Control Center V2)       │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
   │  │ My       │  │ Browse   │  │ Install  │     │
   │  │ Presets  │  │ Store    │  │ Manager  │     │
   │  └──────────┘  └──────────┘  └──────────┘     │
   └───────────────────┬──────────────────────────┘
                       │
              ┌────────▼─────────┐
              │  Lightroom Plugin │
              │  (Select Preset)  │
              └───────────────────┘
```

### Fluxo de Exportação

```
┌─────────────┐
│ 1. Treino   │
│   Completo  │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ 2. Export Wizard    │
│    - Nome           │
│    - Descrição      │
│    - Previews       │
│    - Preço          │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 3. Package Builder  │
│    - Copia modelos  │
│    - Gera previews  │
│    - Cria manifest  │
│    - Assina package │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 4. nelson_silva_    │
│    cinematic.       │
│    nsppreset        │
└─────────────────────┘
```

### Fluxo de Importação

```
┌─────────────────────┐
│ 1. User seleciona   │
│    .nsppreset file  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 2. Validação        │
│    - Integridade    │
│    - Compatibilidade│
│    - Licença        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 3. Instalação       │
│    - Extrai ficheiros│
│    - Copia para     │
│      models/presets/│
│    - Regista no DB  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 4. Preset Disponível│
│    no Lightroom     │
└─────────────────────┘
```

---

## 💻 Implementação

### 1. Export System

**Ficheiro:** `services/ai_core/preset_exporter.py`

```python
import json
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import shutil
from PIL import Image

class PresetExporter:
    """
    Exporta modelos treinados como preset package .nsppreset
    """

    def __init__(self, models_dir: Path, output_dir: Path):
        self.models_dir = Path(models_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_preset(
        self,
        preset_name: str,
        author_name: str,
        author_email: str,
        description: str,
        tags: List[str],
        category: str,
        price: float = 0.0,
        license_type: str = "free",
        preview_images: List[Path] = None,
        website: Optional[str] = None,
        instagram: Optional[str] = None
    ) -> Path:
        """
        Cria um package .nsppreset completo

        Returns:
            Path para o ficheiro .nsppreset criado
        """

        # Gerar slug único
        slug = self._generate_slug(preset_name)
        preset_id = self._generate_uuid()

        # Criar diretório temporário
        temp_dir = self.output_dir / f"temp_{slug}"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 1. Criar estrutura de pastas
            models_folder = temp_dir / "models"
            previews_folder = temp_dir / "previews"
            docs_folder = temp_dir / "docs"

            models_folder.mkdir()
            previews_folder.mkdir()
            docs_folder.mkdir()

            # 2. Copiar modelos
            self._copy_models(models_folder)

            # 3. Processar preview images
            if preview_images:
                self._process_preview_images(preview_images, previews_folder)

            # 4. Gerar manifest.json
            manifest = self._create_manifest(
                preset_id=preset_id,
                name=preset_name,
                slug=slug,
                author_name=author_name,
                author_email=author_email,
                description=description,
                tags=tags,
                category=category,
                price=price,
                license_type=license_type,
                website=website,
                instagram=instagram
            )

            with open(temp_dir / "manifest.json", 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            # 5. Criar README.md
            self._create_readme(temp_dir / "docs" / "README.md", manifest)

            # 6. Criar LICENSE.txt
            self._create_license(temp_dir / "docs" / "LICENSE.txt", license_type)

            # 7. Gerar assinatura
            signature = self._generate_signature(temp_dir)
            with open(temp_dir / "signature.sha256", 'w') as f:
                f.write(signature)

            # 8. Comprimir para .nsppreset
            output_file = self.output_dir / f"{slug}.nsppreset"
            self._create_zip(temp_dir, output_file)

            return output_file

        finally:
            # Limpar diretório temporário
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _copy_models(self, target_dir: Path):
        """Copia ficheiros de modelos necessários"""
        required_files = [
            "best_preset_classifier.pth",
            "best_refinement_model.pth",
            "preset_centers.json",
            "scaler_stat.pkl",
            "scaler_deep.pkl",
            "scaler_deltas.pkl",
            "delta_columns.json"
        ]

        for filename in required_files:
            source = self.models_dir / filename
            if source.exists():
                shutil.copy2(source, target_dir / filename.replace("best_", ""))
            else:
                raise FileNotFoundError(f"Ficheiro necessário não encontrado: {filename}")

    def _process_preview_images(self, images: List[Path], target_dir: Path):
        """Processa e copia preview images"""
        # Criar thumbnail (400x400)
        if images:
            first_image = Image.open(images[0])
            first_image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            first_image.save(target_dir / "thumbnail.jpg", "JPEG", quality=90)

            # Criar hero image (1920x1080)
            hero = Image.open(images[0])
            hero.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            hero.save(target_dir / "hero.jpg", "JPEG", quality=95)

        # Copiar exemplos before/after
        for idx, image_path in enumerate(images[:6], 1):  # Max 6 imagens
            target_name = f"example_{idx:02d}.jpg"
            shutil.copy2(image_path, target_dir / target_name)

    def _create_manifest(self, **kwargs) -> Dict:
        """Cria o manifest.json"""
        return {
            "format_version": "1.0.0",
            "preset": {
                "id": kwargs['preset_id'],
                "name": kwargs['name'],
                "slug": kwargs['slug'],
                "version": "1.0.0",
                "description": kwargs['description'],
                "tags": kwargs['tags'],
                "category": kwargs['category']
            },
            "author": {
                "name": kwargs['author_name'],
                "email": kwargs['author_email'],
                "website": kwargs.get('website'),
                "instagram": kwargs.get('instagram'),
                "verified": False
            },
            "technical": self._get_technical_info(),
            "pricing": {
                "type": kwargs['license_type'],
                "price": kwargs['price'],
                "currency": "EUR",
                "license": "single-user"
            },
            "stats": {
                "downloads": 0,
                "rating": 0.0,
                "reviews": 0,
                "created_at": datetime.now().isoformat() + "Z"
            },
            "compatibility": {
                "lightroom_versions": ["Classic 14.0+"],
                "platforms": ["macOS", "Windows"]
            }
        }

    def _get_technical_info(self) -> Dict:
        """Obtém informação técnica dos modelos"""
        # Ler preset_centers para obter número de presets
        centers_file = self.models_dir / "preset_centers.json"
        if centers_file.exists():
            with open(centers_file) as f:
                centers = json.load(f)
                num_presets = len(centers)
        else:
            num_presets = 4  # default

        # Calcular tamanho total dos modelos
        total_size = 0
        for file in self.models_dir.glob("*.pth"):
            total_size += file.stat().st_size
        size_mb = total_size / (1024 * 1024)

        return {
            "num_presets": num_presets,
            "trained_images": 0,  # TODO: obter do training log
            "model_size_mb": round(size_mb, 1),
            "compatible_version": ">=0.6.0",
            "requires_gpu": False
        }

    def _generate_signature(self, directory: Path) -> str:
        """Gera hash SHA256 de todos os ficheiros"""
        hasher = hashlib.sha256()

        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.name != "signature.sha256":
                with open(file_path, 'rb') as f:
                    hasher.update(f.read())

        return hasher.hexdigest()

    def _create_zip(self, source_dir: Path, output_file: Path):
        """Cria ficheiro ZIP"""
        with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

    @staticmethod
    def _generate_slug(name: str) -> str:
        """Gera slug URL-friendly"""
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug

    @staticmethod
    def _generate_uuid() -> str:
        """Gera UUID único"""
        import uuid
        return str(uuid.uuid4())

    def _create_readme(self, path: Path, manifest: Dict):
        """Cria README.md"""
        content = f"""# {manifest['preset']['name']}

**Version:** {manifest['preset']['version']}
**Author:** {manifest['author']['name']}

## Description

{manifest['preset']['description']}

## Installation

1. Download the `.nsppreset` file
2. Open NSP Control Center V2
3. Go to "Preset Manager"
4. Click "Import Preset"
5. Select the downloaded file

## Usage

1. Open Adobe Lightroom Classic
2. Select photos you want to edit
3. Go to NSP Plugin menu
4. Choose "AI Preset V2 - {manifest['preset']['name']}"
5. Preview and apply!

## License

{manifest['pricing']['type']} - {manifest['pricing']['license']}

## Support

For questions or issues, contact: {manifest['author']['email']}
"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _create_license(self, path: Path, license_type: str):
        """Cria LICENSE.txt"""
        licenses = {
            "free": "This preset is free for personal and commercial use.",
            "commercial": "This preset requires a commercial license. Redistribution is prohibited.",
            "single-user": "This preset is licensed for use by a single user only."
        }

        content = f"""NSP PRESET LICENSE

{licenses.get(license_type, licenses['single-user'])}

© {datetime.now().year} All rights reserved.
"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
```

---

## 🎨 Preset Manager UI

Adicionar nova secção ao Control Center V2:

```html
<!-- control-center-v2/static/index.html -->

<section class="preset-manager-section">
    <div class="section-card">
        <div class="section-header">
            <h2>🎨 Preset Manager</h2>
            <div class="preset-actions">
                <button class="btn btn-primary" onclick="presetManager.importPreset()">
                    📥 Import Preset
                </button>
                <button class="btn btn-secondary" onclick="presetManager.exportPreset()">
                    📤 Export Current
                </button>
            </div>
        </div>

        <!-- Lista de Presets Instalados -->
        <div class="presets-grid" id="presetsGrid">
            <!-- Será populado dinamicamente -->
        </div>
    </div>
</section>
```

---

## 🌐 Marketplace API (Futuro)

Endpoints para o marketplace online:

```python
# services/marketplace_api.py

@router.get("/marketplace/presets")
async def list_presets(
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    sort: str = "popular",
    page: int = 1,
    limit: int = 20
):
    """Lista presets disponíveis no marketplace"""
    pass

@router.get("/marketplace/presets/{preset_id}")
async def get_preset_details(preset_id: str):
    """Detalhes de um preset específico"""
    pass

@router.post("/marketplace/presets")
async def upload_preset(preset_file: UploadFile):
    """Upload de novo preset (requer autenticação)"""
    pass

@router.post("/marketplace/presets/{preset_id}/purchase")
async def purchase_preset(preset_id: str, payment_token: str):
    """Compra de preset (integração com Stripe)"""
    pass

@router.get("/marketplace/presets/{preset_id}/download")
async def download_preset(preset_id: str, license_key: str):
    """Download de preset comprado"""
    pass
```

---

## 💰 Modelo de Negócio

### Tipos de Presets

1. **Gratuitos (Community)**
   - Partilhados pela comunidade
   - Rating e reviews
   - Suporte comunitário

2. **Premium (Pagos)**
   - Preços: €9.99 - €99.99
   - Licença single-user
   - Suporte do autor
   - Updates grátis

3. **Pro Bundles**
   - Pacotes de múltiplos presets
   - Desconto 30-40%
   - Exemplos: "Wedding Collection", "Portrait Bundle"

### Revenue Sharing
- **70% Criador** / 30% Plataforma
- Pagamentos mensais via Stripe
- Mínimo de payout: €50

---

## 🚀 Roadmap de Implementação

### Fase 1: MVP (2 semanas) ✅ Este documento
- [x] Especificação completa
- [ ] Export System
- [ ] Import System
- [ ] Preset Manager UI

### Fase 2: Local Marketplace (1 mês)
- [ ] Lista de presets instalados
- [ ] Preview antes de aplicar
- [ ] Switch entre presets
- [ ] Versionamento

### Fase 3: Online Marketplace (2-3 meses)
- [ ] Backend marketplace
- [ ] Frontend loja
- [ ] Sistema de pagamentos (Stripe)
- [ ] Rating e reviews
- [ ] Sistema de licenciamento

### Fase 4: Comunidade (ongoing)
- [ ] Forums
- [ ] Tutoriais
- [ ] Competições
- [ ] Featured creators

---

## 🎯 Conclusão

O **NSP Preset Marketplace** transforma o plugin numa **plataforma comercial escalável**:

✅ **Para Criadores:**
- Monetizam o seu trabalho
- Alcançam audiência global
- Recebem feedback direto

✅ **Para Utilizadores:**
- Acesso a estilos profissionais
- Testam antes de comprar
- Comunidade ativa

✅ **Para o Negócio:**
- Revenue recorrente
- Network effects
- Escalabilidade global

**Potencial de Mercado:** €100K - €500K MRR em 2 anos com crescimento orgânico
