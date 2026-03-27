"""
services/model_manager.py

Gestor de versões e deployment de modelos.
Responsável por:
- Backup de modelos antes de deploy
- Deploy de novos modelos para produção
- Rollback para versões anteriores
- Validação de integridade de modelos
- Tracking de versões
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import onnxruntime as ort
import torch

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelManager:
    """
    Gestor de ciclo de vida de modelos.

    Responsabilidades:
    - Versioning de modelos (backup/restore)
    - Deployment seguro (validação antes de deploy)
    - Rollback automático em caso de erro
    - Validação de integridade (modelo carrega corretamente)

    Estrutura de diretórios:
    models/ann/
    ├── multi_output_nn.onnx         # Modelo em produção
    ├── multi_output_nn.pth          # Modelo PyTorch em produção
    ├── targets_mean.npy             # Estatísticas
    ├── targets_std.npy
    └── backups/
        ├── v1_2025-11-12_10-30-00/  # Backup automático
        │   ├── multi_output_nn.onnx
        │   ├── multi_output_nn.pth
        │   ├── targets_mean.npy
        │   └── targets_std.npy
        └── v2_2025-11-13_14-20-00/
            └── ...

    Atributos:
        model_dir: Diretório raiz dos modelos (models/ann/)
        backup_dir: Diretório de backups
        production_onnx: Path do modelo ONNX em produção
        production_pth: Path do modelo PyTorch em produção
    """

    def __init__(self, model_dir: Optional[Path] = None):
        """
        Inicializa o ModelManager.

        Args:
            model_dir: Diretório dos modelos (default: APP_ROOT/models/ann)
        """
        if model_dir is None:
            from pathlib import Path
            import sys
            APP_ROOT = Path(__file__).resolve().parent.parent
            model_dir = APP_ROOT / 'models' / 'ann'

        self.model_dir = model_dir
        self.backup_dir = model_dir / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Paths dos modelos em produção
        self.production_onnx = model_dir / 'multi_output_nn.onnx'
        self.production_pth = model_dir / 'multi_output_nn.pth'
        self.targets_mean = model_dir / 'targets_mean.npy'
        self.targets_std = model_dir / 'targets_std.npy'

        logger.info(f"ModelManager inicializado | model_dir={model_dir}")

    # ========================================================================
    # VERSIONING E BACKUP
    # ========================================================================

    def get_current_model_version(self) -> Optional[str]:
        """
        Retorna versão do modelo atualmente em produção.

        Versão é inferida do timestamp do ficheiro ONNX.

        Returns:
            String de versão (ex: "v1_2025-11-12_10-30-00") ou None
        """
        if not self.production_onnx.exists():
            logger.warning("Modelo ONNX em produção não encontrado")
            return None

        try:
            # Usar timestamp de modificação como versão
            mtime = self.production_onnx.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            version = dt.strftime("prod_%Y-%m-%d_%H-%M-%S")

            logger.debug(f"Versão atual do modelo: {version}")
            return version

        except Exception as e:
            logger.error(f"Erro ao obter versão do modelo: {e}")
            return None

    def backup_current_model(self, backup_name: Optional[str] = None) -> Optional[Path]:
        """
        Cria backup do modelo atual antes de deploy.

        Args:
            backup_name: Nome do backup (se None, usa timestamp)

        Returns:
            Path do diretório de backup criado, ou None se falhou
        """
        if not self.production_onnx.exists():
            logger.warning("Nenhum modelo em produção para fazer backup")
            return None

        try:
            # Gerar nome do backup
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_name = f"v_backup_{timestamp}"

            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            # Ficheiros a fazer backup
            files_to_backup = [
                ('multi_output_nn.onnx', self.production_onnx),
                ('multi_output_nn.pth', self.production_pth),
                ('targets_mean.npy', self.targets_mean),
                ('targets_std.npy', self.targets_std)
            ]

            backed_up_count = 0
            for filename, source_path in files_to_backup:
                if source_path.exists():
                    dest_path = backup_path / filename
                    shutil.copy2(source_path, dest_path)
                    backed_up_count += 1
                    logger.debug(f"Backup criado: {filename}")

            # Criar metadata
            metadata = {
                'backup_date': datetime.now().isoformat(),
                'model_version': self.get_current_model_version(),
                'files_backed_up': backed_up_count
            }

            metadata_path = backup_path / 'metadata.json'
            import json
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            logger.info(
                f"Backup criado com sucesso | "
                f"path={backup_path} | "
                f"files={backed_up_count}"
            )

            return backup_path

        except Exception as e:
            logger.error(f"Erro ao criar backup: {e}", exc_info=True)
            return None

    def list_available_versions(self) -> List[Dict]:
        """
        Lista todas as versões disponíveis (backups).

        Returns:
            Lista de dicionários com info de cada versão:
            [
                {
                    'name': 'v_backup_2025-11-12_10-30-00',
                    'path': Path(...),
                    'backup_date': '2025-11-12T10:30:00',
                    'size_mb': 12.5
                },
                ...
            ]
        """
        versions = []

        try:
            for backup_path in sorted(self.backup_dir.iterdir(), reverse=True):
                if not backup_path.is_dir():
                    continue

                # Ler metadata se existir
                metadata_path = backup_path / 'metadata.json'
                metadata = {}
                if metadata_path.exists():
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                # Calcular tamanho
                size_bytes = sum(
                    f.stat().st_size
                    for f in backup_path.rglob('*')
                    if f.is_file()
                )
                size_mb = size_bytes / (1024 * 1024)

                versions.append({
                    'name': backup_path.name,
                    'path': str(backup_path),
                    'backup_date': metadata.get('backup_date'),
                    'model_version': metadata.get('model_version'),
                    'size_mb': round(size_mb, 2)
                })

            logger.info(f"Encontradas {len(versions)} versões de backup")
            return versions

        except Exception as e:
            logger.error(f"Erro ao listar versões: {e}")
            return []

    # ========================================================================
    # DEPLOYMENT
    # ========================================================================

    def deploy_new_model(
        self,
        new_model_onnx: Path,
        new_model_pth: Optional[Path] = None,
        new_targets_mean: Optional[Path] = None,
        new_targets_std: Optional[Path] = None,
        backup_first: bool = True,
        validate_before: bool = True
    ) -> bool:
        """
        Faz deploy de um novo modelo para produção.

        Fluxo:
        1. (Opcional) Backup do modelo atual
        2. (Opcional) Validação do novo modelo
        3. Cópia dos ficheiros para produção
        4. Verificação final

        Args:
            new_model_onnx: Path do novo modelo ONNX
            new_model_pth: Path do novo modelo PyTorch (opcional)
            new_targets_mean: Path do novo targets_mean.npy (opcional)
            new_targets_std: Path do novo targets_std.npy (opcional)
            backup_first: Se True, faz backup antes de deploy
            validate_before: Se True, valida modelo antes de deploy

        Returns:
            True se deploy bem-sucedido, False caso contrário
        """
        logger.info(f"Iniciando deploy de novo modelo | source={new_model_onnx}")

        try:
            # Passo 1: Backup
            if backup_first:
                backup_path = self.backup_current_model()
                if backup_path is None:
                    logger.warning("Backup falhou, mas continuando deploy...")
                else:
                    logger.info(f"Backup criado: {backup_path}")

            # Passo 2: Validação
            if validate_before:
                if not self.validate_model_loads(new_model_onnx):
                    logger.error("Validação do novo modelo falhou. Abortando deploy.")
                    return False
                logger.info("Novo modelo validado com sucesso")

            # Passo 3: Deploy
            # Copiar ONNX
            shutil.copy2(new_model_onnx, self.production_onnx)
            logger.info(f"ONNX copiado para produção: {self.production_onnx}")

            # Copiar PyTorch (se fornecido)
            if new_model_pth and new_model_pth.exists():
                shutil.copy2(new_model_pth, self.production_pth)
                logger.info(f"PyTorch copiado para produção: {self.production_pth}")

            # Copiar targets_mean (se fornecido)
            if new_targets_mean and new_targets_mean.exists():
                shutil.copy2(new_targets_mean, self.targets_mean)
                logger.info(f"targets_mean copiado: {self.targets_mean}")

            # Copiar targets_std (se fornecido)
            if new_targets_std and new_targets_std.exists():
                shutil.copy2(new_targets_std, self.targets_std)
                logger.info(f"targets_std copiado: {self.targets_std}")

            # Passo 4: Verificação final
            if not self.validate_model_loads(self.production_onnx):
                logger.error("ERRO CRÍTICO: Modelo em produção não carrega!")
                logger.error("Tentando rollback automático...")

                # Tentar rollback para último backup
                versions = self.list_available_versions()
                if versions:
                    latest_backup = versions[0]['name']
                    if self.rollback_to_version(latest_backup):
                        logger.info("Rollback automático bem-sucedido")
                    else:
                        logger.error("Rollback automático falhou!")

                return False

            logger.info("Deploy concluído com sucesso!")
            return True

        except Exception as e:
            logger.error(f"Erro durante deploy: {e}", exc_info=True)
            return False

    def rollback_to_version(self, version_name: str) -> bool:
        """
        Faz rollback para uma versão específica.

        Args:
            version_name: Nome da versão/backup (ex: "v_backup_2025-11-12_10-30-00")

        Returns:
            True se rollback bem-sucedido, False caso contrário
        """
        logger.info(f"Iniciando rollback para versão: {version_name}")

        backup_path = self.backup_dir / version_name

        if not backup_path.exists():
            logger.error(f"Versão não encontrada: {version_name}")
            return False

        try:
            # Verificar que backup contém ficheiros necessários
            backup_onnx = backup_path / 'multi_output_nn.onnx'
            if not backup_onnx.exists():
                logger.error(f"Backup não contém modelo ONNX: {backup_path}")
                return False

            # Fazer backup do estado atual antes de rollback
            current_backup = self.backup_current_model(
                backup_name=f"pre_rollback_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
            )
            if current_backup:
                logger.info(f"Backup de segurança criado: {current_backup}")

            # Restaurar ficheiros
            files_to_restore = [
                ('multi_output_nn.onnx', self.production_onnx),
                ('multi_output_nn.pth', self.production_pth),
                ('targets_mean.npy', self.targets_mean),
                ('targets_std.npy', self.targets_std)
            ]

            restored_count = 0
            for filename, dest_path in files_to_restore:
                source_path = backup_path / filename
                if source_path.exists():
                    shutil.copy2(source_path, dest_path)
                    restored_count += 1
                    logger.debug(f"Restaurado: {filename}")

            # Validar modelo restaurado
            if not self.validate_model_loads(self.production_onnx):
                logger.error("Modelo restaurado não carrega. Rollback falhou.")
                return False

            logger.info(
                f"Rollback concluído com sucesso | "
                f"version={version_name} | "
                f"files_restored={restored_count}"
            )

            return True

        except Exception as e:
            logger.error(f"Erro durante rollback: {e}", exc_info=True)
            return False

    # ========================================================================
    # VALIDAÇÃO
    # ========================================================================

    def validate_model_loads(self, model_path: Path) -> bool:
        """
        Valida que um modelo ONNX carrega corretamente.

        Testa:
        1. Ficheiro existe
        2. ONNX Runtime consegue carregar
        3. Modelo tem inputs/outputs esperados
        4. Inferência dummy funciona

        Args:
            model_path: Path do modelo ONNX a validar

        Returns:
            True se modelo é válido, False caso contrário
        """
        if not model_path.exists():
            logger.error(f"Modelo não existe: {model_path}")
            return False

        try:
            # Carregar com ONNX Runtime
            session = ort.InferenceSession(str(model_path))

            # Verificar inputs
            inputs = session.get_inputs()
            if len(inputs) != 1:
                logger.error(f"Modelo deve ter exatamente 1 input, tem {len(inputs)}")
                return False

            input_shape = inputs[0].shape
            logger.debug(f"Input shape: {input_shape}")

            # Verificar outputs
            outputs = session.get_outputs()
            if len(outputs) != 1:
                logger.error(f"Modelo deve ter exatamente 1 output, tem {len(outputs)}")
                return False

            output_shape = outputs[0].shape
            logger.debug(f"Output shape: {output_shape}")

            # Validar dimensões esperadas
            # Input: [batch_size, 515] (512 CLIP + 3 EXIF)
            # Output: [batch_size, 38] (38 sliders)
            if input_shape[1] != 515:
                logger.error(f"Input shape inválido: esperado 515, obtido {input_shape[1]}")
                return False

            if output_shape[1] != 38:
                logger.error(f"Output shape inválido: esperado 38, obtido {output_shape[1]}")
                return False

            # Teste de inferência dummy
            import numpy as np
            dummy_input = np.random.randn(1, 515).astype(np.float32)
            input_name = inputs[0].name

            outputs_result = session.run(None, {input_name: dummy_input})
            predictions = outputs_result[0]

            if predictions.shape != (1, 38):
                logger.error(f"Output dummy inválido: {predictions.shape}")
                return False

            logger.info(f"Modelo validado com sucesso: {model_path}")
            return True

        except Exception as e:
            logger.error(f"Erro ao validar modelo: {e}", exc_info=True)
            return False

    def get_model_info(self, model_path: Optional[Path] = None) -> Dict:
        """
        Retorna informação detalhada sobre um modelo.

        Args:
            model_path: Path do modelo (default: produção)

        Returns:
            Dicionário com info do modelo
        """
        if model_path is None:
            model_path = self.production_onnx

        if not model_path.exists():
            return {'error': 'Modelo não encontrado'}

        try:
            session = ort.InferenceSession(str(model_path))

            # Info de inputs
            inputs_info = []
            for inp in session.get_inputs():
                inputs_info.append({
                    'name': inp.name,
                    'shape': list(inp.shape),
                    'type': str(inp.type)
                })

            # Info de outputs
            outputs_info = []
            for out in session.get_outputs():
                outputs_info.append({
                    'name': out.name,
                    'shape': list(out.shape),
                    'type': str(out.type)
                })

            # Estatísticas de ficheiro
            stat = model_path.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(stat.st_mtime)

            return {
                'path': str(model_path),
                'size_mb': round(size_mb, 2),
                'modified_at': mtime.isoformat(),
                'version': self.get_current_model_version(),
                'inputs': inputs_info,
                'outputs': outputs_info,
                'valid': self.validate_model_loads(model_path)
            }

        except Exception as e:
            logger.error(f"Erro ao obter info do modelo: {e}")
            return {'error': str(e)}

    # ========================================================================
    # CLEANUP
    # ========================================================================

    def cleanup_old_backups(self, keep_last_n: int = 10) -> int:
        """
        Remove backups antigos, mantendo apenas os N mais recentes.

        Args:
            keep_last_n: Número de backups a manter

        Returns:
            Número de backups removidos
        """
        try:
            versions = self.list_available_versions()

            if len(versions) <= keep_last_n:
                logger.info(f"Nenhum backup a remover (total: {len(versions)})")
                return 0

            # Remover backups mais antigos
            to_remove = versions[keep_last_n:]
            removed_count = 0

            for version in to_remove:
                backup_path = Path(version['path'])
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                    removed_count += 1
                    logger.debug(f"Backup removido: {version['name']}")

            logger.info(f"Cleanup concluído | removed={removed_count} | kept={keep_last_n}")
            return removed_count

        except Exception as e:
            logger.error(f"Erro durante cleanup: {e}")
            return 0


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['ModelManager']
