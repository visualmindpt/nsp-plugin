# NSP Packaging Plan

## Objetivo
Gerar um bundle auto-contido (PyInstaller) e integrá-lo com a app Tauri para distribuição em `.dmg/.pkg` com paths previsíveis (`~/Library/Application Support/NSP`).

## Passos
1. **Congelar backend Python**
   - Script: `pyinstaller --onefile --name nsp-engine services/server.py`.
   - Incluir diretório `models/` como dados (`--add-data "models:models"`).
   - Gerar wrapper CLI `nsp-engine` que suporta `--config ~/.config/nsp/config.json`.
   - Antes de empacotar, gerar o manifesto com hashes: `python tools/model_manifest.py`. O resultado (`models/model_bundle.lock.json`) é utilizado pelo Control Center e pelos instaladores para validar versões.
2. **Atualizar Control Center**
   - Em vez de chamar `python -m uvicorn`, invocar `nsp-engine --serve`.
   - Adicionar verificação para instalar bundle se binário não existir.
3. **Plugin Lightroom**
   - `AUTO_START_SERVER_CMD = "/usr/bin/env bash -lc '$HOME/.local/bin/nsp-engine --serve'"`.
4. **Installer**
   - Atualizar `install/macos/install.sh` para copiar o binário PyInstaller em `~/Library/Application Support/NSP/bin`.
   - Opcional: criar `.pkg` com `pkgbuild` e `productsbuild`.

Esta base já permite correr os comandos localmente; quando o código estabilizar basta seguir os passos acima para gerar o executável e atualizar os scripts de arranque.

## Manifesto de modelos

O ficheiro `models/model_bundle.lock.json` funciona como lockfile do bundle. Para o gerar/validar:

```bash
# gerar (usa models/ e requirements por omissão)
python tools/model_manifest.py

# validar hashes antes do release ou arranque do servidor
python tools/model_manifest.py --verify
```

Qualquer alteração nos modelos ou requisitos obriga a regenerar o manifesto, garantindo que o PyInstaller e o Control Center só arrancam versões consistentes.
