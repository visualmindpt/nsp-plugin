# NSP Plugin - Public Datasets Guide

**Data:** 2025-11-25
**Versão:** 1.0

---

## 🎯 IMPORTANTE: Datasets Públicos São APENAS Para Culling!

### Resumo Executivo:

- ✅ **Lightroom Catalogs** → Treinam **AI Preset** (ajustes de edição)
- ⚠️ **Datasets Públicos** → Treinam **Culling** (seleção de fotos) APENAS

**Datasets públicos NÃO contêm ajustes de edição**, logo **NÃO podem treinar AI Preset!**

---

## ⚠️ Download Manual Necessário

Os datasets públicos **não são descarregados automaticamente** pela UI de treino.

### Porquê?

1. **Tamanho enorme** (5GB a 100GB+)
   - Consumo de bandwidth significativo
   - Tempo de download de horas/dias
   - Espaço em disco considerável

2. **Autenticação requerida**
   - Maioria dos datasets requer registo
   - API keys necessárias (Kaggle, COCO, etc.)
   - Aceitar termos de serviço

3. **Restrições legais**
   - Licenças específicas por dataset
   - Alguns são apenas para uso académico
   - Terms of use devem ser aceites manualmente

4. **Complexidade de APIs**
   - Cada dataset tem API diferente
   - Algumas requerem ferramentas específicas (kaggle CLI, AWS CLI, etc.)
   - Estruturas de ficheiros variadas

---

## 💡 RECOMENDAÇÃO: Use os Seus Catálogos Lightroom

**É muito mais simples e eficaz!**

### Vantagens:

✅ **Sem downloads** - os teus ficheiros já estão no computador
✅ **Mais rápido** - dataset pequeno (100-500 fotos vs milhões)
✅ **Melhor resultado** - aprende o TEU estilo específico
✅ **Já organizado** - ratings, edições já feitas
✅ **Conheces os dados** - sabes o que contém

### Como usar:

```bash
# 1. Abre UI de treino
python3 scripts/ui/train_ui_clean.py

# 2. Tab "Quick Start"
# 3. Data Source: "Lightroom Catalog"
# 4. Seleciona o teu .lrcat
# 5. Train!
```

---

## 📚 Datasets Públicos Disponíveis

### 1. AVA (Aesthetic Visual Analysis)

**Descrição:** 250,000+ imagens com ratings de qualidade estética

**Estatísticas:**
- Tamanho: ~25 GB
- Imagens: 255,000
- Ratings: 1-10 (aesthetic quality)

**URL:** http://www.lucamarchesotti.com/

**Como obter:**
1. Visita o site oficial
2. Regista-te e aceita termos
3. Descarrega o dataset
4. Extrai para: `datasets/ava/images/`

**Caso de uso:**
- Treino de base model (conhecimento geral)
- Detecção de qualidade estética
- Não recomendado para estilo pessoal

---

### 2. Flickr-AES

**Descrição:** Dataset de qualidade estética do Flickr

**Estatísticas:**
- Tamanho: ~10 GB
- Imagens: 40,000
- Annotations: Aesthetic scores

**URL:** https://github.com/yiling-chen/flickr-aes

**Como obter:**
1. Clona o repositório GitHub
2. Segue instruções de download
3. Pode requerer Flickr API key
4. Extrai para: `datasets/flickr_aes/images/`

**Caso de uso:**
- Avaliação de qualidade
- Complemento ao AVA
- Variedade de estilos fotográficos

---

### 3. COCO (Common Objects in Context)

**Descrição:** Dataset massivo de object detection

**Estatísticas:**
- Tamanho: ~100 GB
- Imagens: 330,000
- Annotations: Object detection, segmentation

**URL:** https://cocodataset.org/

**Como obter:**
1. Visita cocodataset.org
2. Regista-te (grátis)
3. Descarrega via script ou manual
4. Extrai para: `datasets/coco/images/`

**Caso de uso:**
- Object detection features
- Scene understanding
- **Não recomendado** para photo editing (não tem ajustes)

