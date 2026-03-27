#!/usr/bin/env python3
"""
NSP Plugin Server - GPU Mode Launcher

This script starts the inference server and allows it to use the
best available device, including MPS on Apple Silicon for GPU acceleration.
"""
import os
import sys
import uvicorn
from pathlib import Path

if __name__ == "__main__":
    # Change to project root to ensure all modules are found
    project_root = Path(__file__).parent
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))

    print("=" * 70)
    print("NSP Plugin Inference Server - GPU Mode")
    print("=" * 70)
    print("Starting server on http://127.0.0.1:5678")
    print("Attempting to use best available device (CPU or GPU/MPS)...")
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
