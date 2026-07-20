# Local Model Assets

Everything below `models/` is local and ignored except this policy file. Do not commit model weights, tokenizer files, downloaded caches, license-gated assets, or machine-specific symbolic links.

Local embedding models may be placed below `models/embeddings/` and selected with `CMG_EMBEDDING_MODEL_PATH`. ASR model names and paths remain configuration-owned by `realtime_backend/app/config.py`; Faster-Whisper may use its external cache instead of this directory. Wake-phrase assets may use the separately ignored `wake_phrase_models/` path or a compatible path below `models/`.

See `docs/dev/SETUP.md` for maintained model configuration. No automatic migration or download is performed, and the existing local contents of this directory are intentionally untouched.
