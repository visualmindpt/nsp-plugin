#!/usr/bin/env python3
"""
Script para exportar modelos treinados do NSP Plugin.

Cria um pacote comprimido com todos os ficheiros necessários para
transferir o conhecimento do modelo para outro computador.

Uso:
    python3 export_models.py [--output caminho/para/export.zip]
"""

import sys
import zipfile
import json
from pathlib import Path
from datetime import datetime

def export_models(output_path=None):
    """Exporta todos os modelos e metadados necessários."""

    models_dir = Path('models')

    # Ficheiros essenciais (obrigatórios)
    essential_files = [
        'best_preset_classifier_v2.pth',
        'best_refinement_model_v2.pth',
        'scaler_stat.pkl',
        'scaler_deep.pkl',
        'scaler_deltas.pkl',
        'preset_centers.json',
        'delta_columns.json',
    ]

    # Ficheiros opcionais (bom ter)
    optional_files = [
        'training_history.json',
    ]

    print("=" * 70)
    print("📦 NSP PLUGIN - EXPORTAÇÃO DE MODELOS")
    print("=" * 70)
    print()

    # Verificar ficheiros essenciais
    print("🔍 Verificando ficheiros essenciais...")
    missing_files = []
    existing_files = []

    for filename in essential_files:
        filepath = models_dir / filename
        if filepath.exists():
            size_kb = filepath.stat().st_size / 1024
            existing_files.append((filepath, size_kb))
            print(f"   ✅ {filename:<40} ({size_kb:>6.1f} KB)")
        else:
            missing_files.append(filename)
            print(f"   ❌ {filename:<40} (NÃO ENCONTRADO)")

    if missing_files:
        print()
        print("❌ ERRO: Ficheiros essenciais em falta!")
        print("   Treina os modelos primeiro antes de exportar.")
        print()
        print("   Ficheiros em falta:")
        for f in missing_files:
            print(f"   - {f}")
        return False

    # Ficheiros opcionais
    print()
    print("📋 Ficheiros opcionais:")
    for filename in optional_files:
        filepath = models_dir / filename
        if filepath.exists():
            size_kb = filepath.stat().st_size / 1024
            existing_files.append((filepath, size_kb))
            print(f"   ✅ {filename:<40} ({size_kb:>6.1f} KB)")
        else:
            print(f"   ⚪ {filename:<40} (não existe, ok)")

    # Calcular tamanho total
    total_size_kb = sum(size for _, size in existing_files)

    print()
    print("=" * 70)
    print(f"📊 TOTAL: {len(existing_files)} ficheiros, {total_size_kb:.1f} KB (~{total_size_kb/1024:.2f} MB)")
    print("=" * 70)
    print()

    # Determinar caminho de saída
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"nsp_models_{timestamp}.zip"

    output_path = Path(output_path)

    # Criar ZIP
    print(f"📦 Criando pacote: {output_path}")
    print()

    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filepath, size_kb in existing_files:
                arcname = filepath.name  # Nome dentro do ZIP
                zipf.write(filepath, arcname)
                print(f"   ➕ {arcname}")

            # Adicionar metadados do export
            export_info = {
                "export_date": datetime.now().isoformat(),
                "export_version": "1.0",
                "nsp_plugin_version": "2.0",
                "files_included": [f.name for f, _ in existing_files],
                "total_size_kb": total_size_kb,
            }

            # Tentar adicionar informação do histórico de treino
            history_path = models_dir / 'training_history.json'
            if history_path.exists():
                try:
                    with open(history_path, 'r') as f:
                        history = json.load(f)
                        export_info['training_stats'] = {
                            'total_images': history.get('total_images', 0),
                            'total_catalogs': history.get('total_catalogs', 0),
                            'style_model_version': history.get('style_model_version', 0),
                            'total_sessions': len(history.get('training_sessions', [])),
                        }
                except Exception as e:
                    print(f"   ⚠️  Aviso: Não foi possível ler histórico: {e}")

            # Adicionar README com instruções
            readme_content = f"""# NSP Plugin - Modelos Exportados

## Informação do Export

- **Data**: {export_info['export_date']}
- **Versão NSP Plugin**: {export_info['nsp_plugin_version']}
- **Ficheiros incluídos**: {len(existing_files)}
- **Tamanho total**: {total_size_kb:.1f} KB (~{total_size_kb/1024:.2f} MB)

## Estatísticas de Treino

- Total de imagens treinadas: {export_info.get('training_stats', {}).get('total_images', 'N/A')}
- Total de catálogos: {export_info.get('training_stats', {}).get('total_catalogs', 'N/A')}
- Versão do modelo: V{export_info.get('training_stats', {}).get('style_model_version', 'N/A')}
- Sessões de treino: {export_info.get('training_stats', {}).get('total_sessions', 'N/A')}

## Como Importar

### 1. Descompacta os ficheiros:
```bash
unzip {output_path.name}
```

### 2. Copia para a pasta models/ do outro computador:
```bash
cp *.pth *.pkl *.json /caminho/para/NSP_Plugin/models/
```

### 3. Reinicia o servidor no computador destino:
```bash
pkill -f "services/server.py"
./start_server.sh
```

### 4. Verifica que os modelos foram carregados:
```bash
curl http://127.0.0.1:5678/health
```

Deves ver: `{{"status":"ok","v2_predictor_loaded":true}}`

## Ficheiros Incluídos

{chr(10).join(f"- {f}" for f in export_info['files_included'])}

## Notas Importantes

- ✅ Estes modelos contêm TODO o conhecimento treinado
- ✅ Não é necessário retreinar no computador destino
- ✅ Podes usar imediatamente após copiar e reiniciar servidor
- ⚠️  Certifica-te que a versão do NSP Plugin é compatível (2.0+)
- 💡 Podes continuar a treinar incrementalmente no computador destino

## Compatibilidade

- **NSP Plugin**: v2.0+
- **Python**: 3.8+
- **PyTorch**: 1.8+

---
Exportado automaticamente pelo NSP Plugin Export Tool
"""

            # Adicionar README ao ZIP
            zipf.writestr('README.md', readme_content)
            print(f"   ➕ README.md (instruções)")

            # Adicionar metadados JSON
            zipf.writestr('export_info.json', json.dumps(export_info, indent=2))
            print(f"   ➕ export_info.json (metadados)")

        # Verificar tamanho do ZIP
        zip_size_kb = output_path.stat().st_size / 1024
        compression_ratio = (1 - zip_size_kb / total_size_kb) * 100

        print()
        print("=" * 70)
        print("✅ EXPORT CONCLUÍDO COM SUCESSO!")
        print("=" * 70)
        print()
        print(f"📦 Pacote criado: {output_path}")
        print(f"📊 Tamanho original: {total_size_kb:.1f} KB")
        print(f"📦 Tamanho comprimido: {zip_size_kb:.1f} KB")
        print(f"🗜️  Compressão: {compression_ratio:.1f}%")
        print()
        print("🚀 PRÓXIMOS PASSOS:")
        print()
        print("1. Transfere o ficheiro para o outro computador:")
        print(f"   scp {output_path} user@outro-pc:/caminho/destino/")
        print()
        print("2. No outro computador, descompacta:")
        print(f"   unzip {output_path.name}")
        print()
        print("3. Copia os ficheiros para models/:")
        print("   cp *.pth *.pkl *.json /caminho/NSP_Plugin/models/")
        print()
        print("4. Reinicia o servidor:")
        print("   ./start_server.sh")
        print()
        print("5. Verifica:")
        print("   curl http://127.0.0.1:5678/health")
        print()
        print("=" * 70)

        return True

    except Exception as e:
        print()
        print(f"❌ ERRO ao criar pacote: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Exportar modelos treinados do NSP Plugin")
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Caminho para o ficheiro ZIP de saída (default: nsp_models_TIMESTAMP.zip)'
    )

    args = parser.parse_args()

    success = export_models(args.output)
    sys.exit(0 if success else 1)
