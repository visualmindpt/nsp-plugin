# -*- coding: utf-8 -*-
"""
Config Loader - Sistema centralizado de configuracao para NSP Plugin
Carrega configuracoes de config.json e fornece acesso facil
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """Singleton para carregar e acessar configurações"""

    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    _project_root: Path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Carrega configuração do ficheiro config.json"""
        # Detectar raiz do projeto (onde está o config.json)
        current_file = Path(__file__).resolve()
        self._project_root = current_file.parent

        config_path = self._project_root / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Ficheiro de configuração não encontrado: {config_path}\n"
                "Execute: cp config.example.json config.json"
            )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao parsear config.json: {e}")

        # Expandir paths relativos para absolutos
        self._expand_paths()

    def _expand_paths(self):
        """Converte paths relativos em absolutos baseados na raiz do projeto"""
        if 'paths' in self._config:
            for key, value in self._config['paths'].items():
                if isinstance(value, str):
                    self._config['paths'][key] = str(self._project_root / value)

        if 'database' in self._config:
            for key, value in self._config['database'].items():
                if isinstance(value, str) and value.endswith('.db'):
                    self._config['database'][key] = str(self._project_root / value)

        # Models paths
        if 'models' in self._config:
            models_dir = self.get_path('models_dir')
            for key in ['classifier', 'refiner']:
                if key in self._config['models']:
                    model_name = self._config['models'][key]
                    # Se o modelo não tem caminho completo, assumir que está em models_dir
                    if not os.path.isabs(model_name):
                        self._config['models'][f'{key}_path'] = str(Path(models_dir) / model_name)
                    else:
                        self._config['models'][f'{key}_path'] = model_name

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtém valor de configuração usando notação de ponto
        Exemplo: config.get('server.port') -> 5678
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_path(self, key: str) -> Path:
        """Obtém path de configuração como objeto Path"""
        value = self.get(f'paths.{key}')
        if value is None:
            raise KeyError(f"Path '{key}' não encontrado em config.paths")
        return Path(value)

    def get_server_url(self) -> str:
        """Obtém URL completo do servidor"""
        host = self.get('server.host', '127.0.0.1')
        port = self.get('server.port', 5678)
        return f"http://{host}:{port}"

    def get_model_path(self, model_type: str) -> Path:
        """
        Obtém caminho completo para um modelo
        model_type: 'classifier' ou 'refiner'
        """
        key = f'models.{model_type}_path'
        value = self.get(key)
        if value is None:
            raise KeyError(f"Modelo '{model_type}' não encontrado em config.models")
        return Path(value)

    @property
    def project_root(self) -> Path:
        """Retorna raiz do projeto"""
        return self._project_root

    def reload(self):
        """Recarrega configuração do disco"""
        self._load_config()

    def __repr__(self):
        return f"Config(root={self._project_root})"


# Instância global (singleton)
config = Config()


# Atalhos para acesso rápido
def get_server_url() -> str:
    """Obtém URL do servidor"""
    return config.get_server_url()


def get_model_path(model_type: str) -> Path:
    """Obtém caminho do modelo"""
    return config.get_model_path(model_type)


def get_project_root() -> Path:
    """Obtém raiz do projeto"""
    return config.project_root


def get_config_value(key: str, default: Any = None) -> Any:
    """Obtém valor de configuração"""
    return config.get(key, default)


# Exemplo de uso:
if __name__ == "__main__":
    print("NSP Plugin - Config Loader")
    print("=" * 50)
    print(f"Project Root: {config.project_root}")
    print(f"Server URL: {config.get_server_url()}")
    print(f"Models Dir: {config.get_path('models_dir')}")
    print(f"Classifier: {config.get_model_path('classifier')}")
    print(f"Refiner: {config.get_model_path('refiner')}")
    print(f"Batch Size: {config.get('training.batch_size')}")
    print(f"GPU Enabled: {config.get('performance.use_gpu')}")
