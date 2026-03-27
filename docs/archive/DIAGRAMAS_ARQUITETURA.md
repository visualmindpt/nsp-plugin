# NSP Plugin – Diagramas de Arquitetura

## 1. Diagrama de Componentes (Estado Atual)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE APRESENTAÇÃO                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   Adobe Lightroom Classic                           │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  NSP-Plugin.lrplugin (Lua SDK 11.0)                          │   │   │
│  │  │                                                               │   │   │
│  │  │  Menus:                          Configuração:                │   │   │
│  │  │  • Main.lua                      • Preferences.lua            │   │   │
│  │  │  • SmartCulling.lua              • ChooseModel.lua            │   │   │
│  │  │  • AutoProfiling.lua             • WorkflowPreset.lua         │   │   │
│  │  │  • ConsistencyReport.lua                                      │   │   │
│  │  │  • SendFeedback.lua              State:                       │   │   │
│  │  │  • SyncFeedback.lua              • LrPrefs (local)            │   │   │
│  │  │                                  • HTTP Client (LrHttp)       │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────┬──────────────────────────────────────┘   │
│                                 │                                           │
│  ┌──────────────────────────────┴───────┬───────────────────────────────┐  │
│  │                                      │                               │  │
│  │  Control Center (Tauri v1.5)         │  Gradio UI (app_ui.py)        │  │
│  │  ┌─────────────────────────┐         │  ┌─────────────────────────┐  │  │
│  │  │ Frontend (JS/HTML/CSS)  │         │  │ Pipeline Orchestrator   │  │  │
│  │  │ • Dashboard             │         │  │ • Catalog Extraction    │  │  │
│  │  │ • Workflow Presets      │         │  │ • Embedding Generation  │  │  │
│  │  │ • Diagnostics           │         │  │ • Model Training        │  │  │
│  │  │ • Log Viewer            │         │  │ • Evaluation            │  │  │
│  │  └─────────────────────────┘         │  │ • Feedback Retraining   │  │  │
│  │  │                                   │  └─────────────────────────┘  │  │
│  │  ▼                                   │                               │  │
│  │  ┌─────────────────────────┐         │  Port: 7860                   │  │
│  │  │ Backend (Rust/Tauri)    │         │  Protocol: HTTP               │  │
│  │  │ • Process Manager       │         └───────────────────────────────┘  │
│  │  │ • Config Manager        │                                            │
│  │  │ • Bundle Verifier       │                                            │
│  │  │ • Workflow Manager      │                                            │
│  │  └─────────────────────────┘                                            │
│  │                                                                          │
│  │  State: localStorage + nsp_config.json                                  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP (localhost:5678)
                                  │ JSON REST API
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                          CAMADA DE APLICAÇÃO                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Server (services/server.py)                     │  │
│  │                                                                       │  │
│  │  REST Endpoints:                    Dependencies:                    │  │
│  │  ┌───────────────────────┐          • Pydantic (validation)          │  │
│  │  │ GET  /health          │          • uvicorn (ASGI server)          │  │
│  │  │ POST /predict         │          • logging (structured)           │  │
│  │  │ POST /feedback        │                                           │  │
│  │  │ POST /feedback/bulk   │          Lifecycle:                       │  │
│  │  │ POST /culling/score   │          • startup: load engines          │  │
│  │  │ POST /profiles/assign │          • runtime: request handlers      │  │
│  │  │ POST /consistency/    │          • shutdown: cleanup             │  │
│  │  │      report           │                                           │  │
│  │  └───────────────────────┘                                           │  │
│  │                                                                       │  │
│  │  Error Handling:                    State:                           │  │
│  │  • HTTPException (4xx/5xx)          • Global ENGINE instances        │  │
│  │  • Logging (correlation IDs)        • DB connection pool             │  │
│  └───────────────────────────┬─────────────────────────────────────────┘  │
│                               │                                            │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     Motores de Inferência                            │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ NSPInferenceEngine (services/inference.py)                     │  │  │
│  │  │                                                                 │  │  │
│  │  │  Componentes:                    Workflows:                    │  │  │
│  │  │  • CLIP Encoder (OpenAI)         1. Load image                 │  │  │
│  │  │  • PCA Transformer (512→256)     2. Extract CLIP embedding     │  │  │
│  │  │  • EXIF Scaler (StandardScaler)  3. Apply PCA reduction        │  │  │
│  │  │  • LightGBM Models (22x)         4. Normalize EXIF              │  │  │
│  │  │  • PyTorch NN (multi-output)     5. Predict sliders            │  │  │
│  │  │                                  6. Return develop_vector      │  │  │
│  │  │  Artefactos:                                                    │  │  │
│  │  │  - models/pca_model.pkl                                         │  │  │
│  │  │  - models/exif_scaler.pkl                                       │  │  │
│  │  │  - models/slider_*.txt (22 ficheiros)                           │  │  │
│  │  │  - models/ann/multi_output_nn.pth                               │  │  │
│  │  │  - models/targets_mean.npy, targets_std.npy                     │  │  │
│  │  │  - models/model_bundle.lock.json (SHA-256 verification)         │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ CullingEngine (services/culling.py)                            │  │  │
│  │  │  - Modelo: PyTorch binary classifier (keep/reject)             │  │  │
│  │  │  - Input: Image (RAW via rawpy ou JPEG)                        │  │  │
│  │  │  - Output: {keep_probability, predicted_label, probabilities}  │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ StyleProfileEngine (services/profiling.py)                     │  │  │
│  │  │  - Clustering: KMeans ou DBSCAN                                │  │  │
│  │  │  - Input: Embedding (512-dim)                                  │  │  │
│  │  │  - Output: {label, confidence, distance, artifact_path}        │  │  │
│  │  │  - Artefactos: models/profiles/<timestamp>/                    │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ ConsistencyAnalyzer (services/consistency.py)                  │  │  │
│  │  │  - Análise estatística de develop_vectors                      │  │  │
│  │  │  - Métricas: std, outliers, entropy                            │  │  │
│  │  │  - Persistência: consistency_reports table                     │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE DADOS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                 SQLite (data/nsp_plugin.db)                          │  │
│  │                                                                       │  │
│  │  Tabelas:                                                            │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ training_data                                                   │  │  │
│  │  │ ├─ id (INTEGER PRIMARY KEY)                                    │  │  │
│  │  │ ├─ id_local (TEXT UNIQUE)          -- Lightroom UUID           │  │  │
│  │  │ ├─ file_path (TEXT)                -- Caminho original         │  │  │
│  │  │ ├─ develop_vector (TEXT)           -- JSON [22 floats]         │  │  │
│  │  │ ├─ embedding (TEXT)                -- JSON [512 floats]        │  │  │
│  │  │ ├─ exif_iso (INTEGER)                                          │  │  │
│  │  │ ├─ exif_width (INTEGER)                                        │  │  │
│  │  │ ├─ exif_height (INTEGER)                                       │  │  │
│  │  │ └─ created_at (TIMESTAMP)                                      │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ feedback_records                                                │  │  │
│  │  │ ├─ id (INTEGER PRIMARY KEY)                                    │  │  │
│  │  │ ├─ original_record_id (INTEGER)    -- FK: training_data.id    │  │  │
│  │  │ ├─ corrected_develop_vector (TEXT) -- JSON [22 floats]        │  │  │
│  │  │ └─ created_at (TIMESTAMP)                                      │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ profiles                                                        │  │  │
│  │  │ ├─ id (INTEGER PRIMARY KEY)                                    │  │  │
│  │  │ ├─ label (TEXT)                    -- Nome do perfil           │  │  │
│  │  │ ├─ centroid (TEXT)                 -- JSON embedding médio     │  │  │
│  │  │ ├─ cluster_size (INTEGER)                                      │  │  │
│  │  │ └─ created_at (TIMESTAMP)                                      │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │ consistency_reports                                             │  │  │
│  │  │ ├─ report_id (TEXT PRIMARY KEY)    -- UUID                     │  │  │
│  │  │ ├─ collection_name (TEXT)                                      │  │  │
│  │  │ ├─ summary (TEXT)                  -- JSON stats               │  │  │
│  │  │ └─ generated_at (TIMESTAMP)                                    │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │              File System (~/Library/Application Support/NSP)         │  │
│  │                                                                       │  │
│  │  config/                                                             │  │
│  │  └─ nsp_config.json             -- Single source of truth           │  │
│  │                                                                       │  │
│  │  models/                                                             │  │
│  │  ├─ pca_model.pkl                                                    │  │
│  │  ├─ exif_scaler.pkl                                                  │  │
│  │  ├─ slider_*.txt (22 ficheiros LightGBM)                             │  │
│  │  ├─ ann/                                                             │  │
│  │  │  ├─ multi_output_nn.pth                                           │  │
│  │  │  ├─ targets_mean.npy                                              │  │
│  │  │  └─ targets_std.npy                                               │  │
│  │  ├─ profiles/                                                        │  │
│  │  │  └─ <timestamp>/                                                  │  │
│  │  │     ├─ centroids.npy                                              │  │
│  │  │     └─ metadata.json                                              │  │
│  │  └─ model_bundle.lock.json (SHA-256 manifest)                        │  │
│  │                                                                       │  │
│  │  data/                                                               │  │
│  │  ├─ nsp_plugin.db                                                    │  │
│  │  └─ embeddings_manifest.json                                         │  │
│  │                                                                       │  │
│  │  logs/                                                               │  │
│  │  ├─ server_<timestamp>.log                                           │  │
│  │  ├─ pipeline_<timestamp>.log                                         │  │
│  │  └─ control_center.log                                               │  │
│  │                                                                       │  │
│  │  venv/                          -- Python virtual environment        │  │
│  │  tools/                         -- Utility scripts                   │  │
│  │  services/                      -- Server code                       │  │
│  │  train/                         -- Training scripts                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fluxo de Dados: Predição de Sliders

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   LIGHTROOM PLUGIN (Main.lua)                            │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1. User clica "NSP – Get AI Edit"
                                    │
                                    ▼
                          ┌──────────────────┐
                          │ Validações       │
                          │ • Foto selecionada?
                          │ • Path válido?   │
                          └────────┬─────────┘
                                   │
                                   │ 2. Extrair metadados
                                   │
                          ┌────────▼─────────┐
                          │ Preparar payload │
                          │ {                │
                          │   image_path: "/Volumes/Photos/IMG_1234.ARW",
                          │   exif: {        │
                          │     iso: 400,    │
                          │     width: 6000, │
                          │     height: 4000 │
                          │   },             │
                          │   model: "lightgbm" (ou "nn")
                          │ }                │
                          └────────┬─────────┘
                                   │
                                   │ 3. Health check
                                   │
                          ┌────────▼─────────┐
                          │ GET /health      │
                          │ (timeout: 5s)    │
                          └────────┬─────────┘
                                   │
                      ┌────────────┴────────────┐
                      │                         │
                   200 OK?                   TIMEOUT?
                      │                         │
                      │                         ▼
                      │              ┌──────────────────┐
                      │              │ Auto-start server│
                      │              │ (tools/start_server.sh)
                      │              └────────┬─────────┘
                      │                       │
                      │                       │ Retry health check (25s)
                      │                       │
                      │              ┌────────▼─────────┐
                      │              │ Success? → OK    │
                      │              │ Fail? → ERROR    │
                      │              └──────────────────┘
                      │
                      │ 4. POST /predict (JSON)
                      │
