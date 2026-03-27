#!/usr/bin/env python3
"""
Auto Train Pipeline - 100% Automático
Pipeline completo de treino sem intervenção manual

Features:
- Leitura automática do catálogo Lightroom
- Extração de dataset
- Análise de qualidade
- Seleção automática de hiperparâmetros
- Feature selection
- Treino com todas as otimizações
- Validação e métricas
- Relatórios completos

Uso:
    python scripts/auto_train.py
    python scripts/auto_train.py --catalog /path/to/catalog.lrcat
    python scripts/auto_train.py --quick  # Modo rápido (menos epochs)

Data: 21 Novembro 2025
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
import json

# Adicionar project root ao path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / 'logs' / f'auto_train_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class AutoTrainPipeline:
    """
    Pipeline 100% automático de treino

    Executa todas as etapas desde a leitura do catálogo até o treino final
    """

    def __init__(
        self,
        catalog_path: str = None,
        quick_mode: bool = False,
        skip_quality_check: bool = False,
        force_retrain: bool = False
    ):
        """
        Args:
            catalog_path: Path do catálogo Lightroom (None=usa default)
            quick_mode: Modo rápido com menos epochs
            skip_quality_check: Pula análise de qualidade
            force_retrain: Força re-treino mesmo se modelos existem
        """
        self.catalog_path = catalog_path
        self.quick_mode = quick_mode
        self.skip_quality_check = skip_quality_check
        self.force_retrain = force_retrain

        # Paths
        self.project_root = PROJECT_ROOT
        self.data_dir = self.project_root / "data"
        self.models_dir = self.project_root / "models"
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Config
        self.config = {}
        self.results = {
            "start_time": datetime.now().isoformat(),
            "steps": []
        }

        logger.info("=" * 80)
        logger.info("AUTO TRAIN PIPELINE - 100% AUTOMÁTICO")
        logger.info("=" * 80)
        logger.info(f"Quick mode: {quick_mode}")
        logger.info(f"Skip quality check: {skip_quality_check}")
        logger.info(f"Force retrain: {force_retrain}")

    def step_1_find_catalog(self) -> str:
        """
        Step 1: Encontrar catálogo Lightroom

        Returns:
            Path do catálogo
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Encontrar Catálogo Lightroom")
        logger.info("=" * 80)

        if self.catalog_path:
            catalog = Path(self.catalog_path)
            if not catalog.exists():
                raise FileNotFoundError(f"Catálogo não encontrado: {catalog}")
        else:
            # Tentar encontrar automaticamente
            default_locations = [
                Path.home() / "Pictures" / "Lightroom" / "Lightroom Catalog.lrcat",
                Path.home() / "Imagens" / "Lightroom" / "Lightroom Catalog.lrcat",
                self.data_dir / "lightroom_catalog.lrcat"
            ]

            catalog = None
            for loc in default_locations:
                if loc.exists():
                    catalog = loc
                    break

            if catalog is None:
                raise FileNotFoundError(
                    "Catálogo Lightroom não encontrado. "
                    "Especifique com --catalog /path/to/catalog.lrcat"
                )

        logger.info(f"✓ Catálogo encontrado: {catalog}")
        self.results["steps"].append({"step": 1, "catalog": str(catalog), "status": "success"})
        return str(catalog)

    def step_2_extract_dataset(self, catalog_path: str) -> Path:
        """
        Step 2: Extrair dataset do catálogo

        Args:
            catalog_path: Path do catálogo

        Returns:
            Path do dataset CSV
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Extrair Dataset do Catálogo")
        logger.info("=" * 80)

        from services.ai_core.lightroom_extractor import LightroomCatalogExtractor

        output_csv = self.data_dir / "lightroom_dataset.csv"

        # Extrair
        extractor = LightroomCatalogExtractor(Path(catalog_path))
        df = extractor.create_dataset(
            output_path=str(output_csv),
            min_rating=3  # Apenas fotos com rating >= 3
        )

        logger.info(f"✓ Dataset extraído: {len(df)} fotos")
        logger.info(f"✓ Salvo em: {output_csv}")

        self.results["steps"].append({
            "step": 2,
            "num_photos": len(df),
            "output": str(output_csv),
            "status": "success"
        })

        return output_csv

    def step_3_analyze_quality(self, dataset_path: Path) -> dict:
        """
        Step 3: Analisar qualidade do dataset

        Args:
            dataset_path: Path do dataset

        Returns:
            Report de qualidade
        """
        if self.skip_quality_check:
            logger.info("\n⚠️  Pulando análise de qualidade (--skip-quality-check)")
            return {"skipped": True}

        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Analisar Qualidade do Dataset")
        logger.info("=" * 80)

        from services.dataset_quality_analyzer import DatasetQualityAnalyzer

        analyzer = DatasetQualityAnalyzer(str(dataset_path))
        result = analyzer.analyze()

        logger.info(f"✓ Score de qualidade: {result['score']:.1f}/100")
        logger.info(f"✓ Grade: {result['grade']}")

        if result['issues']:
            logger.warning(f"⚠️  Issues encontrados:")
            for issue in result['issues'][:5]:
                logger.warning(f"   - {issue}")

        # Salvar report
        report_path = self.reports_dir / "dataset_quality.json"
        with open(report_path, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"✓ Report salvo em: {report_path}")

        self.results["steps"].append({
            "step": 3,
            "score": result['score'],
            "grade": result['grade'],
            "num_issues": len(result['issues']),
            "status": "success" if result['score'] >= 60 else "warning"
        })

        # Alertar se qualidade baixa
        if result['score'] < 40:
            logger.error("❌ Qualidade do dataset MUITO BAIXA! Considere melhorar antes de treinar.")
            if not self.force_retrain:
                raise ValueError("Dataset quality too low. Use --force to override.")
        elif result['score'] < 60:
            logger.warning("⚠️  Qualidade do dataset baixa. Resultados podem não ser ótimos.")

        return result

    def step_4_configure_training(self, dataset_path: Path, quality_report: dict):
        """
        Step 4: Configurar hiperparâmetros de treino

        Args:
            dataset_path: Path do dataset
            quality_report: Report de qualidade
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Configurar Hiperparâmetros de Treino")
        logger.info("=" * 80)

        from services.auto_hyperparameter_selector import AutoHyperparameterSelector

        # Selecionar hiperparâmetros
        selector = AutoHyperparameterSelector(str(dataset_path))
        classifier_result = selector.select_hyperparameters(model_type="classifier")
        regressor_result = selector.select_hyperparameters(model_type="regressor")

        self.config = {
            "classifier": classifier_result['hyperparameters'],
            "regressor": regressor_result['hyperparameters'],
            "reasoning": {
                "classifier": classifier_result['reasoning'],
                "regressor": regressor_result['reasoning']
            }
        }

        # Ajustar para quick mode
        if self.quick_mode:
            logger.info("⚡ Quick mode: Reduzindo epochs")
            self.config["classifier"]["epochs"] = max(10, self.config["classifier"]["epochs"] // 3)
            self.config["regressor"]["epochs"] = max(10, self.config["regressor"]["epochs"] // 3)

        logger.info(f"✓ Classifier epochs: {self.config['classifier']['epochs']}")
        logger.info(f"✓ Classifier LR: {self.config['classifier']['learning_rate']:.2e}")
        logger.info(f"✓ Regressor epochs: {self.config['regressor']['epochs']}")
        logger.info(f"✓ Regressor LR: {self.config['regressor']['learning_rate']:.2e}")

        # Salvar config
        config_path = self.reports_dir / "training_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"✓ Config salva em: {config_path}")

        self.results["steps"].append({
            "step": 4,
            "config": self.config,
            "status": "success"
        })

    def step_5_train_models(self):
        """
        Step 5: Treinar modelos

        Executa train_models_v2.py com todas as otimizações
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Treinar Modelos")
        logger.info("=" * 80)

        # Importar e executar treino
        sys.path.insert(0, str(self.project_root / "train"))
        from train.train_models_v2 import main as train_main

        logger.info("Iniciando treino com todas as otimizações ativadas...")
        logger.info("   ✓ Parallel feature extraction")
        logger.info("   ✓ Feature selection")
        logger.info("   ✓ Progressive training")
        logger.info("   ✓ Mixed precision")
        logger.info("   ✓ Auto hyperparameters")

        # Executar treino
        try:
            train_main()
            logger.info("✓ Treino completo!")

            self.results["steps"].append({
                "step": 5,
                "status": "success"
            })

        except Exception as e:
            logger.error(f"❌ Erro no treino: {e}")
            self.results["steps"].append({
                "step": 5,
                "error": str(e),
                "status": "failed"
            })
            raise

    def step_6_validate_models(self):
        """
        Step 6: Validar modelos treinados

        Verifica se os modelos foram criados e estão funcionando
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 6: Validar Modelos")
        logger.info("=" * 80)

        # Verificar se modelos existem
        required_models = [
            "best_preset_classifier.pth",
            "best_refinement_model.pth",
            "scaler_stat.pkl",
            "scaler_deep.pkl",
            "scaler_deltas.pkl"
        ]

        missing = []
        for model_file in required_models:
            model_path = self.models_dir / model_file
            if not model_path.exists():
                missing.append(model_file)

        if missing:
            logger.error(f"❌ Modelos em falta: {missing}")
            self.results["steps"].append({
                "step": 6,
                "missing_models": missing,
                "status": "failed"
            })
            raise FileNotFoundError(f"Missing models: {missing}")

        logger.info("✓ Todos os modelos encontrados")

        # Tentar carregar predictor
        try:
            from services.ai_core.predictor import LightroomAIPredictor

            predictor = LightroomAIPredictor(
                classifier_path=self.models_dir / "best_preset_classifier.pth",
                refinement_path=self.models_dir / "best_refinement_model.pth",
                preset_centers=self.models_dir / "preset_centers.json",
                scaler_stat=self.models_dir / "scaler_stat.pkl",
                scaler_deep=self.models_dir / "scaler_deep.pkl",
                scaler_deltas=self.models_dir / "scaler_deltas.pkl",
                delta_columns=self.models_dir / "delta_columns.json"
            )

            logger.info("✓ Predictor carregado com sucesso")

            self.results["steps"].append({
                "step": 6,
                "status": "success"
            })

        except Exception as e:
            logger.error(f"❌ Erro ao carregar predictor: {e}")
            self.results["steps"].append({
                "step": 6,
                "error": str(e),
                "status": "failed"
            })
            raise

    def step_7_generate_report(self):
        """
        Step 7: Gerar relatório final
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 7: Gerar Relatório Final")
        logger.info("=" * 80)

        self.results["end_time"] = datetime.now().isoformat()

        # Calcular duração
        start = datetime.fromisoformat(self.results["start_time"])
        end = datetime.fromisoformat(self.results["end_time"])
        duration_seconds = (end - start).total_seconds()

        self.results["duration_seconds"] = duration_seconds
        self.results["duration_human"] = f"{duration_seconds // 60:.0f}m {duration_seconds % 60:.0f}s"

        # Status final
        failed_steps = [s for s in self.results["steps"] if s.get("status") == "failed"]
        self.results["success"] = len(failed_steps) == 0

        # Salvar relatório
        report_path = self.reports_dir / f"auto_train_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"✓ Relatório salvo em: {report_path}")

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("RESUMO DO PIPELINE")
        logger.info("=" * 80)
        logger.info(f"Status: {'✓ SUCCESS' if self.results['success'] else '❌ FAILED'}")
        logger.info(f"Duração: {self.results['duration_human']}")
        logger.info(f"Steps completados: {len([s for s in self.results['steps'] if s.get('status') == 'success'])}/{len(self.results['steps'])}")

        if failed_steps:
            logger.error("\n❌ Steps falhados:")
            for step in failed_steps:
                logger.error(f"   Step {step['step']}: {step.get('error', 'Unknown error')}")

        logger.info("=" * 80)

        return self.results

    def run(self) -> dict:
        """
        Executa pipeline completo

        Returns:
            Dict com resultados
        """
        try:
            # Step 1: Encontrar catálogo
            catalog_path = self.step_1_find_catalog()

            # Step 2: Extrair dataset
            dataset_path = self.step_2_extract_dataset(catalog_path)

            # Step 3: Analisar qualidade
            quality_report = self.step_3_analyze_quality(dataset_path)

            # Step 4: Configurar treino
            self.step_4_configure_training(dataset_path, quality_report)

            # Step 5: Treinar modelos
            self.step_5_train_models()

            # Step 6: Validar modelos
            self.step_6_validate_models()

            # Step 7: Gerar relatório
            return self.step_7_generate_report()

        except Exception as e:
            logger.error(f"\n❌ PIPELINE FALHOU: {e}")
            self.results["error"] = str(e)
            self.results["success"] = False
            return self.results


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Auto Train Pipeline - 100% Automático",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s                                    # Modo normal (automático)
  %(prog)s --quick                            # Modo rápido (menos epochs)
  %(prog)s --catalog /path/to/catalog.lrcat   # Catálogo específico
  %(prog)s --force                            # Força re-treino mesmo se modelos existem
  %(prog)s --skip-quality-check               # Pula análise de qualidade
        """
    )

    parser.add_argument(
        "--catalog",
        type=str,
        help="Path do catálogo Lightroom (.lrcat)"
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Modo rápido (reduz epochs para 1/3)"
    )

    parser.add_argument(
        "--skip-quality-check",
        action="store_true",
        help="Pula análise de qualidade do dataset"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Força re-treino mesmo se modelos já existem"
    )

    args = parser.parse_args()

    # Criar e executar pipeline
    pipeline = AutoTrainPipeline(
        catalog_path=args.catalog,
        quick_mode=args.quick,
        skip_quality_check=args.skip_quality_check,
        force_retrain=args.force
    )

    results = pipeline.run()

    # Exit code
    sys.exit(0 if results.get("success") else 1)


if __name__ == "__main__":
    main()
