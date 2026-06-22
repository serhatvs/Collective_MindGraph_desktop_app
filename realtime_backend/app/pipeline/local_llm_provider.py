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

    def __init__(self, base_url: str | None = "http://127.0.0.1:1234/v1", timeout: int = 30, allow_remote: bool = False):
        if base_url is None:
            base_url = "disabled"
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        # Security: Prevent cloud endpoint usage unless explicitly allowed
        if self.base_url != "disabled" and not allow_remote and not self._is_local_endpoint(self.base_url):
            raise ValueError(f"Provider strictly requires a local endpoint. Received: {base_url}")

    def _is_local_endpoint(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        return host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.startswith("192.168.") or host.startswith("10.")

    @property
    def provider_name(self) -> str:
        return "Local Endpoint (LM Studio / Ollama)"

    def is_available(self) -> bool:
        if self.base_url == "disabled":
            return False
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
                {"role": "system", "content": "You are a specialized knowledge extraction assistant. Always respond with raw JSON only, matching the exact schema provided. Do not include conversational text or explanations."},
                {"role": "user", "content": f"{prompt}\n\nREQUIRED JSON SCHEMA:\n{json.dumps(schema)}"}
            ],
            "temperature": 0.0, # Production extraction needs determinism
            "max_tokens": 1500,
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
                        if content.startswith("```json"): content = content[7:]
                        elif content.startswith("```"): content = content[3:]
                        if content.endswith("```"): content = content[:-3]
                
                # 2. Parse and return
                return json.loads(content.strip())
                
        except (URLError, HTTPError, TimeoutError) as e:
            raise RuntimeError(f"Local LLM request failed: {str(e)}")
        except (json.JSONDecodeError, KeyError) as e:
            # Last ditch effort: try to find anything that looks like a JSON object { ... }
            if "{" in content and "}" in content:
                try:
                    import re
                    match = re.search(r"(\{.*\})", content, re.DOTALL)
                    if match:
                        return json.loads(match.group(1))
                except Exception:
                    pass
            raise ValueError(f"Local LLM failed to return valid structured JSON. Raw response: {content[:200]}...")
