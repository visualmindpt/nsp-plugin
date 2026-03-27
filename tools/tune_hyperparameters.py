"""
Script para tuning automático de hyperparâmetros.

FASE 3.5 - Tools
Usa Optuna para encontrar os melhores hyperparâmetros automaticamente.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
from torch.utils.data import random_split
import argparse
import logging
from datetime import datetime

from services.ai_core.hyperparameter_tuner import HyperparameterTuner, MultiObjectiveTuner
from services.ai_core.model_architectures_v2 import OptimizedPresetClassifier
from services.ai_core.model_architectures_v3 import AttentionPresetClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def tune_hyperparameters(
    train_dataset,
    val_dataset,
    model_class: type,
    n_trials: int = 100,
    timeout: Optional[int] = None,
    device: str = 'cuda',
    study_name: str = 'hyperparameter_optimization',
    output_dir: str = 'hyperparameter_tuning',
    multi_objective: bool = False
):
    """
    Executa hyperparameter tuning.

    Args:
        train_dataset: Dataset de treino
        val_dataset: Dataset de validação
        model_class: Classe do modelo
        n_trials: Número de trials
        timeout: Timeout em segundos (opcional)
        device: Device
        study_name: Nome do estudo
        output_dir: Diretório de saída
        multi_objective: Se True, otimiza accuracy e speed
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("HYPERPARAMETER TUNING")
    logger.info("=" * 60)
    logger.info(f"Model class: {model_class.__name__}")
    logger.info(f"Trials: {n_trials}")
    logger.info(f"Multi-objective: {multi_objective}")
    logger.info(f"Device: {device}")
    logger.info("=" * 60)

    # Create tuner
    if multi_objective:
        tuner = MultiObjectiveTuner(
            model_class=model_class,
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            device=device,
            study_name=study_name
        )
    else:
        tuner = HyperparameterTuner(
            model_class=model_class,
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            device=device,
            study_name=study_name,
            direction='maximize'
        )

    # Run optimization
    logger.info("\nStarting optimization...")
    results = tuner.run_optimization(
        n_trials=n_trials,
        timeout=timeout,
        n_jobs=1  # Increase for parallel trials (requires setup)
    )

    # Save results
    logger.info("\nSaving results...")
    tuner.save_study(output_dir / 'study_results.json')

    # Generate plots
    logger.info("Generating plots...")
    try:
        tuner.plot_optimization_history(output_dir / 'study_results.json')
    except Exception as e:
        logger.warning(f"Failed to generate plots: {e}")

    # Print best parameters
    logger.info("\n" + "=" * 60)
    logger.info("BEST HYPERPARAMETERS")
    logger.info("=" * 60)

    best_params = tuner.get_best_params()
    for param, value in best_params.items():
        logger.info(f"{param}: {value}")

    logger.info("\n" + "=" * 60)
    logger.info(f"Best value: {results['best_value']:.4f}")
    logger.info(f"Total trials: {results['n_trials']}")
    logger.info("=" * 60)

    # Save best params to file
    import json
    best_params_file = output_dir / 'best_hyperparameters.json'
    with open(best_params_file, 'w') as f:
        json.dump({
            'best_params': best_params,
            'best_value': results['best_value'],
            'n_trials': results['n_trials']
        }, f, indent=2)

    logger.info(f"\nBest parameters saved to {best_params_file}")

    return best_params, results


def main():
    parser = argparse.ArgumentParser(description='Hyperparameter Tuning')

    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to dataset')
    parser.add_argument('--model-type', type=str, default='v3',
                        choices=['v2', 'v3'],
                        help='Model type (v2: Optimized, v3: Attention)')
    parser.add_argument('--n-trials', type=int, default=100,
                        help='Number of optimization trials')
    parser.add_argument('--timeout', type=int,
                        help='Timeout in seconds (optional)')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device')
    parser.add_argument('--study-name', type=str,
                        default='hyperparameter_optimization',
                        help='Name of Optuna study')
    parser.add_argument('--output-dir', type=str,
                        default='hyperparameter_tuning',
                        help='Output directory')
    parser.add_argument('--multi-objective', action='store_true',
                        help='Optimize both accuracy and speed')
    parser.add_argument('--val-split', type=float, default=0.2,
                        help='Validation split ratio')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("HYPERPARAMETER TUNING TOOL")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Model type: {args.model_type}")
    logger.info(f"Trials: {args.n_trials}")
    logger.info(f"Multi-objective: {args.multi_objective}")
    logger.info("=" * 60)

    # Load dataset
    logger.info("\nLoading dataset...")
    # dataset = load_your_dataset(args.dataset)

    # Split dataset
    # train_size = int(len(dataset) * (1 - args.val_split))
    # val_size = len(dataset) - train_size
    # train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    # logger.info(f"Train samples: {len(train_dataset)}")
    # logger.info(f"Val samples: {len(val_dataset)}")

    # Select model class
    # if args.model_type == 'v2':
    #     model_class = OptimizedPresetClassifier
    # else:
    #     model_class = AttentionPresetClassifier

    # Run tuning
    # best_params, results = tune_hyperparameters(
    #     train_dataset=train_dataset,
    #     val_dataset=val_dataset,
    #     model_class=model_class,
    #     n_trials=args.n_trials,
    #     timeout=args.timeout,
    #     device=args.device,
    #     study_name=args.study_name,
    #     output_dir=args.output_dir,
    #     multi_objective=args.multi_objective
    # )

    logger.info("\n" + "=" * 60)
    logger.info("TUNING COMPLETED")
    logger.info("=" * 60)
    logger.info(f"Results saved to: {args.output_dir}")
    logger.info("\nNext steps:")
    logger.info("1. Review best_hyperparameters.json")
    logger.info("2. Train final model with optimal parameters")
    logger.info("3. Evaluate on test set")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
