"""
Script para quantizar modelos treinados.

FASE 3.5 - Tools
Quantiza modelos para produção: reduz tamanho e acelera inferência.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch
import argparse
import logging
from datetime import datetime

from services.ai_core.model_quantization import ModelQuantizer
from services.ai_core.model_architectures_v2 import (
    OptimizedPresetClassifier,
    OptimizedRefinementRegressor
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def quantize_model(
    model_path: str,
    model_type: str,
    quantization_type: str = 'dynamic',
    calibration_data: Optional[str] = None,
    output_dir: str = 'models/quantized'
):
    """
    Quantiza um modelo treinado.

    Args:
        model_path: Caminho do modelo a quantizar
        model_type: Tipo do modelo ('classifier', 'regressor')
        quantization_type: Tipo de quantização ('dynamic', 'static')
        calibration_data: Dados para calibração (requerido para static)
        output_dir: Diretório de saída
    """
    logger.info(f"Loading model from {model_path}")

    # Load model
    # Note: Adjust dimensions based on your actual model
    if model_type == 'classifier':
        model = OptimizedPresetClassifier(
            stat_features_dim=30,
            deep_features_dim=512,
            num_presets=10
        )
    elif model_type == 'regressor':
        model = OptimizedRefinementRegressor(
            stat_features_dim=30,
            deep_features_dim=512,
            num_presets=10,
            num_params=15
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Load weights
    checkpoint = torch.load(model_path, map_location='cpu')
    model.load_state_dict(checkpoint)
    model.eval()

    logger.info("Model loaded successfully")

    # Get original size
    original_size = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024 * 1024)
    logger.info(f"Original model size: {original_size:.2f} MB")

    # Create quantizer
    quantizer = ModelQuantizer(model, device='cpu')

    # Quantize
    if quantization_type == 'dynamic':
        logger.info("Applying dynamic quantization...")
        quantized_model = quantizer.quantize_dynamic()

    elif quantization_type == 'static':
        logger.info("Applying static quantization...")

        if calibration_data is None:
            raise ValueError("Calibration data required for static quantization")

        # Load calibration data
        # calibration_loader = load_calibration_data(calibration_data)

        # quantized_model = quantizer.quantize_static(calibration_loader)
        raise NotImplementedError("Static quantization requires calibration data")

    else:
        raise ValueError(f"Unknown quantization type: {quantization_type}")

    # Get quantized size
    quantized_size = sum(p.numel() * p.element_size() for p in quantized_model.parameters()) / (1024 * 1024)
    compression_ratio = original_size / quantized_size

    logger.info(f"Quantized model size: {quantized_size:.2f} MB")
    logger.info(f"Compression ratio: {compression_ratio:.2f}x")

    # Save quantized model
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name = Path(model_path).stem
    quantized_path = output_dir / f"{model_name}_quantized.pth"

    torch.save(quantized_model.state_dict(), quantized_path)
    logger.info(f"Quantized model saved to {quantized_path}")

    # Export to different formats
    logger.info("Exporting to ONNX...")
    onnx_path = output_dir / f"{model_name}_quantized.onnx"

    try:
        quantizer.export_to_onnx(
            output_path=str(onnx_path),
            input_shape_stat=(1, 30),
            input_shape_deep=(1, 512),
            has_preset_id=(model_type == 'regressor')
        )
        logger.info(f"ONNX model saved to {onnx_path}")
    except Exception as e:
        logger.warning(f"ONNX export failed: {e}")

    logger.info("Exporting to TorchScript...")
    torchscript_path = output_dir / f"{model_name}_quantized.pt"

    try:
        quantizer.export_to_torchscript(
            output_path=str(torchscript_path),
            input_shape_stat=(1, 30),
            input_shape_deep=(1, 512),
            has_preset_id=(model_type == 'regressor')
        )
        logger.info(f"TorchScript model saved to {torchscript_path}")
    except Exception as e:
        logger.warning(f"TorchScript export failed: {e}")

    # Benchmark speed
    logger.info("\nBenchmarking inference speed...")
    speed_results = quantizer.benchmark_speed(
        input_shape_stat=(1, 30),
        input_shape_deep=(1, 512),
        num_iterations=1000,
        has_preset_id=(model_type == 'regressor')
    )

    logger.info(f"Original inference time: {speed_results['original_time_ms']:.3f} ms")
    logger.info(f"Quantized inference time: {speed_results['quantized_time_ms']:.3f} ms")
    logger.info(f"Speedup: {speed_results['speedup']:.2f}x")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("QUANTIZATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Model: {model_path}")
    logger.info(f"Type: {model_type}")
    logger.info(f"Quantization: {quantization_type}")
    logger.info(f"Size reduction: {original_size:.2f} MB -> {quantized_size:.2f} MB ({compression_ratio:.2f}x)")
    logger.info(f"Speed improvement: {speed_results['speedup']:.2f}x")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Quantize Trained Models')

    parser.add_argument('--model-path', type=str, required=True,
                        help='Path to model checkpoint')
    parser.add_argument('--model-type', type=str, required=True,
                        choices=['classifier', 'regressor'],
                        help='Type of model')
    parser.add_argument('--quantization-type', type=str, default='dynamic',
                        choices=['dynamic', 'static'],
                        help='Type of quantization')
    parser.add_argument('--calibration-data', type=str,
                        help='Path to calibration data (for static quantization)')
    parser.add_argument('--output-dir', type=str, default='models/quantized',
                        help='Output directory')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("MODEL QUANTIZATION")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model_path}")
    logger.info(f"Type: {args.model_type}")
    logger.info(f"Quantization: {args.quantization_type}")
    logger.info("=" * 60)

    quantize_model(
        model_path=args.model_path,
        model_type=args.model_type,
        quantization_type=args.quantization_type,
        calibration_data=args.calibration_data,
        output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
