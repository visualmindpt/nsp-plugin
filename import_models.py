#!/usr/bin/env python3
"""
Script para importar modelos exportados do NSP Plugin.

Descompacta e instala os modelos no diretório correto.

Uso:
    python3 import_models.py caminho/para/nsp_models.zip
"""

import sys
import zipfile
import json
import shutil
from pathlib import Path

def import_models(zip_path):
    """Importa modelos de um ficheiro ZIP exportado."""

    zip_path = Path(zip_path)
    models_dir = Path('models')

    print("=" * 70)
    print("📥 NSP PLUGIN - IMPORTAÇÃO DE MODELOS")
    print("=" * 70)
    print()

    # Verificar se o ZIP existe
    if not zip_path.exists():
        print(f"❌ ERRO: Ficheiro não encontrado: {zip_path}")
        return False

    print(f"📦 Pacote: {zip_path}")
    print(f"📊 Tamanho: {zip_path.stat().st_size / 1024:.1f} KB")
    print()

    # Criar pasta models se não existir
    models_dir.mkdir(exist_ok=True)

    # Ler metadados do export
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Ler export_info.json se existir
            if 'export_info.json' in zipf.namelist():
                with zipf.open('export_info.json') as f:
                    export_info = json.load(f)

                print("📋 Informação do Export:")
                print(f"   Data: {export_info.get('export_date', 'N/A')}")
                print(f"   Versão: {export_info.get('nsp_plugin_version', 'N/A')}")

                if 'training_stats' in export_info:
                    stats = export_info['training_stats']
                    print()
                    print("📊 Estatísticas de Treino:")
                    print(f"   Imagens: {stats.get('total_images', 'N/A')}")
                    print(f"   Catálogos: {stats.get('total_catalogs', 'N/A')}")
                    print(f"   Versão do modelo: V{stats.get('style_model_version', 'N/A')}")
                    print(f"   Sessões: {stats.get('total_sessions', 'N/A')}")

                print()

            # Listar ficheiros a extrair
            model_files = [f for f in zipf.namelist()
                          if f.endswith(('.pth', '.pkl', '.json'))
                          and f != 'export_info.json']

            if not model_files:
                print("❌ ERRO: Nenhum ficheiro de modelo encontrado no ZIP!")
                return False

            print(f"🔍 Encontrados {len(model_files)} ficheiros:")
            for filename in model_files:
                print(f"   • {filename}")

            print()

            # Perguntar confirmação
            response = input("❓ Descompactar e copiar para models/? (s/N): ").strip().lower()

            if response not in ['s', 'sim', 'y', 'yes']:
                print("❌ Importação cancelada pelo utilizador.")
                return False

            print()
            print("📂 Extraindo ficheiros...")
            print()

            # Extrair ficheiros
            for filename in model_files:
                dest_path = models_dir / filename

                # Backup se já existir
                if dest_path.exists():
                    backup_path = dest_path.with_suffix(dest_path.suffix + '.backup')
                    shutil.copy2(dest_path, backup_path)
                    print(f"   💾 Backup: {filename} → {backup_path.name}")

                # Extrair
                zipf.extract(filename, models_dir)
                print(f"   ✅ {filename}")

    except Exception as e:
        print(f"❌ ERRO ao processar ZIP: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()
    print("=" * 70)
    print("✅ IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 70)
    print()
    print("🚀 PRÓXIMOS PASSOS:")
    print()
    print("1. Reinicia o servidor NSP:")
    print("   pkill -f 'services/server.py'")
    print("   ./start_server.sh")
    print()
    print("2. Verifica que os modelos foram carregados:")
    print("   curl http://127.0.0.1:5678/health")
    print()
    print("   Deves ver: {\"status\":\"ok\",\"v2_predictor_loaded\":true}")
    print()
    print("3. Reinicia o Lightroom para usar os novos modelos!")
    print()
    print("=" * 70)
    print()
    print("💡 DICA: Podes continuar a treinar incrementalmente!")
    print("   Os modelos importados são o ponto de partida.")
    print("   Adiciona mais catálogos com 'train_simple.py'")
    print()

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 import_models.py caminho/para/nsp_models.zip")
        sys.exit(1)

    zip_path = sys.argv[1]
    success = import_models(zip_path)
    sys.exit(0 if success else 1)
