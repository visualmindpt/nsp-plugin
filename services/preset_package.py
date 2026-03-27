"""
services/preset_package.py

Classe para criar e extrair packages .nsppreset (formato ZIP).
Valida estrutura conforme especificação do PRESET_MARKETPLACE.md.
"""
from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# Limite de tamanho do package: 100MB
MAX_PACKAGE_SIZE_MB = 100
MAX_PACKAGE_SIZE_BYTES = MAX_PACKAGE_SIZE_MB * 1024 * 1024

# Ficheiros obrigatórios no package
REQUIRED_MODEL_FILES = [
    "classifier.pth",
    "refinement.pth",
    "preset_centers.json",
    "scaler_stat.pkl",
    "scaler_deep.pkl",
    "scaler_deltas.pkl",
    "delta_columns.json"
]

REQUIRED_PREVIEW_FILES = [
    "thumbnail.jpg",
    "hero.jpg"
]


class PresetPackageError(Exception):
    """Erro ao processar preset package."""
    pass


class PresetPackage:
    """
    Classe para criar e extrair packages .nsppreset.

    Um package .nsppreset é um ficheiro ZIP com a seguinte estrutura:
    - manifest.json (obrigatório)
    - models/ (obrigatório)
    - previews/ (obrigatório)
    - docs/ (opcional)
    - signature.sha256 (obrigatório)
    """

    def __init__(self, package_path: Optional[Path] = None):
        """
        Inicializa o PresetPackage.

        Args:
            package_path: Caminho para o ficheiro .nsppreset (para leitura).
                         Se None, cria package novo.
        """
        self.package_path = Path(package_path) if package_path else None
        self.manifest: Optional[Dict] = None
        self.temp_dir: Optional[Path] = None

    @classmethod
    def from_directory(cls, source_dir: Path, output_path: Path) -> PresetPackage:
        """
        Cria package .nsppreset a partir de um diretório.

        Args:
            source_dir: Diretório com estrutura do preset (manifest.json, models/, etc.)
            output_path: Caminho para o ficheiro .nsppreset a criar

        Returns:
            Instância de PresetPackage com o package criado

        Raises:
            PresetPackageError: Se a estrutura for inválida
        """
        source_dir = Path(source_dir)
        output_path = Path(output_path)

        # Validar estrutura do diretório
        manifest_path = source_dir / "manifest.json"
        if not manifest_path.exists():
            raise PresetPackageError("manifest.json não encontrado")

        # Ler e validar manifest
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise PresetPackageError(f"manifest.json inválido: {e}")

        cls._validate_manifest(manifest)

        # Validar presença de modelos
        models_dir = source_dir / "models"
        if not models_dir.exists():
            raise PresetPackageError("Diretório models/ não encontrado")

        for model_file in REQUIRED_MODEL_FILES:
            if not (models_dir / model_file).exists():
                raise PresetPackageError(f"Ficheiro de modelo obrigatório não encontrado: {model_file}")

        # Validar presença de previews
        previews_dir = source_dir / "previews"
        if not previews_dir.exists():
            raise PresetPackageError("Diretório previews/ não encontrado")

        for preview_file in REQUIRED_PREVIEW_FILES:
            if not (previews_dir / preview_file).exists():
                logger.warning(f"Preview obrigatório não encontrado: {preview_file}")

        # Gerar assinatura
        signature = cls._calculate_signature(source_dir)
        signature_path = source_dir / "signature.sha256"
        with open(signature_path, 'w', encoding='utf-8') as f:
            f.write(signature)

        # Criar ZIP
        try:
            cls._create_zip(source_dir, output_path)
        finally:
            # Remover signature temporário
            if signature_path.exists():
                signature_path.unlink()

        logger.info(f"Package criado com sucesso: {output_path}")

        pkg = cls(output_path)
        pkg.manifest = manifest
        return pkg

    def to_directory(self, extract_to: Path, validate: bool = True) -> Path:
        """
        Extrai package .nsppreset para um diretório.

        Args:
            extract_to: Diretório de destino
            validate: Se True, valida integridade antes de extrair

        Returns:
            Path para o diretório extraído

        Raises:
            PresetPackageError: Se o package for inválido ou extração falhar
        """
        if not self.package_path or not self.package_path.exists():
            raise PresetPackageError("Package path não definido ou não existe")

        extract_to = Path(extract_to)

        # Validar tamanho do ficheiro
        file_size = self.package_path.stat().st_size
        if file_size > MAX_PACKAGE_SIZE_BYTES:
            raise PresetPackageError(
                f"Package excede tamanho máximo de {MAX_PACKAGE_SIZE_MB}MB: {file_size / 1024 / 1024:.1f}MB"
            )

        # Validar se é ZIP válido
        if not zipfile.is_zipfile(self.package_path):
            raise PresetPackageError("Ficheiro não é um ZIP válido")

        # Extrair para diretório temporário primeiro (segurança)
        extract_to.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(self.package_path, 'r') as zipf:
                # Verificar path traversal
                for member in zipf.namelist():
                    member_path = Path(member)
                    if member_path.is_absolute() or '..' in member_path.parts:
                        raise PresetPackageError(f"Path traversal detectado: {member}")

                # Extrair
                zipf.extractall(extract_to)

            # Validar estrutura extraída
            if validate:
                self._validate_extracted_structure(extract_to)

            logger.info(f"Package extraído com sucesso para: {extract_to}")
            return extract_to

        except zipfile.BadZipFile as e:
            raise PresetPackageError(f"ZIP corrompido: {e}")
        except Exception as e:
            raise PresetPackageError(f"Erro ao extrair package: {e}")

    def validate_structure(self) -> bool:
        """
        Valida a estrutura do package sem extrair.

        Returns:
            True se válido

        Raises:
            PresetPackageError: Se inválido
        """
        if not self.package_path or not self.package_path.exists():
            raise PresetPackageError("Package path não definido ou não existe")

        try:
            with zipfile.ZipFile(self.package_path, 'r') as zipf:
                files = zipf.namelist()

                # Verificar manifest.json
                if "manifest.json" not in files:
                    raise PresetPackageError("manifest.json não encontrado no package")

                # Ler e validar manifest
                with zipf.open("manifest.json") as f:
                    manifest = json.load(f)
                    self._validate_manifest(manifest)
                    self.manifest = manifest

                # Verificar signature
                if "signature.sha256" not in files:
                    raise PresetPackageError("signature.sha256 não encontrado no package")

                # Verificar modelos obrigatórios
                for model_file in REQUIRED_MODEL_FILES:
                    if f"models/{model_file}" not in files:
                        raise PresetPackageError(f"Modelo obrigatório não encontrado: {model_file}")

                logger.info("Estrutura do package válida")
                return True

        except zipfile.BadZipFile as e:
            raise PresetPackageError(f"ZIP corrompido: {e}")

    def calculate_signature(self) -> str:
        """
        Calcula SHA256 hash do package.

        Returns:
            Hash hexadecimal
        """
        if not self.package_path or not self.package_path.exists():
            raise PresetPackageError("Package path não definido")

        hasher = hashlib.sha256()
        with open(self.package_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_manifest(self) -> Dict:
        """
        Obtém o manifest.json do package.

        Returns:
            Dict com o manifest

        Raises:
            PresetPackageError: Se não conseguir ler o manifest
        """
        if self.manifest:
            return self.manifest

        if not self.package_path or not self.package_path.exists():
            raise PresetPackageError("Package path não definido")

        try:
            with zipfile.ZipFile(self.package_path, 'r') as zipf:
                with zipf.open("manifest.json") as f:
                    self.manifest = json.load(f)
                    return self.manifest
        except Exception as e:
            raise PresetPackageError(f"Erro ao ler manifest: {e}")

    @staticmethod
    def _validate_manifest(manifest: Dict) -> None:
        """
        Valida estrutura do manifest.json.

        Args:
            manifest: Dict do manifest

        Raises:
            PresetPackageError: Se inválido
        """
        required_keys = ["format_version", "preset", "author", "models", "compatibility"]
        for key in required_keys:
            if key not in manifest:
                raise PresetPackageError(f"Chave obrigatória não encontrada no manifest: {key}")

        # Validar preset
        preset = manifest["preset"]
        preset_required = ["id", "name", "version", "description"]
        for key in preset_required:
            if key not in preset:
                raise PresetPackageError(f"Chave obrigatória não encontrada em preset: {key}")

        # Validar author
        author = manifest["author"]
        if "name" not in author:
            raise PresetPackageError("author.name obrigatório no manifest")

        # Validar models
        models = manifest["models"]
        models_required = ["format", "architecture"]
        for key in models_required:
            if key not in models:
                raise PresetPackageError(f"Chave obrigatória não encontrada em models: {key}")

    @staticmethod
    def _calculate_signature(directory: Path) -> str:
        """
        Calcula SHA256 hash de todos os ficheiros no diretório (exceto signature.sha256).

        Args:
            directory: Diretório a processar

        Returns:
            Hash hexadecimal
        """
        hasher = hashlib.sha256()

        # Ordenar ficheiros para hash determinístico
        files = sorted(directory.rglob("*"))
        for file_path in files:
            if file_path.is_file() and file_path.name != "signature.sha256":
                # Adicionar path relativo ao hash (para detectar renomeações)
                rel_path = file_path.relative_to(directory)
                hasher.update(str(rel_path).encode('utf-8'))

                # Adicionar conteúdo do ficheiro
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)

        return hasher.hexdigest()

    @staticmethod
    def _create_zip(source_dir: Path, output_path: Path) -> None:
        """
        Cria ficheiro ZIP a partir de um diretório.

        Args:
            source_dir: Diretório fonte
            output_path: Caminho para o ZIP a criar
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

    @staticmethod
    def _validate_extracted_structure(extract_dir: Path) -> None:
        """
        Valida estrutura de um diretório extraído.

        Args:
            extract_dir: Diretório a validar

        Raises:
            PresetPackageError: Se estrutura inválida
        """
        # Verificar manifest
        manifest_path = extract_dir / "manifest.json"
        if not manifest_path.exists():
            raise PresetPackageError("manifest.json não encontrado após extração")

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                PresetPackage._validate_manifest(manifest)
        except Exception as e:
            raise PresetPackageError(f"Erro ao validar manifest após extração: {e}")

        # Verificar modelos
        models_dir = extract_dir / "models"
        if not models_dir.exists():
            raise PresetPackageError("Diretório models/ não encontrado após extração")

        for model_file in REQUIRED_MODEL_FILES:
            if not (models_dir / model_file).exists():
                raise PresetPackageError(f"Modelo obrigatório não encontrado após extração: {model_file}")

        # Verificar signature
        signature_path = extract_dir / "signature.sha256"
        if not signature_path.exists():
            raise PresetPackageError("signature.sha256 não encontrado após extração")

        # Validar integridade
        with open(signature_path, 'r', encoding='utf-8') as f:
            stored_signature = f.read().strip()

        # Calcular signature atual (excluindo signature.sha256)
        calculated_signature = PresetPackage._calculate_signature(extract_dir)

        if stored_signature != calculated_signature:
            raise PresetPackageError(
                f"Assinatura do package não corresponde. "
                f"Esperado: {stored_signature}, Calculado: {calculated_signature}"
            )

        logger.info("Integridade do package validada com sucesso")


def create_preview_images(
    source_images: List[Path],
    output_dir: Path,
    thumbnail_size: tuple[int, int] = (400, 400),
    hero_size: tuple[int, int] = (1920, 1080)
) -> None:
    """
    Cria previews otimizados para o preset package.

    Args:
        source_images: Lista de imagens fonte
        output_dir: Diretório de destino
        thumbnail_size: Tamanho do thumbnail
        hero_size: Tamanho da hero image
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not source_images:
        logger.warning("Nenhuma imagem fonte fornecida para previews")
        return

    # Criar thumbnail (primeira imagem)
    try:
        img = Image.open(source_images[0])
        img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        img.save(output_dir / "thumbnail.jpg", "JPEG", quality=90, optimize=True)
        logger.info(f"Thumbnail criado: {output_dir / 'thumbnail.jpg'}")
    except Exception as e:
        logger.error(f"Erro ao criar thumbnail: {e}")

    # Criar hero image (primeira imagem)
    try:
        img = Image.open(source_images[0])
        img.thumbnail(hero_size, Image.Resampling.LANCZOS)
        img.save(output_dir / "hero.jpg", "JPEG", quality=95, optimize=True)
        logger.info(f"Hero image criada: {output_dir / 'hero.jpg'}")
    except Exception as e:
        logger.error(f"Erro ao criar hero image: {e}")

    # Copiar exemplos before/after (máximo 6 imagens)
    for idx, img_path in enumerate(source_images[:6], 1):
        try:
            img = Image.open(img_path)
            # Redimensionar para max 1920x1080 mantendo aspect ratio
            img.thumbnail(hero_size, Image.Resampling.LANCZOS)
            output_path = output_dir / f"example_{idx:02d}.jpg"
            img.save(output_path, "JPEG", quality=92, optimize=True)
            logger.info(f"Exemplo criado: {output_path}")
        except Exception as e:
            logger.error(f"Erro ao processar exemplo {idx}: {e}")
