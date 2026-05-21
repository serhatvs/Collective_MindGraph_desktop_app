import pytest
import json
from unittest.mock import patch, MagicMock
from collective_mindgraph.infrastructure.ai.local_llm_provider import LocalLLMEndpointProvider

def test_localhost_accepted():
    provider = LocalLLMEndpointProvider(base_url="http://127.0.0.1:1234/v1")
    assert provider.provider_name == "Local Endpoint (LM Studio / Ollama)"

def test_public_endpoint_rejected():
    with pytest.raises(ValueError, match="strictly requires a local endpoint"):
        LocalLLMEndpointProvider(base_url="https://api.openai.com/v1")

@patch("urllib.request.urlopen")
def test_is_available(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    provider = LocalLLMEndpointProvider()
    assert provider.is_available() is True

@patch("urllib.request.urlopen")
def test_generate_structured_json_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [
            {
                "message": {
                    "content": '```json\n{"summary": "Test"}\n```'
                }
            }
        ]
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    provider = LocalLLMEndpointProvider()
    result = provider.generate_structured_json("hello", {"summary": "string"})
    
    assert result == {"summary": "Test"}

@patch("urllib.request.urlopen")
def test_generate_structured_json_invalid(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [
            {
                "message": {
                    "content": 'I cannot do that.'
                }
            }
        ]
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    provider = LocalLLMEndpointProvider()
    with pytest.raises(ValueError, match="failed to return valid structured JSON"):
        provider.generate_structured_json("hello", {"summary": "string"})
