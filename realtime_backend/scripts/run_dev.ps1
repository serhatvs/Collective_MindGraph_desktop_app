$env:CMG_RT_LOG_LEVEL = "INFO"
uvicorn app.main:app --reload --port 8080
