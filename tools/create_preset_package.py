#!/usr/bin/env python3
"""
tools/create_preset_package.py

Script CLI para criar packages .nsppreset a partir de modelos treinados.

Uso:
    python tools/create_preset_package.py \
        --name "Nelson Silva Cinematic" \
        --models models/ \
        --previews previews/ \
        --output nelson_silva_cinematic.nsppreset

    python tools/create_preset_package.py \
        --name "Wedding Collection" \
        --author "João Silva" \
        --email "joao@example.com" \
        --models /path/to/models \
        --output wedding_collection.nsppreset
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Adicionar raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.preset_manager import PresetManager
from services.preset_package import create_preview_images

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse argumentos da linha de comandos."""
    parser = argparse.ArgumentParser(
        description="Cria um package .nsppreset a partir de modelos treinados",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:

  Criar preset básico:
    %(prog)s --name "My Preset" --models models/ --output my_preset.nsppreset

  Criar preset com previews:
    %(prog)s --name "Cinematic" --models models/ --previews previews/ --output cinematic.nsppreset

  Criar preset completo:
    %(prog)s \
        --name "Wedding Collection" \
        --author "João Silva" \
        --email "joao@example.com" \
        --website "https://joaosilva.com" \
        --description "Preset profissional para casamentos" \
        --category "Wedding" \
        --tags "wedding,romantic,soft" \
        --models /path/to/models \
        --previews /path/to/previews \
        --output wedding.nsppreset
        """
    )

    # Obrigatórios
    parser.add_argument(
        "--name",
        required=True,
        help="Nome do preset"
    )

    parser.add_argument(
        "--models",
        required=True,
        type=Path,
        help="Diretório com os modelos (*.pth, *.pkl, *.json)"
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Caminho para o ficheiro .nsppreset a criar"
    )

    # Opcionais - Autor
    parser.add_argument(
        "--author",
        default="Unknown",
        help="Nome do autor do preset (default: Unknown)"
    )

    parser.add_argument(
        "--email",
        default="",
        help="Email do autor (opcional)"
    )

    parser.add_argument(
        "--website",
        help="Website do autor (opcional)"
    )

    parser.add_argument(
        "--instagram",
        help="Instagram do autor (opcional, ex: @username)"
    )

    # Opcionais - Descrição
    parser.add_argument(
        "--description",
        default="",
        help="Descrição do preset (opcional)"
    )

    parser.add_argument(
        "--category",
        default="Custom",
        choices=["Professional", "Wedding", "Portrait", "Landscape", "Custom", "Default"],
        help="Categoria do preset (default: Custom)"
    )

    parser.add_argument(
        "--tags",
        help="Tags separadas por vírgula (ex: 'cinematic,moody,dramatic')"
    )

    # Opcionais - Previews
    parser.add_argument(
        "--previews",
        type=Path,
        help="Diretório com imagens para previews (opcional)"
    )

    # Opcionais - Licença
    parser.add_argument(
        "--license",
        default="free",
        choices=["free", "commercial", "single-user"],
        help="Tipo de licença (default: free)"
    )

    parser.add_argument(
        "--price",
        type=float,
        default=0.0,
        help="Preço do preset em EUR (default: 0.0)"
    )

    # Opcionais - Técnico
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Versão do preset (default: 1.0.0)"
    )

    parser.add_argument(
        "--num-samples",
        type=int,
        default=0,
        help="Número de amostras usadas no treino (opcional)"
    )

    # Flags
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verbose (mais logs)"
    )

    return parser.parse_args()


def validate_arguments(args: argparse.Namespace) -> None:
    """
    Valida argumentos fornecidos.

    Raises:
        ValueError: Se argumentos inválidos
    """
    # Validar diretório de modelos
    if not args.models.exists():
        raise ValueError(f"Diretório de modelos não encontrado: {args.models}")

    if not args.models.is_dir():
        raise ValueError(f"Caminho de modelos não é um diretório: {args.models}")

    # Validar previews (se fornecidos)
    if args.previews:
        if not args.previews.exists():
            raise ValueError(f"Diretório de previews não encontrado: {args.previews}")

        if not args.previews.is_dir():
            raise ValueError(f"Caminho de previews não é um diretório: {args.previews}")

    # Validar output
    if args.output.exists():
        logger.warning(f"Ficheiro de output já existe e será sobrescrito: {args.output}")

    # Validar extensão
    if not str(args.output).endswith('.nsppreset'):
        args.output = Path(str(args.output) + '.nsppreset')
        logger.info(f"Extensão .nsppreset adicionada: {args.output}")


def collect_preview_images(previews_dir: Optional[Path]) -> Optional[List[Path]]:
    """
    Recolhe imagens de preview do diretório.

    Args:
        previews_dir: Diretório com as imagens

    Returns:
        Lista de Paths para as imagens, ou None se sem previews
    """
    if not previews_dir:
        return None

    # Extensões suportadas
    extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}

    images = []
    for ext in extensions:
        images.extend(previews_dir.glob(f"*{ext}"))
        images.extend(previews_dir.glob(f"*{ext.upper()}"))

    if not images:
        logger.warning(f"Nenhuma imagem encontrada em: {previews_dir}")
        return None

    # Ordenar por nome e limitar a 6
    images = sorted(images)[:6]
    logger.info(f"Encontradas {len(images)} imagens de preview")

    return images


def create_metadata_dict(args: argparse.Namespace) -> dict:
    """
    Cria dict de metadata a partir dos argumentos.

    Args:
        args: Argumentos parseados

    Returns:
        Dict com metadata para o preset
    """
    metadata = {
        "name": args.name,
        "version": args.version,
        "description": args.description,
        "category": args.category,
        "author_name": args.author,
        "author_email": args.email,
        "license_type": args.license,
        "price": args.price
    }

    # Adicionar campos opcionais se fornecidos
    if args.website:
        metadata["author_website"] = args.website

    if args.instagram:
        metadata["author_instagram"] = args.instagram

    if args.tags:
        # Converter string separada por vírgulas em lista
        metadata["tags"] = [tag.strip() for tag in args.tags.split(",")]
    else:
        metadata["tags"] = []

    if args.num_samples > 0:
        metadata["num_samples"] = args.num_samples

    return metadata


def main() -> int:
    """
    Função principal.

    Returns:
        Exit code (0 = sucesso, 1 = erro)
    """
    try:
        # Parse argumentos
        args = parse_arguments()

        # Configurar logging
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        logger.info("=" * 70)
        logger.info("NSP Preset Package Creator")
        logger.info("=" * 70)

        # Validar argumentos
        logger.info("A validar argumentos...")
        validate_arguments(args)

        # Recolher previews
        logger.info("A recolher previews...")
        preview_images = collect_preview_images(args.previews)

        # Criar metadata
        logger.info("A criar metadata...")
        metadata = create_metadata_dict(args)

        logger.info(f"Preset: {metadata['name']} v{metadata['version']}")
        logger.info(f"Autor: {metadata['author_name']}")
        logger.info(f"Categoria: {metadata['category']}")
        logger.info(f"Tags: {', '.join(metadata['tags']) if metadata['tags'] else 'Nenhuma'}")

        # Criar preset manager
        logger.info("A inicializar PresetManager...")
        preset_manager = PresetManager()

        # Criar package
        logger.info("A criar package .nsppreset...")
        logger.info(f"Modelos: {args.models}")
        logger.info(f"Output: {args.output}")

        output_path = preset_manager.create_preset_package(
            models_dir=args.models,
            metadata=metadata,
            previews=preview_images,
            output_path=args.output
        )

        # Sucesso
        logger.info("=" * 70)
        logger.info(f"✓ Preset criado com sucesso!")
        logger.info(f"✓ Ficheiro: {output_path}")
        logger.info(f"✓ Tamanho: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 70)

        # Validar package criado
        logger.info("A validar package criado...")
        validation_result = preset_manager.validate_preset(output_path)

        if validation_result["valid"]:
            logger.info("✓ Package validado com sucesso!")
            manifest = validation_result["manifest"]
            logger.info(f"  - Preset ID: {manifest['preset']['id']}")
            logger.info(f"  - Formato: {manifest['format_version']}")
        else:
            logger.error("✗ Validação falhou:")
            for error in validation_result["errors"]:
                logger.error(f"  - {error}")
            return 1

        return 0

    except KeyboardInterrupt:
        logger.warning("\n\nInterrompido pelo utilizador")
        return 1

    except Exception as e:
        logger.error(f"\n✗ Erro ao criar preset: {e}", exc_info=args.verbose if 'args' in locals() else False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
