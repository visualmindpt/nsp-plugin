# NSP Plugin Inference Server - Exhaustive Test Report

**Date**: 2025-11-10
**Server**: NSP Plugin Inference Server (services/server.py)
**Port**: 5678 (correct port for NSP inference)
**Tester**: Claude Code AI Assistant

---

## Executive Summary

**STATUS**: CRITICAL FAILURE - Server cannot start
**Root Cause**: Segmentation Fault (Exit 139) during CLIP model loading
**Impact**: Complete service outage - no endpoints accessible
**Priority**: P0 - BLOCKING

---

## Test Results Overview

| Test Category | Status | Details |
|--------------|--------|---------|
| Server Connection | FAILED | Process crashes during startup |
| Health Endpoint | NOT TESTED | Server doesn't start |
| Predict Endpoint | NOT TESTED | Server doesn't start |
| Model Files | PARTIAL | Some models found, 12/22 sliders missing |
| Database | SUCCESS | Found and accessible |
| Error Handling | NOT TESTED | Server doesn't start |
| Rate Limiting | NOT TESTED | Server doesn't start |

---

## Detailed Findings

### 1. CRITICAL: Server Startup Failure

**Issue**: Segmentation Fault (Exit Code 139)

```
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
2025-11-10 11:07:57,757 - INFO - Use pytorch device_name: mps
[CRASH - Exit 139]
```

**Timeline**:
1. Server process starts successfully
2. Database initialization completes
3. CLIP model loading begins
4. PyTorch attempts to use MPS (Apple Metal) backend
5. **SEGMENTATION FAULT** - immediate crash

**Attempted Fixes**:
- Set environment variables (`PYTORCH_ENABLE_MPS_FALLBACK=1`)
- Modified code to force CPU device in `NSPInferenceEngine.__init__()`
- Modified code to force CPU device in `SentenceTransformer` calls
- **All attempts failed** - crash persists even with CPU forced

**Root Cause Analysis**:
The crash occurs when loading the CLIP Vision Transformer model from HuggingFace transformers library. This is a known issue with:
- PyTorch 2.2.0 + transformers + sentence-transformers
- macOS with MPS backend
- Specific CLIP model architecture

Even when forcing CPU, the crash persists because the transformers library may still attempt MPS operations during model initialization before the device parameter takes effect.

**Error Traceback**:
```
Using a slow image processor as `use_fast` is unset...
[Segmentation Fault - no Python traceback, crash at C++ level]
```

---

### 2. Model Inventory

#### LightGBM Slider Models

**Location**: `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/models/`

**Found (10/22):**
1. slider_blacks.txt (791 KB)
2. slider_clarity.txt (791 KB)
3. slider_contrast.txt (790 KB)
4. slider_dehaze.txt (4.7 KB)
5. slider_exposure.txt (798 KB)
6. slider_grain.txt (790 KB)
7. slider_highlights.txt (781 KB)
8. slider_nr_color.txt (4.7 KB)
9. slider_nr_detail.txt (4.7 KB)
10. slider_nr_luminance.txt (4.7 KB)

**MISSING (12/22):**
- slider_shadows.txt
- slider_whites.txt
- slider_texture.txt
- slider_vibrance.txt
- slider_saturation.txt
- slider_temp.txt (temperature)
- slider_tint.txt
- slider_sharpen_amount.txt
- slider_sharpen_radius.txt
- slider_sharpen_detail.txt
- slider_sharpen_masking.txt
- slider_vignette.txt

**Impact**: Even if server starts, predictions would be incomplete (only 10/22 sliders available)

#### Support Files

**Found**:
- pca_model.pkl (71 KB) - PCA for embedding dimensionality reduction
- exif_scaler.pkl (655 bytes) - StandardScaler for EXIF normalization
- model_bundle.lock.json (5.5 KB) - Model manifest/metadata

#### Neural Network Model

**Found**:
- ann/multi_output_nn.pth (exists, size not verified)

#### CLIP Embedding Model

**Found**:
- clip-ViT-B-32/models--sentence-transformers--clip-ViT-B-32/snapshots/.../0_CLIPModel/model.safetensors
- clip-ViT-B-32/models--sentence-transformers--clip-ViT-B-32/snapshots/.../0_CLIPModel/pytorch_model.bin

**Status**: Model files exist but **CRASH when loading**

#### Smart Culling Model

**Found**:
- culling_model.pth (81.8 MB)

---

### 3. Database Status

**Location**: `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/data/nsp_plugin.db`

**Status**: OPERATIONAL

**Details**:
- Size: ~88 KB
- WAL mode: Enabled (good for concurrency)
- Tables found: training_data, feedback_records (and others)
- Training records: Count available (varies)
- Feedback records: Table exists

