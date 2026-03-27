# -*- coding: utf-8 -*-
"""
Script de teste para validar imports e funcionamento basico das otimizacoes FASE 1.
"""

import sys
from pathlib import Path
import torch
import numpy as np

print("=" * 70)
print("TESTE DE VALIDACAO - FASE 1 OTIMIZACOES")
print("=" * 70)

# 1. Testar imports de model_architectures_v2
print("\n[1/5] Testando model_architectures_v2...")
try:
    from services.ai_core.model_architectures_v2 import (
        OptimizedPresetClassifier,
        OptimizedRefinementRegressor,
        AttentionLayer,
        count_parameters,
        get_model_size_mb
    )
    print("OK - Imports")

    # Instanciar modelos
    classifier = OptimizedPresetClassifier(
        stat_features_dim=50,
        deep_features_dim=512,
        num_presets=4
    )
    regressor = OptimizedRefinementRegressor(
        stat_features_dim=50,
        deep_features_dim=512,
        num_presets=4,
        num_params=58
    )

    # Contar parâmetros
    classifier_params = count_parameters(classifier)
    regressor_params = count_parameters(regressor)
    classifier_size = get_model_size_mb(classifier)
    regressor_size = get_model_size_mb(regressor)

    print("OK - OptimizedPresetClassifier: {} params, {:.2f} MB".format(
        classifier_params, classifier_size))
    print("OK - OptimizedRefinementRegressor: {} params, {:.2f} MB".format(
        regressor_params, regressor_size))

    # Teste de forward pass
    stat_feat = torch.randn(2, 50)
    deep_feat = torch.randn(2, 512)
    preset_ids = torch.tensor([0, 1])

    output_classifier = classifier(stat_feat, deep_feat)
    output_regressor = regressor(stat_feat, deep_feat, preset_ids)

    print("OK - Forward pass classifier: {}".format(output_classifier.shape))
    print("OK - Forward pass regressor: {}".format(output_regressor.shape))

except Exception as e:
    print("ERRO: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. Testar imports de data_augmentation
print("\n[2/5] Testando data_augmentation...")
try:
    from services.ai_core.data_augmentation import (
        augment_stat_features,
        augment_deep_features,
        mixup_deltas,
        DataAugmentationDataset,
        BatchMixupCollator
    )
    print("OK - Imports")

    # Testar funcoes de augmentation
    stat_features = torch.randn(10, 50)
    deep_features = torch.randn(10, 512)
    deltas = torch.randn(10, 58)

    aug_stat = augment_stat_features(stat_features, noise_std=0.05)
    aug_deep = augment_deep_features(deep_features, dropout_prob=0.1)
    mixed = mixup_deltas(deltas[:5], deltas[5:], alpha=0.3)

    print("OK - Stat augmentation: {}".format(aug_stat.shape))
    print("OK - Deep augmentation: {}".format(aug_deep.shape))
    print("OK - Mixup: {}".format(mixed.shape))

    # Testar dataset wrapper
    from services.ai_core.training_utils import LightroomDataset

    base_dataset = LightroomDataset(
        stat_features.numpy(),
        deep_features.numpy(),
        np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
        deltas.numpy()
    )

    aug_dataset = DataAugmentationDataset(
        base_dataset,
        augment_stat=True,
        augment_deep=True,
        augment_deltas=True
    )

    sample = aug_dataset[0]
    print("OK - DataAugmentationDataset, sample keys: {}".format(list(sample.keys())))

except Exception as e:
    print("ERRO: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Testar imports de trainer_v2
print("\n[3/5] Testando trainer_v2...")
try:
    from services.ai_core.trainer_v2 import (
        OptimizedClassifierTrainer,
        OptimizedRefinementTrainer
    )
    print("OK - Imports")

    # Instanciar trainers (sem treinar)
    device = 'cpu'  # Usar CPU para teste

    classifier_trainer = OptimizedClassifierTrainer(
        classifier,
        device=device,
        use_mixed_precision=False  # Desabilitar para CPU
    )

    weights = torch.ones(58)
    regressor_trainer = OptimizedRefinementTrainer(
        regressor,
        weights,
        device=device,
        use_mixed_precision=False
    )

    print("OK - OptimizedClassifierTrainer criado (device={})".format(device))
    print("OK - OptimizedRefinementTrainer criado (device={})".format(device))

except Exception as e:
    print("ERRO: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Testar dataset_stats
print("\n[4/5] Testando dataset_stats...")
try:
    from services.dataset_stats import DatasetStatistics
    print("OK - Import")

    # Criar dataset de teste
    import pandas as pd

    test_data = {
        'image_path': ['image_{}.jpg'.format(i) for i in range(100)],
        'preset_cluster': [i % 4 for i in range(100)],
        'rating': [3 + (i % 3) for i in range(100)],
        'feature_1': np.random.randn(100),
        'feature_2': np.random.randn(100),
        'delta_exposure': np.random.randn(100)
    }

    test_df = pd.DataFrame(test_data)
    temp_csv = Path('test_dataset_temp.csv')
    test_df.to_csv(temp_csv, index=False)

    # Testar analise
    stats = DatasetStatistics(temp_csv)
    computed_stats = stats.compute_stats()

    print("OK - Estatisticas computadas: {}".format(list(computed_stats.keys())))
    print("OK - Dataset size: {}".format(computed_stats['dataset_size']['total_images']))
    print("OK - Num presets: {}".format(computed_stats['presets']['num_presets']))

    # Limpar arquivo temporario
    temp_csv.unlink()

except Exception as e:
    print("ERRO: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Verificar compatibilidade PyTorch
print("\n[5/5] Verificando compatibilidade PyTorch...")
try:
    print("OK - PyTorch version: {}".format(torch.__version__))
    print("OK - CUDA available: {}".format(torch.cuda.is_available()))
    print("OK - MPS available: {}".format(torch.backends.mps.is_available()))

    # Verificar GradScaler (mixed precision)
    from torch.cuda.amp import GradScaler, autocast
    print("OK - Mixed precision support")

except Exception as e:
    print("ERRO: {}".format(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Resumo final
print("\n" + "=" * 70)
print("RESUMO DOS TESTES")
print("=" * 70)
print("OK - model_architectures_v2")
print("OK - data_augmentation")
print("OK - trainer_v2")
print("OK - dataset_stats")
print("OK - PyTorch compatibility")
print("\nTODOS OS TESTES PASSARAM!")
print("\nProximo passo: Configure o CATALOG_PATH em train/train_models_v2.py")
print("e execute: python train/train_models_v2.py")
print("=" * 70)
