"""
Gestor de Presets NSP Plugin
Gestão de presets treinados (instalação, listagem, aplicação)
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# EXCEÇÕES PERSONALIZADAS
# ============================================================================

class PresetNotFoundError(Exception):
    """Exceção levantada quando um preset não é encontrado"""
    pass

class PresetAlreadyInstalledError(Exception):
    """Exceção levantada quando se tenta instalar um preset que já existe"""
    pass

# ============================================================================
# GESTOR DE PRESETS
# ============================================================================

class PresetManager:
    """Gestor de presets do NSP Plugin"""

    def __init__(self, presets_dir: Path = None):
        self.presets_dir = presets_dir or Path(__file__).parent.parent / "presets"
        self.presets_dir.mkdir(parents=True, exist_ok=True)

        self.installed_dir = self.presets_dir / "installed"
        self.installed_dir.mkdir(parents=True, exist_ok=True)

        self.default_dir = self.presets_dir / "default"
        self.active_preset_file = self.presets_dir / "active_preset.json"

        self._ensure_default_preset()

    def _ensure_default_preset(self):
        """Garante que o preset default existe"""
        if not self.default_dir.exists():
            logger.info("Criando preset default...")
            self.create_default_preset()

    def create_default_preset(self):
        """Cria preset default a partir dos modelos atuais"""
        self.default_dir.mkdir(parents=True, exist_ok=True)

        models_src = Path(__file__).parent.parent / "models"
        models_dest = self.default_dir / "models"
        models_dest.mkdir(exist_ok=True)

        # Copiar modelos principais
        for model_file in ["best_preset_classifier.pth", "best_refinement_model.pth"]:
            src = Path(__file__).parent.parent / model_file
            if src.exists():
                shutil.copy2(src, models_dest / model_file)

        # Copiar configurações
        for config_file in ["preset_centers.json", "delta_columns.json"]:
            src = models_src / config_file
            if src.exists():
                shutil.copy2(src, models_dest / config_file)

        # Criar manifest
        manifest = {
            "format_version": "1.0.0",
            "preset": {
                "id": "default",
                "name": "NSP Default Preset",
                "version": "1.0.0",
                "description": "Preset padrão do NSP Plugin",
                "category": "System"
            },
            "models": {
                "format": "pytorch",
                "architecture": "V2"
            }
        }

        with open(self.default_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info("Preset default criado com sucesso")

    def list_presets(self) -> List[Dict]:
        """Lista todos os presets instalados"""
        presets = []

        # Adicionar default
        if self.default_dir.exists():
            manifest_path = self.default_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                    presets.append({"id": "default", "path": str(self.default_dir), **manifest["preset"]})

        # Adicionar instalados
        if self.installed_dir.exists():
            for preset_dir in self.installed_dir.iterdir():
                if preset_dir.is_dir():
                    manifest_path = preset_dir / "manifest.json"
                    if manifest_path.exists():
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                            presets.append({"id": preset_dir.name, "path": str(preset_dir), **manifest["preset"]})

        return presets

    def get_preset(self, preset_id: str) -> Optional[Dict]:
        """Obtém informação de um preset específico"""
        for preset in self.list_presets():
            if preset["id"] == preset_id:
                return preset
        return None

    def get_active_preset(self) -> Dict:
        """Retorna o preset ativo"""
        if self.active_preset_file.exists():
            with open(self.active_preset_file) as f:
                data = json.load(f)
                preset_id = data.get("preset_id", "default")
        else:
            preset_id = "default"

        preset = self.get_preset(preset_id)
        if preset:
            return preset

        # Fallback para default
        return self.get_preset("default")

    def set_active_preset(self, preset_id: str) -> bool:
        """Define o preset ativo"""
        preset = self.get_preset(preset_id)
        if not preset:
            logger.error(f"Preset {preset_id} não encontrado")
            return False

        with open(self.active_preset_file, "w") as f:
            json.dump({"preset_id": preset_id}, f)

        logger.info(f"Preset ativo alterado para: {preset['name']}")
        return True

    def get_preset_models_path(self, preset_id: str) -> Optional[Path]:
        """Retorna o caminho da pasta models de um preset"""
        preset = self.get_preset(preset_id)
        if preset:
            return Path(preset["path"]) / "models"
        return None

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def ensure_default_preset_exists(models_dir: Path = None):
    """
    Garante que o preset default existe

    Args:
        models_dir: Diretório raiz do projeto (opcional)
    """
    presets_dir = (models_dir or Path(__file__).parent.parent) / "presets"
    default_dir = presets_dir / "default"

    if not default_dir.exists():
        logger.info("Preset default não existe, criando...")
        manager = PresetManager(presets_dir=presets_dir)
        manager.create_default_preset()
    else:
        logger.debug("Preset default já existe")
