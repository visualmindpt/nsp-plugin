#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation Script - Todas as Features Implementadas
Valida que todas as 19 features estão corretamente implementadas e funcionais

Testa:
- Estrutura de arquivos
- Imports de módulos
- Configurações
- Features individuais
- Integrações

Data: 21 Novembro 2025
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Any, List
import traceback

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class FeatureValidator:
    """
    Validador completo de features

    Executa testes de validação para todas as 19 features
    """

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "tests": []
        }

    def log_test(self, name: str, status: str, message: str = "", details: Any = None):
        """
        Registra resultado de um teste

        Args:
            name: Nome do teste
            status: "pass", "fail", "warning"
            message: Mensagem descritiva
            details: Detalhes adicionais
        """
        self.results["total_tests"] += 1

        if status == "pass":
            self.results["passed"] += 1
            icon = "✅"
        elif status == "fail":
            self.results["failed"] += 1
            icon = "❌"
        else:  # warning
            self.results["warnings"] += 1
            icon = "⚠️"

        test_result = {
            "name": name,
            "status": status,
            "message": message,
            "details": details
        }

        self.results["tests"].append(test_result)

        logger.info(f"{icon} {name}: {message}")

    # ========== VALIDAÇÃO DE ESTRUTURA ==========

    def validate_file_structure(self):
        """Valida que todos os arquivos necessários existem"""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDAÇÃO 1: Estrutura de Arquivos")
        logger.info("=" * 80)

        required_files = {
            # Fase 1
            "services/dataset_quality_analyzer.py": "Dataset Quality Analyzer",
            "services/auto_hyperparameter_selector.py": "Auto Hyperparameter Selector",
            "services/learning_rate_finder.py": "Learning Rate Finder",
            "services/training_utils.py": "Training Utils (Mixed Precision, etc)",
            "services/scene_classifier.py": "Scene Classifier",
            "services/duplicate_detector.py": "Duplicate Detector",

            # Fase 2
            "services/ai_core/feature_cache.py": "Feature Cache",
            "services/ai_core/parallel_feature_extractor.py": "Parallel Feature Extractor",
            "services/ai_core/progressive_trainer.py": "Progressive Trainer",
            "services/alert_manager.py": "Alert Manager",
            "services/monitoring.py": "Monitoring System",
            "control-center-v2/static/js/websocket-client.js": "WebSocket Client",

            # Fase 3
            "services/ai_core/feature_selector.py": "Feature Selector",
            "services/ai_core/optuna_tuner.py": "Optuna Tuner",
            "scripts/auto_train.py": "Auto Train Pipeline",
            "services/scheduled_retrainer.py": "Scheduled Retrainer",
            "NSP-Plugin.lrplugin/PredictionCache.lua": "Prediction Cache (Plugin)",
            "NSP-Plugin.lrplugin/BatchProcessor.lua": "Batch Processor (Plugin)",
            "services/ai_core/gradient_checkpointing.py": "Gradient Checkpointing",

            # Core files
            "train/train_models_v2.py": "Main Training Script",
            "services/server.py": "API Server"
        }

        missing = []
        found = []

        for file_path, description in required_files.items():
            full_path = self.project_root / file_path
            if full_path.exists():
                found.append(description)
                self.log_test(
                    f"File: {file_path}",
                    "pass",
                    f"Found - {description}"
                )
            else:
                missing.append(description)
                self.log_test(
                    f"File: {file_path}",
                    "fail",
                    f"Missing - {description}"
                )

        logger.info(f"\n📊 Files: {len(found)}/{len(required_files)} encontrados")

        return len(missing) == 0

    # ========== VALIDAÇÃO DE IMPORTS ==========

    def validate_imports(self):
        """Valida que todos os módulos podem ser importados"""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDAÇÃO 2: Imports de Módulos Python")
        logger.info("=" * 80)

        modules_to_test = [
            ("services.dataset_quality_analyzer", "DatasetQualityAnalyzer"),
            ("services.auto_hyperparameter_selector", "AutoHyperparameterSelector"),
            ("services.learning_rate_finder", "find_optimal_lr"),
            ("services.training_utils", "MixedPrecisionTrainer"),
            ("services.scene_classifier", "SceneClassifier"),
            ("services.duplicate_detector", "DuplicateDetector"),
            ("services.ai_core.feature_cache", "FeatureCache"),
            ("services.ai_core.parallel_feature_extractor", "ParallelFeatureExtractor"),
            ("services.ai_core.progressive_trainer", "ProgressiveTrainer"),
            ("services.alert_manager", "get_alert_manager"),
            ("services.monitoring", "get_monitoring_collector"),
            ("services.ai_core.feature_selector", "FeatureSelector"),
            ("services.ai_core.optuna_tuner", "OptunaHyperparameterTuner"),
            ("services.scheduled_retrainer", "ScheduledRetrainer"),
            ("services.ai_core.gradient_checkpointing", "add_gradient_checkpointing"),
        ]

        import_errors = []

        for module_name, class_or_func in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_or_func])
                obj = getattr(module, class_or_func)

                self.log_test(
                    f"Import: {module_name}.{class_or_func}",
                    "pass",
                    "Importado com sucesso"
                )
            except Exception as e:
                import_errors.append(f"{module_name}.{class_or_func}: {e}")
                self.log_test(
                    f"Import: {module_name}.{class_or_func}",
                    "fail",
                    f"Erro: {str(e)}"
                )

        logger.info(f"\n📊 Imports: {len(modules_to_test) - len(import_errors)}/{len(modules_to_test)} bem-sucedidos")

        return len(import_errors) == 0

    # ========== VALIDAÇÃO DE CONFIGURAÇÕES ==========

    def validate_configurations(self):
        """Valida configurações em train_models_v2.py"""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDAÇÃO 3: Configurações em train_models_v2.py")
        logger.info("=" * 80)

        try:
            # Ler train_models_v2.py
            train_file = self.project_root / "train" / "train_models_v2.py"

            if not train_file.exists():
                self.log_test(
                    "Config File",
                    "fail",
                    "train_models_v2.py não encontrado"
                )
                return False

            content = train_file.read_text()

            # Verificar flags importantes
            flags_to_check = {
                "USE_AUTO_HYPERPARAMS": "Auto Hyperparameters",
                "USE_LR_FINDER": "Learning Rate Finder",
                "USE_PARALLEL_EXTRACTION": "Parallel Extraction",
                "USE_PROGRESSIVE_TRAINING": "Progressive Training",
                "USE_FEATURE_SELECTION": "Feature Selection",
                "USE_MIXED_PRECISION": "Mixed Precision",
                "GRADIENT_ACCUMULATION_STEPS": "Gradient Accumulation"
            }

            for flag, description in flags_to_check.items():
                if flag in content:
                    # Tentar extrair valor
                    for line in content.split('\n'):
                        if flag in line and '=' in line and not line.strip().startswith('#'):
                            value = line.split('=')[1].strip().split('#')[0].strip()
                            self.log_test(
                                f"Config: {flag}",
                                "pass",
                                f"{description} = {value}"
                            )
                            break
                else:
                    self.log_test(
                        f"Config: {flag}",
                        "warning",
                        f"{description} não encontrado"
                    )

            return True

        except Exception as e:
            self.log_test(
                "Configurations",
                "fail",
                f"Erro ao validar configurações: {e}"
            )
            return False

    # ========== TESTES FUNCIONAIS ==========

    def test_feature_cache(self):
        """Testa Feature Cache"""
        logger.info("\n" + "=" * 80)
        logger.info("TESTE 4: Feature Cache")
        logger.info("=" * 80)

        try:
            from services.ai_core.feature_cache import FeatureCache
            import tempfile

            cache = FeatureCache()

            # Test set/get - criar ficheiro temporário real
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jpg', delete=False) as f:
                test_key = f.name
                f.write("dummy image data")

            test_features = {"feature1": 1.0, "feature2": 2.0}

            cache.set(test_key, test_features)
            retrieved = cache.get(test_key)

            # Cleanup
            Path(test_key).unlink(missing_ok=True)

            if retrieved == test_features:
                self.log_test(
                    "Feature Cache - Set/Get",
                    "pass",
                    "Cache funcionando corretamente"
                )
            else:
                self.log_test(
                    "Feature Cache - Set/Get",
                    "fail",
                    f"Esperado {test_features}, obtido {retrieved}"
                )

            # Test stats
            stats = cache.get_stats()
            self.log_test(
                "Feature Cache - Stats",
                "pass",
                f"Cache hits: {stats.get('cache_hits', 0)}"
            )

            return True

        except Exception as e:
            self.log_test(
                "Feature Cache",
                "fail",
                f"Erro: {str(e)}\n{traceback.format_exc()}"
            )
            return False

    def test_feature_selector(self):
        """Testa Feature Selector"""
        logger.info("\n" + "=" * 80)
        logger.info("TESTE 5: Feature Selector")
        logger.info("=" * 80)

        try:
            from services.ai_core.feature_selector import FeatureSelector
            import numpy as np
            import pandas as pd

            # Criar dados sintéticos
            X = pd.DataFrame(np.random.rand(100, 20), columns=[f"f{i}" for i in range(20)])
            y = np.random.randint(0, 3, 100)

            selector = FeatureSelector(method="selectkbest", task="classification")

            # Test SelectKBest
            X_selected, scores = selector.select_k_best(X, y, k=10)

            if X_selected.shape[1] == 10:
                self.log_test(
                    "Feature Selector - SelectKBest",
                    "pass",
                    f"Selecionou {X_selected.shape[1]} features de {X.shape[1]}"
                )
            else:
                self.log_test(
                    "Feature Selector - SelectKBest",
                    "fail",
                    f"Esperado 10 features, obteve {X_selected.shape[1]}"
                )

            # Test report
            report = selector.get_selection_report()
            if "selected_features" in report:
                self.log_test(
                    "Feature Selector - Report",
                    "pass",
                    f"Report gerado com {len(report['selected_features'])} features"
                )
            else:
                self.log_test(
                    "Feature Selector - Report",
                    "fail",
                    "Report incompleto"
                )

            return True

        except Exception as e:
            self.log_test(
                "Feature Selector",
                "fail",
                f"Erro: {str(e)}\n{traceback.format_exc()}"
            )
            return False

    def test_alert_manager(self):
        """Testa Alert Manager"""
        logger.info("\n" + "=" * 80)
        logger.info("TESTE 6: Alert Manager")
        logger.info("=" * 80)

        try:
            from services.alert_manager import get_alert_manager, AlertType, AlertLevel
            import asyncio

            manager = get_alert_manager()

            async def test_alerts():
                # Create test alert
                alert = await manager.create_alert(
                    alert_type=AlertType.SYSTEM,
                    level=AlertLevel.INFO,
                    message="Test alert",
                    force=True
                )

                if alert:
                    self.log_test(
                        "Alert Manager - Create Alert",
                        "pass",
                        f"Alerta criado: {alert.id}"
                    )
                else:
                    self.log_test(
                        "Alert Manager - Create Alert",
                        "fail",
                        "Não foi possível criar alerta"
                    )

                # Get stats
                stats = manager.get_stats()
                self.log_test(
                    "Alert Manager - Stats",
                    "pass",
                    f"Total alerts: {stats.get('total_alerts', 0)}"
                )

            asyncio.run(test_alerts())

            return True

        except Exception as e:
            self.log_test(
                "Alert Manager",
                "fail",
                f"Erro: {str(e)}\n{traceback.format_exc()}"
            )
            return False

    def test_monitoring(self):
        """Testa Monitoring System"""
        logger.info("\n" + "=" * 80)
        logger.info("TESTE 7: Monitoring System")
        logger.info("=" * 80)

        try:
            from services.monitoring import get_monitoring_collector

            collector = get_monitoring_collector()

            # Test get all metrics
            metrics = collector.get_all_metrics()

            if "gpu" in metrics and "model" in metrics and "system" in metrics:
                self.log_test(
                    "Monitoring - Get All Metrics",
                    "pass",
                    "Todas as métricas disponíveis"
                )
            else:
                self.log_test(
                    "Monitoring - Get All Metrics",
                    "fail",
                    f"Métricas incompletas: {list(metrics.keys())}"
                )

            # Test summary
            summary = collector.get_summary()

            if "status" in summary:
                self.log_test(
                    "Monitoring - Summary",
                    "pass",
                    f"Status: {summary['status']}"
                )
            else:
                self.log_test(
                    "Monitoring - Summary",
                    "fail",
                    "Summary incompleto"
                )

            return True

        except Exception as e:
            self.log_test(
                "Monitoring System",
                "fail",
                f"Erro: {str(e)}\n{traceback.format_exc()}"
            )
            return False

    def test_gradient_checkpointing(self):
        """Testa Gradient Checkpointing"""
        logger.info("\n" + "=" * 80)
        logger.info("TESTE 8: Gradient Checkpointing")
        logger.info("=" * 80)

        try:
            from services.ai_core.gradient_checkpointing import (
                add_gradient_checkpointing,
                CheckpointedSequential,
                calculate_memory_savings
            )
            import torch
            import torch.nn as nn

            # Test wrapper
            model = nn.Sequential(
                nn.Linear(10, 20),
                nn.ReLU(),
                nn.Linear(20, 5)
            )

            model_checkpoint = add_gradient_checkpointing(model, num_segments=2)

            self.log_test(
                "Gradient Checkpointing - Wrapper",
                "pass",
                "Modelo wrapped com sucesso"
            )

            # Test forward pass
            x = torch.randn(4, 10)
            output = model_checkpoint(x)

            if output.shape == (4, 5):
                self.log_test(
                    "Gradient Checkpointing - Forward",
                    "pass",
                    f"Forward pass OK: {output.shape}"
                )
            else:
                self.log_test(
                    "Gradient Checkpointing - Forward",
                    "fail",
                    f"Shape incorreto: {output.shape}"
                )

            # Test memory savings calculation
            savings = calculate_memory_savings(model, with_checkpointing=True)

            self.log_test(
                "Gradient Checkpointing - Memory Savings",
                "pass",
                f"Estimativa: {savings['total_mb']:.1f} MB"
            )

            return True

        except Exception as e:
            self.log_test(
                "Gradient Checkpointing",
                "fail",
                f"Erro: {str(e)}\n{traceback.format_exc()}"
            )
            return False

    # ========== EXECUTAR TUDO ==========

    def run_all_validations(self):
        """Executa todas as validações"""
        logger.info("\n" + "=" * 80)
        logger.info("🚀 INICIANDO VALIDAÇÃO COMPLETA")
        logger.info("=" * 80)

        # 1. Estrutura de arquivos
        self.validate_file_structure()

        # 2. Imports
        self.validate_imports()

        # 3. Configurações
        self.validate_configurations()

        # 4-8. Testes funcionais
        self.test_feature_cache()
        self.test_feature_selector()
        self.test_alert_manager()
        self.test_monitoring()
        self.test_gradient_checkpointing()

        # Gerar relatório final
        return self.generate_report()

    def generate_report(self):
        """Gera relatório final"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 RELATÓRIO FINAL DE VALIDAÇÃO")
        logger.info("=" * 80)

        total = self.results["total_tests"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        warnings = self.results["warnings"]

        success_rate = (passed / total * 100) if total > 0 else 0

        logger.info(f"\nTotal de testes: {total}")
        logger.info(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
        logger.info(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        logger.info(f"⚠️  Warnings: {warnings} ({warnings/total*100:.1f}%)")

        logger.info(f"\n🎯 Taxa de sucesso: {success_rate:.1f}%")

        if failed == 0:
            logger.info("\n✅ VALIDAÇÃO COMPLETA COM SUCESSO!")
            logger.info("Todas as features estão funcionais.")
        else:
            logger.warning(f"\n⚠️  VALIDAÇÃO INCOMPLETA: {failed} testes falharam")
            logger.warning("Verifique os logs acima para detalhes.")

        # Salvar relatório JSON
        report_path = self.project_root / "reports" / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"\n📄 Relatório salvo em: {report_path}")

        return self.results


def main():
    """Main function"""
    validator = FeatureValidator()
    results = validator.run_all_validations()

    # Exit code baseado em falhas
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
