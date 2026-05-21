"""
Check readiness for real local LLM interaction.
Verifies endpoint reachability, local-only safety, and structured JSON extraction.
"""

import os
import sys
import json
import urllib.request
from pathlib import Path

# Add src to path for core imports
sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))

from collective_mindgraph.infrastructure.ai.local_llm_provider import LocalLLMEndpointProvider

def main():
    print("--- Collective MindGraph Local LLM Readiness Check ---")
    
    endpoint = os.getenv("CMG_LOCAL_LLM_ENDPOINT") or os.getenv("CMG_RT_LLM_ENDPOINT") or "http://127.0.0.1:1234/v1"
    provider_type = os.getenv("CMG_LOCAL_LLM_PROVIDER") or os.getenv("CMG_RT_LLM_PROVIDER") or "lmstudio"
    allow_remote = (os.getenv("CMG_ALLOW_REMOTE_ACCESS") or os.getenv("CMG_RT_ALLOW_REMOTE_ACCESS", "false")).lower() == "true"
    
    print(f"Provider Type: {provider_type}")
    print(f"Endpoint: {endpoint}")
    print(f"Allow Remote Access: {allow_remote}")

    try:
        llm = LocalLLMEndpointProvider(base_url=endpoint, timeout=10, allow_remote=allow_remote)
    except ValueError as e:
        print(f"❌ PUBLIC_ENDPOINT_REJECTED: {e}")
        print("\n❌ STATUS: PUBLIC_ENDPOINT_REJECTED")
        return

    is_local = llm._is_local_endpoint(endpoint)
    print(f"Endpoint is Local/Private Safe: {'Yes' if is_local else 'No'}")
    
    if not is_local:
        print("\n❌ STATUS: CONFIG_ERROR (Public endpoints forbidden)")
        return

    reachable = llm.is_available()
    print(f"Server Reachable: {'Yes' if reachable else 'No'}")
    
    if not reachable:
        print("\n⚠️ STATUS: UNAVAILABLE")
        print("Local LLM provider is wired but unreachable; extraction will fallback to technical technical patterns.")
        return

    print("✅ Local LLM server detected.")
    
    # Check model list and detect selected model
    selected_model = "unknown"
    try:
        req = urllib.request.Request(f"{endpoint.rstrip('/')}/models", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            models = data.get("data", [])
            if models:
                 print(f"✅ Models Detected: {[m.get('id') for m in models]}")
                 selected_model = models[0].get('id')
                 print(f"Selected Model: {selected_model}")
            else:
                 print("⚠️ Model list empty.")
    except Exception:
        print("⚠️ Could not retrieve model list.")

    # Test Prompt
    print("Testing prompt generation...")
    prompt_ok = False
    try:
        # Simple text prompt test (not structured yet)
        payload = {
            "messages": [{"role": "user", "content": "say ok"}],
            "max_tokens": 5
        }
        req = urllib.request.Request(
            f"{endpoint.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            print(f"✅ Test Prompt Response: {content.strip()}")
            prompt_ok = True
    except Exception as e:
        print(f"❌ Test Prompt Failed: {e}")

    # Test Structured JSON Extraction
    print("Testing structured JSON extraction...")
    json_ok = False
    try:
        schema = {
            "type": "object", 
            "properties": {
                "meeting_title": {"type": "string"},
                "attendee_count": {"type": "integer"}
            },
            "required": ["meeting_title", "attendee_count"]
        }
        result = llm.generate_structured_json(
            "Extract: We had a 'Sprint Planning' with 5 people.", 
            schema
        )
        if isinstance(result, dict) and "meeting_title" in result:
            print(f"✅ Structured JSON Extraction Works: Yes")
            print(f"Response: {json.dumps(result)}")
            json_ok = True
        else:
            print(f"❌ Structured JSON returned invalid data type: {type(result)}")
    except Exception as e:
        print(f"❌ Structured JSON Extraction Failed: {e}")

    # Final Status Determination
    if json_ok:
        print("\n✅ STATUS: ACTIVE")
    elif prompt_ok:
        print("\n⚠️ STATUS: FALLBACK_ONLY (LLM active but failed structured extraction)")
    else:
        print("\n⚠️ STATUS: FALLBACK_ONLY (LLM reachable but prompt failed)")

if __name__ == "__main__":
    main()
