#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/test_preset_system.py

Script de teste completo para o sistema de gestão de presets.
"""
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.preset_manager import PresetManager
from services.preset_package import PresetPackage
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_list_presets():
    """Testa listagem de presets."""
    logger.info("\n=== Teste 1: Listar Presets ===")
    manager = PresetManager(models_dir=PROJECT_ROOT / "models")
    presets = manager.list_presets(include_default=True)

    logger.info("Presets encontrados: {}".format(len(presets)))
    for preset in presets:
        logger.info("  - {} v{} (ID: {})".format(
            preset['name'],
            preset['version'],
            preset['id']
        ))

    assert len(presets) > 0, "Nenhum preset encontrado"
    logger.info("✓ Teste passou")
    return True


def test_get_preset_detail():
    """Testa obtenção de detalhes de preset."""
    logger.info("\n=== Teste 2: Obter Detalhes de Preset ===")
    manager = PresetManager(models_dir=PROJECT_ROOT / "models")

    # Obter preset default
    preset = manager.get_preset("default-preset")

    logger.info("Preset: {} v{}".format(
        preset['preset']['name'],
        preset['preset']['version']
    ))
    logger.info("Autor: {}".format(preset['author']['name']))
    logger.info("Categoria: {}".format(preset['preset']['category']))

    assert preset is not None, "Preset default não encontrado"
    logger.info("✓ Teste passou")
    return True


def test_active_preset():
    """Testa gestão de preset activo."""
    logger.info("\n=== Teste 3: Preset Activo ===")
    manager = PresetManager(models_dir=PROJECT_ROOT / "models")

    # Obter preset activo
    active = manager.get_active_preset()

    if active:
        logger.info("Preset activo: {} (ID: {})".format(
            active['preset']['name'],
            active['preset']['id']
        ))
        logger.info("✓ Teste passou")
        return True
    else:
        logger.warning("Nenhum preset activo definido")
        return False


def test_create_preset_package():
    """Testa criação de package .nsppreset."""
    logger.info("\n=== Teste 4: Criar Package .nsppreset ===")

    manager = PresetManager(models_dir=PROJECT_ROOT / "models")

    # Criar metadata de teste
    metadata = {
        "name": "Test Preset",
        "version": "1.0.0",
        "description": "Preset de teste criado automaticamente",
        "author_name": "Test Author",
        "author_email": "test@example.com",
        "category": "Custom",
        "tags": ["test", "demo"],
        "license_type": "free"
    }

    # Criar package
    output_path = PROJECT_ROOT / "tmp" / "test_preset.nsppreset"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = manager.create_preset_package(
            models_dir=PROJECT_ROOT / "models",
            metadata=metadata,
            previews=None,
            output_path=output_path
        )

        logger.info("Package criado: {}".format(result))
        logger.info("Tamanho: {:.2f} MB".format(
            result.stat().st_size / 1024 / 1024
        ))

        # Validar package
        validation = manager.validate_preset(result)

        if validation['valid']:
            logger.info("✓ Package válido")
        else:
            logger.error("✗ Package inválido: {}".format(validation['errors']))
            return False

        logger.info("✓ Teste passou")
        return True

    except Exception as e:
        logger.error("✗ Erro ao criar package: {}".format(e), exc_info=True)
        return False


def test_install_uninstall_preset():
    """Testa instalação e desinstalação de preset."""
    logger.info("\n=== Teste 5: Instalar/Desinstalar Preset ===")

    manager = PresetManager(models_dir=PROJECT_ROOT / "models")

    # Criar package temporário
    metadata = {
        "name": "Temporary Test Preset",
        "version": "1.0.0",
        "description": "Preset temporário para teste",
        "author_name": "Test",
        "category": "Custom",
        "license_type": "free"
    }

    package_path = PROJECT_ROOT / "tmp" / "temp_preset.nsppreset"
    package_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Criar package
        manager.create_preset_package(
            models_dir=PROJECT_ROOT / "models",
            metadata=metadata,
            previews=None,
            output_path=package_path
        )

        # Instalar
        logger.info("A instalar preset...")
        preset_id = manager.install_preset(package_path, force=True)
        logger.info("Preset instalado: {}".format(preset_id))

        # Verificar se foi instalado
        presets = manager.list_presets(include_default=True)
        installed = any(p['id'] == preset_id for p in presets)
        assert installed, "Preset não foi instalado correctamente"

        # Desinstalar
        logger.info("A desinstalar preset...")
        manager.uninstall_preset(preset_id)

        # Verificar se foi removido
        presets = manager.list_presets(include_default=True)
        removed = not any(p['id'] == preset_id for p in presets)
        assert removed, "Preset não foi removido correctamente"

        logger.info("✓ Teste passou")
        return True

    except Exception as e:
        logger.error("✗ Erro: {}".format(e), exc_info=True)
        return False
    finally:
        # Limpar
        if package_path.exists():
            package_path.unlink()


def test_export_preset():
    """Testa exportação de preset existente."""
    logger.info("\n=== Teste 6: Exportar Preset ===")

    manager = PresetManager(models_dir=PROJECT_ROOT / "models")
    output_path = PROJECT_ROOT / "tmp" / "exported_default.nsppreset"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Exportar preset default
        result = manager.export_preset(
            preset_id="default-preset",
            output_path=output_path,
            use_current_models=False
        )

        logger.info("Preset exportado: {}".format(result))
        logger.info("Tamanho: {:.2f} MB".format(
            result.stat().st_size / 1024 / 1024
        ))

        # Validar
        package = PresetPackage(result)
        package.validate_structure()

        logger.info("✓ Teste passou")
        return True

    except Exception as e:
        logger.error("✗ Erro: {}".format(e), exc_info=True)
        return False


def run_all_tests():
    """Executa todos os testes."""
    logger.info("=" * 70)
    logger.info("TESTE COMPLETO DO SISTEMA DE PRESETS")
    logger.info("=" * 70)

    tests = [
        ("Listar Presets", test_list_presets),
        ("Obter Detalhes", test_get_preset_detail),
        ("Preset Activo", test_active_preset),
        ("Criar Package", test_create_preset_package),
        ("Instalar/Desinstalar", test_install_uninstall_preset),
        ("Exportar Preset", test_export_preset),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error("✗ Teste '{}' falhou: {}".format(name, e), exc_info=True)
            results.append((name, False))

    # Sumário
    logger.info("\n" + "=" * 70)
    logger.info("SUMÁRIO DOS TESTES")
    logger.info("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASSOU" if result else "✗ FALHOU"
        logger.info("{}: {}".format(name, status))

    logger.info("-" * 70)
    logger.info("Resultados: {}/{} testes passaram".format(passed, total))
    logger.info("=" * 70)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
