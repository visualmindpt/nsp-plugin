"""
train/ann/retrain_nn_from_feedback.py

Script para fine-tuning da rede neuronal multi-output usando o feedback
granular validado, recolhido a partir das interações do utilizador.
"""
import argparse
import logging
import sqlite3
from pathlib import Path
import sys
import json
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader
import onnxruntime as ort

# Adicionar root do projeto ao path para imports
APP_ROOT = Path(__file__).resolve().parent.parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

from services.inference import NSPInferenceEngine
from services.db_utils import get_db_connection
from services.feedback_manager import FeedbackManager
from train.ann.train_nn import MultiOutputNN
from slider_config import ALL_SLIDER_NAMES

# --- Configuração ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = APP_ROOT / 'data'
MODELS_DIR = APP_ROOT / 'models'
DB_PATH = DATA_DIR / 'nsp_plugin.db'
NN_MODEL_DIR = MODELS_DIR / "ann"
PYTORCH_MODEL_PATH = NN_MODEL_DIR / "multi_output_nn.pth"
ONNX_MODEL_PATH = NN_MODEL_DIR / "multi_output_nn.onnx"

# --- Funções ---

def load_feedback_data(db_path: Path, min_quality: float = 0.7) -> (defaultdict, list):
    """
    Carrega feedback validado da base de dados, agrupado por imagem.
    """
    logger.info(f"A carregar feedback validado de {db_path} com qualidade mínima {min_quality:.2f}")
    
    feedback_by_image = defaultdict(list)
    all_feedback_ids = []

    try:
        # Usar o FeedbackManager para obter os dados já formatados
        feedback_manager = FeedbackManager(db_path=db_path)
        
        # Obter todos os feedbacks validados que ainda não foram usados
        validated_feedback = feedback_manager.get_validated_feedback_for_training(
            min_quality=min_quality,
            exclude_outliers=True
        )

        if not validated_feedback:
            logger.info("Nenhum feedback novo para treino encontrado.")
            return defaultdict(list), []

        for item in validated_feedback:
            record_id = item['original_record_id']
            feedback_by_image[record_id].append(item)
            all_feedback_ids.append(item['id'])
        
        logger.info(f"Encontrados {len(validated_feedback)} feedbacks granulares para {len(feedback_by_image)} imagens.")
        return feedback_by_image, all_feedback_ids

    except sqlite3.Error as e:
        logger.error(f"Erro de base de dados ao carregar feedback: {e}", exc_info=True)
        return defaultdict(list), []

def prepare_training_data(feedback_by_image: defaultdict, inference_engine: NSPInferenceEngine) -> (np.ndarray, np.ndarray):
    """
    Prepara os dados de treino (X, y) a partir do feedback.
    X: Features da imagem (embedding + EXIF)
    y: Vetor de sliders corrigido pelo utilizador
    """
    logger.info("A preparar dados de treino a partir do feedback...")
    
    X_train, y_train = [], []

    for record_id, feedbacks in feedback_by_image.items():
        if not feedbacks:
            continue
        
        # Usar o primeiro feedback para obter info da imagem
        first_feedback = feedbacks[0]
        image_path = first_feedback['image_path']
        
        try:
            # 1. Gerar features (X) para a imagem
            exif_data = json.loads(first_feedback['exif'])
            features = inference_engine._build_features(image_path, exif_data)
            
            # 2. Construir o vetor de target (y)
            # Começar com o vetor de desenvolvimento original
            corrected_vector = np.array(json.loads(first_feedback['develop_vector']), dtype=np.float32)

            # Aplicar as correções granulares do utilizador
            for feedback_item in feedbacks:
                slider_index = feedback_item['slider_index']
                user_value = feedback_item['user_value']
                corrected_vector[slider_index] = user_value
            
            X_train.append(features.flatten())
            y_train.append(corrected_vector)

        except Exception as e:
            logger.error(f"Falha ao processar feedback para record_id {record_id} (imagem: {image_path}): {e}", exc_info=True)
            continue
            
    if not X_train or not y_train:
        logger.warning("Nenhum dado de treino foi preparado.")
        return np.array([]), np.array([])

    logger.info(f"Preparados {len(X_train)} amostras para fine-tuning.")
    return np.array(X_train, dtype=np.float32), np.array(y_train, dtype=np.float32)


