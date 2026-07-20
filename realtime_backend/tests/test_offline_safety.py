from pathlib import Path
import pytest
from realtime_backend.app.utils.offline_safety import (
    is_local_url,
    validate_local_endpoint,
    validate_local_model_path
)

def test_is_local_url():
    assert is_local_url("http://localhost:1234") is True
    assert is_local_url("http://127.0.0.1:8080") is True
    assert is_local_url("http://192.168.1.50:11434") is True
    assert is_local_url("http://10.0.0.1") is True
    assert is_local_url("http://172.16.0.2") is True
    assert is_local_url("http://[::1]:1234") is True
    assert is_local_url("http://0.0.0.0") is True
    
    assert is_local_url("https://api.openai.com/v1") is False
    assert is_local_url("https://huggingface.co") is False
    assert is_local_url("http://google.com") is False
    assert is_local_url("https://10.evil.example/v1") is False
    assert is_local_url("https://192.168.evil.example/v1") is False
    assert is_local_url("file://localhost/model") is False
    assert is_local_url("ftp://127.0.0.1/model") is False

def test_validate_local_endpoint():
    # Should pass
    validate_local_endpoint("http://localhost:1234", "test")
    validate_local_endpoint("http://192.168.1.1", "test")
    
    # Should raise
    with pytest.raises(ValueError, match="not a local/private address"):
        validate_local_endpoint("https://api.openai.com/v1", "OpenAI")
        
    # Should pass with override
    validate_local_endpoint("https://api.openai.com/v1", "OpenAI", allow_remote=True)
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        validate_local_endpoint("file://localhost/model", "test", allow_remote=True)

def test_validate_local_model_path(tmp_path):
    local_file = tmp_path / "model.bin"
    local_file.write_text("fake model")
    
    # Absolute local path should pass
    validate_local_model_path(str(local_file.resolve()), "test")
    
    # Relative path to existing file should pass
    # (Assuming we run tests from root and path is relative to it)
    
    # Remote-looking ID should fail if not exists
    with pytest.raises(ValueError, match="not found locally"):
        validate_local_model_path("pyannote/speaker-diarization-3.1", "pyannote")
        
    # Should pass with override
    validate_local_model_path("pyannote/speaker-diarization-3.1", "pyannote", allow_remote=True)

if __name__ == "__main__":
    test_is_local_url()
    test_validate_local_endpoint()
    print("Offline safety utility tests passed!")
