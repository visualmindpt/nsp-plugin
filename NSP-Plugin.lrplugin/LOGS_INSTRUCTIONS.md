# NSP Plugin - Instruções para Visualizar Logs

## Localização dos Logs do Lightroom Classic

O Lightroom Classic grava logs do plugin em ficheiros de texto que podem ser acedidos de várias formas.

### Método 1: Via Interface do Lightroom (MAIS FÁCIL)

1. Abrir Lightroom Classic
2. Menu: `File > Plugin Manager` (ou `Ficheiro > Gestor de Plug-ins`)
3. Selecionar "NSP Plugin" na lista
4. Clicar no botão **"View Log File"** ou **"Ver Ficheiro de Log"**
5. O ficheiro de log abrirá automaticamente no editor de texto padrão

### Método 2: Localização Manual no macOS

Os logs do Lightroom estão geralmente em:

```
~/Library/Logs/Adobe/Lightroom Classic/
```

Ou seja:
```
/Users/[SEU_NOME]/Library/Logs/Adobe/Lightroom Classic/
```

**NOTA:** A pasta `Library` pode estar oculta. Para aceder:

1. No Finder, pressionar `Cmd + Shift + G` (Go to Folder)
2. Colar o caminho: `~/Library/Logs/Adobe/Lightroom Classic/`
3. Pressionar Enter

### Método 3: Via Terminal (para desenvolvimento)

#### Ver logs em tempo real (tail -f)

```bash
# Ver todos os logs do Lightroom em tempo real
tail -f ~/Library/Logs/Adobe/Lightroom\ Classic/*.log

# Filtrar apenas logs do NSP Plugin
tail -f ~/Library/Logs/Adobe/Lightroom\ Classic/*.log | grep -i "NSPPlugin"
```

#### Procurar por texto específico nos logs

```bash
# Procurar por "NSPPlugin" em todos os logs
grep -r "NSPPlugin" ~/Library/Logs/Adobe/Lightroom\ Classic/

# Procurar por erros do plugin
grep -r "NSPPlugin.*ERROR" ~/Library/Logs/Adobe/Lightroom\ Classic/

# Procurar por warnings
grep -r "NSPPlugin.*WARN" ~/Library/Logs/Adobe/Lightroom\ Classic/
```

#### Ver últimas 100 linhas de logs

```bash
# Ver últimas 100 linhas
tail -100 ~/Library/Logs/Adobe/Lightroom\ Classic/*.log

# Ver últimas 100 linhas do NSP Plugin
tail -100 ~/Library/Logs/Adobe/Lightroom\ Classic/*.log | grep -i "NSPPlugin"
```

## Identificadores de Log do Plugin

O NSP Plugin usa os seguintes identificadores nos logs:

- `NSPPlugin.CommonV2` - Funções comuns, servidor, HTTP, mapeamento de sliders
- `NSPPlugin.ApplyAIPresetV2` - Aplicação de presets AI
- `NSPPlugin.StartServer` - Inicialização do servidor FastAPI
- `NSPPlugin.ShowStats` - Estatísticas de feedback
- `NSPPlugin.Settings` - Configurações do plugin

## Exemplos de Comandos Úteis

### Ver apenas logs de hoje

```bash
# macOS
grep "$(date '+%Y-%m-%d')" ~/Library/Logs/Adobe/Lightroom\ Classic/*.log | grep NSPPlugin
```

### Ver logs de build_develop_settings (mapeamento de sliders)

```bash
grep "build_develop_settings" ~/Library/Logs/Adobe/Lightroom\ Classic/*.log
```

### Ver logs de predições AI

```bash
grep "predict_v2\|Predição\|SLIDERS RECEBIDOS" ~/Library/Logs/Adobe/Lightroom\ Classic/*.log
```

### Ver apenas erros críticos

```bash
grep -E "ERROR|CRÍTICO|FATAL" ~/Library/Logs/Adobe/Lightroom\ Classic/*.log | grep NSPPlugin
```

## Console.app (macOS)

O Console.app **NÃO** mostra logs do Lightroom por defeito, pois o Lightroom usa `LrLogger` que grava em ficheiros, não no sistema de logs unificado do macOS.

**NOTA:** Se quiser ver logs em tempo real durante o desenvolvimento:

1. Abrir Terminal
2. Executar: `tail -f ~/Library/Logs/Adobe/Lightroom\ Classic/*.log`
3. Manter a janela aberta enquanto testa o plugin no Lightroom

## Estrutura dos Logs do Plugin

Os logs seguem este formato:

```
2025-11-14 15:30:45 [NSPPlugin.CommonV2] INFO: build_develop_settings: ENTRADA
2025-11-14 15:30:45 [NSPPlugin.CommonV2] INFO:    → Tipo de sliders_dict: table
2025-11-14 15:30:45 [NSPPlugin.CommonV2] INFO: ━━━ SLIDERS RECEBIDOS DO SERVIDOR ━━━
2025-11-14 15:30:45 [NSPPlugin.CommonV2] INFO:    [01] Python: exposure                     = 0.5
2025-11-14 15:30:45 [NSPPlugin.CommonV2] INFO:    ✅ Mapeado: exposure → Exposure2012 = 0.5
```

## Níveis de Log

- `TRACE` - Informação muito detalhada (depuração profunda)
- `INFO` - Informação normal de operação
- `WARN` - Avisos (não impedem execução)
- `ERROR` - Erros que impedem operação

## Limpeza de Logs

Para limpar logs antigos:

```bash
# Ver tamanho dos logs
du -sh ~/Library/Logs/Adobe/Lightroom\ Classic/

# Apagar logs mais antigos que 7 dias
find ~/Library/Logs/Adobe/Lightroom\ Classic/ -name "*.log" -mtime +7 -delete
```

## Problemas Comuns

### "Não vejo logs do NSP Plugin"

1. Verificar que o plugin está ativado no Plugin Manager
2. Executar qualquer função do plugin (Apply AI Preset, etc.)
3. Verificar novamente os logs

### "Logs muito grandes"

O Lightroom rotaciona logs automaticamente. Se os logs ficarem muito grandes:

1. Fechar Lightroom
2. Apagar ficheiros `.log` antigos
3. Reiniciar Lightroom

### "Quero logs mais detalhados"

Todos os loggers do plugin já estão configurados com `logger:enable("logfile")`, que é o nível máximo de detalhe disponível no Lightroom SDK.

## Contacto

Para reportar problemas com logs ou questões técnicas, incluir sempre:

1. Versão do Lightroom Classic
2. macOS version
3. Últimas 50 linhas dos logs: `tail -50 ~/Library/Logs/Adobe/Lightroom\ Classic/*.log | grep NSPPlugin`
