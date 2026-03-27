#!/usr/bin/env python3
"""
Safe server startup script that forces CPU backend to avoid MPS crashes.
"""
import os
import sys

# CRITICAL: Set this BEFORE importing torch/transformers
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO'] = '0.0'

# This script forces CPU to avoid MPS crashes during inference.
import torch

# Also monkey-patch sentence_transformers device selection
def patch_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer
        original_init = SentenceTransformer.__init__

        def patched_init(self, *args, **kwargs):
            # Force device to CPU
            kwargs['device'] = 'cpu'
            print("INFO: SentenceTransformer forced to use CPU device")
            return original_init(self, *args, **kwargs)

        SentenceTransformer.__init__ = patched_init
    except ImportError:
        pass

patch_sentence_transformers()

# Now safe to import and run server
if __name__ == "__main__":
    import uvicorn
    from pathlib import Path

    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))

    print("=" * 70)
    print("NSP Plugin Inference Server - Safe CPU Mode")
    print("=" * 70)
    print("Starting server on http://127.0.0.1:5678")
    print("Using CPU backend (MPS disabled to prevent segmentation faults)")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    uvicorn.run(
        "services.server:app",
        host="127.0.0.1",
        port=5678,
        reload=False,
        log_level="info"
    )