┌─────────────────────▼─────────────────────────────────────────────────────┐
│                      FASTAPI SERVER (/predict endpoint)                   │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. Validar payload (Pydantic)                                           │
│     ├─ image_path existe?                                                │
│     └─ exif válido?                                                      │
│                                                                           │
│  2. Materializar input                                                   │
│     ├─ Se image_path: usar direto                                        │
│     └─ Se preview_b64: decode → temp file                                │
│                                                                           │
│  3. Routing por modelo                                                   │
│     ├─ model="lightgbm" → NSPInferenceEngine.predict_lightgbm()          │
│     └─ model="nn"       → NSPInferenceEngine.predict_nn()                │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 5. Inferência
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│              NSPInferenceEngine.predict_lightgbm()                        │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Step 1: Encode Image                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ encode_image(image_path)                                           │  │
│  │ ├─ Load image (PIL ou rawpy)                                       │  │
│  │ ├─ Resize (224x224)                                                │  │
│  │ ├─ CLIP.encode_image() → embedding [512-dim]                       │  │
│  │ └─ PCA.transform(embedding) → reduced [256-dim]                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  Step 2: Prepare Features                                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ exif_features = [iso, width, height]                               │  │
│  │ exif_scaled = exif_scaler.transform(exif_features)                 │  │
│  │ features = concat(embedding_reduced, exif_scaled) → [259-dim]      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  Step 3: Predict Sliders (22x)                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ for slider_name in ALL_SLIDER_NAMES:                               │  │
│  │   model = self.lightgbm_models[slider_name]                        │  │
│  │   prediction = model.predict([features])[0]                        │  │
│  │   sliders[slider_name] = clip(prediction, -100, +100)              │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  Step 4: Return                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ {                                                                   │  │
│  │   "exposure": -0.15,                                                │  │
│  │   "contrast": 12.3,                                                 │  │
│  │   "highlights": -35.0,                                              │  │
│  │   ...  (22 sliders)                                                 │  │
│  │ }                                                                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 6. Serializar response
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                     FastAPI Response (JSON)                               │
│  {                                                                        │
│    "model": "lightgbm",                                                   │
│    "sliders": {                                                           │
│      "exposure": -0.15,                                                   │
│      "contrast": 12.3,                                                    │
│      ...                                                                  │
│    },                                                                     │
│    "cull_score": null                                                     │
│  }                                                                        │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 7. HTTP 200 OK
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                   LIGHTROOM PLUGIN (Main.lua)                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  8. Mapear sliders para Lightroom SDK                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ DEVELOP_MAPPING = {                                                │  │
│  │   exposure      → "Exposure2012",                                  │  │
│  │   contrast      → "Contrast2012",                                  │  │
│  │   highlights    → "Highlights2012",                                │  │
│  │   ...                                                              │  │
│  │ }                                                                   │  │
│  │                                                                     │  │
│  │ developSettings = {}                                                │  │
│  │ for sliderName, value in pairs(sliders):                           │  │
│  │   lrKey = DEVELOP_MAPPING[sliderName]                              │  │
│  │   developSettings[lrKey] = value                                   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  9. Aplicar no Lightroom                                                 │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ catalog:withWriteAccessDo("Aplicar NSP", function()                │  │
│  │   photo:applyDevelopSettings(developSettings)                      │  │
│  │ end)                                                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  10. (Opcional) Auto-feedback                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ if shouldAutoFeedback():                                            │  │
│  │   POST /feedback {                                                  │  │
│  │     original_record_id: photo.localIdentifier,                     │  │
│  │     corrected_develop_vector: collectDevelopVector(photo)          │  │
│  │   }                                                                 │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  11. Mostrar resultado                                                   │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ LrDialogs.message("NSP Plugin", "Ajustes aplicados!", "info")      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Fluxo de Treino End-to-End

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          GRADIO UI (app_ui.py)                           │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1. User upload .lrcat
                                    │
                                    ▼
                          ┌──────────────────┐
                          │ Pipeline Options │
                          │ • Culling: ON/OFF│
                          │ • PCA components │
                          │ • Model: LightGBM│
                          │   + Neural Net   │
                          └────────┬─────────┘
                                   │
                                   │ 2. Click "Executar pipeline completo"
                                   │
                                   ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                       PASSO 1: Extração do Catálogo                       │