**⚠️ Aviso:** Dataset ENORME, não recomendado para NSP Plugin

---

### 4. PAQ-2-PIQ

**Descrição:** Perceptual Image Quality dataset

**Estatísticas:**
- Tamanho: ~5 GB
- Imagens: 40,000
- Annotations: Quality scores

**URL:** https://github.com/baidut/paq2piq

**Como obter:**
1. Visita repositório GitHub
2. Segue instruções
3. Registo pode ser necessário
4. Extrai para: `datasets/paq2piq/images/`

**Caso de uso:**
- Quality assessment
- Technical quality (não estilo)
- Complemento a outros datasets

---

## 🛠️ Como Configurar Dataset Público (Se Realmente Quiseres)

### Passo 1: Obter o Dataset Manualmente

```bash
# Exemplo para AVA:

# 1. Visita http://www.lucamarchesotti.com/
# 2. Regista-te
# 3. Descarrega AVA.zip (~25GB)
# 4. Extrai

cd ~/Downloads
unzip AVA.zip
```

### Passo 2: Organizar Estrutura

```bash
# Cria estrutura esperada pelo NSP Plugin
cd /path/to/NSP_Plugin/datasets
mkdir -p ava/images

# Move imagens
mv ~/Downloads/AVA/images/* ava/images/

# Cria labels.csv
echo "image_id,aesthetic_score,technical_quality" > ava/labels.csv
# ... popula com dados do AVA.txt
```

### Passo 3: Verificar com Script Helper

```bash
# A UI cria script helper automaticamente
cd datasets/ava
./download_ava.sh

# Output:
# ✅ Found 255000 images in datasets/ava/images
# ✅ Dataset structure verified!
```

### Passo 4: Usar na UI

```bash
# Abre UI
python3 scripts/ui/train_ui_clean.py

# Tab "Quick Start"
# Data Source: "Public Dataset"
# Dataset: "AVA"
# Train!
```

---

## 📋 Estrutura de Dataset Esperada

Qualquer dataset público deve seguir esta estrutura:

```
datasets/
└── dataset_id/
    ├── images/                    # Pasta com imagens
    │   ├── image001.jpg
    │   ├── image002.jpg
    │   └── ...
    ├── labels.csv                 # Anotações (opcional)
    ├── dataset_info.json          # Metadata (criado pela UI)
    └── download_dataset_id.sh     # Script helper (criado pela UI)
```

### labels.csv (Opcional)

Formato:
```csv
image_id,label,score
image001.jpg,landscape,8.5
image002.jpg,portrait,7.2
```

Se não existir, será criado vazio.

---

## 🚀 Workflow Recomendado

### Para Iniciantes:

```bash
# OPÇÃO 1: Usar catálogos Lightroom (RECOMENDADO)
1. Abre train_ui_clean.py
2. Quick Start → Lightroom Catalog
3. Seleciona .lrcat com 50-200 fotos editadas (rating ≥3)
4. Train!

# Resultado: Modelo personalizado em 30-60 minutos
```

### Para Utilizadores Avançados:

```bash
# OPÇÃO 2: Combinar Lightroom + Public Dataset

# Fase 1: Base knowledge (opcional)
1. Descarrega AVA ou Flickr-AES manualmente
2. Train base model com dataset público (~2-4 horas)
3. Exporta modelo: Tab "Gestão de Modelos" → Export

# Fase 2: Personal style (principal)
4. Importa base model noutro computador
5. Train incremental com catálogos Lightroom
6. Resultado: Base geral + estilo pessoal

# Desvantagem: Muito mais complexo, resultado marginal
```

### Para Investigação:

```bash
# OPÇÃO 3: Experimentação científica

1. Descarrega múltiplos datasets
2. Train modelos separados
3. Compara métricas (MAE, accuracy)
4. Publica paper 😄

# Requer: Muito tempo, espaço em disco, conhecimento ML
```

---

## ❓ FAQ

### Q: Porque não implementar download automático?

