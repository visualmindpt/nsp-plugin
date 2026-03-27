#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
train_culling.py

Script de treino para o Culling AI Classifier
Treina um modelo binário para classificar fotos como Keep ou Reject
"""
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from torch.utils.data import Dataset, DataLoader
import logging
from typing import Tuple, Dict
import json

# Imports do projeto
from services.ai_core.culling_model import CullingClassifier, compute_stats_features
from services.ai_core.deep_feature_extractor import DeepFeatureExtractor
from services.ai_core.lightroom_extractor import LightroomCatalogExtractor

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configurações
# ============================================================================

# Caminhos
CATALOG_PATH = Path("/Users/nelsonsilva/Lightroom Catalog.lrcat")  # ATUALIZAR
MODELS_DIR = Path("models")
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Parâmetros de treino
BATCH_SIZE = 16
EPOCHS = 30
LEARNING_RATE = 0.001
PATIENCE = 5  # Early stopping
MIN_SAMPLES_PER_CLASS = 50  # Mínimo de fotos Keep e Reject

# Thresholds de rating
KEEP_THRESHOLD = 4  # rating >= 4 = Keep
REJECT_THRESHOLD = 2  # rating <= 2 = Reject

# ============================================================================
# Dataset Customizado
# ============================================================================

class CullingDataset(Dataset):
    """Dataset para treino do Culling Classifier"""

    def __init__(self, deep_features: np.ndarray, stats_features: np.ndarray, labels: np.ndarray):
        self.deep_features = torch.FloatTensor(deep_features)
        self.stats_features = torch.FloatTensor(stats_features)
        self.labels = torch.FloatTensor(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.deep_features[idx], self.stats_features[idx], self.labels[idx]


# ============================================================================
# Funções de Treino
# ============================================================================

def extract_rated_dataset(catalog_path: Path, keep_threshold: int = KEEP_THRESHOLD, reject_threshold: int = REJECT_THRESHOLD) -> pd.DataFrame:
    """
    Extrai dataset do Lightroom com ratings

    Returns:
        DataFrame com colunas: image_path, rating, label (0=Reject, 1=Keep)
    """
    logger.info("📊 A extrair dataset do catálogo Lightroom...")

    extractor = LightroomCatalogExtractor(catalog_path)

    # Extrair TODAS as fotos com rating (não filtrar por min_rating)
    df = extractor.extract_edits(min_rating=1)

    if df.empty:
        raise ValueError("Nenhuma foto encontrada no catálogo")

    logger.info(f"Total de fotos extraídas: {len(df)}")

    # Criar labels baseado em rating
    def rating_to_label(rating):
        if rating >= keep_threshold:
            return 1  # Keep
        elif rating <= reject_threshold:
            return 0  # Reject
        else:
            return None  # Ignorar (ratings intermédios)

    df['label'] = df['rating'].apply(rating_to_label)

    # Filtrar apenas Keep e Reject (ignorar intermédios)
    df = df[df['label'].notna()].copy()

    # Estatísticas
    num_keep = (df['label'] == 1).sum()
    num_reject = (df['label'] == 0).sum()

    logger.info(f"\n📈 Distribuição de labels:")
    logger.info(f"  Keep (rating >= {keep_threshold}): {num_keep} fotos")
    logger.info(f"  Reject (rating <= {reject_threshold}): {num_reject} fotos")
    logger.info(f"  Total utilizável: {len(df)} fotos")

    # Validar quantidade mínima
    if num_keep < MIN_SAMPLES_PER_CLASS or num_reject < MIN_SAMPLES_PER_CLASS:
        raise ValueError(
            f"Dados insuficientes para treino!\n"
            f"Necessário pelo menos {MIN_SAMPLES_PER_CLASS} fotos de cada classe.\n"
            f"Encontrado: {num_keep} Keep, {num_reject} Reject"
        )

    return df


def extract_features(dataset: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extrai features de todas as imagens

    Returns:
        deep_features: (N, 512) - Features do MobileNetV3
        stats_features: (N, 10) - Features estatísticas
    """
    logger.info("🔍 A extrair features das imagens...")

    # Inicializar extractors
    deep_extractor = DeepFeatureExtractor()

    deep_features_list = []
    stats_features_list = []
    successful_indices = []

    for idx, row in dataset.iterrows():
        image_path = row['image_path']

        try:
            # Features deep
            deep_features = deep_extractor.extract_single(str(image_path))

            # Features estatísticas
            stats_features = compute_stats_features(Path(image_path))

            deep_features_list.append(deep_features)
            stats_features_list.append(stats_features)
            successful_indices.append(idx)

            if (len(successful_indices) % 50) == 0:
                logger.info(f"  Processadas {len(successful_indices)}/{len(dataset)} imagens...")

        except Exception as e:
            logger.warning(f"Erro ao processar {image_path}: {e}")
            continue

    logger.info(f"✅ Features extraídas de {len(successful_indices)}/{len(dataset)} imagens")

    # Filtrar dataset para manter apenas imagens com features válidas
    dataset_filtered = dataset.loc[successful_indices].copy()

    deep_features = np.array(deep_features_list)
    stats_features = np.array(stats_features_list)

    return deep_features, stats_features, dataset_filtered


