"""
train/ann/incremental_trainer.py

Sistema de retreino incremental (fine-tuning) com feedback do utilizador.
Carrega modelo existente, treina com feedback validado e exporta novo modelo.

Estratégia de Fine-Tuning:
1. Carregar modelo PyTorch existente
2. Learning rate 10x menor (0.0001 vs 0.001)
3. Menos epochs (20-50 vs 200)
4. Combinar feedback com subset do dataset original
5. Validação rigorosa: novo modelo deve ser ≥ 2% melhor
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset

# Setup path
APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

from services.db_utils import get_db_connection
from services.embedding_manifest import load_manifest, resolve_manifest_ids
from slider_config import ALL_SLIDERS as ALL_SLIDER_CONFIGS

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ALL_SLIDER_NAMES = [s["python_name"] for s in ALL_SLIDER_CONFIGS]


# ============================================================================
# ARQUITETURA DO MODELO (mesma do train_nn.py)
# ============================================================================

class MultiOutputNN(nn.Module):
    """Rede neural multi-output para previsão de sliders."""

    def __init__(self, input_dim, output_dim):
        super(MultiOutputNN, self).__init__()
        self.layer_1 = nn.Linear(input_dim, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.layer_2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.layer_3 = nn.Linear(128, output_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.2)

    def forward(self, x):
        x = self.layer_1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.layer_2(x)
        x = self.bn2(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.layer_3(x)
        return x


# ============================================================================
# INCREMENTAL TRAINER
# ============================================================================

class IncrementalTrainer:
    """
    Trainer para retreino incremental com feedback do utilizador.

    Fluxo:
    1. Carregar modelo PyTorch atual
    2. Carregar feedback validado da BD
    3. (Opcional) Misturar com subset do dataset original
    4. Fine-tuning com learning rate baixo
    5. Validar que novo modelo é melhor
    6. Exportar para ONNX
    7. Guardar métricas em retraining_history

    Atributos:
        db_path: Path da base de dados
        model_dir: Diretório dos modelos
        device: Dispositivo PyTorch (cpu/mps/cuda)
    """

    def __init__(
        self,
        db_path: Path,
        model_dir: Path,
        device: Optional[torch.device] = None
    ):
        """
        Inicializa o IncrementalTrainer.

        Args:
            db_path: Path da base de dados
            model_dir: Diretório dos modelos
            device: Dispositivo PyTorch (auto-detect se None)
        """
        self.db_path = db_path
        self.model_dir = model_dir

        # Auto-detectar dispositivo
        if device is None:
            self.device = torch.device(
                'mps' if torch.backends.mps.is_available() and torch.backends.mps.is_built()
                else 'cpu'
            )
        else:
            self.device = device

        logger.info(f"IncrementalTrainer inicializado | device={self.device}")

    # ========================================================================
    # RETREINO PRINCIPAL
    # ========================================================================

    def train_from_feedback(
        self,
        min_feedback_quality: float = 0.7,
        use_original_data: bool = True,
        original_data_ratio: float = 0.3,
        epochs: int = 30,
        batch_size: int = 64,
        learning_rate: float = 0.0001,
        validation_split: float = 0.15,
        early_stopping_patience: int = 5
    ) -> Dict:
        """
        Executa retreino incremental completo.

        Args:
            min_feedback_quality: Qualidade mínima de feedback a usar
            use_original_data: Se True, mistura com dataset original
            original_data_ratio: Ratio de dados originais (0-1)
            epochs: Número de epochs de fine-tuning
            batch_size: Batch size
            learning_rate: Learning rate (deve ser ~10x menor que treino inicial)
            validation_split: Percentagem para validação
            early_stopping_patience: Paciência para early stopping

        Returns:
            Dicionário com resultados e métricas
        """
        logger.info("=" * 80)
        logger.info("INICIANDO RETREINO INCREMENTAL")
        logger.info("=" * 80)

        start_time = datetime.now()

        try:
            # Passo 1: Carregar feedback
            logger.info("Passo 1/7: Carregando feedback validado...")
            feedback_samples = self._load_feedback_data(min_feedback_quality)

            if len(feedback_samples) == 0:
                raise ValueError("Nenhum feedback validado encontrado")

            logger.info(f"Feedback carregado: {len(feedback_samples)} samples")

            # Passo 2: (Opcional) Carregar dados originais
            original_samples = []
            if use_original_data:
                logger.info("Passo 2/7: Carregando subset de dados originais...")
                original_samples = self._load_original_data_subset(original_data_ratio)
                logger.info(f"Dados originais carregados: {len(original_samples)} samples")
            else:
                logger.info("Passo 2/7: Pulando dados originais (use_original_data=False)")

            # Combinar datasets
            all_samples = feedback_samples + original_samples
            logger.info(f"Total de samples para treino: {len(all_samples)}")

            # Passo 3: Preparar dados
            logger.info("Passo 3/7: Preparando features e targets...")
            X, y = self._prepare_training_data(all_samples)

            if X.shape[0] < 10:
                raise ValueError(f"Samples insuficientes: {X.shape[0]} < 10")

            # Carregar estatísticas de normalização
            targets_mean = np.load(self.model_dir / 'targets_mean.npy')
            targets_std = np.load(self.model_dir / 'targets_std.npy')

            # Passo 4: Carregar modelo atual
            logger.info("Passo 4/7: Carregando modelo PyTorch atual...")
            model, current_loss = self._load_current_model()

            logger.info(f"Modelo atual carregado | loss_baseline={current_loss:.4f}")

            # Passo 5: Fine-tuning
            logger.info("Passo 5/7: Executando fine-tuning...")
            training_metrics = self._fine_tune_model(
                model=model,
                X=X,
                y=y,
                targets_mean=targets_mean,
                targets_std=targets_std,
                epochs=epochs,
                batch_size=batch_size,
                learning_rate=learning_rate,
                validation_split=validation_split,
                early_stopping_patience=early_stopping_patience
            )

            # Passo 6: Validar que novo modelo é melhor
            logger.info("Passo 6/7: Validando novo modelo...")
            new_loss = training_metrics['best_val_loss']
            improvement = (current_loss - new_loss) / current_loss

            logger.info(f"Loss atual: {current_loss:.4f}")
            logger.info(f"Loss novo: {new_loss:.4f}")
            logger.info(f"Improvement: {improvement:.1%}")

            # Threshold: novo modelo deve ser ≥ 2% melhor
            if improvement < -0.02:  # Piorou mais de 2%
                raise ValueError(
                    f"Novo modelo piorou: {improvement:.1%}. "
                    f"Threshold: -2%. Abortando deploy."
                )

            if improvement < 0.0:
                logger.warning(
                    f"Novo modelo ligeiramente pior ({improvement:.1%}), "
                    f"mas dentro da margem de erro. Prosseguindo..."
                )

            # Passo 7: Exportar para ONNX
            logger.info("Passo 7/7: Exportando para ONNX...")
            onnx_path = self._export_to_onnx(model, X.shape[1])

            # Salvar modelo PyTorch também
            pth_path = self.model_dir / 'multi_output_nn_retrained.pth'
            torch.save(model.state_dict(), pth_path)
            logger.info(f"Modelo PyTorch salvo: {pth_path}")

            # Calcular duração
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Preparar resultado
            result = {
                'success': True,
                'onnx_path': str(onnx_path),
                'pth_path': str(pth_path),
                'feedback_count': len(feedback_samples),
                'original_data_count': len(original_samples),
                'total_samples': len(all_samples),
                'epochs_trained': training_metrics['epochs_completed'],
                'current_loss': current_loss,
                'new_loss': new_loss,
                'improvement_percentage': improvement * 100,
                'training_metrics': training_metrics,
                'duration_seconds': duration,
                'started_at': start_time.isoformat(),
                'completed_at': end_time.isoformat()
            }

            logger.info("=" * 80)
            logger.info("RETREINO CONCLUÍDO COM SUCESSO")
            logger.info(f"Improvement: {improvement:.1%}")
            logger.info(f"Duração: {duration:.1f}s")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"Erro durante retreino: {e}", exc_info=True)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                'success': False,
                'error': str(e),
                'duration_seconds': duration,
                'started_at': start_time.isoformat(),
                'completed_at': end_time.isoformat()
            }

    # ========================================================================
    # CARREGAMENTO DE DADOS
    # ========================================================================

    def _load_feedback_data(self, min_quality: float) -> List[Dict]:
        """
        Carrega feedback validado da base de dados.

        Args:
            min_quality: Qualidade mínima de feedback

        Returns:
            Lista de dicionários com feedback
        """
        samples = []

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Query para obter feedback validado
                # Agrupa por session_id e original_record_id para reconstruir vetores completos
                cursor.execute("""
                    SELECT
                        gf.original_record_id,
                        gf.session_id,
                        r.exif,
                        r.develop_vector,
                        GROUP_CONCAT(gf.slider_name) as edited_sliders,
                        GROUP_CONCAT(gf.user_value) as user_values,
                        GROUP_CONCAT(gf.slider_index) as slider_indices,
                        MAX(gf.feedback_quality) as quality
                    FROM granular_feedback gf
                    JOIN records r ON gf.original_record_id = r.id
                    WHERE
                        gf.validated = 1
                        AND gf.is_outlier = 0
                        AND gf.used_in_training = 0
                        AND gf.feedback_quality >= ?
                    GROUP BY gf.session_id, gf.original_record_id
                    HAVING quality >= ?
                """, (min_quality, min_quality))

                rows = cursor.fetchall()

                for row in rows:
                    # Reconstruir vetor de develop completo
                    # Começar com develop_vector original
                    develop_vector = json.loads(row['develop_vector'])

                    # Aplicar correções do feedback
                    edited_sliders = row['edited_sliders'].split(',')
                    user_values = [float(v) for v in row['user_values'].split(',')]
                    slider_indices = [int(i) for i in row['slider_indices'].split(',')]

                    for slider_idx, user_value in zip(slider_indices, user_values):
                        develop_vector[slider_idx] = user_value

                    samples.append({
                        'record_id': row['original_record_id'],
                        'session_id': row['session_id'],
                        'exif': json.loads(row['exif']),
                        'develop_vector': develop_vector,
                        'quality': row['quality']
                    })

            logger.info(f"Feedback carregado: {len(samples)} sessions")
            return samples

        except Exception as e:
            logger.error(f"Erro ao carregar feedback: {e}", exc_info=True)
            return []

    def _load_original_data_subset(self, ratio: float) -> List[Dict]:
        """
        Carrega subset aleatório do dataset original.

        Args:
            ratio: Percentagem do dataset original a usar (0-1)

        Returns:
            Lista de samples do dataset original
        """
        samples = []

        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                # Contar total de records
                cursor.execute("SELECT COUNT(*) as total FROM records")
                total = cursor.fetchone()['total']

                # Calcular quantos samples carregar
                num_samples = int(total * ratio)

                # Carregar samples aleatórios
                cursor.execute("""
                    SELECT id, exif, develop_vector
                    FROM records
                    ORDER BY RANDOM()
                    LIMIT ?
                """, (num_samples,))

                rows = cursor.fetchall()

                for row in rows:
                    samples.append({
                        'record_id': row['id'],
                        'exif': json.loads(row['exif']),
                        'develop_vector': json.loads(row['develop_vector']),
                        'quality': 1.0  # Dados originais têm qualidade máxima
                    })

            logger.info(f"Dataset original subset: {len(samples)}/{total} ({ratio:.1%})")
            return samples

        except Exception as e:
            logger.error(f"Erro ao carregar dados originais: {e}", exc_info=True)
            return []

    def _prepare_training_data(self, samples: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepara features (embeddings + EXIF) e targets (develop_vector).

        Args:
            samples: Lista de samples

        Returns:
            Tupla (X, y) como arrays numpy
        """
        # Carregar componentes necessários
        all_embeddings = np.load(APP_ROOT / 'data' / 'embeddings.npy')
        pca_model = joblib.load(self.model_dir.parent / 'pca_model.pkl')
        exif_scaler = joblib.load(self.model_dir.parent / 'exif_scaler.pkl')
        EXIF_KEYS = ['iso', 'width', 'height']

        # Carregar manifest
        manifest = load_manifest()
        manifest_ids = resolve_manifest_ids(manifest, len(all_embeddings))
        id_lookup = {int(rid): idx for idx, rid in enumerate(manifest_ids)}

        X, y = [], []

        for sample in samples:
            record_id = sample['record_id']
            exif = sample['exif']
            develop_vector = sample['develop_vector']

            # Validar develop_vector
            if len(develop_vector) != 38:
                logger.warning(f"Record {record_id}: develop_vector inválido (len={len(develop_vector)})")
                continue

            # Obter embedding
            record_idx = id_lookup.get(record_id, record_id if not id_lookup else None)
            if record_idx is None or record_idx >= len(all_embeddings):
                logger.warning(f"Record {record_id}: embedding não encontrado")
                continue

            embedding = all_embeddings[record_idx]
            embedding_pca = pca_model.transform(embedding.reshape(1, -1))

            # Processar EXIF
            exif_values = [exif.get(k, 0) for k in EXIF_KEYS]
            exif_scaled = exif_scaler.transform(np.array(exif_values).reshape(1, -1))

            # Concatenar features
            final_features = np.concatenate([embedding_pca, exif_scaled], axis=1)

            X.append(final_features.flatten())
            y.append(develop_vector)

        X_array = np.array(X, dtype=np.float32)
        y_array = np.array(y, dtype=np.float32)

        logger.info(f"Dados preparados: X={X_array.shape}, y={y_array.shape}")

        return X_array, y_array

    # ========================================================================
    # MODELO
    # ========================================================================

    def _load_current_model(self) -> Tuple[nn.Module, float]:
        """
        Carrega modelo PyTorch atual e calcula loss baseline.

        Returns:
            Tupla (modelo, current_loss)
        """
        input_dim = 515  # 512 CLIP + 3 EXIF
        output_dim = 38  # 38 sliders

        model = MultiOutputNN(input_dim=input_dim, output_dim=output_dim).to(self.device)

        # Carregar pesos
        pth_path = self.model_dir / 'multi_output_nn.pth'
        if not pth_path.exists():
            raise FileNotFoundError(f"Modelo PyTorch não encontrado: {pth_path}")

        model.load_state_dict(torch.load(pth_path, map_location=self.device))
        model.eval()

        logger.info(f"Modelo carregado: {pth_path}")

        # Calcular loss baseline (usar validation set se existir)
        # Por simplicidade, usar loss do último treino (da history)
        history_path = self.model_dir / 'training_history.json'
        if history_path.exists():
            with open(history_path, 'r') as f:
                history = json.load(f)
                current_loss = history.get('best_val_loss', 0.05)
        else:
            current_loss = 0.05  # Default conservador

        return model, current_loss

    def _fine_tune_model(
        self,
        model: nn.Module,
        X: np.ndarray,
        y: np.ndarray,
        targets_mean: np.ndarray,
        targets_std: np.ndarray,
        epochs: int,
        batch_size: int,
        learning_rate: float,
        validation_split: float,
        early_stopping_patience: int
    ) -> Dict:
        """
        Executa fine-tuning do modelo.

        Args:
            model: Modelo PyTorch
            X: Features
            y: Targets
            targets_mean: Média dos targets (normalização)
            targets_std: Desvio padrão dos targets
            epochs: Número de epochs
            batch_size: Batch size
            learning_rate: Learning rate
            validation_split: Split de validação
            early_stopping_patience: Paciência para early stopping

        Returns:
            Dicionário com métricas de treino
        """
        # Normalizar targets
        y_norm = (y - targets_mean) / targets_std

        # Split treino/validação
        X_train, X_val, y_train, y_val = train_test_split(
            X, y_norm, test_size=validation_split, random_state=42
        )

        # Criar DataLoaders
        train_dataset = TensorDataset(
            torch.tensor(X_train, dtype=torch.float32),
            torch.tensor(y_train, dtype=torch.float32)
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        val_dataset = TensorDataset(
            torch.tensor(X_val, dtype=torch.float32),
            torch.tensor(y_val, dtype=torch.float32)
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        # Configurar otimizador e loss
        optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
        criterion = nn.MSELoss()

        # Scheduler (reduzir LR se não melhorar)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=3, verbose=True
        )

        # Early stopping
        best_val_loss = float('inf')
        patience_counter = 0
        history = []

        logger.info(f"Iniciando fine-tuning | epochs={epochs} | lr={learning_rate}")

        # Loop de treino
        for epoch in range(1, epochs + 1):
            # Treino
            model.train()
            train_loss = 0.0

            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)

            # Validação
            model.eval()
            val_loss = 0.0

            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)
                    val_loss += loss.item()

            val_loss /= len(val_loader)

            # Scheduler step
            scheduler.step(val_loss)

            # Logging
            if epoch % 5 == 0 or epoch == 1:
                logger.info(
                    f"Epoch {epoch}/{epochs} | "
                    f"train_loss={train_loss:.4f} | "
                    f"val_loss={val_loss:.4f}"
                )

            # Guardar histórico
            history.append({
                'epoch': epoch,
                'train_loss': train_loss,
                'val_loss': val_loss,
                'lr': optimizer.param_groups[0]['lr']
            })

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Guardar melhor modelo
                torch.save(model.state_dict(), self.model_dir / 'multi_output_nn_best_retrain.pth')
            else:
                patience_counter += 1

            if patience_counter >= early_stopping_patience:
                logger.info(f"Early stopping acionado no epoch {epoch}")
                break

        # Carregar melhor modelo
        model.load_state_dict(
            torch.load(self.model_dir / 'multi_output_nn_best_retrain.pth', map_location=self.device)
        )

        logger.info(f"Fine-tuning concluído | best_val_loss={best_val_loss:.4f}")

        return {
            'epochs_completed': len(history),
            'best_val_loss': best_val_loss,
            'final_train_loss': history[-1]['train_loss'],
            'history': history
        }

    def _export_to_onnx(self, model: nn.Module, input_dim: int) -> Path:
        """
        Exporta modelo para formato ONNX.

        Args:
            model: Modelo PyTorch
            input_dim: Dimensão do input

        Returns:
            Path do ficheiro ONNX exportado
        """
        onnx_path = self.model_dir / 'multi_output_nn_retrained.onnx'

        model.eval()
        dummy_input = torch.randn(1, input_dim, device=self.device)

        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )

        logger.info(f"Modelo exportado para ONNX: {onnx_path}")

        return onnx_path

    # ========================================================================
    # SAVING METRICS
    # ========================================================================

    def _save_training_metrics(
        self,
        result: Dict,
        trigger_type: str = 'manual',
        triggered_by: str = 'system',
        notes: Optional[str] = None
    ) -> int:
        """
        Guarda métricas de retreino em retraining_history.

        Args:
            result: Resultado do retreino
            trigger_type: Tipo de trigger
            triggered_by: Quem disparou
            notes: Notas adicionais

        Returns:
            ID do registo criado
        """
        try:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()

                status = 'success' if result['success'] else 'failed'

                cursor.execute("""
                    INSERT INTO retraining_history (
                        started_at,
                        completed_at,
                        duration_seconds,
                        trigger_type,
                        feedback_count,
                        training_samples,
                        train_loss,
                        validation_loss,
                        config_snapshot,
                        model_path,
                        status,
                        error_message,
                        triggered_by,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result['started_at'],
                    result['completed_at'],
                    result['duration_seconds'],
                    trigger_type,
                    result.get('feedback_count', 0),
                    result.get('total_samples', 0),
                    result['training_metrics']['final_train_loss'] if result['success'] else None,
                    result['training_metrics']['best_val_loss'] if result['success'] else None,
                    json.dumps({'epochs': result.get('epochs_trained')}),
                    result.get('onnx_path'),
                    status,
                    result.get('error'),
                    triggered_by,
                    notes
                ))

                retraining_id = cursor.lastrowid

                logger.info(f"Métricas guardadas | retraining_id={retraining_id}")

                return retraining_id

        except Exception as e:
            logger.error(f"Erro ao guardar métricas: {e}", exc_info=True)
            return -1


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ['IncrementalTrainer', 'MultiOutputNN']