**A:** Razões técnicas e legais:
- Cada dataset tem API diferente (AVA, COCO, Kaggle, etc.)
- Requer autenticação/API keys individuais
- Termos de uso devem ser aceites manualmente
- Download de 100GB+ causaria problemas de bandwidth
- Muitos datasets mudam URLs frequentemente
- Manutenção seria complexa

### Q: Vale a pena usar datasets públicos?

**A:** **Geralmente NÃO**, para a maioria dos utilizadores.

**Casos onde SIM:**
- Investigação académica
- Comparação de algoritmos
- Base model geral (antes de personal style)

**Casos onde NÃO:**
- Queres aprender o TEU estilo → usa Lightroom
- Dataset pequeno (< 10k imagens) → usa Lightroom
- Primeira vez a usar NSP Plugin → usa Lightroom

### Q: Posso combinar Lightroom + Public Dataset?

**A:** Sim, mas complicado:

```bash
# Workflow:
1. Train base model com public dataset (V1)
2. Export modelo V1
3. Import modelo V1 noutro computador
4. Train incremental com Lightroom (V2, V3, ...)

# Resultado: Base geral + estilo pessoal
# Desvantagem: Muito mais complexo que só Lightroom
```

Normalmente **não compensa** - treinar só com Lightroom é mais simples e eficaz.

### Q: Quanto espaço em disco preciso?

**A:** Depende do dataset:

| Dataset | Tamanho | Recomendado |
|---------|---------|-------------|
| AVA | ~25 GB | 30 GB livre |
| Flickr-AES | ~10 GB | 15 GB livre |
| COCO | ~100 GB | 120 GB livre |
| PAQ-2-PIQ | ~5 GB | 10 GB livre |
| **Lightroom** | **~1-2 GB** | **5 GB livre** |

Lightroom catalogs são **muito mais leves**!

### Q: Quanto tempo demora?

**A:** Download + Setup + Training:

| Método | Download | Setup | Training | Total |
|--------|----------|-------|----------|-------|
| Public Dataset (AVA) | 4-8h | 1h | 3-6h | **8-15h** |
| Public Dataset (Flickr) | 2-4h | 30min | 2-4h | **4-8h** |
| **Lightroom (200 fotos)** | **0min** | **0min** | **30-60min** | **30-60min** |

Lightroom é **10-20x mais rápido**!

### Q: O script helper faz download automático?

**A:** Não. O script `download_dataset_id.sh`:
- **NÃO faz download** das imagens
- **Verifica** se já descarregaste
- **Valida** estrutura de pastas
- **Conta** imagens encontradas
- **Mostra** próximos passos

Deves descarregar manualmente primeiro, depois correr o script para verificar.

---

## 🎯 Conclusão

### TL;DR:

1. ✅ **RECOMENDADO:** Usa os teus **catálogos Lightroom**
   - Mais rápido
   - Mais simples
   - Melhor resultado (teu estilo)

2. ⚠️ **Avançado:** Datasets públicos
   - Download manual necessário
   - Muito complexo
   - Apenas para casos específicos

3. 📋 **Setup Instructions:**
   - UI fornece instruções detalhadas
   - Scripts helper para validação
   - Sem download automático

### Recomendação Final:

**Usa Lightroom!** É mais simples, rápido e eficaz para 99% dos casos.

---

## 📚 Recursos

### Links Úteis:

- **AVA Dataset:** http://www.lucamarchesotti.com/
- **Flickr-AES:** https://github.com/yiling-chen/flickr-aes
- **COCO:** https://cocodataset.org/
- **PAQ-2-PIQ:** https://github.com/baidut/paq2piq

### Documentação NSP Plugin:

- `README.md` - Visão geral do plugin
- `INCREMENTAL_TRAINING_REGRESSION.md` - Guia de treino incremental
- `PRESET_CLEANUP.md` - Mudanças no plugin (AI only)
- `train_ui_clean.py` - Interface de treino

### Suporte:

- Issues: (criar repositório GitHub)
- Email: (teu email)

---

**Última atualização:** 2025-11-25
**Autor:** Claude Code + Nelson Silva
**Versão:** 1.0