**Issues Detected**:
```
WARNING - Falha ao criar índice: no such column: id_local
WARNING - Falha ao criar índice: no such column: created_at
```

**Impact**: Performance indexes could not be created due to missing columns. This doesn't block startup but may impact query performance.

**Recommendation**: Verify database schema matches expected structure from `tools/extract_from_lrcat.py`

---

### 4. API Endpoints (Design Review)

**Base URL**: http://127.0.0.1:5678

The following endpoints SHOULD be available (if server starts):

#### Core Endpoints
- `GET /health` - Health check and model status
- `POST /predict` - Main inference (LightGBM or NN)
- `POST /feedback` - Submit feedback for single image
- `POST /feedback/bulk` - Bulk feedback submission

#### Advanced Endpoints (ViLearnStyle AI)
- `POST /culling/score` - Smart culling batch scoring
- `POST /profiles/assign` - Auto-profiling style assignment
- `POST /consistency/report` - Consistency analysis

#### Security Features
- Rate limiting configured:
  - `/predict`: 10 requests/minute
  - `/feedback`: 30 requests/minute
  - `/culling/score`: 5 requests/minute
- Localhost-only binding (127.0.0.1)
- Path validation and sanitization
- MIME type checking
- Base64 payload size limits (50MB)

**Status**: Unable to test - server doesn't start

---

### 5. Test Scripts Created

**Files Created**:
1. `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/test_inference_server.py`
   - Comprehensive test suite for all endpoints
   - Error handling validation
   - Rate limiting tests
   - **Ready to run** once server is fixed

2. `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/diagnostic_report.md`
   - Detailed diagnostic findings
   - Architecture analysis
   - Fix recommendations

3. `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/start_server_cpu.sh`
   - Safe startup script (attempted CPU forcing)
   - **Did not resolve crash**

4. `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/run_server_safe.py`
   - Python startup with monkey-patching
   - **Did not resolve crash**

---

## Recommendations (Prioritized)

### CRITICAL Priority (P0) - Fix Server Crash

**Option 1: Downgrade PyTorch/Transformers (Fastest)**
```bash
cd /Users/nelsonsilva/Documentos/gemini/projetos/NSP\ Plugin_dev_full_package
source venv/bin/activate
pip install torch==2.0.1 torchvision==0.15.2
pip install transformers==4.30.0 sentence-transformers==2.2.2
```

**Option 2: Use Pre-encoded Embeddings**
Since training data likely already has embeddings in the database, modify code to skip CLIP loading:
- Check if `training_data` table has `embedding` column populated
- Modify `/predict` endpoint to require embeddings from client
- Only load CLIP when absolutely necessary

**Option 3: Convert to ONNX Runtime**
Export CLIP model to ONNX format which has better macOS compatibility:
```bash
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('clip-ViT-B-32')
model.save('models/clip-onnx', create_model_card=False)
# Then convert to ONNX with optimum library
"
```

**Option 4: Docker Container**
Run server in Docker to isolate from macOS-specific issues:
```bash
docker run -p 5678:5678 -v $(pwd)/models:/app/models python:3.11-slim
# Install deps and run server
```

**IMMEDIATE WORKAROUND**: Use existing embeddings from database if available. Check:
```bash
sqlite3 data/nsp_plugin.db "SELECT COUNT(*) FROM training_data WHERE embedding IS NOT NULL"
```

### HIGH Priority (P1) - Train Missing Slider Models

**Missing Models**: 12 out of 22 sliders

**Action Required**:
```bash
cd /Users/nelsonsilva/Documentos/gemini/projetos/NSP\ Plugin_dev_full_package
source venv/bin/activate
python train/train_sliders.py
```

**Prerequisites**:
- Valid training data in database
- Embeddings already generated
- EXIF data normalized

**Expected Output**: 22 LightGBM models (one per slider)

### MEDIUM Priority (P2) - Fix Database Schema

**Issue**: Missing columns preventing index creation

**Investigation**:
```bash
sqlite3 data/nsp_plugin.db
.schema training_data
# Check if id_local and created_at columns exist
```

**Fix** (if columns missing):
```sql
ALTER TABLE training_data ADD COLUMN id_local TEXT;
ALTER TABLE training_data ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_id_local ON training_data(id_local);
CREATE INDEX IF NOT EXISTS idx_created_at ON training_data(created_at);
```

### LOW Priority (P3) - Dependency Warnings

**Issue**: LibreSSL vs OpenSSL warning

**Fix**:
```bash
brew install openssl@3
pip install --upgrade --force-reinstall urllib3 requests
```

---

## Code Changes Made

### File: `services/inference.py`

**Lines 113-116** (Added):
```python
# FORCE CPU to avoid MPS segmentation fault on macOS
self.device = torch.device("cpu")
if device and device != "cpu":
    logging.warning(f"Requested device '{device}' but forcing CPU to avoid MPS crashes")
```

