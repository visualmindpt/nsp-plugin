# 🎓 Guia: Transfer Learning e Smart Culling na UI Gradio

**Data:** 16 Novembro 2025
**Status:** Production Ready

---

## ✅ O Que Foi Implementado?

Foram adicionadas **2 novas tabs** à UI Gradio (`train_ui_v2.py`):

1. **🎓 Tab 5: Transfer Learning** - Para treinar com datasets pequenos usando CLIP/DINOv2/ConvNeXt
2. **⭐ Tab 6: Smart Culling** - Para treinar modelo de avaliação automática de qualidade de fotos

Ambas as tabs incluem:
- ✅ Informação clara sobre quando usar
- ✅ Comparação de resultados esperados
- ✅ Configurações ajustáveis
- ✅ Logs em tempo real
- ✅ Download de logs
- ✅ Indicadores de status

---

## 🎓 Tab Transfer Learning - Como Usar

### Quando Usar?

**✅ USE Transfer Learning quando:**
- Tens **menos de 200 fotos** editadas
- Dataset muito pequeno (< 50 fotos) com **overfitting severo**
- Queres **80-85% accuracy com apenas 50 fotos**
- Precisas de treino **mais rápido** (15-30 min vs 1-2 horas)

**❌ NÃO USE quando:**
- Tens dataset grande (> 500 fotos bem balanceadas)
- Pipeline normal já dá bons resultados (> 75% accuracy)
- Não tens GPU (Transfer Learning é mais lento em CPU)

### Passos:

1. **Abrir UI Gradio:**
   ```bash
   ./start_train_ui.sh
   ```

2. **Ir para Tab "🎓 Transfer Learning"**

3. **Configurar:**
   - **Modelo Base**: CLIP (recomendado para datasets pequenos)
   - **Épocas**: 30-50 (suficiente com Transfer Learning)
   - **Batch Size**: 16 (reduza se tiver pouca memória GPU)
   - **Learning Rate**: 1e-3 (padrão funciona bem)
   - **Usar Atenção**: Sim (melhora accuracy)
   - **Paciência**: 10 (early stopping)

4. **Clicar "🚀 Iniciar Transfer Learning"**

5. **Acompanhar logs em tempo real**

6. **Resultado:**
   - Modelo salvo em `models/clip_preset_model.pth`
   - Accuracy esperada: **80-85% com 50 fotos** (vs ~45% sem Transfer Learning)

### Modelos Disponíveis:

| Modelo | Melhor Para | Dataset Mínimo | Accuracy Esperada | Velocidade |
|--------|-------------|----------------|-------------------|------------|
| **CLIP** | Compreensão semântica, estilos diversos | 50 fotos | 80-85% | Rápido |
| **DINOv2** | Qualidade técnica, detalhes | 75 fotos | 75-80% | Médio |
| **ConvNeXt** | Balanço entre os dois | 100 fotos | 78-83% | Lento |

💡 **Recomendação**: Comece com CLIP e 30 épocas.

---

## ⭐ Tab Smart Culling - Como Usar

### Quando Usar?

**✅ USE Smart Culling quando:**
- Tens **milhares de fotos** para selecionar
- Queres **automatizar a seleção inicial** de fotos
- Precisas de avaliar **qualidade técnica** (nitidez, exposição, composição)
- Queres **economizar tempo** na fase de culling

**❌ NÃO USE quando:**
- Tens poucas fotos (< 100)
- Queres avaliação subjetiva/artística pura
- Não tens exemplos de fotos boas/más no teu catálogo

### Opção 1: Dataset Lightroom (Recomendado se tens ratings)

**Requisitos:**
- 200+ fotos com ratings (⭐) no catálogo Lightroom

**Passos:**

1. **No Lightroom Classic:**
   - Avaliar fotos com ratings (⭐⭐⭐⭐⭐ = excelente, ⭐ = fraca)
   - Garantir que tens pelo menos 200 fotos avaliadas

2. **Na UI Gradio, Tab "⭐ Smart Culling":**
   - **Tipo de Dataset**: Lightroom
   - **Épocas**: 50-70
   - **Batch Size**: 32
   - **Learning Rate**: 1e-4
   - **Paciência**: 10

3. **Clicar "🚀 Iniciar Treino de Culling"**

4. **Resultado:**
   - Modelo salvo em `models/dinov2_culling_model.pth`
   - Accuracy esperada: **70-75%**
   - Tempo de treino: **30-60 minutos**

### Opção 2: Dataset AVA (Modelo genérico)

**Requisitos:**
- Nenhum! Usa dataset público

**Passos:**

