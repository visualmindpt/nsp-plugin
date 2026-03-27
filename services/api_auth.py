# -*- coding: utf-8 -*-
"""
API Authentication System - Sistema simples de autenticacao com API keys
Suporta geração, validação e múltiplos níveis de acesso
"""

import secrets
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AccessLevel(str, Enum):
    """Níveis de acesso para API keys"""
    READ_ONLY = "read_only"          # Apenas GET endpoints
    STANDARD = "standard"            # GET + POST predict/feedback
    ADMIN = "admin"                  # Acesso total incluindo treino
    FULL = "full"                    # Acesso total sem limites


class APIKey:
    """Representa uma API key"""

    def __init__(
        self,
        key: str,
        name: str,
        access_level: AccessLevel = AccessLevel.STANDARD,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        enabled: bool = True,
        description: str = ""
    ):
        self.key = key
        self.name = name
        self.access_level = access_level
        self.created_at = created_at or datetime.now()
        self.expires_at = expires_at
        self.enabled = enabled
        self.description = description
        self.last_used_at: Optional[datetime] = None
        self.usage_count = 0

    def to_dict(self) -> Dict:
        """Serializa para dict (sem expor key completa)"""
        return {
            "name": self.name,
            "key_prefix": self.key[:8] + "...",
            "access_level": self.access_level.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "enabled": self.enabled,
            "description": self.description,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_count": self.usage_count
        }

    def is_valid(self) -> bool:
        """Verifica se key está válida"""
        if not self.enabled:
            return False

        if self.expires_at and datetime.now() > self.expires_at:
            return False

        return True

    def record_usage(self):
        """Registra uso da key"""
        self.last_used_at = datetime.now()
        self.usage_count += 1


class APIKeyManager:
    """Gestor de API keys"""

    def __init__(self, keys_file: Path = None):
        self.keys_file = keys_file or Path("data/api_keys.json")
        self.keys: Dict[str, APIKey] = {}
        self._load_keys()

    def _load_keys(self):
        """Carrega keys do ficheiro"""
        if not self.keys_file.exists():
            logger.info("Ficheiro de API keys não existe. Será criado quando adicionar primeira key.")
            return

        try:
            with open(self.keys_file, 'r') as f:
                data = json.load(f)

            for key_data in data.get('keys', []):
                key = APIKey(
                    key=key_data['key'],
                    name=key_data['name'],
                    access_level=AccessLevel(key_data['access_level']),
                    created_at=datetime.fromisoformat(key_data['created_at']),
                    expires_at=datetime.fromisoformat(key_data['expires_at']) if key_data.get('expires_at') else None,
                    enabled=key_data.get('enabled', True),
                    description=key_data.get('description', '')
                )
                key.last_used_at = datetime.fromisoformat(key_data['last_used_at']) if key_data.get('last_used_at') else None
                key.usage_count = key_data.get('usage_count', 0)

                self.keys[key.key] = key

            logger.info(f"Carregadas {len(self.keys)} API keys")

        except Exception as e:
            logger.error(f"Erro ao carregar API keys: {e}", exc_info=True)

    def _save_keys(self):
        """Guarda keys no ficheiro"""
        try:
            self.keys_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'keys': [
                    {
                        'key': key.key,
                        'name': key.name,
                        'access_level': key.access_level.value,
                        'created_at': key.created_at.isoformat(),
                        'expires_at': key.expires_at.isoformat() if key.expires_at else None,
                        'enabled': key.enabled,
                        'description': key.description,
                        'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                        'usage_count': key.usage_count
                    }
                    for key in self.keys.values()
                ]
            }

            with open(self.keys_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"API keys guardadas em {self.keys_file}")

        except Exception as e:
            logger.error(f"Erro ao guardar API keys: {e}", exc_info=True)

    def generate_key(
        self,
        name: str,
        access_level: AccessLevel = AccessLevel.STANDARD,
        expires_in_days: Optional[int] = None,
        description: str = ""
    ) -> str:
        """
        Gera nova API key

        Args:
            name: Nome descritivo da key
            access_level: Nível de acesso
            expires_in_days: Dias até expirar (None = sem expiração)
            description: Descrição opcional

        Returns:
            API key gerada (formato: nsp_xxxxxxxxxxxxxxxxxxxx)
        """
        # Gerar key segura
        random_bytes = secrets.token_bytes(32)
        key = "nsp_" + secrets.token_urlsafe(32)

        # Calcular expiração
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)

        # Criar API key
        api_key = APIKey(
            key=key,
            name=name,
            access_level=access_level,
            expires_at=expires_at,
            description=description
        )

        self.keys[key] = api_key
        self._save_keys()

        logger.info(f"Nova API key gerada: {name} (nivel: {access_level.value})")

        return key

    def validate_key(self, key: str) -> Optional[APIKey]:
        """
        Valida API key

        Args:
            key: API key a validar

        Returns:
            APIKey se válida, None se inválida
        """
        if not key or not key.startswith("nsp_"):
            return None

        api_key = self.keys.get(key)

        if not api_key or not api_key.is_valid():
            return None

        # Registrar uso
        api_key.record_usage()
        self._save_keys()

        return api_key

    def revoke_key(self, key: str) -> bool:
        """
        Revoga (desativa) uma API key

        Args:
            key: API key a revogar

        Returns:
            True se revogada, False se não encontrada
        """
        api_key = self.keys.get(key)

        if not api_key:
            return False

        api_key.enabled = False
        self._save_keys()

        logger.info(f"API key revogada: {api_key.name}")

        return True

    def delete_key(self, key: str) -> bool:
        """
        Remove completamente uma API key

        Args:
            key: API key a remover

        Returns:
            True se removida, False se não encontrada
        """
        if key not in self.keys:
            return False

        name = self.keys[key].name
        del self.keys[key]
        self._save_keys()

        logger.info(f"API key removida: {name}")

        return True

    def list_keys(self, include_disabled: bool = False) -> List[Dict]:
        """
        Lista todas as API keys

        Args:
            include_disabled: Incluir keys desativadas

        Returns:
            Lista de dicts com informação das keys
        """
        keys = []

        for api_key in self.keys.values():
            if not include_disabled and not api_key.enabled:
                continue

            keys.append(api_key.to_dict())

        return keys

    def get_access_level(self, key: str) -> Optional[AccessLevel]:
        """Obtém nível de acesso de uma key"""
        api_key = self.validate_key(key)
        return api_key.access_level if api_key else None

    def has_permission(self, key: str, required_level: AccessLevel) -> bool:
        """
        Verifica se key tem permissão para um nível de acesso

        Hierarquia: READ_ONLY < STANDARD < ADMIN < FULL
        """
        api_key = self.validate_key(key)

        if not api_key:
            return False

        levels_hierarchy = {
            AccessLevel.READ_ONLY: 1,
            AccessLevel.STANDARD: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.FULL: 4
        }

        return levels_hierarchy[api_key.access_level] >= levels_hierarchy[required_level]


