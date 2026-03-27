# -*- coding: utf-8 -*-
"""
Script para comparar modelos originais vs otimizados.
"""
import torch
from services.ai_core.model_architectures import PresetClassifier, RefinementRegressor
from services.ai_core.model_architectures_v2 import (
    OptimizedPresetClassifier,
    OptimizedRefinementRegressor,
    count_parameters,
    get_model_size_mb
)

print("=" * 70)
print("COMPARACAO: MODELOS ORIGINAIS vs OTIMIZADOS")
print("=" * 70)

# Configuracoes
stat_dim = 50
deep_dim = 512
num_presets = 4
num_params = 58

# Modelos originais
print("\nMODELOS ORIGINAIS:")
print("-" * 70)

original_classifier = PresetClassifier(stat_dim, deep_dim, num_presets)
original_regressor = RefinementRegressor(stat_dim, deep_dim, num_presets, num_params)

orig_clf_params = count_parameters(original_classifier)
orig_clf_size = get_model_size_mb(original_classifier)
orig_reg_params = count_parameters(original_regressor)
orig_reg_size = get_model_size_mb(original_regressor)

print("PresetClassifier:")
print("  Parametros: {:,}".format(orig_clf_params))
print("  Tamanho: {:.2f} MB".format(orig_clf_size))

print("\nRefinementRegressor:")
print("  Parametros: {:,}".format(orig_reg_params))
print("  Tamanho: {:.2f} MB".format(orig_reg_size))

# Modelos otimizados
print("\n" + "=" * 70)
print("MODELOS OTIMIZADOS (FASE 1):")
print("-" * 70)

opt_classifier = OptimizedPresetClassifier(stat_dim, deep_dim, num_presets)
opt_regressor = OptimizedRefinementRegressor(stat_dim, deep_dim, num_presets, num_params)

opt_clf_params = count_parameters(opt_classifier)
opt_clf_size = get_model_size_mb(opt_classifier)
opt_reg_params = count_parameters(opt_regressor)
opt_reg_size = get_model_size_mb(opt_regressor)

print("OptimizedPresetClassifier:")
print("  Parametros: {:,}".format(opt_clf_params))
print("  Tamanho: {:.2f} MB".format(opt_clf_size))

print("\nOptimizedRefinementRegressor:")
print("  Parametros: {:,}".format(opt_reg_params))
print("  Tamanho: {:.2f} MB".format(opt_reg_size))

# Reducao
print("\n" + "=" * 70)
print("REDUCAO DE PARAMETROS:")
print("-" * 70)

clf_reduction = (1 - opt_clf_params / orig_clf_params) * 100
reg_reduction = (1 - opt_reg_params / orig_reg_params) * 100

print("PresetClassifier:")
print("  Reducao de parametros: {:.1f}%".format(clf_reduction))
print("  De {:,} para {:,}".format(orig_clf_params, opt_clf_params))
print("  Tamanho: {:.2f} MB -> {:.2f} MB ({:.1f}% menor)".format(
    orig_clf_size, opt_clf_size, (1 - opt_clf_size / orig_clf_size) * 100))

print("\nRefinementRegressor:")
print("  Reducao de parametros: {:.1f}%".format(reg_reduction))
print("  De {:,} para {:,}".format(orig_reg_params, opt_reg_params))
print("  Tamanho: {:.2f} MB -> {:.2f} MB ({:.1f}% menor)".format(
    orig_reg_size, opt_reg_size, (1 - opt_reg_size / orig_reg_size) * 100))

print("\n" + "=" * 70)
print("MELHORIAS ADICIONAIS (FASE 1):")
print("-" * 70)
print("- Attention mechanism no classificador")
print("- Skip connections no regressor")
print("- BatchNorm em todas as camadas")
print("- Dropout mais agressivo (0.4-0.5)")
print("- Data augmentation (ruido, dropout, mixup)")
print("- OneCycleLR scheduler")
print("- Mixed precision training")
print("- Sistema de analise de dataset")
print("=" * 70)