│                   (tools/extract_from_lrcat.py)                           │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: /Users/user/Pictures/Lightroom/Catalog.lrcat                     │
│                                                                           │
│  1. Abrir catálogo SQLite (Adobe_images, Adobe_libraryImageDevelopHistoryStep)
│  2. Query: SELECT id_local, absolutePath, develop_settings                │
│  3. Para cada imagem:                                                     │
│     a. Extrair id_local (UUID do Lightroom)                              │
│     b. Construir file_path absoluto (volume + relativePath)              │
│     c. Parsear develop_settings (Lua-like table → JSON)                  │
│     d. Extrair 22 sliders → develop_vector [floats]                      │
│     e. Ler EXIF (ISO, width, height)                                     │
│  4. Inserir em nsp_plugin.db → training_data                             │
│                                                                           │
│  Output:                                                                  │
│  • 850 registos inseridos                                                │
│  • Log: "Extraction complete. 850 images processed."                     │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 3. (Opcional) Passo 2: Culling
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                         PASSO 2: Smart Culling                            │
│                      (tools/run_culling.py)                               │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: training_data (850 registos)                                     │
│  Threshold: 0.4                                                           │
│                                                                           │
│  1. Para cada registo:                                                    │
│     a. CullingEngine.score_image(file_path)                              │
│     b. keep_probability < 0.4? → marcar para remoção                     │
│  2. DELETE FROM training_data WHERE keep_prob < threshold                │
│                                                                           │
│  Output:                                                                  │
│  • 623 imagens mantidas                                                  │
│  • 227 imagens removidas (desfocadas, mal expostas)                      │
│  • Log: "Culling complete. 623 keepers, 227 rejects."                    │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 4. Passo 3: Gerar embeddings
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                    PASSO 3: Geração de Embeddings                         │
│                 (tools/generate_real_embeddings.py)                       │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: training_data (623 registos sem embeddings)                      │
│                                                                           │
│  1. Load CLIP model (OpenAI/ViT-B-32)                                    │
│  2. Para cada registo:                                                    │
│     a. Load image (file_path)                                            │
│     b. Preprocess (resize, normalize)                                    │
│     c. embedding = CLIP.encode_image(image) → [512-dim]                  │
│     d. UPDATE training_data SET embedding = JSON(embedding)              │
│  3. Criar manifesto:                                                      │
│     embeddings_manifest.json = {                                         │
│       "generated_at": "2025-11-09T...",                                  │
│       "clip_model": "ViT-B-32",                                          │
│       "count": 623,                                                      │
│       "ids": [...]                                                       │
│     }                                                                     │
│                                                                           │
│  Output:                                                                  │
│  • 623 embeddings gerados                                                │
│  • Tempo: ~15 min (GPU) ou ~45 min (CPU)                                │
│  • Log: "Embeddings generation complete. 623 images encoded."            │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 5. Passo 4: Preparar features (PCA)
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                      PASSO 4: Preparação de Features                      │
│                     (tools/prepare_features.py)                           │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: training_data (623 registos com embeddings)                      │
│  PCA components: 256                                                      │
│                                                                           │
│  1. Carregar embeddings da DB                                            │
│     embeddings = np.array([JSON.loads(row.embedding) for row in data])  │
│     shape: (623, 512)                                                    │
│                                                                           │
│  2. Treinar PCA                                                           │
│     pca = PCA(n_components=256)                                          │
│     pca.fit(embeddings)                                                  │
│     pickle.dump(pca, 'models/pca_model.pkl')                             │
│                                                                           │
│  3. Treinar EXIF scaler                                                  │
│     exif_data = [[row.exif_iso, row.exif_width, row.exif_height], ...]  │
│     scaler = StandardScaler()                                            │
│     scaler.fit(exif_data)                                                │
│     pickle.dump(scaler, 'models/exif_scaler.pkl')                        │
│                                                                           │
│  Output:                                                                  │
│  • models/pca_model.pkl (PCA 512→256)                                    │
│  • models/exif_scaler.pkl (StandardScaler)                               │
│  • Log: "Feature preparation complete. PCA variance: 95.3%"              │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 6. Passo 5: Treinar LightGBM
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                       PASSO 5: Treino LightGBM                            │
│                      (train/train_sliders.py)                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: training_data (623 registos)                                     │
│  Sliders: 22                                                              │
│                                                                           │
│  1. Preparar dataset                                                      │
│     X = PCA.transform(embeddings) + scaler.transform(exif)               │
│     y = develop_vectors (623, 22)                                        │
│     train_test_split (80/20)                                             │
│                                                                           │
│  2. Para cada slider (22x):                                              │
│     a. y_train = y_train[:, slider_idx]                                  │
│     b. lgbm_model = lgb.LGBMRegressor(                                   │
│          num_leaves=31,                                                  │
│          learning_rate=0.05,                                             │
│          n_estimators=200                                                │
│        )                                                                  │
│     c. lgbm_model.fit(X_train, y_train)                                  │
│     d. lgbm_model.booster_.save_model(f'models/slider_{name}.txt')      │
│                                                                           │
│  3. Atualizar manifesto                                                  │
│     model_bundle.lock.json:                                              │
│       {                                                                   │
│         "schema_version": 1,                                             │
│         "bundle_version": "1.0.0",                                       │
│         "trained_at": "2025-11-09T...",                                  │
│         "files": [                                                        │
│           {"path": "models/slider_exposure.txt", "sha256": "abc..."},    │
│           ...  (22 sliders + PCA + scaler)                               │
│         ]                                                                 │
│       }                                                                   │
│                                                                           │
│  Output:                                                                  │
│  • models/slider_*.txt (22 ficheiros)                                    │
│  • models/model_bundle.lock.json (updated)                               │
│  • Log: "LightGBM training complete. 22 models saved."                   │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 7. Passo 6: Avaliar LightGBM
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                      PASSO 6: Avaliação LightGBM                          │
│                    (train/evaluate_models.py)                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: Test set (20% de 623 = ~125 imagens)                            │
│                                                                           │
│  1. Para cada slider (22x):                                              │
│     a. model = lgb.Booster(model_file=f'models/slider_{name}.txt')      │
│     b. y_pred = model.predict(X_test)                                    │
│     c. y_true = y_test[:, slider_idx]                                    │
│     d. mae = mean_absolute_error(y_true, y_pred)                         │
│     e. Log: f"Slider '{name}': MAE = {mae:.2f}"                          │
│                                                                           │
│  2. Overall MAE:                                                          │
│     overall_mae = mean([mae_exposure, mae_contrast, ...])                │
│     Log: f"Overall Mean Absolute Error: {overall_mae:.2f}"               │
│                                                                           │
│  Output (Gradio table):                                                  │
│  ┌───────────────┬─────────┬──────┐                                      │
│  │ Modelo        │ Slider  │ MAE  │                                      │
│  ├───────────────┼─────────┼──────┤                                      │
│  │ LightGBM      │ exposure│ 0.18 │                                      │
│  │ LightGBM      │ contrast│ 8.34 │                                      │
│  │ LightGBM      │ ...     │ ...  │                                      │
│  └───────────────┴─────────┴──────┘                                      │
│  Overall: 16.50                                                           │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 8. (Opcional) Passo 8: Treinar Neural Network
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                   PASSO 8: Treino Rede Neural                             │
│                    (train/ann/train_nn.py)                                │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: training_data (623 registos)                                     │
│                                                                           │
│  1. Preparar dataset (igual ao LightGBM)                                 │
│  2. Normalizar targets                                                   │
│     targets_mean = y_train.mean(axis=0)                                  │
│     targets_std = y_train.std(axis=0)                                    │
│     y_train_normalized = (y_train - targets_mean) / targets_std          │
│                                                                           │
│  3. Definir arquitetura                                                  │
│     class MultiOutputNN(nn.Module):                                      │
│       def __init__(self):                                                │
│         self.fc1 = nn.Linear(259, 512)  # input_dim = 256 (PCA) + 3 (EXIF)
│         self.fc2 = nn.Linear(512, 256)                                   │
│         self.fc3 = nn.Linear(256, 22)   # 22 sliders                     │
│       def forward(self, x):                                              │
│         x = F.relu(self.fc1(x))                                          │
│         x = F.relu(self.fc2(x))                                          │
│         return self.fc3(x)                                               │
│                                                                           │
│  4. Treinar                                                              │
│     optimizer = Adam(lr=0.001)                                           │
│     loss_fn = MSELoss()                                                  │
│     for epoch in range(100):                                             │
│       for batch in train_loader:                                         │
│         optimizer.zero_grad()                                            │
│         preds = model(batch_X)                                           │
│         loss = loss_fn(preds, batch_y)                                   │
│         loss.backward()                                                  │
│         optimizer.step()                                                 │
│                                                                           │
│  5. Guardar artefactos                                                   │
│     torch.save(model.state_dict(), 'models/ann/multi_output_nn.pth')    │
│     np.save('models/targets_mean.npy', targets_mean)                     │
│     np.save('models/targets_std.npy', targets_std)                       │
│                                                                           │
│  Output:                                                                  │
│  • models/ann/multi_output_nn.pth                                        │
│  • models/targets_mean.npy, targets_std.npy                              │
│  • Log: "Neural Network training complete. Epochs: 100, Final loss: 0.45"│
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 9. Passo 9: Avaliar Neural Network
                        │