# Instância global
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Obtém instância global do API key manager"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
        logger.info("APIKeyManager inicializado")
    return _api_key_manager


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    manager = get_api_key_manager()

    # Gerar keys de exemplo
    print("\n🔑 Gerando API keys de exemplo...")

    key1 = manager.generate_key(
        name="Plugin Lightroom",
        access_level=AccessLevel.STANDARD,
        description="Key principal do plugin Lightroom"
    )
    print(f"  Standard Key: {key1}")

    key2 = manager.generate_key(
        name="Admin Dashboard",
        access_level=AccessLevel.ADMIN,
        expires_in_days=90,
        description="Key admin com expiração 90 dias"
    )
    print(f"  Admin Key: {key2}")

    key3 = manager.generate_key(
        name="Read-only Monitor",
        access_level=AccessLevel.READ_ONLY,
        description="Key apenas leitura para monitorização"
    )
    print(f"  Read-only Key: {key3}")

    # Listar keys
    print("\n📋 API Keys criadas:")
    for key_info in manager.list_keys():
        print(f"  • {key_info['name']} ({key_info['access_level']})")
        print(f"    Prefix: {key_info['key_prefix']}")
        print(f"    Created: {key_info['created_at']}")
        print(f"    Enabled: {key_info['enabled']}")
        print()

    # Validar key
    print(f"\n✅ Validando key1...")
    validated = manager.validate_key(key1)
    if validated:
        print(f"  ✓ Key válida: {validated.name}")
        print(f"  ✓ Access level: {validated.access_level.value}")
        print(f"  ✓ Usage count: {validated.usage_count}")

    # Testar permissões
    print(f"\n🔐 Testando permissões...")
    print(f"  key1 (STANDARD) tem STANDARD? {manager.has_permission(key1, AccessLevel.STANDARD)}")
    print(f"  key1 (STANDARD) tem ADMIN? {manager.has_permission(key1, AccessLevel.ADMIN)}")
    print(f"  key2 (ADMIN) tem ADMIN? {manager.has_permission(key2, AccessLevel.ADMIN)}")
    print(f"  key3 (READ_ONLY) tem STANDARD? {manager.has_permission(key3, AccessLevel.STANDARD)}")
