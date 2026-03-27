#!/usr/bin/env python3
"""
Script SIMPLES de treino incremental para NSP Plugin.

Uso:
    python train_simple.py /path/to/catalog.lrcat
    python train_simple.py /path/to/catalog1.lrcat /path/to/catalog2.lrcat

O modelo aprende incrementalmente - nunca perde conhecimento anterior!
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        print("❌ Erro: Forneça pelo menos um catálogo Lightroom!")
        print("")
        print("Uso:")
        print("  python train_simple.py /path/to/catalog.lrcat")
        print("  python train_simple.py catalog1.lrcat catalog2.lrcat catalog3.lrcat")
        print("")
        sys.exit(1)

    catalogs = sys.argv[1:]

    # Validar que os catálogos existem
    for catalog in catalogs:
        if not Path(catalog).exists():
            logger.error(f"❌ Catálogo não encontrado: {catalog}")
            sys.exit(1)
        if not catalog.endswith('.lrcat'):
            logger.error(f"❌ Ficheiro não é um catálogo Lightroom (.lrcat): {catalog}")
            sys.exit(1)

    logger.info("=" * 70)
    logger.info("🚀 NSP Plugin - Treino Incremental SIMPLES")
    logger.info("=" * 70)
    logger.info(f"📁 Catálogos para processar: {len(catalogs)}")
    for i, cat in enumerate(catalogs, 1):
        logger.info(f"   {i}. {Path(cat).name}")
    logger.info("")

    # Importar módulos de treino
    try:
        from train.train_incremental_v2 import run_incremental_training_pipeline
        from services.ai_core.lightroom_extractor import LightroomCatalogExtractor
        logger.info("✅ Módulos de treino carregados")
    except ImportError as e:
        logger.error(f"❌ Erro ao importar módulos: {e}")
        logger.error("Execute: pip install -r requirements.txt")
        sys.exit(1)

    # Processar cada catálogo incrementalmente
    # Cada catálogo adiciona conhecimento ao modelo anterior

    total_success = 0
    total_errors = 0

    for i, catalog_path in enumerate(catalogs, 1):
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"📖 Catálogo {i}/{len(catalogs)}: {Path(catalog_path).name}")
        logger.info("=" * 70)

        # Verificar se há fotos válidas primeiro
        try:
            extractor = LightroomCatalogExtractor(catalog_path)
            photos = extractor.extract_photos_with_adjustments(min_rating=3)

            if not photos:
                logger.warning("")
                logger.warning(f"⚠️  Nenhuma foto com rating ≥3 encontrada")
                logger.warning(f"   Dica: Atribui estrelas (3-5) às fotos editadas no Lightroom")
                logger.warning("")
                total_errors += 1
                continue

            logger.info(f"✅ {len(photos)} fotos encontradas com ajustes")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Erro ao extrair dados: {e}")
            total_errors += 1
            continue

        # Treinar incrementalmente com este catálogo
        try:
            logger.info("🎯 A iniciar treino incremental...")
            logger.info("")

            result = run_incremental_training_pipeline(
                catalog_path=catalog_path,
                mode="incremental",  # Sempre incremental (adiciona ao modelo existente)
                num_presets=4,
                min_rating=3,
                classifier_epochs=30,
                refiner_epochs=50,
                batch_size=16,
                patience=10,
                freeze_base_layers=True,
                incremental_lr_factor=0.1
            )

            if result["success"]:
                logger.info("")
                logger.info(f"✅ Catálogo {i} treinado com sucesso!")
                total_success += 1
            else:
                logger.error(f"❌ Falha no treino do catálogo {i}: {result.get('error', 'Unknown')}")
                total_errors += 1

        except Exception as e:
            logger.error("")
            logger.error(f"❌ ERRO durante o treino do catálogo {i}:")
            logger.error(f"   {e}")
            logger.error("")
            import traceback
            traceback.print_exc()
            total_errors += 1
            continue

    # Resumo final
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 RESUMO FINAL")
    logger.info("=" * 70)
    logger.info(f"✅ Catálogos treinados com sucesso: {total_success}/{len(catalogs)}")
    if total_errors > 0:
        logger.info(f"❌ Catálogos com erros: {total_errors}/{len(catalogs)}")
    logger.info("")

    if total_success > 0:
        logger.info("=" * 70)
        logger.info("✅ TREINO INCREMENTAL CONCLUÍDO!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📊 Modelos atualizados em: models/")
        logger.info("   • best_preset_classifier_v2.pth")
        logger.info("   • best_refinement_model_v2.pth")
        logger.info("")
        logger.info("🔄 Para adicionar mais conhecimento:")
        logger.info("   python train_simple.py /path/to/novo_catalogo.lrcat")
        logger.info("")
        logger.info("🚀 Reinicia o servidor para usar os modelos atualizados:")
        logger.info("   ./start_server.sh")
        logger.info("")
    else:
        logger.error("")
        logger.error("❌ Nenhum catálogo foi treinado com sucesso!")
        logger.error("")
        logger.error("Verifica que os catálogos têm:")
        logger.error("  1. Fotos importadas no Lightroom")
        logger.error("  2. Com ajustes/presets aplicados")
        logger.error("  3. Com rating de 3-5 estrelas")
        logger.error("")
        sys.exit(1)


if __name__ == "__main__":
    main()