┌───────────────────────▼───────────────────────────────────────────────────┐
│                   PASSO 9: Avaliação Rede Neural                          │
│                    (train/ann/evaluate_nn.py)                             │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Processo idêntico ao Passo 6, mas com:                                  │
│  • model = MultiOutputNN()                                               │
│  • model.load_state_dict(torch.load('models/ann/multi_output_nn.pth'))  │
│  • Denormalizar predições: y_pred * targets_std + targets_mean           │
│                                                                           │
│  Output (Gradio table):                                                  │
│  Overall MAE: 34.35                                                       │
│                                                                           │
└───────────────────────┬───────────────────────────────────────────────────┘
                        │
                        │ 10. Pipeline Complete
                        │
                        ▼
                  ┌────────────┐
                  │ Gradio UI  │
                  │ "PIPELINE  │
                  │  COMPLETO  │
                  │ FINALIZADO"│
                  └────────────┘
```

---

## 4. Diagrama de Estado: Lifecycle do Servidor

```
                         ┌──────────────┐
                         │   STOPPED    │
                         │              │
                         │ • Process=None
                         │ • Port livre │
                         └───────┬──────┘
                                 │
                                 │ Trigger:
                                 │ • Control Center → "Start Server"
                                 │ • Plugin Lua → Auto-start
                                 │
                                 ▼
                         ┌──────────────┐
                         │   STARTING   │
                         │              │
                         │ • spawn_server_process()
                         │ • Health checks iniciados
                         └───────┬──────┘
                                 │
                    ┌────────────┼────────────┐
                    │                         │
               Health OK?                Health TIMEOUT?
                    │                         │
                    ▼                         ▼
            ┌──────────────┐          ┌──────────────┐
            │   RUNNING    │          │    FAILED    │
            │              │          │              │
            │ • GET /health = 200     │ • Retry 3x?  │
            │ • Process alive         │ • Log error  │
            │ • Port occupied         │ • Cleanup    │
            └───────┬──────┘          └──────┬───────┘
                    │                        │
                    │                        │ Retry
                    │                        └─────────────┐
                    │                                      │
                    │ Triggers:                            ▼
                    │ • POST /predict                ┌──────────────┐
                    │ • POST /feedback               │  RESTARTING  │
                    │ • ...                          │              │
                    │                                │ • Kill process
                    │ Error?                         │ • Re-spawn   │
                    │                                └──────────────┘
                    ▼                                      │
            ┌──────────────┐                              │
            │  DEGRADED    │                              │
            │              │                              │
            │ • Some endpoints fail                       │
            │ • Fallback active         ◄─────────────────┘
            │ • Warning logs            │
            └───────┬──────┘            │
                    │                   │
                    │ Auto-recover?     │
                    │                   │
         ┌──────────┴──────────┐        │
         │                     │        │
        YES                   NO        │
         │                     │        │
         ▼                     ▼        │
   ┌──────────────┐    ┌──────────────┐│
   │   RUNNING    │    │   SHUTDOWN   ││
   │  (recovered) │    │              ││
   │              │    │ • Graceful   ││
   │ • Logs:      │    │   cleanup    ││
   │   "Recovered │    │ • Close DB   ││
   │    from      │    │ • Kill child ││
   │    degraded" │    │   processes  ││
   └──────────────┘    └──────┬───────┘│
         │                    │        │
         │                    ▼        │
         │             ┌──────────────┐│
         │             │   STOPPED    ││
         │             └──────────────┘│
         │                             │
         └─────────────────────────────┘
