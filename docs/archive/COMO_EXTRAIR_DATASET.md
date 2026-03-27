# 📋 Como Extrair o Dataset do Catálogo Lightroom

**Data:** 16 Novembro 2025

---

## ❌ Erro Comum

Se vires este erro ao tentar usar Transfer Learning ou Culling:

```
❌ Dataset não encontrado! Execute primeiro a extração do catálogo Lightroom.
```

É porque o ficheiro `data/lightroom_dataset.csv` ainda não foi criado.

---

## ✅ Solução: Extrair Dataset do Catálogo

### Passo 1: Abrir a UI Gradio

```bash
./start_train_ui.sh
```

### Passo 2: Configurar Caminho do Catálogo

Na barra lateral esquerda, **configurar o catálogo Lightroom**:

#### Opção A: Arrastar Ficheiro
1. Arrastar o ficheiro `.lrcat` para a área "Arrasta ou seleciona o catálogo"

#### Opção B: Escrever Caminho Manual
1. No campo "Caminho completo do catálogo"
2. Escrever o path completo, ex:
   ```
   /Users/teuuser/Pictures/Lightroom/Lightroom Catalog.lrcat
   ```

### Passo 3: Extrair Dados

#### Opção A: Tab "Pipeline Completo" (Recomendado)
1. Ir para **Tab "🚀 Pipeline Completo"**
2. Clicar **"▶️ Executar Pipeline Completo"**
3. Aguardar conclusão (extrai dataset + treina modelos)

#### Opção B: Tab "Passo a Passo" (Só Extrair)
1. Ir para **Tab "🔧 Passo a Passo"**
2. Clicar **"1️⃣ Extrair Dados do Catálogo"**
3. Aguardar extração (1-5 minutos dependendo do tamanho)

### Passo 4: Verificar Extração

Após a extração, deves ver:

```
✅ Extração concluída. X imagens processadas.
```

E o ficheiro será criado em:
```
data/lightroom_dataset.csv
```

---

## 📊 Verificar Dataset com Estatísticas

Depois da extração, podes verificar a qualidade do dataset:

1. Ir para **Tab "📊 Estatísticas do Dataset"**
2. Clicar **"🔄 Calcular Estatísticas"**
3. Ver:
   - Número de imagens
   - Distribuição de presets
   - Balanceamento
   - Recomendações

---

## 🎓 Usar Transfer Learning Depois

**Agora sim**, podes usar Transfer Learning:

1. Ir para **Tab "🎓 Transfer Learning"**
2. Selecionar modelo (CLIP recomendado)
3. Clicar **"🚀 Iniciar Transfer Learning"**
4. Aguardar treino (15-30 min)

---

## ⭐ Usar Smart Culling Depois

**Com o dataset extraído**, podes treinar Culling:

1. Ir para **Tab "⭐ Smart Culling"**
2. Selecionar **"Lightroom"** como dataset
3. Clicar **"🚀 Iniciar Treino de Culling"**
4. Aguardar treino (30-60 min)

---

## 🔧 Troubleshooting

### "Catálogo não encontrado"
- Verificar que o path do `.lrcat` está correto
- Verificar que tens permissões de leitura no ficheiro

### "Nenhuma imagem processada"
- Verificar que tens fotos com **rating >= 3** no catálogo
- Se quiseres incluir fotos com rating menor:
  - Na barra lateral, mudar "Rating Mínimo" para 1 ou 2

### "Dataset vazio após extração"
- Verificar que as fotos têm **ajustes aplicados** no Lightroom
- Fotos sem edições não são exportadas

---

## 💡 Recomendações

### Para Melhores Resultados:

1. **Mínimo de fotos:**
   - Pipeline Normal: 500 fotos
   - Transfer Learning: 50 fotos
   - Smart Culling: 200 fotos com ratings

2. **Ratings no Lightroom:**
   - Avaliar fotos com ⭐⭐⭐ a ⭐⭐⭐⭐⭐
   - Mínimo 3 estrelas para treino

3. **Diversidade:**
   - Fotos de diferentes estilos
   - Diferentes condições de iluminação
   - Diferentes tipos de cena

---

**Última Atualização:** 16 Novembro 2025
