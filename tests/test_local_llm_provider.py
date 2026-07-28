import json
from unittest.mock import MagicMock, patch

import pytest

from collective_mindgraph.infrastructure.ai.local_language_model import (
    LocalEndpointLanguageModel,
)


def test_localhost_accepted():
    provider = LocalEndpointLanguageModel("http://127.0.0.1:1234/v1")
    assert provider.provider_name == "Local Endpoint (LM Studio / Ollama)"


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.openai.com/v1",
        "https://10.evil.example/v1",
        "https://192.168.evil.example/v1",
        "file://localhost/model",
        "ftp://127.0.0.1/model",
        "http:///missing-host",
    ],
)
def test_nonlocal_or_non_http_endpoints_are_rejected(endpoint):
    with pytest.raises(ValueError):
        LocalEndpointLanguageModel(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    ["http://172.16.0.2:1234/v1", "http://[::1]:1234/v1"],
)
def test_private_and_ipv6_loopback_endpoints_are_accepted(endpoint):
    assert LocalEndpointLanguageModel(endpoint)._is_local_endpoint(endpoint)


@patch("urllib.request.urlopen")
def test_availability_probe(mock_urlopen):
    response = MagicMock(status=200)
    mock_urlopen.return_value.__enter__.return_value = response
    assert LocalEndpointLanguageModel().is_available()


@patch("urllib.request.urlopen")
def test_structured_generation_accepts_fenced_json(mock_urlopen):
    response = MagicMock()
    response.read.return_value = json.dumps(
        {"choices": [{"message": {"content": '```json\n{"summary":"Test"}\n```'}}]}
    ).encode()
    mock_urlopen.return_value.__enter__.return_value = response

    provider = LocalEndpointLanguageModel(
        model_name="test-model",
        api_key="local-secret",
    )
    assert provider.generate_structured_json("hello", {}) == {"summary": "Test"}
    request = mock_urlopen.call_args.args[0]
    sent = json.loads(request.data.decode("utf-8"))
    assert sent["model"] == "test-model"
    assert request.get_header("Authorization") == "Bearer local-secret"
