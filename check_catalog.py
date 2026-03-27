#!/usr/bin/env python3
"""
Script de diagnóstico para verificar quantas fotos são realmente usáveis para treino.
"""

import sys
from pathlib import Path
import pandas as pd

if len(sys.argv) < 2:
    print("Uso: python3 check_catalog.py /caminho/para/catalog.lrcat")
    sys.exit(1)

catalog_path = sys.argv[1]

print("=" * 70)
print("🔍 DIAGNÓSTICO DO CATÁLOGO LIGHTROOM")
print("=" * 70)
print(f"📁 Catálogo: {Path(catalog_path).name}")
print()

from services.ai_core.lightroom_extractor import LightroomCatalogExtractor

try:
    extractor = LightroomCatalogExtractor(Path(catalog_path))

    # Extrair com diferentes ratings (usando extract_edits apenas para contar)
    print("📊 Análise por Rating:")
    print("-" * 70)

    for rating in [0, 1, 2, 3, 4, 5]:
        try:
            df = extractor.extract_edits(min_rating=rating)
            count = len(df)
            print(f"   {'⭐' * rating if rating > 0 else 'Sem rating':<20} Rating ≥{rating}: {count:>4} fotos")
        except Exception as e:
            print(f"   {'⭐' * rating if rating > 0 else 'Sem rating':<20} Rating ≥{rating}: ERRO - {e}")

    print()
    print("⏳ A parsear ajustes do XMP (pode demorar)...")
    print()

    print()
    print("=" * 70)
    print("🎯 FOTOS USÁVEIS PARA TREINO (Rating ≥3):")
    print("=" * 70)

    # Usar create_dataset() que parseia o XMP e extrai todos os ajustes!
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        df_usable = extractor.create_dataset(output_path=tmp_path, min_rating=3)
    finally:
        # Limpar ficheiro temporário
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # DEBUG: Mostrar que colunas foram extraídas
    print("🔍 DEBUG - Colunas extraídas:")
    print("-" * 70)
    print(f"   Total de colunas: {len(df_usable.columns)}")
    print(f"   Colunas: {list(df_usable.columns)}")
    print()

    # DEBUG: Mostrar primeiras linhas
    if len(df_usable) > 0:
        print("📸 DEBUG - Primeiras 3 fotos (sample):")
        print("-" * 70)
        print(df_usable.head(3))
        print()

    if len(df_usable) == 0:
        print("❌ PROBLEMA: Nenhuma foto com rating ≥3 encontrada!")
        print()
        print("💡 SOLUÇÃO:")
        print("   1. Abre o catálogo no Lightroom")
        print("   2. Seleciona fotos editadas que gostas")
        print("   3. Atribui rating de 3-5 estrelas (tecla 3, 4 ou 5)")
        print("   4. Tenta treinar novamente")
    else:
        print(f"✅ Total de fotos usáveis: {len(df_usable)}")
        print()

        # Analisar ajustes
        print("📈 Análise de Ajustes:")
        print("-" * 70)

        # Verificar se há ajustes válidos - só colunas numéricas
        numeric_cols = df_usable.select_dtypes(include=['float64', 'int64']).columns
        adjustment_columns = [col for col in numeric_cols if col not in ['rating', 'preset_cluster']]

        if adjustment_columns:
            try:
                # Converter para numérico forçadamente
                df_numeric = df_usable[adjustment_columns].apply(pd.to_numeric, errors='coerce')
                # Calcular quantas fotos têm ajustes não-zero
                has_adjustments = (df_numeric.abs() > 0.01).any(axis=1)
                with_adjustments = has_adjustments.sum()
                without_adjustments = (~has_adjustments).sum()

                print(f"   Com ajustes aplicados:    {with_adjustments:>4} fotos")
                print(f"   Sem ajustes (zeros):      {without_adjustments:>4} fotos")
                print()

                if with_adjustments < 10:
                    print("⚠️  AVISO: Poucas fotos com ajustes!")
                    print("   Recomendado: 30-50 fotos editadas")
            except Exception as e:
                print(f"   ⚠️  Erro ao analisar ajustes: {e}")
        else:
            print("   ⚠️  Nenhuma coluna de ajustes numérica encontrada")

        # Verificar diversidade de ajustes
        print()
        print("🎨 Análise de Diversidade:")
        print("-" * 70)

        # Calcular variância dos ajustes
        if adjustment_columns:
            try:
                df_numeric = df_usable[adjustment_columns].apply(pd.to_numeric, errors='coerce')
                variance = df_numeric.var().mean()
                print(f"   Variância média dos ajustes: {variance:.4f}")

                if variance < 0.001:
                    print("   ⚠️  BAIXA: Todas as fotos têm ajustes muito similares")
                    print("   💡 Adiciona mais fotos com estilos ligeiramente diferentes")
                elif variance < 0.01:
                    print("   ⚙️  MODERADA: Alguma variação presente")
                else:
                    print("   ✅ BOA: Boa diversidade de ajustes")
            except Exception as e:
                print(f"   ⚠️  Erro ao calcular variância: {e}")
        else:
            print("   ⚠️  Não foi possível calcular variância")

        print()
        print("=" * 70)
        print("📋 RESUMO:")
        print("=" * 70)

        if len(df_usable) < 20:
            print(f"❌ Poucas fotos ({len(df_usable)}) - Adiciona mais!")
            print("   Mínimo: 20 fotos | Recomendado: 50-100 fotos")
        elif len(df_usable) < 50:
            print(f"⚠️  Suficiente mas limitado ({len(df_usable)} fotos)")
            print("   Recomendado: 50-100 fotos para melhores resultados")
        else:
            print(f"✅ Boa quantidade ({len(df_usable)} fotos)")

        print()

except Exception as e:
    print(f"❌ Erro ao processar catálogo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 70)