**Lines 178, 190** (Added):
```python
device='cpu',  # Force CPU to avoid MPS crashes
```

**Result**: Did not prevent crash (issue is deeper in transformers library)

---

## Environment Information

**System**:
- OS: macOS (Darwin 24.6.0)
- Working Directory: `/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package`
- Python: 3.9 (venv)

**Dependencies** (Key):
- PyTorch: 2.2.0
- transformers: (version in venv)
- sentence-transformers: (version in venv)
- FastAPI: (version in venv)
- LightGBM: (version in venv)

**Hardware**:
- Apple Silicon (MPS available)
- MPS built: True

---

## Comparison: NSP Inference Server vs Licensing Server

| Aspect | NSP Inference | Licensing |
|--------|--------------|-----------|
| **Port** | 5678 | 8080 |
| **Purpose** | AI predictions | License management |
| **Location** | services/server.py | licensing/server.py |
| **Status** | CRASHED | Unknown (not tested) |
| **Database** | nsp_plugin.db | nsp_licensing.db |
| **Models** | LightGBM, NN, CLIP | None |
| **Endpoints** | /predict, /feedback, /culling | /activate, /validate, /heartbeat |

**Note**: The licensing server (port 8080) was not tested in this report. A separate test exists at `licensing/test_server_exhaustive.py`.

---

## Next Steps

### Immediate (Today)
1. Try downgrading PyTorch/transformers (Option 1 above)
2. Test if server starts successfully
3. Run `test_inference_server.py` comprehensive test suite
4. Document results

### Short-term (This Week)
1. Train missing 12 slider models
2. Fix database schema issues
3. Verify all endpoints with real image data
4. Performance benchmarking

### Long-term (This Month)
1. Implement ONNX conversion for better macOS compatibility
2. Add monitoring and observability
3. Create Docker deployment option
4. Write user documentation

---

## Test Execution Log

```
2025-11-10 11:06:00 - Started server test
2025-11-10 11:06:05 - Server startup initiated
2025-11-10 11:06:50 - Server process running (PID: 31844)
2025-11-10 11:07:00 - Waiting for health endpoint...
2025-11-10 11:07:10 - Connection refused (server still starting)
2025-11-10 11:07:20 - Connection refused (server still loading models)
2025-11-10 11:07:40 - CRASH DETECTED (Exit 139 - Segmentation Fault)
2025-11-10 11:07:50 - Attempt 1: Force CPU via environment variables - FAILED
2025-11-10 11:09:00 - Attempt 2: Force CPU via code modification - FAILED
2025-11-10 11:10:00 - Attempt 3: Monkey-patch torch.device - FAILED (broke isinstance)
2025-11-10 11:11:25 - Attempt 4: Background process with logging - CRASHED after ~15s
2025-11-10 11:12:00 - Conclusion: CLIP model loading incompatible with current environment
```

---

## Files Reference

**Test Scripts**:
- test_inference_server.py - Comprehensive endpoint tests (ready to run)
- test_server_exhaustive.py (licensing) - Licensing server tests

**Documentation**:
- EXHAUSTIVE_TEST_REPORT.md (this file)
- diagnostic_report.md - Technical diagnostic
- CLAUDE.md - Project architecture guide
- REAL_DATA_TRAINING_GUIDE.md - Training best practices

**Server Files**:
- services/server.py - NSP inference server (port 5678)
- licensing/server.py - License server (port 8080)
- services/inference.py - ML inference engine

**Model Files**:
- models/slider_*.txt - LightGBM models (10/22 found)
- models/ann/multi_output_nn.pth - Neural network
- models/clip-ViT-B-32/ - CLIP embeddings (CRASHES)
- models/culling_model.pth - Smart culling

---

## Support Contacts

**Project**: NSP Plugin (ViLearnStyle AI)
**Documentation**: See `docs/` directory
**Issues**: Review `docs/STATUS.md` for known issues

---

**Report Generated**: 2025-11-10 11:12:00
**Report Author**: Claude Code (Anthropic AI Assistant)
**Report Type**: Exhaustive Server Testing
**Report Status**: COMPLETE

---

## Appendix A: Expected Successful Responses

### Health Endpoint (when working)
```json
{
  "status": "ok",
  "models": {
    "lightgbm": true,
    "nn": true
  },
  "artifacts_dir": "/path/to/models"
}
```

### Predict Endpoint (when working)
```json
{
  "model": "lightgbm",
  "sliders": {
    "exposure": 0.5,
    "contrast": 10.0,
    "highlights": -20.0,
    "shadows": 15.0,
    ... (22 total sliders)
  },
  "cull_score": null
}
```

### Error Response (expected)
```json
{
  "detail": "Error message here"
}
```

---

**END OF REPORT**
