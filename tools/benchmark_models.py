"""
Script para benchmark de modelos.

FASE 3.5 - Tools
Compara diferentes modelos em termos de accuracy, velocidade e tamanho.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import argparse
import logging
import time
import json
from typing import Dict, List
import numpy as np

from services.ai_core.model_architectures_v2 import (
    OptimizedPresetClassifier,
    OptimizedRefinementRegressor,
    count_parameters,
    get_model_size_mb
)
from services.ai_core.model_architectures_v3 import (
    AttentionPresetClassifier,
    AttentionRefinementRegressor
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelBenchmark:
    """
    Benchmark de modelos: accuracy, speed, size.
    """

    def __init__(self, device: str = 'cuda'):
        """
        Inicializa benchmark.

        Args:
            device: Device para benchmark
        """
        self.device = device
        self.results = []

    def benchmark_model(
        self,
        model: nn.Module,
        model_name: str,
        test_loader: DataLoader,
        task: str = 'classification',
        num_warmup: int = 10,
        num_iterations: int = 100
    ) -> Dict:
        """
        Benchmark completo de um modelo.

        Args:
            model: Modelo a avaliar
            model_name: Nome do modelo
            test_loader: DataLoader de teste
            task: Tipo de tarefa ('classification', 'regression')
            num_warmup: Iterações de warmup
            num_iterations: Iterações para benchmark de velocidade

        Returns:
            Dicionário com métricas
        """
        logger.info(f"\nBenchmarking: {model_name}")
        logger.info("=" * 60)

        model = model.to(self.device)
        model.eval()

        # 1. Model Size
        num_params = count_parameters(model)
        size_mb = get_model_size_mb(model)

        logger.info(f"Parameters: {num_params:,}")
        logger.info(f"Size: {size_mb:.2f} MB")

        # 2. Accuracy
        if task == 'classification':
            accuracy = self._evaluate_classification(model, test_loader)
            logger.info(f"Accuracy: {accuracy:.4f}")
        elif task == 'regression':
            mse = self._evaluate_regression(model, test_loader)
            accuracy = mse  # Use MSE as metric
            logger.info(f"MSE: {mse:.4f}")
        else:
            raise ValueError(f"Unknown task: {task}")

        # 3. Inference Speed
        inference_time = self._benchmark_speed(
            model,
            test_loader,
            num_warmup=num_warmup,
            num_iterations=num_iterations,
            task=task
        )

        logger.info(f"Inference time: {inference_time:.3f} ms/sample")

        # 4. Throughput
        throughput = 1000 / inference_time  # samples/second

        logger.info(f"Throughput: {throughput:.2f} samples/sec")

        # Compile results
        results = {
            'model_name': model_name,
            'num_parameters': num_params,
            'size_mb': size_mb,
            'accuracy': accuracy,
            'inference_time_ms': inference_time,
            'throughput_samples_per_sec': throughput,
            'task': task
        }

        self.results.append(results)

        return results

    def _evaluate_classification(
        self,
        model: nn.Module,
        test_loader: DataLoader
    ) -> float:
        """Avalia accuracy de classificação."""
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in test_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                labels = batch['label'].to(self.device)

                outputs = model(stat_feat, deep_feat)
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()

        return correct / total if total > 0 else 0.0

    def _evaluate_regression(
        self,
        model: nn.Module,
        test_loader: DataLoader
    ) -> float:
        """Avalia MSE de regressão."""
        total_mse = 0.0
        total_samples = 0

        with torch.no_grad():
            for batch in test_loader:
                stat_feat = batch['stat_features'].to(self.device)
                deep_feat = batch['deep_features'].to(self.device)
                preset_id = batch['preset_id'].to(self.device)
                targets = batch['deltas'].to(self.device)

                outputs = model(stat_feat, deep_feat, preset_id)
                mse = ((outputs - targets) ** 2).mean()

                total_mse += mse.item() * targets.size(0)
                total_samples += targets.size(0)

        return total_mse / total_samples if total_samples > 0 else 0.0

    def _benchmark_speed(
        self,
        model: nn.Module,
        test_loader: DataLoader,
        num_warmup: int = 10,
        num_iterations: int = 100,
        task: str = 'classification'
    ) -> float:
        """
        Benchmark de velocidade de inferência.

        Returns:
            Tempo médio em ms por sample
        """
        # Get a batch for benchmarking
        batch = next(iter(test_loader))
        stat_feat = batch['stat_features'].to(self.device)
        deep_feat = batch['deep_features'].to(self.device)

        if task == 'regression':
            preset_id = batch['preset_id'].to(self.device)
        else:
            preset_id = None

        # Warmup
        with torch.no_grad():
            for _ in range(num_warmup):
                if preset_id is not None:
                    _ = model(stat_feat, deep_feat, preset_id)
                else:
                    _ = model(stat_feat, deep_feat)

        # Benchmark
        if self.device == 'cuda':
            torch.cuda.synchronize()

        times = []

        with torch.no_grad():
            for _ in range(num_iterations):
                start = time.time()

                if preset_id is not None:
                    _ = model(stat_feat, deep_feat, preset_id)
                else:
                    _ = model(stat_feat, deep_feat)

                if self.device == 'cuda':
                    torch.cuda.synchronize()

                elapsed = (time.time() - start) * 1000  # Convert to ms
                times.append(elapsed)

        # Average time per batch
        avg_time_per_batch = np.mean(times)

        # Convert to per sample
        batch_size = stat_feat.size(0)
        avg_time_per_sample = avg_time_per_batch / batch_size

        return avg_time_per_sample

    def compare_models(self) -> Dict:
        """
        Compara todos os modelos benchmarked.

        Returns:
            Dicionário com comparação
        """
        if not self.results:
            logger.warning("No models benchmarked yet")
            return {}

        logger.info("\n" + "=" * 60)
        logger.info("MODEL COMPARISON")
        logger.info("=" * 60)

        # Create comparison table
        logger.info(f"\n{'Model':<30} {'Params':<12} {'Size (MB)':<10} {'Accuracy':<10} {'Speed (ms)':<12} {'Throughput':<15}")
        logger.info("-" * 100)

        for result in self.results:
            logger.info(
                f"{result['model_name']:<30} "
                f"{result['num_parameters']:<12,} "
                f"{result['size_mb']:<10.2f} "
                f"{result['accuracy']:<10.4f} "
                f"{result['inference_time_ms']:<12.3f} "
                f"{result['throughput_samples_per_sec']:<15.2f}"
            )

        # Find best models
        best_accuracy = max(self.results, key=lambda x: x['accuracy'])
        best_speed = min(self.results, key=lambda x: x['inference_time_ms'])
        smallest = min(self.results, key=lambda x: x['size_mb'])

        logger.info("\n" + "=" * 60)
        logger.info("BEST MODELS")
        logger.info("=" * 60)
        logger.info(f"Best Accuracy: {best_accuracy['model_name']} ({best_accuracy['accuracy']:.4f})")
        logger.info(f"Fastest: {best_speed['model_name']} ({best_speed['inference_time_ms']:.3f} ms)")
        logger.info(f"Smallest: {smallest['model_name']} ({smallest['size_mb']:.2f} MB)")

        comparison = {
            'results': self.results,
            'best_accuracy': best_accuracy,
            'best_speed': best_speed,
            'smallest': smallest
        }

        return comparison

    def save_results(self, output_path: str):
        """
        Salva resultados do benchmark.

        Args:
            output_path: Caminho do arquivo JSON
        """
        comparison = self.compare_models()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(comparison, f, indent=2)

        logger.info(f"\nResults saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Benchmark Models')

    parser.add_argument('--test-data', type=str, required=True,
                        help='Path to test dataset')
    parser.add_argument('--models', type=str, nargs='+', required=True,
                        help='Paths to model checkpoints')
    parser.add_argument('--model-names', type=str, nargs='+',
                        help='Names for models (optional)')
    parser.add_argument('--model-type', type=str, default='classifier',
                        choices=['classifier', 'regressor'],
                        help='Type of models')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size for testing')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device for benchmark')
    parser.add_argument('--output', type=str, default='benchmark_results.json',
                        help='Output file for results')
    parser.add_argument('--num-iterations', type=int, default=100,
                        help='Number of iterations for speed benchmark')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MODEL BENCHMARK")
    logger.info("=" * 60)
    logger.info(f"Test data: {args.test_data}")
    logger.info(f"Models: {len(args.models)}")
    logger.info(f"Device: {args.device}")
    logger.info("=" * 60)

    # Load test dataset
    # test_dataset = load_test_dataset(args.test_data)
    # test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    # Create benchmark
    benchmark = ModelBenchmark(device=args.device)

    # Benchmark each model
    # for i, model_path in enumerate(args.models):
    #     model_name = args.model_names[i] if args.model_names else Path(model_path).stem
    #
    #     # Load model
    #     if args.model_type == 'classifier':
    #         model = OptimizedPresetClassifier(...)
    #     else:
    #         model = OptimizedRefinementRegressor(...)
    #
    #     checkpoint = torch.load(model_path)
    #     model.load_state_dict(checkpoint)
    #
    #     # Benchmark
    #     benchmark.benchmark_model(
    #         model=model,
    #         model_name=model_name,
    #         test_loader=test_loader,
    #         task=args.model_type,
    #         num_iterations=args.num_iterations
    #     )

    # Compare and save
    # benchmark.save_results(args.output)

    logger.info("\n" + "=" * 60)
    logger.info("BENCHMARK COMPLETED")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