def fine_tune_model(model: MultiOutputNN, X_train: np.ndarray, y_train: np.ndarray, epochs: int = 5, learning_rate: float = 1e-4):
    """
    Afina (fine-tunes) o modelo de rede neuronal com os novos dados.
    """
    logger.info(f"A iniciar fine-tuning por {epochs} épocas com learning rate de {learning_rate:.0e}...")
    
    device = torch.device('mps' if torch.backends.mps.is_available() and torch.backends.mps.is_built() else 'cpu')
    model.to(device)
    
    # Carregar mean/std para normalização dos targets
    target_mean = np.load(NN_MODEL_DIR / 'targets_mean.npy')
    target_std = np.load(NN_MODEL_DIR / 'targets_std.npy')
    
    y_train_normalized = (y_train - target_mean) / target_std
    
    # Criar DataLoader
    dataset = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train_normalized, dtype=torch.float32))
    train_loader = DataLoader(dataset, batch_size=max(1, len(X_train) // 4), shuffle=True) # Usar batches pequenos

    # Definir critério e otimizador
    criterion = nn.MSELoss()
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate)

    model.train()
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
        
        avg_epoch_loss = epoch_loss / len(train_loader)
        logger.info(f"Epoch {epoch}/{epochs} - Loss: {avg_epoch_loss:.6f}")

    logger.info("Fine-tuning concluído.")
    return model

def save_model_artifacts(model: MultiOutputNN, model_dir: Path, X_sample: np.ndarray):
    """Guarda o modelo PyTorch e exporta-o para ONNX."""
    
    # 1. Guardar o modelo PyTorch
    torch.save(model.state_dict(), PYTORCH_MODEL_PATH)
    logger.info(f"Modelo PyTorch atualizado guardado em {PYTORCH_MODEL_PATH}")

    # 2. Exportar para ONNX
    try:
        device = next(model.parameters()).device
        dummy_input = torch.tensor(X_sample[0:1], dtype=torch.float32).to(device)
        
        torch.onnx.export(
            model,
            dummy_input,
            ONNX_MODEL_PATH,
            export_params=True,
            opset_version=11,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        logger.info(f"Modelo exportado para ONNX em {ONNX_MODEL_PATH}")
    except Exception as e:
        logger.error(f"Falha ao exportar modelo para ONNX: {e}", exc_info=True)


def main(args):
    """Função principal para orquestrar o processo de retreino."""
    logger.info("--- A iniciar script de retreino da Rede Neuronal a partir de feedback ---")

    if not DB_PATH.exists():
        logger.error(f"Base de dados não encontrada em {DB_PATH}. A sair.")
        return

    # 1. Carregar dados de feedback
    feedback_by_image, feedback_ids_to_mark = load_feedback_data(DB_PATH, args.min_quality)
    if not feedback_ids_to_mark:
        return # Sai se não houver nada a fazer

    # 2. Preparar dados de treino
    try:
        inference_engine = NSPInferenceEngine()
    except Exception as e:
        logger.error(f"Falha ao carregar o motor de inferência: {e}. O retreino não pode continuar.", exc_info=True)
        return
        
    X_train, y_train = prepare_training_data(feedback_by_image, inference_engine)
    if X_train.shape[0] == 0:
        logger.warning("Nenhum dado de treino válido foi gerado. A sair.")
        return

    # 3. Carregar modelo existente
    if not PYTORCH_MODEL_PATH.exists():
        logger.error(f"Modelo PyTorch não encontrado em {PYTORCH_MODEL_PATH}. Não é possível fazer fine-tuning.")
        return
        
    input_dim = X_train.shape[1]
    output_dim = y_train.shape[1]
    model = MultiOutputNN(input_dim=input_dim, output_dim=output_dim)
    model.load_state_dict(torch.load(PYTORCH_MODEL_PATH))
    logger.info(f"Modelo PyTorch '{PYTORCH_MODEL_PATH}' carregado com sucesso.")

    # 4. Fine-tune do modelo
    tuned_model = fine_tune_model(model, X_train, y_train, epochs=args.epochs, lr=args.lr)

    # 5. Guardar artefactos (modelo PyTorch e ONNX)
    logger.info("A guardar os artefactos do modelo atualizado...")
    save_model_artifacts(tuned_model, NN_MODEL_DIR, X_train)

    # 6. Marcar feedback como utilizado
    logger.info(f"A marcar {len(feedback_ids_to_mark)} feedbacks como utilizados na base de dados.")
    feedback_manager = FeedbackManager(db_path=DB_PATH)
    success = feedback_manager.mark_feedback_as_used(feedback_ids_to_mark)
    if success:
        logger.info("Feedbacks marcados com sucesso.")
    else:
        logger.error("Falha ao marcar feedbacks como utilizados.")

    logger.info("--- Script de retreino concluído ---")


def parse_args():
    parser = argparse.ArgumentParser(description="Retreina a rede neuronal com feedback de utilizador.")
    parser.add_argument('--epochs', type=int, default=5, help="Número de épocas para o fine-tuning.")
    parser.add_argument('--lr', type=float, default=1e-4, help="Learning rate para o fine-tuning.")
    parser.add_argument('--min-quality', type=float, default=0.7, help="Qualidade mínima do feedback a ser considerado.")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    main(args)
