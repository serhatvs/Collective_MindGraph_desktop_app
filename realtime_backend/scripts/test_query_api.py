"""
Test the backend /query endpoint with different modes.
"""

import httpx
import json
import sys

def main():
    base_url = "http://127.0.0.1:8080"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    print(f"--- Testing Collective MindGraph Query API at {base_url} ---")
    
    query = "FastAPI"
    modes = ["keyword", "semantic", "hybrid"]
    
    for mode in modes:
        print(f"\nMode: {mode.upper()}")
        url = f"{base_url}/query?q={query}&mode={mode}"
        try:
            response = httpx.get(url, timeout=5)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                print(f"Results Count: {len(results)}")
                if results:
                    for i, res in enumerate(results[:2]):
                        print(f"  [{i}] Type: {res['result_type']}, Match By: {res.get('matched_by')}, Score: {res.get('score')}")
                        if res.get('edge_path'):
                            print(f"      Path: {res['edge_path']}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    main()
