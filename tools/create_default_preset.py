#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/create_default_preset.py

Script para criar o preset default com os modelos actuais.
"""
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.preset_manager import ensure_default_preset_exists
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("=" * 70)
    print("NSP Default Preset Creator")
    print("=" * 70)

    try:
        ensure_default_preset_exists(models_dir=PROJECT_ROOT)
        print("\nPreset default criado/verificado com sucesso!")
        print("=" * 70)
    except Exception as e:
        print("\nErro ao criar preset default: {}".format(e))
        sys.exit(1)
