"""
Diagnostic: dump raw Keepa response so we can see what's actually coming back.

Usage:
    python3 sources/keepa_debug.py "your search query"
"""

import gzip
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
import zlib

KEEPA_BASE = "https://api.keepa.com"


def fetch_raw(path: str, params: dict) -> dict:
    params["key"] = os.environ["KEEPA_API_KEY"]
    url = f"{KEEPA_BASE}{path}?{urllib.parse.urlencode(params)}"
    print(f"\n=== Calling: {path}?{urllib.parse.urlencode({k: v for k, v in params.items() if k != 'key'})}")
    req = urllib.request.Request(url, headers={
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "deal-hunter/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            print(f"HTTP {r.status}, Content-Encoding={enc!r}, {len(raw)} bytes raw")
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw)
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            if (e.headers.get("Content-Encoding") or "").lower() == "gzip":
                body = gzip.decompress(body)
        except Exception:
            pass
        print(f"HTTP error {e.code}:\n{body.decode('utf-8', errors='replace')[:800]}")
        raise


def main():
    if "KEEPA_API_KEY" not in os.environ:
        print("Set KEEPA_API_KEY first")
        sys.exit(1)

    query = sys.argv[1] if len(sys.argv) > 1 else "Pyrex glass food storage"

    print(f"\n### TEST 1: token check (free, no token cost)")
    try:
        data = fetch_raw("/token", {})
        print(json.dumps(data, indent=2)[:600])
    except Exception as e:
        print(f"failed: {e}")

    print(f"\n### TEST 2: text search for {query!r}")
    try:
        data = fetch_raw("/search", {"type": "product", "term": query, "domain": 1})
        print(f"Top-level keys: {list(data.keys())}")
        print(f"tokensLeft: {data.get('tokensLeft')}")
        print(f"asinList: {data.get('asinList')}")
        print(f"categories count: {len(data.get('categories') or [])}")
        print(f"totalResults: {data.get('totalResults')}")
        print("\nFull response (first 2000 chars):")
        print(json.dumps(data, indent=2)[:2000])
    except Exception as e:
        print(f"failed: {e}")

    print(f"\n### TEST 3: direct ASIN lookup (B07GFKJM5N - a Pyrex product)")
    try:
        data = fetch_raw("/product", {"domain": 1, "asin": "B07GFKJM5N", "stats": 30})
        print(f"Top-level keys: {list(data.keys())}")
        print(f"tokensLeft: {data.get('tokensLeft')}")
        products = data.get("products") or []
        print(f"products returned: {len(products)}")
        if products:
            p = products[0]
            print(f"  title: {p.get('title')!r}")
            print(f"  productGroup: {p.get('productGroup')!r}")
            print(f"  has stats: {'stats' in p}")
    except Exception as e:
        print(f"failed: {e}")


if __name__ == "__main__":
    main()