def train_culling_model(
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: torch.device,
    epochs: int = EPOCHS,
    patience: int = PATIENCE
) -> CullingClassifier:
    """
    Treina o Culling Classifier

    Returns:
        Modelo treinado
    """
    logger.info("🎓 A treinar Culling Classifier...")

    model = CullingClassifier(deep_dim=512, stats_dim=10).to(device)

    criterion = nn.BCELoss()  # Binary Cross Entropy
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

    best_val_loss = float('inf')
    patience_counter = 0
    best_model_state = None

    for epoch in range(epochs):
        # --- Training ---
        model.train()
        train_loss = 0.0
        train_preds = []
        train_labels = []

        for deep, stats, labels in train_loader:
            deep = deep.to(device)
            stats = stats.to(device)
            labels = labels.to(device).unsqueeze(1)

            optimizer.zero_grad()
            outputs = model(deep, stats)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            train_preds.extend((outputs > 0.5).cpu().numpy().flatten())
            train_labels.extend(labels.cpu().numpy().flatten())

        train_loss /= len(train_loader)
        train_acc = accuracy_score(train_labels, train_preds)

        # --- Validation ---
        model.eval()
        val_loss = 0.0
        val_preds = []
        val_labels = []

        with torch.no_grad():
            for deep, stats, labels in val_loader:
                deep = deep.to(device)
                stats = stats.to(device)
                labels = labels.to(device).unsqueeze(1)

                outputs = model(deep, stats)
                loss = criterion(outputs, labels)

                val_loss += loss.item()
                val_preds.extend((outputs > 0.5).cpu().numpy().flatten())
                val_labels.extend(labels.cpu().numpy().flatten())

        val_loss /= len(val_loader)
        val_acc = accuracy_score(val_labels, val_preds)

        logger.info(
            f"Epoch {epoch+1}/{epochs} | "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
            f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}"
        )

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
            logger.info(f"  ✅ Novo melhor modelo (val_loss: {val_loss:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"⏹️  Early stopping após {epoch+1} epochs")
                break

    # Carregar melhor modelo
    if best_model_state:
        model.load_state_dict(best_model_state)

    return model


def evaluate_model(model: CullingClassifier, test_loader: DataLoader, device: torch.device) -> Dict:
    """
    Avalia o modelo no conjunto de teste

    Returns:
        Dict com métricas de avaliação
    """
    logger.info("📊 A avaliar modelo no conjunto de teste...")

    model.eval()
    all_preds = []
    all_labels = []
    all_probs = []

    with torch.no_grad():
        for deep, stats, labels in test_loader:
            deep = deep.to(device)
            stats = stats.to(device)

            outputs = model(deep, stats)
            probs = outputs.cpu().numpy().flatten()
            preds = (probs > 0.5).astype(int)

            all_preds.extend(preds)
            all_labels.extend(labels.numpy().flatten())
            all_probs.extend(probs)

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)

    # Calcular métricas
    accuracy = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds)
    recall = recall_score(all_labels, all_preds)
    f1 = f1_score(all_labels, all_preds)
    conf_matrix = confusion_matrix(all_labels, all_preds)

    metrics = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'confusion_matrix': conf_matrix.tolist()
    }

    logger.info(f"\n{'='*60}")
    logger.info("📈 MÉTRICAS DE AVALIAÇÃO")
    logger.info(f"{'='*60}")
    logger.info(f"Accuracy:  {accuracy:.4f}")
    logger.info(f"Precision: {precision:.4f} (% de Keep corretos)")
    logger.info(f"Recall:    {recall:.4f} (% de Keep identificados)")
    logger.info(f"F1-Score:  {f1:.4f}")
    logger.info(f"\nMatriz de Confusão:")
    logger.info(f"                Predicted")
    logger.info(f"              Reject  Keep")
    logger.info(f"Actual Reject   {conf_matrix[0][0]:4d}  {conf_matrix[0][1]:4d}")
    logger.info(f"       Keep     {conf_matrix[1][0]:4d}  {conf_matrix[1][1]:4d}")
    logger.info(f"{'='*60}\n")

    return metrics


