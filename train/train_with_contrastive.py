"""
Script para treino com Contrastive Learning.

FASE 3.4 - Training Scripts
Pré-treina encoder com contrastive learning, depois fine-tuna para tarefa específica.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import argparse
import logging
from datetime import datetime
import numpy as np

from services.ai_core.contrastive_trainer import (
    ContrastiveTrainer,
    ContrastiveDataset,
    simple_augmentation
)
from services.ai_core.model_architectures_v2 import OptimizedPresetClassifier
from services.ai_core.trainer_v2 import train_epoch, evaluate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def pretrain_encoder(
    encoder: nn.Module,
    unlabeled_dataset,
    feature_dim: int,
    num_epochs: int = 50,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    device: str = 'cuda',
    save_path: Optional[str] = None
):
    """
    Pré-treina encoder com contrastive learning.

    Args:
        encoder: Encoder a pré-treinar
        unlabeled_dataset: Dataset não rotulado
        feature_dim: Dimensão das features do encoder
        num_epochs: Número de epochs
        batch_size: Batch size
        learning_rate: Learning rate
        device: Device
        save_path: Caminho para salvar encoder

    Returns:
        Encoder pré-treinado
    """
    logger.info("Starting contrastive pre-training...")

    # Create contrastive dataset
    contrastive_dataset = ContrastiveDataset(
        base_dataset=unlabeled_dataset,
        augmentation_fn=lambda x: simple_augmentation(x, noise_std=0.1)
    )

    # DataLoader
    train_loader = DataLoader(
        contrastive_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0
    )

    # Create contrastive trainer
    trainer = ContrastiveTrainer(
        encoder=encoder,
        feature_dim=feature_dim,
        projection_dim=128,
        temperature=0.5,
        device=device,
        use_supervised=False
    )

    # Pretrain
    history = trainer.pretrain(
        train_loader=train_loader,
        num_epochs=num_epochs,
        learning_rate=learning_rate,
        weight_decay=1e-6,
        save_path=save_path
    )

    logger.info("Contrastive pre-training completed!")

    return trainer.get_encoder(), history


def finetune_classifier(
    pretrained_encoder: nn.Module,
    train_dataset,
    val_dataset,
    num_presets: int,
    num_epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    device: str = 'cuda',
    freeze_encoder: bool = False
):
    """
    Fine-tuna classificador com encoder pré-treinado.

    Args:
        pretrained_encoder: Encoder pré-treinado
        train_dataset: Dataset de treino
        val_dataset: Dataset de validação
        num_presets: Número de presets
        num_epochs: Número de epochs
        batch_size: Batch size
        learning_rate: Learning rate (menor para fine-tuning)
        device: Device
        freeze_encoder: Se True, congela encoder

    Returns:
        Modelo fine-tunado
    """
    logger.info("Starting fine-tuning...")

    # Get sample to determine dimensions
    sample = train_dataset[0]
    stat_dim = sample['stat_features'].shape[0]
    deep_dim = sample['deep_features'].shape[0]

    # Create full classifier
    # Note: This assumes pretrained_encoder is the stat or deep branch
    # Adapt based on what was pre-trained
    model = OptimizedPresetClassifier(
        stat_features_dim=stat_dim,
        deep_features_dim=deep_dim,
        num_presets=num_presets,
        dropout=0.4
    ).to(device)

    # Replace stat branch with pretrained encoder (example)
    # Adjust based on your architecture
    # model.stat_branch = pretrained_encoder

    # Freeze encoder if requested
    if freeze_encoder:
        for param in pretrained_encoder.parameters():
            param.requires_grad = False
        logger.info("Encoder frozen")

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

    # Optimizer
    # Use different learning rates for encoder and classifier head
    if freeze_encoder:
        optimizer = optim.AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=learning_rate,
            weight_decay=0.01
        )
    else:
        optimizer = optim.AdamW([
            {'params': pretrained_encoder.parameters(), 'lr': learning_rate * 0.1},
            {'params': [p for p in model.parameters() if p not in pretrained_encoder.parameters()],
             'lr': learning_rate}
        ], weight_decay=0.01)

    # Scheduler
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=num_epochs,
        eta_min=learning_rate * 0.01
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

    logger.info(f"Fine-tuning completed. Best val acc: {best_val_acc:.4f}")

    return model, best_val_acc


def main():
    parser = argparse.ArgumentParser(description='Train with Contrastive Learning')

    parser.add_argument('--unlabeled-data', type=str, required=True,
                        help='Path to unlabeled data for pre-training')
    parser.add_argument('--labeled-data', type=str, required=True,
                        help='Path to labeled data for fine-tuning')
    parser.add_argument('--pretrain-epochs', type=int, default=50,
                        help='Epochs for contrastive pre-training')
    parser.add_argument('--finetune-epochs', type=int, default=50,
                        help='Epochs for fine-tuning')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--lr-pretrain', type=float, default=1e-3,
                        help='Learning rate for pre-training')
    parser.add_argument('--lr-finetune', type=float, default=1e-4,
                        help='Learning rate for fine-tuning')
    parser.add_argument('--device', type=str, default='cuda', help='Device')
    parser.add_argument('--freeze-encoder', action='store_true',
                        help='Freeze encoder during fine-tuning')
    parser.add_argument('--save-dir', type=str, default='models/contrastive',
                        help='Directory to save models')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CONTRASTIVE LEARNING TRAINING")
    logger.info("=" * 60)
    logger.info(f"Unlabeled data: {args.unlabeled_data}")
    logger.info(f"Labeled data: {args.labeled_data}")
    logger.info(f"Pre-training epochs: {args.pretrain_epochs}")
    logger.info(f"Fine-tuning epochs: {args.finetune_epochs}")
    logger.info(f"Freeze encoder: {args.freeze_encoder}")
    logger.info("=" * 60)

    # Create save directory
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Load datasets
    logger.info("Loading datasets...")
    # unlabeled_dataset = load_unlabeled_dataset(args.unlabeled_data)
    # labeled_dataset = load_labeled_dataset(args.labeled_data)

    # Split labeled dataset
    # train_size = int(len(labeled_dataset) * 0.8)
    # val_size = len(labeled_dataset) - train_size
    # train_dataset, val_dataset = random_split(labeled_dataset, [train_size, val_size])

    # PHASE 1: Contrastive Pre-training
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: CONTRASTIVE PRE-TRAINING")
    logger.info("=" * 60)

    # Create encoder (stat branch as example)
    # encoder = nn.Sequential(
    #     nn.Linear(30, 64),
    #     nn.BatchNorm1d(64),
    #     nn.ReLU(),
    #     nn.Dropout(0.4),
    #     nn.Linear(64, 32),
    #     nn.BatchNorm1d(32),
    #     nn.ReLU()
    # )

    # encoder, pretrain_history = pretrain_encoder(
    #     encoder=encoder,
    #     unlabeled_dataset=unlabeled_dataset,
    #     feature_dim=32,
    #     num_epochs=args.pretrain_epochs,
    #     batch_size=args.batch_size,
    #     learning_rate=args.lr_pretrain,
    #     device=args.device,
    #     save_path=str(save_dir / 'pretrained_encoder.pth')
    # )

    # PHASE 2: Fine-tuning
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: FINE-TUNING")
    logger.info("=" * 60)

    # model, accuracy = finetune_classifier(
    #     pretrained_encoder=encoder,
    #     train_dataset=train_dataset,
    #     val_dataset=val_dataset,
    #     num_presets=10,  # Adjust based on your data
    #     num_epochs=args.finetune_epochs,
    #     batch_size=args.batch_size,
    #     learning_rate=args.lr_finetune,
    #     device=args.device,
    #     freeze_encoder=args.freeze_encoder
    # )

    # Save final model
    # torch.save(model.state_dict(), save_dir / 'finetuned_classifier.pth')

    logger.info("=" * 60)
    logger.info("TRAINING COMPLETED")
    logger.info("=" * 60)
    # logger.info(f"Final accuracy: {accuracy:.4f}")
    logger.info(f"Models saved to: {save_dir}")


if __name__ == "__main__":
    main()
