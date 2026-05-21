"""
Check readiness for real local semantic retrieval.
Verifies local embedding model configuration, library availability, and offline safety.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add src to path for repository access
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

def main():
    print("--- Collective MindGraph Semantic Readiness Check ---")
    
    enabled = os.getenv("CMG_EMBEDDINGS_ENABLED", "true").lower() == "true"
    provider = os.getenv("CMG_EMBEDDING_PROVIDER", "mock")
    model_path = os.getenv("CMG_EMBEDDING_MODEL_PATH", "")
    allow_download = os.getenv("CMG_ALLOW_REMOTE_MODEL_DOWNLOAD", "false").lower() == "true"
    db_path = os.getenv("CMG_RT_DATA_DIR", "realtime_backend_data") + "/collective_mindgraph.sqlite3"
    
    print(f"Configured Provider: {provider}")
    print(f"Embeddings Enabled: {enabled}")
    print(f"Model Path: {model_path or '(empty)'}")
    print(f"Allow Remote Download: {allow_download}")

    if not enabled:
        print("\n❌ STATUS: DISABLED")
        return

    # Check Vector Store Reachability
    vector_count = 0
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT COUNT(*) FROM v2_embeddings").fetchone()
            vector_count = row[0] if row else 0
            conn.close()
            print(f"✅ Vector Store reachable. Count: {vector_count}")
        except Exception as e:
            print(f"⚠️ Vector Store check failed: {e}")
    else:
        print(f"⚠️ Vector Store not found at {db_path} (Empty index)")

    if provider == "mock":
        print(f"Vector Count: {vector_count}")
        print("Semantic Usable: Yes (Mock)")
        print("\n⚠️ STATUS: MOCK_ONLY")
        return

    # Check for library
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ Library 'sentence-transformers' installed.")
    except ImportError:
        print("❌ Library 'sentence-transformers' missing. Run 'pip install sentence-transformers'.")
        print("\n❌ STATUS: DEPENDENCY_MISSING")
        return

    # Check for model path
    if not model_path:
        print("❌ CMG_EMBEDDING_MODEL_PATH is not set.")
        print("\n❌ STATUS: MISSING_MODEL")
        return

    p = Path(model_path)
    if not p.exists():
        print(f"❌ Model path does not exist: {model_path}")
        print("\n❌ STATUS: MISSING_MODEL - configure valid local embedding model path")
        return

    print("✅ Local embedding model files found.")
    
    # Try loading and dimension detection
    try:
        model = SentenceTransformer(model_path, local_files_only=not allow_download)
        dimension = model.get_sentence_embedding_dimension()
        print(f"✅ Model loaded successfully. Dimension: {dimension}")
        print(f"Vector Count: {vector_count}")
        print("Semantic Usable: Yes")
        print("\n✅ STATUS: REAL_ACTIVE")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        print("\n❌ STATUS: CONFIG_ERROR - model loading failed")

if __name__ == "__main__":
    main()
