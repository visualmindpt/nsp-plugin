# -*- coding: utf-8 -*-
"""
Training Validator - Valida configuracao e ambiente antes de iniciar treino
Previne erros comuns e economiza tempo ao detectar problemas antes de iniciar
"""

import sys
from pathlib import Path
import logging
from typing import List, Tuple, Optional
import torch
import psutil
import shutil

# Adicionar root ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config_loader import config

logger = logging.getLogger(__name__)


class TrainingValidator:
    """Valida pré-requisitos para treino"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_all(self, catalog_path: Optional[Path] = None) -> Tuple[bool, List[str], List[str]]:
        """
        Executa todas as validações

        Returns:
            (is_valid, errors, warnings)
        """
        logger.info("🔍 Iniciando validações de pré-treino...")

        self._validate_python_version()
        self._validate_dependencies()
        self._validate_catalog(catalog_path)
        self._validate_directories()
        self._validate_system_resources()
        self._validate_gpu()
        self._validate_disk_space()
        self._validate_config()

        # Resumo
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMO DAS VALIDAÇÕES")
        logger.info("="*60)

        if self.errors:
            logger.error(f"❌ {len(self.errors)} ERROS CRÍTICOS encontrados:")
            for err in self.errors:
                logger.error(f"   • {err}")

        if self.warnings:
            logger.warning(f"⚠️  {len(self.warnings)} AVISOS encontrados:")
            for warn in self.warnings:
                logger.warning(f"   • {warn}")

        if self.info:
            logger.info(f"ℹ️  {len(self.info)} INFORMAÇÕES:")
            for info in self.info:
                logger.info(f"   • {info}")

        is_valid = len(self.errors) == 0

        if is_valid:
            logger.info("\n✅ Todas as validações passaram! Pronto para treinar.")
        else:
            logger.error("\n❌ Corrija os erros acima antes de iniciar o treino.")

        logger.info("="*60 + "\n")

        return is_valid, self.errors, self.warnings

    def _validate_python_version(self):
        """Verifica versão do Python"""
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.errors.append(f"Python 3.8+ requerido. Versão atual: {version.major}.{version.minor}")
        else:
            self.info.append(f"Python {version.major}.{version.minor}.{version.micro} ✓")

    def _validate_dependencies(self):
        """Verifica dependências críticas"""
        required_packages = [
            ('torch', 'PyTorch'),
            ('numpy', 'NumPy'),
            ('pandas', 'Pandas'),
            ('sklearn', 'scikit-learn'),
            ('PIL', 'Pillow'),
            ('cv2', 'OpenCV')
        ]

        for package, name in required_packages:
            try:
                __import__(package)
                self.info.append(f"{name} instalado ✓")
            except ImportError:
                self.errors.append(f"{name} não instalado. Execute: pip install {package}")

    def _validate_catalog(self, catalog_path: Optional[Path]):
        """Valida catálogo do Lightroom"""
        if catalog_path is None:
            self.warnings.append("Nenhum catálogo especificado. Usar dados existentes ou especificar com --catalog")
            return

        catalog_path = Path(catalog_path)

        if not catalog_path.exists():
            self.errors.append(f"Catálogo não encontrado: {catalog_path}")
            return

        if not catalog_path.suffix == '.lrcat':
            self.errors.append(f"Ficheiro não é um catálogo válido (.lrcat): {catalog_path}")
            return

        # Verificar tamanho mínimo (catálogos válidos têm pelo menos 100KB)
        size_mb = catalog_path.stat().st_size / (1024 * 1024)
        if size_mb < 0.1:
            self.warnings.append(f"Catálogo muito pequeno ({size_mb:.2f} MB). Pode estar corrompido.")
        else:
            self.info.append(f"Catálogo válido ({size_mb:.1f} MB) ✓")

        # Verificar se está aberto no Lightroom (pode causar problemas)
        try:
            with open(catalog_path, 'rb') as f:
                pass  # Apenas tenta abrir
            self.info.append("Catálogo acessível ✓")
        except PermissionError:
            self.warnings.append(
                "Catálogo pode estar aberto no Lightroom. "
                "Feche o Lightroom antes de extrair dados para evitar problemas."
            )

    def _validate_directories(self):
        """Valida estrutura de diretórios"""
        required_dirs = [
            config.get_path('models_dir'),
            config.get_path('data_dir'),
            config.get_path('logs_dir')
        ]

        for dir_path in required_dirs:
            dir_path = Path(dir_path)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.info.append(f"Criado diretório: {dir_path.name}")
                except Exception as e:
                    self.errors.append(f"Não foi possível criar {dir_path}: {e}")
            else:
                self.info.append(f"Diretório {dir_path.name} existe ✓")

    def _validate_system_resources(self):
        """Valida recursos do sistema (RAM, CPU)"""
        # RAM
        memory = psutil.virtual_memory()
        ram_gb = memory.total / (1024 ** 3)
        ram_available_gb = memory.available / (1024 ** 3)

        if ram_gb < 8:
            self.warnings.append(f"RAM total baixa: {ram_gb:.1f} GB. Recomendado: 8GB+")
        else:
            self.info.append(f"RAM total: {ram_gb:.1f} GB ✓")

        if ram_available_gb < 4:
            self.warnings.append(
                f"RAM disponível baixa: {ram_available_gb:.1f} GB. "
                "Feche aplicações para libertar memória."
            )

        # CPU
        cpu_count = psutil.cpu_count(logical=False)
        if cpu_count < 2:
            self.warnings.append(f"Poucos cores CPU: {cpu_count}. Treino pode ser lento.")
        else:
            self.info.append(f"CPU cores: {cpu_count} ✓")

    def _validate_gpu(self):
        """Valida disponibilidade e capacidade da GPU"""
        if not torch.cuda.is_available():
            self.warnings.append(
                "GPU CUDA não disponível. Treino será em CPU (10-50x mais lento). "
                "Considere usar Google Colab ou máquina com GPU."
            )
            self.info.append("Modo: CPU")
            return

        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

        self.info.append(f"GPU: {gpu_name} ({gpu_memory_gb:.1f} GB) ✓")

        if gpu_memory_gb < 4:
            self.warnings.append(
                f"Memória GPU baixa: {gpu_memory_gb:.1f} GB. "
                "Reduza batch_size se tiver erros de Out-of-Memory."
            )

        # Testar se GPU está funcional
        try:
            test_tensor = torch.randn(100, 100).cuda()
            test_result = test_tensor @ test_tensor.T
            del test_tensor, test_result
            torch.cuda.empty_cache()
            self.info.append("GPU funcional ✓")
        except Exception as e:
            self.errors.append(f"GPU não funcional: {e}")

    def _validate_disk_space(self):
        """Valida espaço em disco"""
        disk = shutil.disk_usage(config.project_root)
        free_gb = disk.free / (1024 ** 3)

        if free_gb < 1:
            self.errors.append(
                f"Espaço em disco crítico: {free_gb:.1f} GB. "
                "Liberte espaço antes de treinar."
            )
        elif free_gb < 5:
            self.warnings.append(
                f"Espaço em disco baixo: {free_gb:.1f} GB. "
                "Recomendado: 5GB+ para logs, checkpoints e modelos."
            )
        else:
            self.info.append(f"Espaço em disco: {free_gb:.1f} GB ✓")

    def _validate_config(self):
        """Valida ficheiro de configuração"""
        try:
            # Verificar se config.json está válido
            server_url = config.get_server_url()
            batch_size = config.get('training.batch_size')

            self.info.append("config.json válido ✓")

            # Validar valores sensíveis
            if batch_size < 4:
                self.warnings.append(f"batch_size muito pequeno: {batch_size}. Pode ser lento.")
            elif batch_size > 64:
                self.warnings.append(f"batch_size muito grande: {batch_size}. Pode causar OOM.")

        except Exception as e:
            self.errors.append(f"Erro ao ler config.json: {e}")


def validate_before_training(catalog_path: Optional[Path] = None) -> bool:
    """
    Função helper para validar antes de iniciar treino

    Returns:
        True se válido, False se há erros críticos
    """
    validator = TrainingValidator()
    is_valid, errors, warnings = validator.validate_all(catalog_path)
    return is_valid


# Exemplo de uso
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Valida ambiente para treino")
    parser.add_argument('--catalog', type=str, help="Caminho para catálogo .lrcat")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s - %(message)s"
    )

    catalog = Path(args.catalog) if args.catalog else None
    is_valid = validate_before_training(catalog)

    sys.exit(0 if is_valid else 1)
