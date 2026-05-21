"""Local LLM Provider implementation for strictly local endpoints (LM Studio, Ollama)."""

import json
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError
from typing import Dict, Any

from .ai_provider import LocalLLMProvider

class LocalLLMEndpointProvider(LocalLLMProvider):
    """
    OpenAI-compatible local endpoint provider (e.g., LM Studio, Ollama).
    Enforces local-only URLs.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        # Security: Prevent cloud endpoint usage
        if not self._is_local_endpoint(self.base_url):
            raise ValueError(f"Provider strictly requires a local endpoint. Received: {base_url}")

    def _is_local_endpoint(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        return host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("192.168.") or host.startswith("10.")

    @property
    def provider_name(self) -> str:
        return "Local Endpoint (LM Studio / Ollama)"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/models", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except (URLError, HTTPError, TimeoutError):
            return False

    def generate_structured_json(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Requests structured JSON output using OpenAI compatible chat completions."""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Always output valid JSON matching the schema."},
                {"role": "user", "content": f"{prompt}\n\nExpected JSON schema:\n{json.dumps(schema)}"}
            ],
            "temperature": 0.1,
            # We use standard chat completion since some local endpoints don't fully support response_format
            # "response_format": {"type": "json_object"}
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                content = data["choices"][0]["message"]["content"]
                
                # Attempt to extract JSON from markdown blocks if local LLM returned formatting
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                return json.loads(content.strip())
                
        except (URLError, HTTPError, TimeoutError) as e:
            raise RuntimeError(f"Local LLM request failed: {str(e)}")
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Local LLM failed to return valid structured JSON: {str(e)}")
