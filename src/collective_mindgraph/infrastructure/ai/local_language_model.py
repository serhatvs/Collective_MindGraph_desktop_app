"""OpenAI-compatible language-model adapter restricted to approved endpoints."""

import ipaddress
import json
import urllib.parse
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError

from collective_mindgraph.application.ports import LocalLanguageModel


class LocalEndpointLanguageModel(LocalLanguageModel):
    """
    OpenAI-compatible local endpoint provider (e.g., LM Studio, Ollama).
    Enforces local-only URLs.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        timeout: int = 30,
        allow_remote: bool = False,
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._model_name = (model_name or "").strip()
        self._api_key = api_key

        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Provider endpoint must use HTTP or HTTPS. Received: {base_url}")
        # Security: Prevent cloud endpoint usage unless explicitly allowed
        if not allow_remote and not self._is_local_endpoint(self.base_url):
            raise ValueError(f"Provider strictly requires a local endpoint. Received: {base_url}")

    def _is_local_endpoint(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.casefold() not in {"http", "https"}:
            return False
        host = parsed.hostname or ""
        if host.casefold() == "localhost":
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_unspecified
        )

    @property
    def provider_name(self) -> str:
        return "Local Endpoint (LM Studio / Ollama)"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.base_url}/models",
                headers=self._headers(),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except (URLError, HTTPError, TimeoutError):
            return False

    def generate_structured_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Requests structured JSON output using OpenAI compatible chat completions."""
        content = ""
        model_name = self._resolve_model()
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a specialized knowledge extraction assistant. Always respond with raw JSON only, matching the exact schema provided. Do not include conversational text or explanations.",
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nREQUIRED JSON SCHEMA:\n{json.dumps(schema)}",
                },
            ],
            "temperature": 0.0,  # Extraction needs deterministic output.
            "max_tokens": 1500,
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(content_type=True),
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body)
                content = data["choices"][0]["message"]["content"]

                # 1. Clean Markdown
                content = content.strip()
                if "```" in content:
                    # Extract content between ```json and ``` or just ```
                    import re

                    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if match:
                        content = match.group(1)
                    else:
                        # Fallback: strip the start/end markers manually
                        if content.startswith("```json"):
                            content = content[7:]
                        elif content.startswith("```"):
                            content = content[3:]
                        if content.endswith("```"):
                            content = content[:-3]

                # 2. Parse and return
                return json.loads(content.strip())

        except (URLError, HTTPError, TimeoutError) as e:
            raise RuntimeError(f"Local LLM request failed: {str(e)}")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            # Last ditch effort: try to find anything that looks like a JSON object { ... }
            if "{" in content and "}" in content:
                try:
                    import re

                    match = re.search(r"(\{.*\})", content, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except (json.JSONDecodeError, TypeError):
                    pass
            raise ValueError(
                f"Local LLM failed to return valid structured JSON. Raw response: {content[:200]}..."
            )

    def _resolve_model(self) -> str:
        if self._model_name and self._model_name.casefold() not in {"auto", "none"}:
            return self._model_name
        request = urllib.request.Request(
            f"{self.base_url}/models",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError) as exc:
            raise RuntimeError(f"Local LLM model discovery failed: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Local LLM model discovery returned invalid JSON.") from exc
        models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(models, list) or not models or not isinstance(models[0], dict):
            raise ValueError("Local LLM endpoint did not report an available model.")
        identifier = str(models[0].get("id") or "").strip()
        if not identifier:
            raise ValueError("Local LLM endpoint reported a model without an id.")
        self._model_name = identifier
        return identifier

    def _headers(self, *, content_type: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = "application/json"
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