1. **Na UI Gradio, Tab "⭐ Smart Culling":**
   - **Tipo de Dataset**: AVA
   - **Número de Imagens**: 1000 (≈ 2GB, suficiente para treino robusto)
   - **Clicar "📥 Fazer Download do AVA"**
   - **Aguardar download** (pode demorar 30-60 minutos)

2. **Após download:**
   - **Épocas**: 50-70
   - **Batch Size**: 32
   - **Learning Rate**: 1e-4
   - **Paciência**: 10

3. **Clicar "🚀 Iniciar Treino de Culling"**

4. **Resultado:**
   - Modelo salvo em `models/dinov2_culling_model.pth`
   - Accuracy esperada: **85%+**
   - Tempo de treino: **2-3 horas**

### Como Usar o Modelo Treinado:

Após o treino, o modelo será salvo em `models/dinov2_culling_model.pth`.

**Uso programático:**

```python
from services.culling import CullingPredictor

predictor = CullingPredictor()
score = predictor.predict_quality("path/to/image.jpg")

if score >= 0.9:
    print("⭐⭐⭐ Excelente!")
elif score >= 0.75:
    print("⭐⭐ Muito Boa")
elif score >= 0.6:
    print("⭐ Boa")
else:
    print("Razoável/Fraca")
```

💡 **Integração futura**: Este modelo será integrado no plugin Lightroom para culling automático.

---

## 🔧 Troubleshooting

### Erro: "Dataset não encontrado"

**Solução:**
1. Ir para Tab "🚀 Pipeline Completo" ou "🔧 Passo a Passo"
2. Executar "1️⃣ Extrair Dados do Catálogo"
3. Voltar à tab Transfer Learning/Culling

### Erro: "CLIP não disponível"

**Solução:**
```bash
pip install transformers torch torchvision timm
```

### Erro: "AVA dataset não encontrado"

**Solução:**
1. Na Tab "⭐ Smart Culling"
2. Selecionar "Tipo de Dataset: AVA"
3. Clicar "📥 Fazer Download do AVA"
4. Aguardar download completar

### Treino muito lento em CPU

**Solução:**
- Transfer Learning e Culling requerem GPU para performance ideal
- Em Mac M1/M2: Device automático é MPS (aceleração GPU)
- Em Windows/Linux: Device automático é CUDA (se disponível)
- Se só tens CPU: Considere usar pipeline normal em vez de Transfer Learning

---

## 📊 Comparação: Pipeline Normal vs Transfer Learning vs Culling

| Métrica | Pipeline Normal | Transfer Learning (CLIP) | Smart Culling |
|---------|----------------|--------------------------|---------------|
| **Dataset Mínimo** | 500 fotos | 50 fotos | 200 fotos (LR) ou 0 (AVA) |
| **Accuracy** | 60-75% | 80-85% | 70-85% |
| **Tempo de Treino** | 1-2 horas | 15-30 min | 30-180 min |
| **Uso de Memória** | Alto | Médio | Médio |
| **Quando Usar** | Dataset grande | Dataset pequeno | Culling automático |

---

## 💡 Recomendações

### Para Datasets Pequenos (< 100 fotos):
1. ✅ **Usar Transfer Learning (Tab 5)**
   - Modelo: CLIP
   - Épocas: 30
   - Resultado: 80-85% accuracy

### Para Culling de Milhares de Fotos:
1. ✅ **Se tens ratings**: Usar Smart Culling Lightroom (Tab 6)
2. ✅ **Se NÃO tens ratings**: Fazer download AVA e treinar (Tab 6)

### Para Datasets Grandes (> 500 fotos):
1. ✅ **Usar Pipeline Normal (Tab 1)**
   - Mais preciso para o teu estilo específico
   - Transfer Learning não traz vantagem significativa

---

## 📚 Documentação Adicional

- **Transfer Learning Detalhado**: `TRANSFER_LEARNING_GUIDE.md`
- **Transfer Learning Quick Start**: `TRANSFER_LEARNING_QUICKSTART.md`
- **Implementação de Recomendações**: `GUIA_IMPLEMENTACAO_RECOMENDACOES.md`

---

## 🎉 Pronto!

Agora tens acesso completo a Transfer Learning e Smart Culling diretamente na UI Gradio, sem precisar de linha de comando!

**Para começar:**

```bash
./start_train_ui.sh
```

Depois escolhe a tab apropriada:
- **Tab 5 (🎓 Transfer Learning)**: Para datasets pequenos
- **Tab 6 (⭐ Smart Culling)**: Para avaliação automática de qualidade

---

**Última Atualização:** 16 Novembro 2025
