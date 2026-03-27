# NSP Plugin — Plano de Implementação

**Estado:** Em desenvolvimento
**Última actualização:** 2026-03-27
**Versão actual:** 2.0 (Style Learner)
**Próxima versão:** 2.1 (Style Learner + Reference Match)

---

## Índice

1. [Contexto e Visão](#1-contexto-e-visão)
2. [Estado Actual do Codebase](#2-estado-actual-do-codebase)
3. [Fase A — Correcções à Versão Actual](#fase-a--correcções-à-versão-actual)
4. [Fase B — Nova Vertente: Reference Match](#fase-b--nova-vertente-reference-match)
5. [Arquitectura Final dos Dois Modos](#5-arquitectura-final-dos-dois-modos)
6. [Estrutura de Ficheiros a Criar](#6-estrutura-de-ficheiros-a-criar)
7. [Dados de Treino Necessários](#7-dados-de-treino-necessários)
8. [Ordem de Implementação Recomendada](#8-ordem-de-implementação-recomendada)

---

## 1. Contexto e Visão

### Dois modos distintos no mesmo plugin

O NSP Plugin terá duas vertentes que coexistem sem interferir:

```
Lightroom → File → Plug-in Extras
  ├── AI Preset V2              ← Modo actual (Style Learner)
  └── Match Reference Style     ← Novo modo (Reference Match)
```

### Diferença conceptual

| | Style Learner (actual) | Reference Match (novo) |
|---|---|---|
| **Como aprende** | Analisa padrão de edições do catálogo | Compara foto nova com uma referência editada |
| **Input do utilizador** | Nenhum (automático) | Selecciona 1 foto de referência |
| **Pergunta que responde** | "Como costumas editar este tipo de foto?" | "Como fazer esta foto ficar igual à referência?" |
| **Melhor para** | Workflow diário, fotos variadas | Shootings com look coerente, match de cor |
| **Treino necessário** | Sim, a partir do catálogo | Sim, a partir de pares (neutro, editado) |
| **Modelo** | Classifier + Regressor (2 modelos) | StyleFingerprintExtractor + ReferenceRegressor |

---

## 2. Estado Actual do Codebase

### O que já foi feito (desde a criação do repo)

- [x] `predictor.py` — adicionado `import pandas as pd` (era NameError em `batch_predict`)
- [x] `train_models_v2.py` — corrigido bug de early stopping no progressive training (comparava `val_loss` com `train_loss[-1]` em vez de `best_val_loss`)
- [x] `services/server.py` — removido `import sys` duplicado
- [x] `trainer_v2.py` — adicionado parâmetro `class_weights` ao `OptimizedClassifierTrainer`
- [x] `train_models_v2.py` — split 70/15/15 (era 80/20 sem test set)
- [x] `train_models_v2.py` — `CATALOG_PATH` lê de `LIGHTROOM_CATALOG_PATH` env var
- [x] `train_models_v2.py` — pesos de classe calculados automaticamente antes de criar o trainer
- [x] `requirements.txt` — removidos `groovy==0.1.2` e `Deprecated==1.3.1`
- [x] Adicionados: `.env.example`, `pyproject.toml`, `requirements-dev.txt`, `LICENSE`
- [x] 35 testes sintéticos ML em `tests/test_ml_synthetic.py` (todos a passar)
- [x] `README.md` reescrito com diagrama de arquitectura, referência de API, guia de treino

### O que NÃO está terminado

Ver Fase A abaixo.

---

## Fase A — Correcções à Versão Actual

### A1 — Paths hardcoded no trainer (BUG)

**Ficheiros:** `services/ai_core/trainer_v2.py` linhas 236, 245, 463, 472

**Problema:** O trainer guarda e carrega os checkpoints com paths relativos ao CWD:
```python
torch.save(self.model.state_dict(), 'best_preset_classifier_v2.pth')   # linha 236
self.model.load_state_dict(torch.load('best_preset_classifier_v2.pth')) # linha 245
```
Se o script for executado fora da raiz do projecto, os ficheiros vão para o lugar errado ou o load falha.

**Correcção:**
Adicionar parâmetro `checkpoint_path: Optional[Path] = None` ao método `train()` de ambos os trainers. Quando `None`, usar o path relativo como fallback. O chamador em `train_models_v2.py` passa `MODELS_DIR / 'best_preset_classifier_v2.pth'`.

```python
# trainer_v2.py — OptimizedClassifierTrainer.train()
def train(self, ..., checkpoint_path: Optional[Path] = None):
    ckpt = Path(checkpoint_path) if checkpoint_path else Path('best_preset_classifier_v2.pth')
    ...
    torch.save(self.model.state_dict(), ckpt)
    ...
    self.model.load_state_dict(torch.load(ckpt))
```

Mesma correcção para `OptimizedRefinementTrainer` com `'best_refinement_model_v2.pth'`.

---

### A2 — Test set calculado mas nunca usado (OMISSÃO)

**Ficheiro:** `train/train_models_v2.py`

**Problema:** O split 70/15/15 foi implementado e o test set é retornado por `prepare_training_data()`, mas nenhuma função de avaliação final é executada sobre ele. Os dados de teste `X_stat_test`, `X_deep_test`, `y_test_labels`, `y_test_deltas` são simplesmente ignorados depois do treino.

**Correcção:** Adicionar uma função `evaluate_on_test_set()` chamada no final do pipeline, que:
1. Cria `LightroomDataset` com os dados de teste
2. Corre `trainer.validate()` (que já existe) com o modelo final
3. Loga accuracy do classificador + MAE por parâmetro do regressor no test set
4. Guarda resultado em `models/test_evaluation.json`

```python
def evaluate_on_test_set(
    classifier_model, regressor_model,
    X_stat_test, X_deep_test,
    y_test_labels, y_test_deltas,
    delta_columns, scaler_deltas, device
):
    """Avaliação final não-enviesada no test set separado."""
    test_ds = LightroomDataset(X_stat_test, X_deep_test, y_test_labels, y_test_deltas)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)

    # Classificador
    clf_trainer = OptimizedClassifierTrainer(classifier_model, device=device, use_mixed_precision=False)
    test_loss, test_acc, preds, labels = clf_trainer.validate(test_loader)
    report = classification_report(labels, preds, output_dict=True)

    # Regressor
    reg_trainer = OptimizedRefinementTrainer(regressor_model, ...)
    reg_loss, mae_per_param, _, _ = reg_trainer.validate(test_loader)

    results = {
        "classifier": {"test_loss": test_loss, "test_accuracy": test_acc, "report": report},
        "regressor":  {"test_loss": reg_loss, "mae_per_param": mae_per_param.tolist()}
    }
    with open(MODELS_DIR / 'test_evaluation.json', 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Test Accuracy: {test_acc:.4f} | Test MAE (avg): {mae_per_param.mean():.4f}")
    return results
```

---

### A3 — `pct_start` do OneCycleLR demasiado alto para datasets pequenos

**Ficheiro:** `services/ai_core/trainer_v2.py` linhas 199 e 421

**Problema:** `pct_start=0.3` significa que 30% do treino é fase de warmup (LR a subir). Com CLASSIFIER_EPOCHS=50 e batches pequenos, o modelo passa demasiado tempo a aquecer e pouco tempo a convergir.

**Correcção:** Mudar para `pct_start=0.1` em ambos os trainers (10% de warmup é suficiente para datasets pequenos).

```python
self.scheduler = optim.lr_scheduler.OneCycleLR(
    self.optimizer,
    max_lr=max_lr,
    total_steps=total_steps,
    pct_start=0.1,   # era 0.3
    ...
)
```

---

### A4 — Ausência de avaliação do classificador no test set por classe

**Ficheiro:** `train/train_models_v2.py`

**Problema:** O classification report final (precision/recall/F1 por preset) é apenas calculado no validation set, não no test set. Depois de A2 ser implementado, o report deve incluir as métricas por classe do test set, e ser guardado no `test_evaluation.json` para análise posterior.

---

### A5 — `data/` contém ficheiros grandes não ignorados correctamente

**Ficheiro:** `.gitignore`

**Problema:** `data/api_keys.json` está explicitamente ignorado, mas `data/nsp_plugin.db` e `data/feedback.db` têm entradas `*.db` no gitignore que funcionam. No entanto, `data/lightroom_dataset.csv`, `data/image_features.csv`, e `data/deep_features.npy` continuam presentes no disco e podem ser acidentalmente staged se o dev remover as entradas do .gitignore.

**Correcção:** Adicionar um ficheiro `data/.gitkeep` e documentar no README que `data/` é um directório de runtime — nunca fazer commit dos seus conteúdos.

---

### A6 — Logging de treino sem timestamp no ficheiro

**Ficheiro:** `train/train_models_v2.py`

**Problema:** O logger escreve para stdout mas não para ficheiro. Numa sessão de treino longa é impossível recuperar o histórico se o terminal for fechado.

**Correcção:** Adicionar `FileHandler` ao logging setup com path `logs/train_{timestamp}.log`:

```python
log_file = Path('logs') / f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_file.parent.mkdir(exist_ok=True)
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(file_handler)
```

---

## Fase B — Nova Vertente: Reference Match

### Visão Geral

O utilizador selecciona no Lightroom uma foto que já editou à sua maneira (a "referência") e as fotos que quer igualar. O plugin analisa o resultado visual da referência, analisa cada foto nova, e prediz os parâmetros Lightroom que produzem o look mais próximo possível.

```
[REFERÊNCIA: foto editada] ──► StyleFingerprintExtractor ──► style_vector (128-dim)
                                                                      │
[NOVA FOTO: estado neutro] ──► ImageFeatureExtractor ──► photo_vector │
                                DeepFeatureExtractor  ──► deep_vector  │
                                                             │         │
                                                             └────┬────┘
                                                                  ▼
                                                        ReferenceRegressor
                                                        input: [photo_vector,
                                                                deep_vector,
                                                                style_vector]
                                                                  │
                                                                  ▼
                                                   Parâmetros Lightroom absolutos
                                                   (não deltas — valores finais)
```

**Diferença importante face ao modo actual:**
O modo actual prediz **deltas** (ajustes sobre um centro de preset). O Reference Match prediz **valores absolutos** — porque o alvo é o look da referência, não um centro de cluster aprendido.

---

### B1 — `StyleFingerprintExtractor`

**Ficheiro a criar:** `services/ai_core/style_fingerprint_extractor.py`

**O que faz:** Dado o path de um JPEG/PNG já editado (o resultado final, não o RAW), extrai uma representação numérica do seu *look visual* — independente do conteúdo fotográfico.

**Features a extrair (128 valores totais):**

```
Luminância (32 valores):
  - Histograma de luminância em 16 bins (normalizado)
  - Média, desvio padrão, skewness, kurtosis da luminância
  - Percentis 5, 25, 50, 75, 95

Cor (48 valores):
  - Médias R, G, B por terço da imagem (shadows/mids/highlights) → 9 valores
  - Histograma de saturação em 8 bins → 8 valores
  - Histograma de hue em 12 bins → 12 valores
  - Temperatura de cor estimada (método grey-world) → 1 valor
  - Tint estimado → 1 valor
  - Média HSV por canal → 3 valores
  - Desvio padrão HSV por canal → 3 valores
  - Rácio de píxeis muito saturados (> 0.8) → 1 valor
  - Rácio de píxeis dessaturados (< 0.1) → 1 valor
  - Dominância de cor (entropia do histograma de hue) → 1 valor
  - Contraste de cor (desvio padrão inter-canal) → 1 valor
  - Cross-channel correlations (RG, RB, GB) → 3 valores
  - Split toning: médias de hue em shadows vs highlights → 4 valores

Contraste/Tonalidade (24 valores):
  - Curva de tons amostrada em 8 pontos (sombras → luzes) → 8 valores
  - Rácio de píxeis em shadows (<0.2), mids (0.2-0.8), highlights (>0.8) → 3 valores
  - Contraste local (Laplacian variance) → 1 valor
  - Dinâmica tonal (max - min brightness por patch 16x16, média) → 1 valor
  - Rácio de clipping em highlights → 1 valor
  - Rácio de clipping em shadows → 1 valor
  - Score de "moody" (low-key ratio) → 1 valor
  - Score de "airy" (high-key ratio) → 1 valor
  - Gradiente médio (edge density) → 1 valor

Grain/Textura (8 valores):
  - Energia de alta frequência (DFT) por banda → 4 valores
  - Variância de ruído estimada → 1 valor
  - Score de "clarity" (sharpness local) → 1 valor
  - Homogeneidade (GLCM) → 1 valor
  - Contraste (GLCM) → 1 valor

Total: 32 + 48 + 24 + 8 = 112 → arredondar para 128 com padding/features extra
```

**Interface:**

```python
class StyleFingerprintExtractor:
    def extract(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        Retorna vector numpy de shape (128,) com a assinatura visual do look.
        image_path deve apontar para o JPEG exportado (resultado editado),
        não para o RAW original.
        """
```

**Notas de implementação:**
- Usa apenas `Pillow`, `numpy`, `scipy` — sem dependências pesadas
- Deve ser rápido (< 50ms por imagem)
- Completamente independente do modo Style Learner
- Normalizar internamente (output em [-1, 1] por canal)

---

### B2 — `ReferencePairDataset`

**Ficheiro a criar:** `services/ai_core/reference_pair_dataset.py`

**O que faz:** Dataset PyTorch para treino do ReferenceRegressor. Cada amostra é um triplo:
- Features da foto a editar (stat + deep, estado neutro/RAW)
- Style fingerprint da foto de referência
- Parâmetros Lightroom que foram aplicados à foto a editar (ground truth)

**Como construir os dados de treino:**
No catálogo existem N fotos editadas. Para cada foto `P` com parâmetros `params_P`:
1. Extrair `photo_features_P` (stat + deep do RAW/estado neutro)
2. Para cada outra foto `R` no mesmo shooting (mesmo dia/sessão), exportar JPEG de `R` e extrair `style_fingerprint_R`
3. A amostra de treino é: `(photo_features_P, style_fingerprint_R, params_P)`
   — "dado que a referência R tem este look, os parâmetros correctos para P são estes"

**Porquê usar fotos do mesmo shooting como pares?**
Porque dentro de um shooting o fotógrafo mantém o mesmo look. Foto R editada e foto P (que ainda não está editada) devem ter o mesmo resultado final. O modelo aprende: "quando a referência tem este fingerprint e a foto tem estas features, aplica estes parâmetros."

```python
class ReferencePairDataset(Dataset):
    def __init__(
        self,
        photo_stat_features: np.ndarray,    # [N, stat_dim]
        photo_deep_features: np.ndarray,    # [N, deep_dim]
        reference_fingerprints: np.ndarray, # [N, 128] — fingerprint da ref para cada amostra
        target_params: np.ndarray,          # [N, num_params] — parâmetros absolutos
    )
```

---

### B3 — `ReferenceRegressor`

**Ficheiro a criar:** `services/ai_core/reference_regressor.py`

**Arquitectura:**

```python
class ReferenceRegressor(nn.Module):
    def __init__(
        self,
        stat_features_dim: int,   # dimensão features estatísticas (ex: 40)
        deep_features_dim: int,   # dimensão deep features (ex: 512)
        style_fingerprint_dim: int = 128,
        num_params: int = 60,
        width_factor: float = 1.0
    )
```

**Forward pass:**

```
stat_features  [B, stat_dim]  ──► stat_branch  ──► [B, 64]
deep_features  [B, deep_dim]  ──► deep_branch  ──► [B, 64]
style_vector   [B, 128]       ──► style_branch ──► [B, 64]
                                                      │
                               Concat + Attention     │
                                      │               │
                               ┌──────┴──────┐        │
                               │  Fusion MLP │ ◄──────┘
                               │  [192→128→64│
                               └──────┬──────┘
                                      │
                               Skip connection
                                      │
                               Output [B, num_params]
                               (parâmetros absolutos)
```

**Diferença chave face ao `OptimizedRefinementRegressor`:**
- Input adicional: `style_vector` (128-dim fingerprint da referência)
- Output: parâmetros **absolutos** (não deltas sobre preset center)
- Sem `preset_id` embedding — não há clustering
- Loss: `WeightedMSELoss` com pesos por importância de parâmetro (reusar `PARAM_IMPORTANCE` já definido)

**Nota sobre o output absoluto vs delta:**
Predizer valores absolutos é mais simples mas requer que o scaler cubra o range completo dos parâmetros. Alternativa: predizer delta relativamente ao estado neutro (todos os parâmetros a 0). São equivalentes — escolher absoluto por ser mais interpretável.

---

### B4 — `ReferenceMatchTrainer`

**Ficheiro a criar:** `services/ai_core/reference_match_trainer.py`
(ou adicionar classe ao `trainer_v2.py` existente)

**Estrutura:** Semelhante ao `OptimizedRefinementTrainer` mas:
- Batch contém `style_fingerprint` em vez de `preset_id`
- Loss é `WeightedMSELoss` sobre parâmetros absolutos
- Métricas: MAE por parâmetro + MAE médio global

```python
class ReferenceMatchTrainer:
    def __init__(
        self,
        model: ReferenceRegressor,
        param_weights: torch.Tensor,
        device: str = 'cpu',
        use_mixed_precision: bool = True,
        weight_decay: float = 0.02
    )

    def train_epoch(self, loader: DataLoader) -> float: ...
    def validate(self, loader: DataLoader) -> Tuple[float, np.ndarray]: ...
    def train(self, train_loader, val_loader, epochs, patience, ...) -> ReferenceRegressor: ...
```

---

### B5 — Script de treino do modo Reference

**Ficheiro a criar:** `train/train_reference_model.py`

**Pipeline:**

```
1. EXTRAIR DADOS DO CATÁLOGO
   Reutilizar LightroomCatalogExtractor (já existe)
   Output: dataset com (image_path, params, session_id/date)

2. AGRUPAR POR SESSÃO
   Fotos do mesmo dia/sessão formam grupos
   Cada grupo = potential reference pairs

3. EXTRAIR FEATURES
   Para cada foto:
     - photo_stat  = ImageFeatureExtractor.extract_all_features(raw_path)  [existente]
     - photo_deep  = DeepFeatureExtractor.extract_features(raw_path)       [existente]
   Para cada foto editada (como potencial referência):
     - style_fp    = StyleFingerprintExtractor.extract(jpeg_exported_path) [novo]

4. CONSTRUIR PARES DE TREINO
   Para cada foto P no catálogo:
     Para cada outra foto R na mesma sessão que P:
       amostra = (features_P, fingerprint_R, params_P)
   Resultado: N × (S-1) amostras onde S = tamanho médio de sessão

5. NORMALIZAR
   Scaler separado para style_fingerprints: scaler_style.pkl
   Scaler para params absolutos: scaler_params_ref.pkl
   (Guardar em models/)

6. TREINAR
   ReferenceRegressor com ReferenceMatchTrainer
   70/15/15 split, early stopping, checkpoint em models/reference_model.pth

7. AVALIAR
   Métricas no test set: MAE por parâmetro, MAE médio
   Guardar em models/reference_test_evaluation.json
```

**Ficheiros de modelo gerados:**
```
models/
  reference_model.pth            ← pesos do ReferenceRegressor
  scaler_style.pkl               ← normalização dos style fingerprints
  scaler_params_ref.pkl          ← normalização dos parâmetros absolutos
  reference_test_evaluation.json ← métricas no test set
```

---

### B6 — Endpoint FastAPI: `/predict/reference`

**Ficheiro:** `services/server.py`

**Novos modelos Pydantic:**

```python
class ReferenceMatchRequest(BaseModel):
    image_path: Optional[str] = None
    image_b64: Optional[str] = None
    reference_path: Optional[str] = None   # path do JPEG exportado da referência
    reference_b64: Optional[str] = None    # alternativa base64

class ReferenceMatchResponse(BaseModel):
    predicted_params: Dict[str, float]     # parâmetros absolutos para aplicar
    reference_fingerprint_norm: float      # score 0-1 de quão bem a referência foi identificada
    processing_time_ms: float
```

**Lógica do endpoint:**

```python
@app.post("/predict/reference", response_model=ReferenceMatchResponse)
async def predict_reference(request: Request):
    # 1. Materializar imagem nova e referência (path ou base64)
    photo_path, ref_path = _materialize_inputs(...)

    # 2. Extrair features da foto nova (reutiliza extractors existentes)
    stat_features = stat_extractor.extract_all_features(photo_path)
    deep_features = deep_extractor.extract_features(photo_path)

    # 3. Extrair fingerprint da referência (novo extractor)
    style_fp = style_fingerprint_extractor.extract(ref_path)

    # 4. Normalizar
    stat_scaled  = scaler_stat.transform(stat_features)
    deep_scaled  = scaler_deep.transform(deep_features)
    style_scaled = scaler_style.transform(style_fp)

    # 5. Predizer
    params_normalized = reference_model(stat_scaled, deep_scaled, style_scaled)
    params = scaler_params_ref.inverse_transform(params_normalized)

    # 6. Clamping (reutilizar _clamp_parameter existente)
    final_params = {name: _clamp_parameter(name, val) for name, val in zip(param_names, params)}

    return ReferenceMatchResponse(predicted_params=final_params, ...)
```

**Carregamento do modelo no startup:**
Adicionar ao `startup_event()` em `server.py` — carrega `reference_model.pth`, `scaler_style.pkl`, `scaler_params_ref.pkl`. Se os ficheiros não existirem, o endpoint retorna 503 com mensagem "Reference model not trained yet".

---

### B7 — Plugin Lua: `MatchReferenceStyle.lua`

**Ficheiro a criar:** `NSP-Plugin.lrplugin/MatchReferenceStyle.lua`

**Fluxo UX:**

```
1. Utilizador selecciona 1 foto de referência (já editada à sua maneira)
   + N fotos a editar

2. Plugin valida:
   - Exactamente 1 referência (a primeira foto seleccionada, ou prompt de escolha)
   - Pelo menos 1 foto adicional
   - Servidor disponível

3. Exportar referência como JPEG temporário
   (Lightroom API: LrExportSession com as definições exportadas)
   → /tmp/nsp_reference_{uuid}.jpg

4. Para cada foto a editar:
   a. Exportar preview como JPEG temporário
   b. POST /predict/reference {image_path: preview, reference_path: ref_jpeg}
   c. Aplicar params retornados via LrDevelopController.setValue()

5. Limpar ficheiros temporários
6. Mostrar summary: "X fotos processadas com o look de [nome da referência]"
```

**Registo em `Info.lua`:**

```lua
LrPluginMenuItems = {
    {
        title = "AI Preset V2",
        file = "ApplyAIPresetV2.lua",
    },
    {
        title = "Match Reference Style",  -- NOVO
        file = "MatchReferenceStyle.lua",
    },
},
```

**Considerações:**
- A exportação do JPEG de referência deve usar resolução reduzida (max 800px lado maior) para velocidade
- O `LrExportSession` precisa de usar as definições guardadas da foto (não re-exportar com neutralização)
- Tratar o caso em que a referência não tem JPEG exportado disponível — usar preview do Lightroom como fallback

---

### B8 — Exportação de JPEGs do catálogo para treino

**Problema:** O `StyleFingerprintExtractor` precisa dos JPEGs exportados das fotos editadas (não os RAWs). O Lightroom não expõe o "resultado visual" da edição directamente via SQL no catálogo — é preciso exportar.

**Solução:** Script utilitário que exporta JPEGs de baixa resolução para treino:

**Ficheiro a criar:** `tools/export_training_jpegs.lua` (Lua, corre dentro do Lightroom)
ou
**Alternativa:** `tools/export_training_jpegs.py` que usa as previews já geradas pelo Lightroom (estão em `[Catalog Name] Previews.lrdata`)

**Recomendação:** Usar as previews existentes — são JPEGs já renderizados com as edições aplicadas, a 1:1 ou standard. Estão em formato proprietário mas legíveis com `rawpy` ou directamente como JPEG depois de localizar o ficheiro correcto.

**Script a criar:** `tools/extract_lightroom_previews.py`
- Input: path do catálogo `.lrcat`
- Output: directório `data/previews/` com `{image_id}.jpg` para cada foto editada
- Usa a base de dados SQLite do catálogo para mapear `image_id → preview_path`

---

## 5. Arquitectura Final dos Dois Modos

```
NSP Plugin v2.1
│
├── MODO 1: Style Learner (actual)
│   │
│   ├── Treino:
│   │   train/train_models_v2.py
│   │     → LightroomCatalogExtractor (lê catálogo)
│   │     → ImageFeatureExtractor + DeepFeatureExtractor (features do RAW)
│   │     → PresetIdentifier (K-Means clustering)
│   │     → OptimizedClassifierTrainer → best_preset_classifier_v2.pth
│   │     → OptimizedRefinementTrainer → best_refinement_model_v2.pth
│   │
│   └── Inferência:
│       POST /predict {image_path}
│         → LightroomAIPredictor.predict()
│           → ImageFeatureExtractor + DeepFeatureExtractor
│           → OptimizedPresetClassifier → preset_id
│           → OptimizedRefinementRegressor → deltas
│           → preset_center[preset_id] + deltas = parâmetros finais
│         ← {preset_id, confidence, final_params}
│
└── MODO 2: Reference Match (novo)
    │
    ├── Treino:
    │   train/train_reference_model.py
    │     → LightroomCatalogExtractor (lê catálogo)
    │     → tools/extract_lightroom_previews.py (JPEGs das edições)
    │     → ImageFeatureExtractor + DeepFeatureExtractor (features do RAW)
    │     → StyleFingerprintExtractor (fingerprint do JPEG editado)
    │     → ReferencePairDataset (pares dentro de sessões)
    │     → ReferenceMatchTrainer → reference_model.pth
    │
    └── Inferência:
        POST /predict/reference {image_path, reference_path}
          → ImageFeatureExtractor + DeepFeatureExtractor (foto nova)
          → StyleFingerprintExtractor (referência)
          → ReferenceRegressor → parâmetros absolutos
          → _clamp_parameter() → parâmetros finais
        ← {predicted_params}
```

---

## 6. Estrutura de Ficheiros a Criar

```
NSP Plugin_dev_full_package/
│
├── services/ai_core/
│   ├── style_fingerprint_extractor.py   [B1] NOVO
│   ├── reference_pair_dataset.py        [B2] NOVO
│   ├── reference_regressor.py           [B3] NOVO
│   └── reference_match_trainer.py       [B4] NOVO (ou adicionar a trainer_v2.py)
│
├── train/
│   └── train_reference_model.py         [B5] NOVO
│
├── tools/
│   └── extract_lightroom_previews.py    [B8] NOVO
│
├── NSP-Plugin.lrplugin/
│   └── MatchReferenceStyle.lua          [B7] NOVO
│
├── models/  (gerados pelo treino)
│   ├── reference_model.pth              gerado por B5
│   ├── scaler_style.pkl                 gerado por B5
│   ├── scaler_params_ref.pkl            gerado por B5
│   └── reference_test_evaluation.json  gerado por B5
│
└── tests/
    ├── test_ml_synthetic.py             [FEITO] 35 testes a passar
    ├── test_style_fingerprint.py        [A CRIAR] testes para StyleFingerprintExtractor
    └── test_reference_pipeline.py       [A CRIAR] testes end-to-end do modo Reference
```

---

## 7. Dados de Treino Necessários

### Para o modo Style Learner (actual)

Já implementado. Requer:
- Catálogo Lightroom com path em `LIGHTROOM_CATALOG_PATH`
- Mínimo recomendado: 100 fotos editadas com rating ≥ 3

### Para o modo Reference Match (novo)

Requer adicionalmente:
- JPEGs exportados das fotos editadas (para o `StyleFingerprintExtractor`)
  - Usar `tools/extract_lightroom_previews.py` (a criar)
  - Ou exportar manualmente para `data/previews/`
- Fotos organizadas por sessão (data de captura é suficiente)
  - O catálogo SQLite tem `captureTime` em `AgLibraryFile` — usar para agrupar
- Mínimo recomendado: 5+ sessões com 10+ fotos cada

### Qualidade dos dados

O modo Reference Match é mais sensível à qualidade dos dados do que o Style Learner porque:
1. Os pares (foto nova, referência) devem ser do mesmo shooting — se misturares sessões com looks muito diferentes, o modelo aprende uma média inútil
2. O JPEG da referência deve corresponder à edição final — previews geradas a 1:1 são ideais; previews standard (reduzidas) são aceitáveis mas podem perder nuances de grain/sharpness

---

## 8. Ordem de Implementação Recomendada

### Sprint 1 — Correcções à versão actual (Fase A)

Prioridade alta — sem estas correcções, os resultados de treino são menos fiáveis.

```
A1  trainer_v2.py — paths hardcoded             (~30 min)
A2  train_models_v2.py — usar test set          (~1h)
A3  trainer_v2.py — pct_start 0.3 → 0.1        (~5 min)
A4  train_models_v2.py — report por classe test (~30 min)
A5  .gitignore + data/.gitkeep                  (~10 min)
A6  train_models_v2.py — logging para ficheiro  (~20 min)
```

### Sprint 2 — Infraestrutura de dados Reference (Fase B, parte 1)

Sem dados, não há treino.

```
B8  tools/extract_lightroom_previews.py         (~2h)
    Validar que os JPEGs gerados têm qualidade suficiente
    Testar com catálogo real
```

### Sprint 3 — Core do modo Reference (Fase B, parte 2)

```
B1  style_fingerprint_extractor.py              (~3h)
    + tests/test_style_fingerprint.py
    Validar que fingerprints de fotos semelhantes são próximos
    e de fotos diferentes são distantes (cosine similarity)

B2  reference_pair_dataset.py                   (~1h)
    Testar com dados sintéticos primeiro

B3  reference_regressor.py                      (~2h)
    Arquitectura + testes de sanidade (shapes, grad flow)
```

### Sprint 4 — Treino e avaliação

```
B4  reference_match_trainer.py                  (~2h)
B5  train/train_reference_model.py              (~3h)
    Treinar com dados reais do catálogo
    Avaliar MAE no test set
    Benchmark vs baseline: "aplicar parâmetros médios do catálogo"
```

### Sprint 5 — Integração no servidor e plugin

```
B6  server.py — /predict/reference endpoint     (~2h)
B7  MatchReferenceStyle.lua                     (~3h)
    Testar fluxo completo no Lightroom
```

### Sprint 6 — Testes e documentação

```
tests/test_reference_pipeline.py                (~2h)
Actualizar README com documentação do novo modo
Actualizar CHANGELOG.md
```

---

## Notas para o Programador

### Sobre os dois scalers de parâmetros

O modo Style Learner usa `scaler_deltas.pkl` (normaliza **deltas** relativos ao preset center).
O modo Reference Match usa `scaler_params_ref.pkl` (normaliza **valores absolutos**).
São diferentes e não podem ser misturados. O carregamento em `server.py` deve ser explícito.

### Sobre a exportação de previews do Lightroom

O Lightroom guarda previews em `[Catalog Name] Previews.lrdata/`, numa estrutura de directórios por UUID. O mapeamento entre foto e preview está na tabela `Adobe_imageDevelopBeforeSettings` e `AgLibraryIPTC` no SQLite. Alternativa mais simples: usar o SDK Lua para exportar directamente via `LrExportSession` com `LR_format = 'JPEG'` e `LR_jpeg_quality = 80`.

### Sobre a qualidade do StyleFingerprintExtractor

O extractor deve ser **agnóstico ao conteúdo** — dois retratos com o mesmo look devem ter fingerprints similares mesmo que um seja de frente e o outro de perfil. Evitar features que dependam de conteúdo (ex: detecção de faces, classificação de cenas). Focar em distribuições de cor/tom globais.

### Sobre o mínimo de dados para treino

Com poucos dados (< 200 fotos), considerar data augmentation no espaço de fingerprints: pequenas perturbações nos histogramas de cor, jitter de saturação. Isto é especialmente importante para o modo Reference Match porque o número de pares cresce com S² (S = tamanho de sessão) mas pode ser insuficiente se o catálogo tiver poucas sessões.

### Sobre compatibilidade entre versões

Os modelos dos dois modos são completamente independentes:
- Style Learner: `best_preset_classifier_v2.pth`, `best_refinement_model_v2.pth`, `scaler_stat.pkl`, `scaler_deep.pkl`, `scaler_deltas.pkl`, `preset_centers.json`, `delta_columns.json`
- Reference Match: `reference_model.pth`, `scaler_style.pkl`, `scaler_params_ref.pkl`

Ambos os modos partilham `scaler_stat.pkl` e `scaler_deep.pkl` (mesmo extractor de features base).
**Importante:** Se re-treinar o Style Learner, os scalers `scaler_stat.pkl` e `scaler_deep.pkl` mudam. O Reference Match deve ser re-treinado também (ou usar scalers separados).
**Recomendação:** Criar `scaler_stat_ref.pkl` e `scaler_deep_ref.pkl` independentes para o modo Reference de forma a evitar este acoplamento.
