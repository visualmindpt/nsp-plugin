"""
Quantização de Modelos para Inferência Rápida.

FASE 3.2 - Model Quantization
Implementa:
- Dynamic quantization: Mais fácil, boa para CPU
- Static quantization: Melhor performance, requer calibração
- ONNX export: Para deployment cross-platform
- TorchScript: Para mobile/edge devices

Benefícios esperados:
- Modelo 4x menor (728 KB → ~180 KB)
- Inferência 2-3x mais rápida em CPU
- Pequena perda de accuracy (~1-2%)
"""

import torch
import torch.nn as nn
import torch.quantization as quant
from torch.utils.data import DataLoader
import numpy as np
from typing import Optional, Tuple, Dict
import logging
from pathlib import Path
import time
import onnx
import onnxruntime as ort

logger = logging.getLogger(__name__)


class ModelQuantizer:
    """
    Quantizador de modelos PyTorch.

    Suporta múltiplos métodos de quantização para
    diferentes cenários de deployment.
    """

    def __init__(self, model: nn.Module, device: str = 'cpu'):
        """
        Inicializa quantizador.

        Args:
            model: Modelo PyTorch a quantizar
            device: Device ('cpu' recomendado para quantização)
        """
        self.original_model = model.to(device)
        self.device = device
        self.quantized_model = None

        logger.info(f"Initialized ModelQuantizer on {device}")

    def quantize_dynamic(
        self,
        dtype: torch.dtype = torch.qint8,
        modules_to_quantize: Optional[set] = None
    ) -> nn.Module:
        """
        Quantização dinâmica (mais fácil).

        Quantiza pesos em INT8, ativações permanecem FP32.
        Bom para modelos com operações lineares dominantes.

        Args:
            dtype: Tipo de quantização (torch.qint8, torch.float16)
            modules_to_quantize: Set de módulos a quantizar (default: {nn.Linear, nn.LSTM})

        Returns:
            Modelo quantizado
        """
        if modules_to_quantize is None:
            modules_to_quantize = {nn.Linear}

        logger.info("Applying dynamic quantization...")

        # Move to CPU (required for quantization)
        model_cpu = self.original_model.to('cpu')
        model_cpu.eval()

        # Dynamic quantization
        quantized_model = quant.quantize_dynamic(
            model_cpu,
            modules_to_quantize,
            dtype=dtype
        )

        self.quantized_model = quantized_model

        logger.info("Dynamic quantization completed")

        return quantized_model

    def quantize_static(
        self,
        calibration_loader: DataLoader,
        qconfig: str = 'fbgemm'
    ) -> nn.Module:
        """
        Quantização estática (melhor performance).

        Quantiza pesos E ativações. Requer calibração com dados.
        Melhor performance, mas mais complexo.

        Args:
            calibration_loader: DataLoader para calibração
            qconfig: Configuração ('fbgemm' para x86, 'qnnpack' para ARM)

        Returns:
            Modelo quantizado
        """
        logger.info("Applying static quantization...")

        # Move to CPU
        model_cpu = self.original_model.to('cpu')
        model_cpu.eval()

        # Set qconfig
        if qconfig == 'fbgemm':
            model_cpu.qconfig = quant.get_default_qconfig('fbgemm')
        elif qconfig == 'qnnpack':
            model_cpu.qconfig = quant.get_default_qconfig('qnnpack')
        else:
            raise ValueError(f"Unknown qconfig: {qconfig}")

        # Prepare for quantization
        model_prepared = quant.prepare(model_cpu, inplace=False)

        # Calibrate with data
        logger.info("Calibrating model...")
        model_prepared.eval()

        with torch.no_grad():
            for batch in calibration_loader:
                stat_feat = batch['stat_features']
                deep_feat = batch['deep_features']

                # Forward pass (no need for output)
                if 'preset_id' in batch:
                    # Regressor
                    preset_id = batch['preset_id']
                    _ = model_prepared(stat_feat, deep_feat, preset_id)
                else:
                    # Classifier
                    _ = model_prepared(stat_feat, deep_feat)

        # Convert to quantized model
        quantized_model = quant.convert(model_prepared, inplace=False)

        self.quantized_model = quantized_model

        logger.info("Static quantization completed")

        return quantized_model

    def evaluate_accuracy_loss(
        self,
        test_loader: DataLoader,
        task: str = 'classification'
    ) -> Dict[str, float]:
        """
        Avalia perda de accuracy devido à quantização.

        Args:
            test_loader: DataLoader de teste
            task: Tipo de tarefa ('classification', 'regression')

        Returns:
            Dicionário com métricas originais e quantizadas
        """
        if self.quantized_model is None:
            raise ValueError("No quantized model available. Run quantization first.")

        logger.info("Evaluating accuracy loss...")

        # Evaluate original model
        original_metric = self._evaluate_model(
            self.original_model,
            test_loader,
            task
        )

        # Evaluate quantized model
        quantized_metric = self._evaluate_model(
            self.quantized_model,
            test_loader,
            task
        )

        # Compute loss
        accuracy_loss = original_metric - quantized_metric

        results = {
            'original': original_metric,
            'quantized': quantized_metric,
            'loss': accuracy_loss,
            'loss_percentage': (accuracy_loss / original_metric) * 100 if original_metric > 0 else 0
        }

        logger.info(f"Original: {original_metric:.4f}")
        logger.info(f"Quantized: {quantized_metric:.4f}")
        logger.info(f"Loss: {accuracy_loss:.4f} ({results['loss_percentage']:.2f}%)")

        return results

    def _evaluate_model(
        self,
        model: nn.Module,
        test_loader: DataLoader,
        task: str
    ) -> float:
        """Avalia modelo em test set."""
        model.eval()

        if task == 'classification':
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

            return correct / total

        elif task == 'regression':
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

            return total_mse / total_samples

        else:
            raise ValueError(f"Unknown task: {task}")

    def benchmark_speed(
        self,
        input_shape_stat: Tuple[int, ...],
        input_shape_deep: Tuple[int, ...],
        num_iterations: int = 1000,
        has_preset_id: bool = False
    ) -> Dict[str, float]:
        """
        Benchmark de velocidade: original vs quantizado.

        Args:
            input_shape_stat: Shape das stat features (batch_size, stat_dim)
            input_shape_deep: Shape das deep features (batch_size, deep_dim)
            num_iterations: Número de iterações
            has_preset_id: Se True, inclui preset_id (para regressores)

        Returns:
            Dicionário com tempos
        """
        if self.quantized_model is None:
            raise ValueError("No quantized model available.")

        logger.info(f"Benchmarking speed ({num_iterations} iterations)...")

        # Create dummy inputs
        stat_feat = torch.randn(*input_shape_stat)
        deep_feat = torch.randn(*input_shape_deep)

        if has_preset_id:
            preset_id = torch.randint(0, 10, (input_shape_stat[0],))
        else:
            preset_id = None

        # Benchmark original
        self.original_model.eval()
        start = time.time()

        with torch.no_grad():
            for _ in range(num_iterations):
                if preset_id is not None:
                    _ = self.original_model(stat_feat, deep_feat, preset_id)
                else:
                    _ = self.original_model(stat_feat, deep_feat)

        original_time = (time.time() - start) / num_iterations * 1000  # ms

        # Benchmark quantized
        self.quantized_model.eval()
        start = time.time()

        with torch.no_grad():
            for _ in range(num_iterations):
                if preset_id is not None:
                    _ = self.quantized_model(stat_feat, deep_feat, preset_id)
                else:
                    _ = self.quantized_model(stat_feat, deep_feat)

        quantized_time = (time.time() - start) / num_iterations * 1000  # ms

        speedup = original_time / quantized_time

        results = {
            'original_time_ms': original_time,
            'quantized_time_ms': quantized_time,
            'speedup': speedup
        }

        logger.info(f"Original: {original_time:.3f} ms/iter")
        logger.info(f"Quantized: {quantized_time:.3f} ms/iter")
        logger.info(f"Speedup: {speedup:.2f}x")

        return results

    def export_to_onnx(
        self,
        output_path: str,
        input_shape_stat: Tuple[int, ...],
        input_shape_deep: Tuple[int, ...],
        has_preset_id: bool = False,
        opset_version: int = 13
    ):
        """
        Exporta modelo para ONNX.

        Args:
            output_path: Caminho do arquivo ONNX
            input_shape_stat: Shape das stat features
            input_shape_deep: Shape das deep features
            has_preset_id: Se True, modelo é regressor
            opset_version: Versão do ONNX opset
        """
        logger.info(f"Exporting to ONNX: {output_path}")

        model = self.quantized_model if self.quantized_model else self.original_model
        model.eval()

        # Create dummy inputs
        stat_feat = torch.randn(*input_shape_stat)
        deep_feat = torch.randn(*input_shape_deep)

        if has_preset_id:
            preset_id = torch.randint(0, 10, (input_shape_stat[0],))
            dummy_input = (stat_feat, deep_feat, preset_id)
            input_names = ['stat_features', 'deep_features', 'preset_id']
        else:
            dummy_input = (stat_feat, deep_feat)
            input_names = ['stat_features', 'deep_features']

        output_names = ['output']

        # Export
        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            input_names=input_names,
            output_names=output_names,
            opset_version=opset_version,
            dynamic_axes={
                'stat_features': {0: 'batch_size'},
                'deep_features': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            }
        )

        logger.info(f"ONNX export completed: {output_path}")

        # Validate ONNX
        try:
            onnx_model = onnx.load(output_path)
            onnx.checker.check_model(onnx_model)
            logger.info("ONNX model validated successfully")
        except Exception as e:
            logger.warning(f"ONNX validation failed: {e}")

    def export_to_torchscript(
        self,
        output_path: str,
        input_shape_stat: Tuple[int, ...],
        input_shape_deep: Tuple[int, ...],
        has_preset_id: bool = False
    ):
        """
        Exporta modelo para TorchScript.

        Args:
            output_path: Caminho do arquivo TorchScript
            input_shape_stat: Shape das stat features
            input_shape_deep: Shape das deep features
            has_preset_id: Se True, modelo é regressor
        """
        logger.info(f"Exporting to TorchScript: {output_path}")

        model = self.quantized_model if self.quantized_model else self.original_model
        model.eval()

        # Create dummy inputs
        stat_feat = torch.randn(*input_shape_stat)
        deep_feat = torch.randn(*input_shape_deep)

        if has_preset_id:
            preset_id = torch.randint(0, 10, (input_shape_stat[0],))
            dummy_input = (stat_feat, deep_feat, preset_id)
        else:
            dummy_input = (stat_feat, deep_feat)

        # Trace model
        traced_model = torch.jit.trace(model, dummy_input)

        # Save
        traced_model.save(output_path)

        logger.info(f"TorchScript export completed: {output_path}")

    def get_model_size(self, model: Optional[nn.Module] = None) -> float:
        """
        Calcula tamanho do modelo em MB.

        Args:
            model: Modelo (default: quantized_model)

        Returns:
            Tamanho em MB
        """
        if model is None:
            model = self.quantized_model if self.quantized_model else self.original_model

        param_size = sum(p.nelement() * p.element_size() for p in model.parameters())
        buffer_size = sum(b.nelement() * b.element_size() for b in model.buffers())

        size_mb = (param_size + buffer_size) / (1024 * 1024)

        return size_mb


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    # Create dummy model
    class DummyClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1 = nn.Linear(30 + 512, 128)
            self.fc2 = nn.Linear(128, 64)
            self.fc3 = nn.Linear(64, 10)

        def forward(self, stat_feat, deep_feat):
            x = torch.cat([stat_feat, deep_feat], dim=1)
            x = torch.relu(self.fc1(x))
            x = torch.relu(self.fc2(x))
            return self.fc3(x)

    model = DummyClassifier()

    # Create quantizer
    quantizer = ModelQuantizer(model, device='cpu')

    # Dynamic quantization
    quantized_model = quantizer.quantize_dynamic()

    # Check sizes
    original_size = quantizer.get_model_size(model)
    quantized_size = quantizer.get_model_size(quantized_model)

    print(f"Original size: {original_size:.2f} MB")
    print(f"Quantized size: {quantized_size:.2f} MB")
    print(f"Compression: {original_size/quantized_size:.2f}x")

    # Benchmark
    results = quantizer.benchmark_speed(
        input_shape_stat=(1, 30),
        input_shape_deep=(1, 512),
        num_iterations=100
    )

    print(f"Speedup: {results['speedup']:.2f}x")

    print("Model quantization ready!")