# ============================================================================
# Main Pipeline
# ============================================================================

def main():
    logger.info("🚀 NSP Plugin - Treino de Culling AI")
    logger.info("="*60)

    try:
        # 1. Extrair dataset com ratings
        dataset = extract_rated_dataset(CATALOG_PATH)

        # 2. Extrair features
        deep_features, stats_features, dataset = extract_features(dataset)
        labels = dataset['label'].values

        # 3. Split dataset (60% train, 20% val, 20% test)
        logger.info("📂 A dividir dataset...")
        X_train_deep, X_temp_deep, X_train_stats, X_temp_stats, y_train, y_temp = train_test_split(
            deep_features, stats_features, labels,
            test_size=0.4, stratify=labels, random_state=42
        )

        X_val_deep, X_test_deep, X_val_stats, X_test_stats, y_val, y_test = train_test_split(
            X_temp_deep, X_temp_stats, y_temp,
            test_size=0.5, stratify=y_temp, random_state=42
        )

        logger.info(f"  Train: {len(y_train)} | Val: {len(y_val)} | Test: {len(y_test)}")

        # 4. Criar DataLoaders
        train_dataset = CullingDataset(X_train_deep, X_train_stats, y_train)
        val_dataset = CullingDataset(X_val_deep, X_val_stats, y_val)
        test_dataset = CullingDataset(X_test_deep, X_test_stats, y_test)

        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
        test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

        # 5. Treinar modelo
        device = torch.device('mps' if torch.backends.mps.is_available() else
                             'cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"🖥️  Usando device: {device}")

        model = train_culling_model(train_loader, val_loader, device)

        # 6. Avaliar no conjunto de teste
        metrics = evaluate_model(model, test_loader, device)

        # 7. Guardar modelo
        model_path = MODELS_DIR / "culling_classifier.pth"
        torch.save({
            'model_state_dict': model.state_dict(),
            'metrics': metrics,
            'config': {
                'deep_dim': 512,
                'stats_dim': 10,
                'keep_threshold': KEEP_THRESHOLD,
                'reject_threshold': REJECT_THRESHOLD
            }
        }, model_path)

        logger.info(f"✅ Modelo guardado em: {model_path}")

        # 8. Guardar métricas
        metrics_path = MODELS_DIR / "culling_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=4)

        logger.info(f"✅ Métricas guardadas em: {metrics_path}")

        logger.info("\n🎉 Treino de Culling AI concluído com sucesso!")

    except Exception as e:
        logger.error(f"❌ Erro durante o treino: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
