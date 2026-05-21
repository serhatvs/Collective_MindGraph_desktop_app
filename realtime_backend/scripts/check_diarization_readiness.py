"""
Check readiness for real local speaker diarization (Pyannote).
Verifies library installation, local model path, and offline loading.
"""

import os
import sys
import importlib
from pathlib import Path

def main():
    print("--- Collective MindGraph Diarization Readiness Check ---")
    
    enabled = os.getenv("CMG_RT_DIARIZATION_ENABLED", "false").lower() == "true"
    provider = os.getenv("CMG_RT_DIARIZER_PROVIDER", "pyannote")
    model_name = os.getenv("CMG_RT_DIARIZER_MODEL", "pyannote/speaker-diarization-3.1")
    allow_download = os.getenv("CMG_RT_ALLOW_REMOTE_DOWNLOAD", "false").lower() == "true"
    
    print(f"Diarization Enabled: {enabled}")
    print(f"Provider: {provider}")
    print(f"Model Name/Path: {model_name}")
    print(f"Allow Remote Download: {allow_download}")

    if not enabled:
        print("\n❌ STATUS: NOT ENABLED (Default Roadmap state)")
        return

    # Check for libraries
    missing_libs = []
    for lib in ["torch", "pyannote.audio"]:
        try:
            importlib.import_module(lib)
            print(f"✅ Library '{lib}' found.")
        except ImportError:
            missing_libs.append(lib)
            print(f"❌ Library '{lib}' missing.")

    if missing_libs:
        print(f"\n❌ STATUS: DEPENDENCY_MISSING ({', '.join(missing_libs)})")
        return

    # Check model path if it's an absolute path
    if os.path.isabs(model_name):
        if Path(model_name).exists():
            print("✅ Local model path exists.")
        else:
            print(f"❌ Local model path does not exist: {model_name}")
            print("\n❌ STATUS: MISSING_MODEL")
            return
    else:
        print("⚠️ Model name is not an absolute path. Pyannote usually expects a HF repo ID or a local path.")
        if not allow_download:
            print("⚠️ Since allow_download is False, Pyannote must find this model in its local cache.")

    # Try loading the pipeline (HEAVY)
    print("Attempting to load Pyannote pipeline (this may take a moment)...")
    try:
        from pyannote.audio import Pipeline
        # Note: loading might still try to hit HF for config.yaml if not fully local
        pipeline = Pipeline.from_pretrained(model_name, use_auth_token=os.getenv("CMG_RT_PYANNOTE_TOKEN"))
        if pipeline:
            print("✅ Diarization pipeline loaded successfully.")
            print("\n✅ STATUS: ACTIVE")
        else:
            print("❌ Pipeline failed to initialize.")
            print("\n❌ STATUS: CONFIG_ERROR")
    except Exception as e:
        print(f"❌ Failed to load diarization model: {e}")
        print("\n❌ STATUS: UNAVAILABLE (Requires manual model cache or valid token)")

if __name__ == "__main__":
    main()
