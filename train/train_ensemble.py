"""
Script para treinar Ensemble de Modelos.

FASE 3.4 - Training Scripts
Treina múltiplos modelos e combina em ensemble para melhor accuracy.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import argparse
import logging
from datetime import datetime

from services.ai_core.model_architectures_v2 import OptimizedPresetClassifier, OptimizedRefinementRegressor
from services.ai_core.model_architectures_v3 import AttentionPresetClassifier, AttentionRefinementRegressor
from services.ai_core.ensemble_predictor import BaggingEnsemble, EnsemblePredictor, save_ensemble
from services.ai_core.trainer_v2 import train_epoch, evaluate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_single_model(
    model: nn.Module,
    train_dataset,
    val_dataset,
    num_epochs: int = 50,
    learning_rate: float = 1e-3,
    batch_size: int = 32,
    device: str = 'cuda'
) -> nn.Module:
    """
    Treina um modelo único.

    Args:
        model: Modelo a treinar
        train_dataset: Dataset de treino
        val_dataset: Dataset de validação
        num_epochs: Número de epochs
        learning_rate: Learning rate
        batch_size: Batch size
        device: Device

    Returns:
        Modelo treinado
    """
    model = model.to(device)

    # DataLoaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0
    )

    # Optimizer and scheduler
    optimizer = optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=0.01
    )

    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=learning_rate * 10,
        epochs=num_epochs,
        steps_per_epoch=len(train_loader),
        pct_start=0.1
    )

    # Loss
    criterion = nn.CrossEntropyLoss()

    # Training loop
    best_val_acc = 0
    patience = 0
    max_patience = 15

    for epoch in range(num_epochs):
        # Train
        train_loss, train_acc = train_epoch(
            model,
            train_loader,
            criterion,
            optimizer,
            scheduler,
            device,
            task='classification'
        )

        # Validate
        val_loss, val_acc = evaluate(
            model,
            val_loader,
            criterion,
            device,
            task='classification'
        )

        logger.info(
            f"Epoch {epoch+1}/{num_epochs} - "
            f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f} - "
            f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}"
        )

        # Early stopping
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience = 0
        else:
            patience += 1
            if patience >= max_patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    logger.info(f"Training completed. Best val acc: {best_val_acc:.4f}")

    return model


def train_ensemble_classifier(
    train_dataset,
    val_dataset,
    n_models: int = 5,
    model_type: str = 'v2',
    num_epochs: int = 50,
    learning_rate: float = 1e-3,
    batch_size: int = 32,
    device: str = 'cuda',
    save_dir: str = 'models/ensemble'
):
    """
    Treina ensemble de classificadores.

    Args:
        train_dataset: Dataset de treino
        val_dataset: Dataset de validação
        n_models: Número de modelos no ensemble
        model_type: Tipo de modelo ('v2', 'v3')
        num_epochs: Número de epochs
        learning_rate: Learning rate
        batch_size: Batch size
        device: Device
        save_dir: Diretório para salvar modelos
    """
    logger.info(f"Training ensemble of {n_models} models")
    logger.info(f"Model type: {model_type}")

    # Get sample to determine dimensions
    sample = train_dataset[0]
    stat_dim = sample['stat_features'].shape[0]
    deep_dim = sample['deep_features'].shape[0]
    num_presets = len(set([s['label'].item() for s in train_dataset]))

    logger.info(f"Stat dim: {stat_dim}, Deep dim: {deep_dim}, Num presets: {num_presets}")

    # Select model class
    if model_type == 'v2':
        model_class = OptimizedPresetClassifier
    elif model_type == 'v3':
        model_class = AttentionPresetClassifier
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Model kwargs
    model_kwargs = {
        'stat_features_dim': stat_dim,
        'deep_features_dim': deep_dim,
        'num_presets': num_presets,
        'dropout': 0.4
    }

    # Create bagging ensemble
    bagging = BaggingEnsemble(
        model_class=model_class,
        model_kwargs=model_kwargs,
        n_models=n_models,
        bootstrap_ratio=0.8
    )

    # Training function
    def trainer_fn(model, dataset):
        # Create validation split from bootstrap dataset
        val_size = max(1, len(dataset) // 5)
        train_size = len(dataset) - val_size
        train_subset, val_subset = random_split(dataset, [train_size, val_size])

        return train_single_model(
            model,
            train_subset,
            val_subset,
            num_epochs=num_epochs,
            learning_rate=learning_rate,
            batch_size=batch_size,
            device=device
        )

    # Train ensemble
    models = bagging.train(
        train_dataset=train_dataset,
        trainer_fn=trainer_fn,
        device=device
    )

    # Create ensemble predictor
    ensemble = bagging.get_ensemble(voting='soft')

    # Evaluate ensemble on validation set
    logger.info("\nEvaluating ensemble on validation set...")
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    ensemble.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for batch in val_loader:
            stat_feat = batch['stat_features'].to(device)
            deep_feat = batch['deep_features'].to(device)
            labels = batch['label'].to(device)

            outputs = ensemble(stat_feat, deep_feat)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

    ensemble_acc = correct / total
    logger.info(f"Ensemble validation accuracy: {ensemble_acc:.4f}")

    # Save ensemble
    save_ensemble(ensemble, save_dir, ensemble_name='classifier_ensemble')
    logger.info(f"Ensemble saved to {save_dir}")

    return ensemble, ensemble_acc


def main():
    parser = argparse.ArgumentParser(description='Train Ensemble of Models')

    parser.add_argument('--dataset', type=str, required=True, help='Path to dataset')
    parser.add_argument('--n-models', type=int, default=5, help='Number of models in ensemble')
    parser.add_argument('--model-type', type=str, default='v3', choices=['v2', 'v3'],
                        help='Model type')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--lr', type=float, default=1e-3, help='Learning rate')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--device', type=str, default='cuda', help='Device')
    parser.add_argument('--save-dir', type=str, default='models/ensemble',
                        help='Directory to save models')
    parser.add_argument('--val-split', type=float, default=0.2, help='Validation split ratio')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("ENSEMBLE TRAINING")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Number of models: {args.n_models}")
    logger.info(f"Model type: {args.model_type}")
    logger.info(f"Epochs: {args.epochs}")
    logger.info(f"Learning rate: {args.lr}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Device: {args.device}")
    logger.info("=" * 60)

    # Load dataset
    # Note: This is a placeholder. Replace with actual dataset loading.
    logger.info("Loading dataset...")
    # dataset = load_your_dataset(args.dataset)

    # Split dataset
    # train_size = int(len(dataset) * (1 - args.val_split))
    # val_size = len(dataset) - train_size
    # train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    # Train ensemble
    # ensemble, accuracy = train_ensemble_classifier(
    #     train_dataset=train_dataset,
    #     val_dataset=val_dataset,
    #     n_models=args.n_models,
    #     model_type=args.model_type,
    #     num_epochs=args.epochs,
    #     learning_rate=args.lr,
    #     batch_size=args.batch_size,
    #     device=args.device,
    #     save_dir=args.save_dir
    # )

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETED")
    logger.info("=" * 60)
    # logger.info(f"Final ensemble accuracy: {accuracy:.4f}")
    logger.info(f"Models saved to: {args.save_dir}")


if __name__ == "__main__":
    main()