```

---

## 5. Entity-Relationship Diagram (SQLite)

```
┌─────────────────────────────────────────────┐
│           training_data                     │
├─────────────────────────────────────────────┤
│ PK  id                INTEGER               │
│ UQ  id_local          TEXT                  │
│     file_path         TEXT                  │
│     develop_vector    TEXT (JSON [22])      │
│     embedding         TEXT (JSON [512])     │
│     exif_iso          INTEGER               │
│     exif_width        INTEGER               │
│     exif_height       INTEGER               │
│     created_at        TIMESTAMP             │
│     updated_at        TIMESTAMP             │
└──────────────┬──────────────────────────────┘
               │
               │ 1
               │
               │ N
               ▼
┌─────────────────────────────────────────────┐
│         feedback_records                    │
├─────────────────────────────────────────────┤
│ PK  id                     INTEGER          │
│ FK  original_record_id     INTEGER ────┐    │
│     corrected_develop_vector TEXT (JSON)│   │
│     created_at             TIMESTAMP    │    │
└─────────────────────────────────────────┼────┘
                                          │
                                          │ References
                                          └─► training_data.id


┌─────────────────────────────────────────────┐
│              profiles                       │
├─────────────────────────────────────────────┤
│ PK  id                INTEGER               │
│     label             TEXT                  │
│     centroid          TEXT (JSON [512])     │
│     cluster_size      INTEGER               │
│     metadata          TEXT (JSON)           │
│     created_at        TIMESTAMP             │
└─────────────────────────────────────────────┘


