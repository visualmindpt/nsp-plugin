# Treino Incremental Simples - Guia de Uso

## O que faz este script?

O `train_simple.py` permite treinar o modelo NSP Plugin de forma **incremental** e **simples**.

**Incremental** significa que cada vez que treinas com um novo catálogo, o modelo:
- ✅ **APRENDE** os novos estilos e ajustes
- ✅ **MANTÉM** todo o conhecimento anterior
- ✅ **NUNCA PERDE** o que já aprendeu

## Requisitos

Antes de treinar, certifica-te que:

1. ✅ Tens fotos editadas no Lightroom
2. ✅ As fotos têm ajustes/presets aplicados
3. ✅ As fotos têm rating de **3-5 estrelas** (importante!)
4. ✅ O ambiente virtual está ativo: `source venv/bin/activate`

## Uso Básico

### Treinar com 1 catálogo:
```bash
python3 train_simple.py /caminho/para/catalog.lrcat
```

### Treinar com múltiplos catálogos:
```bash
python3 train_simple.py catalog1.lrcat catalog2.lrcat catalog3.lrcat
```

## Workflow Típico

### Primeiro Treino (início):
```bash
# Treina com as primeiras fotos editadas
python3 train_simple.py ~/Lightroom/Catalogos/2024-Inverno.lrcat
```

### Adicionar mais conhecimento (semana seguinte):
```bash
# Adiciona novo catálogo - modelo aprende SEM perder o anterior!
python3 train_simple.py ~/Lightroom/Catalogos/2024-Primavera.lrcat
```

### Adicionar ainda mais (mês seguinte):
```bash
# Continua a adicionar conhecimento incrementalmente
python3 train_simple.py ~/Lightroom/Catalogos/2024-Verao.lrcat
```

## O que acontece durante o treino?

1. **Validação**: Verifica se o catálogo existe e tem fotos com rating ≥3
2. **Extração**: Extrai ajustes das fotos (Exposição, Contraste, Temperatura, etc.)
3. **Treino Incremental**:
   - Se existirem modelos anteriores: **adiciona** conhecimento novo
   - Se for a primeira vez: treina do zero
4. **Guardado**: Modelos atualizados em `models/`

## Após o Treino

Depois de treinar com sucesso, **reinicia o servidor** para carregar os novos modelos:

```bash
./start_server.sh
```

## Dicas Importantes

### Ratings no Lightroom
O script **só usa fotos com 3-5 estrelas**. Porquê?
- ⭐⭐⭐ (3 estrelas) = Foto boa, ajuste OK
- ⭐⭐⭐⭐ (4 estrelas) = Foto muito boa, ajuste excelente
- ⭐⭐⭐⭐⭐ (5 estrelas) = Foto perfeita, ajuste perfeito

Fotos sem rating ou com 1-2 estrelas são ignoradas (geralmente são fotos não editadas ou descartadas).

### Quantas fotos preciso?
- **30-50 fotos**: Treino inicial funciona, mas modelo ainda está a aprender
- **100-200 fotos**: Modelo começa a dar bons resultados
- **300-500 fotos**: Modelo maduro, resultados excelentes
- **500+ fotos**: Modelo profissional, resultados consistentes

### Treino Incremental vs Do Zero
- **Incremental** (padrão): Adiciona conhecimento ao modelo existente
  - Usa quando já tens modelo treinado e queres adicionar novos estilos
  - Mais rápido (30 epochs classifier, 50 epochs refiner)

- **Do Zero** (primeira vez): Treina modelo completamente novo
  - Usa quando não tens modelos anteriores
  - Mais lento mas necessário na primeira vez

O script **deteta automaticamente** qual usar!

## Resolução de Problemas

### "Nenhuma foto com rating ≥3 encontrada"
**Solução**: No Lightroom, seleciona as fotos editadas e atribui-lhes 3-5 estrelas

### "Erro ao importar módulos"
**Solução**:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Catálogo não encontrado"
**Solução**: Verifica que o caminho está correto e o ficheiro tem extensão `.lrcat`

### Treino muito lento
**Solução**: Normal! Treino demora tempo (15-30 min por catálogo dependendo do número de fotos)

## Estrutura de Ficheiros

Após treinar, terás:

```
models/
├── best_preset_classifier_v2.pth  # Modelo que classifica presets
├── best_refinement_model_v2.pth   # Modelo que ajusta parâmetros
├── scaler_*.pkl                    # Scalers para normalização
├── preset_centers.json             # Centros dos presets identificados
├── delta_columns.json              # Colunas de ajustes
└── training_history.json           # Histórico completo de treinos

data/
└── lightroom_dataset_*.csv         # Datasets extraídos
```

## Exemplos Práticos

### Fotógrafo de Casamentos
```bash
# Treina com catálogo de casamentos do Inverno
python3 train_simple.py ~/LR/Casamentos-Inverno-2024.lrcat

# Mais tarde, adiciona casamentos da Primavera
python3 train_simple.py ~/LR/Casamentos-Primavera-2024.lrcat

# Modelo agora sabe ajustar fotos de casamento em diferentes estações!
```

### Fotógrafo de Paisagens
```bash
# Treina com paisagens montanhosas
python3 train_simple.py ~/LR/Paisagens-Montanha.lrcat

# Adiciona paisagens costeiras
python3 train_simple.py ~/LR/Paisagens-Costa.lrcat

# Modelo aprende ambos os estilos!
```

## Suporte

Se encontrares problemas, verifica:
1. Logs durante o treino (o script mostra tudo no terminal)
2. Ficheiro `training_history.json` para histórico
3. Se o servidor está parado durante o treino (fecha-o com Ctrl+C)

---

**Regra de Ouro**: Cada vez que tens fotos novas editadas, corre o script! O modelo só melhora. 🚀
