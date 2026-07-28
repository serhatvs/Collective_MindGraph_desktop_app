"""Check local language-model reachability and endpoint safety."""

from __future__ import annotations

import os

from collective_mindgraph.infrastructure.ai import LocalEndpointLanguageModel


def main() -> int:
    endpoint = (
        os.getenv("CMG_LOCAL_LLM_ENDPOINT")
        or os.getenv("CMG_RT_LLM_ENDPOINT")
        or "http://127.0.0.1:1234/v1"
    )
    allow_remote = (
        os.getenv("CMG_ALLOW_REMOTE_ACCESS")
        or os.getenv("CMG_RT_ALLOW_REMOTE_ACCESS", "false")
    ).casefold() == "true"
    print("--- Collective MindGraph Local AI Readiness ---")
    print(f"Endpoint: {endpoint}")
    try:
        model = LocalEndpointLanguageModel(
            base_url=endpoint,
            timeout=10,
            allow_remote=allow_remote,
        )
    except ValueError as error:
        print(f"UNSAFE_ENDPOINT: {error}")
        return 2
    if not model.is_available():
        print("UNAVAILABLE: The local endpoint did not answer.")
        return 1
    print("READY: The local endpoint is reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