┌─────────────────────────────────────────────┐
│       consistency_reports                   │
├─────────────────────────────────────────────┤
│ PK  report_id         TEXT (UUID)           │
│     collection_name   TEXT                  │
│     summary           TEXT (JSON)           │
│     generated_by      TEXT                  │
│     generated_at      TIMESTAMP             │
└─────────────────────────────────────────────┘
```

---

## 6. Deployment Architecture (Target)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER MACHINE (macOS)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  /Applications/                                                         │
│  └─ NSP Control Center.app                                             │
│     ├─ Contents/                                                        │
│     │  ├─ MacOS/nsp-control-center (Tauri binary)                      │
│     │  └─ Resources/                                                    │
│     │     ├─ index.html, main.js (frontend)                            │
│     │     └─ icon.icns                                                  │
│     └─ [Code-signed + Notarized]                                       │
│                                                                         │
│  ~/Library/Application Support/NSP/                                    │
│  ├─ bin/                                                                │
│  │  └─ nsp-engine (PyInstaller bundle ou Conda env)                   │
│  ├─ config/                                                             │
│  │  └─ nsp_config.json                                                 │
│  ├─ models/                                                             │
│  │  ├─ pca_model.pkl                                                   │
│  │  ├─ exif_scaler.pkl                                                 │
│  │  ├─ slider_*.txt (22)                                               │
│  │  ├─ ann/multi_output_nn.pth                                         │
│  │  └─ model_bundle.lock.json                                          │
│  ├─ data/                                                               │
│  │  ├─ nsp_plugin.db                                                   │
│  │  └─ embeddings_manifest.json                                        │
│  ├─ logs/                                                               │
│  │  ├─ server.log                                                      │
│  │  ├─ control_center.log                                              │
│  │  └─ plugin.log                                                      │
│  └─ cache/                                                              │
│     └─ embeddings/ (hash-based cache)                                  │
│                                                                         │
│  ~/Documents/NSP Plugin.lrplugin (symlink)                             │
│  → ~/Library/Application Support/NSP/NSP-Plugin.lrplugin               │
│                                                                         │
│  ~/Library/Application Support/Adobe/Lightroom/Modules/                │
│  └─ NSP-Plugin.lrplugin (installed via Plugin Manager)                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Error Recovery Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        ERROR DETECTION                                   │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Error Type Detection  │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ SERVER_DOWN     │   │ MODEL_MISSING   │   │ DB_CORRUPTED    │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         ▼                     ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ RECOVERY ACTION │   │ RECOVERY ACTION │   │ RECOVERY ACTION │
│                 │   │                 │   │                 │
│ 1. Auto-start   │   │ 1. Download     │   │ 1. Backup DB    │
│    attempt      │   │    pre-trained  │   │ 2. Recreate     │
│ 2. Wait 30s     │   │ 2. Prompt user  │   │    schema       │
│ 3. Retry (3x)   │   │    to retrain   │   │ 3. Restore data │
│ 4. Fallback:    │   │ 3. Fallback:    │   │ 4. Re-index     │
│    - Use        │   │    - Use default│   │                 │
│      preset     │   │      LR preset  │   │                 │
│    - Show       │   │    - Disable    │   │                 │
│      manual     │   │      AI features│   │                 │
│      start      │   │                 │   │                 │
│      guide      │   │                 │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                      │
         └──────────────────┬──┴──────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ LOG ERROR + CONTEXT   │
                │                       │
                │ • Error type          │
                │ • Stack trace         │
                │ • System info         │
                │ • Recovery attempt    │
                │ • Correlation ID      │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ NOTIFY USER           │
                │                       │
                │ • Clear message       │
                │ • Action buttons      │
                │ • Link to docs        │
                │ • Support ticket      │
                └───────────────────────┘
```
