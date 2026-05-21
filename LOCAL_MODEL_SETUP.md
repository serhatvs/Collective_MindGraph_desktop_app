# LOCAL_MODEL_SETUP.md

## Collective MindGraph: Local AI Model Setup Guide

To transition from the **MOCK/FALLBACK** state to a **REAL_ACTIVE** local AI runtime, follow these steps to configure your local models and endpoints.

### 1. Semantic Memory (Local Embeddings)

Collective MindGraph uses `sentence-transformers` for conceptual memory retrieval.

#### Recommended Model
- **Name**: `paraphrase-multilingual-MiniLM-L12-v2`
- **Why**: Excellent Turkish support, fast CPU inference, small memory footprint (~470MB).

#### Setup Steps
1.  **Install Library**:
    ```bash
    pip install sentence-transformers
    ```
2.  **Download Model**:
    Go to [Hugging Face](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2) and download the model files to a local folder (e.g., `models/embedding-model`).
3.  **Configure Environment**:
    Set these variables in your `.env` file:
    ```bash
    CMG_EMBEDDINGS_ENABLED=true
    CMG_EMBEDDING_PROVIDER=sentence_transformers
    CMG_EMBEDDING_MODEL_PATH=/absolute/path/to/models/embedding-model
    CMG_EMBEDDING_DIMENSION=384
    CMG_ALLOW_REMOTE_MODEL_DOWNLOAD=false
    ```
4.  **Verify**:
    ```bash
    PYTHONPATH=src:. realtime_backend/.venv/bin/python3 realtime_backend/scripts/check_semantic_readiness.py
    ```
    **Expected Status**: `✅ STATUS: REAL_ACTIVE`

---

### 2. Local AI Layer (LLM Extraction)

Collective MindGraph requires an OpenAI-compatible local endpoint for structured knowledge extraction.

#### Chosen Runtime: **LM Studio**
- **Why**: Superior support for GGUF models, easy "Start Server" toggle, and robust OpenAI compatibility.
- **VRAM Expectation**: ~5-6GB for the 8B model, leaving enough room for STT on an 8GB GPU.

#### Setup Steps
1.  **Download & Install**: [lmstudio.ai](https://lmstudio.ai/)
2.  **Search & Download Model**:
    - Search for: `Meta-Llama-3.1-8B-Instruct-GGUF`
    - Recommended Provider: `bartowski` or `MaziyarPanahi`
    - Recommended Quantization: **`Q4_K_M`** or **`Q5_K_M`**
3.  **Start Local Server**: 
    - Go to the **Local Server** tab (↔ icon).
    - Select the downloaded model at the top.
    - Click **Start Server**.
    - Default Port: `1234`
4.  **Configure Environment**:
    Set these variables in your `.env` file:
    ```bash
    CMG_LOCAL_LLM_PROVIDER=lmstudio
    CMG_LOCAL_LLM_ENDPOINT=http://127.0.0.1:1234/v1
    CMG_ALLOW_REMOTE_ACCESS=false
    ```

#### Verification
Run the readiness script to confirm structured JSON extraction works:
```bash
PYTHONPATH=src:. realtime_backend/.venv/bin/python3 realtime_backend/scripts/check_local_llm_readiness.py
```
**Expected Status**: `✅ STATUS: ACTIVE` (Once server is reachable and JSON test passes).

---

### 3. Verification Commands

Run these to ensure the full production backbone is alive:

```bash
# Check Semantic Retrieval
PYTHONPATH=src:. realtime_backend/.venv/bin/python3 realtime_backend/scripts/check_semantic_readiness.py

# Check Local LLM & Extraction
PYTHONPATH=src:. realtime_backend/.venv/bin/python3 realtime_backend/scripts/check_local_llm_readiness.py

# Inspect Graph Population
PYTHONPATH=src:. realtime_backend/.venv/bin/python3 realtime_backend/scripts/inspect_graph_status.py
```

*Note: If these report UNAVAILABLE or MOCK, the system will automatically use Heuristic Fallbacks to ensure zero-failure meeting capture.*
