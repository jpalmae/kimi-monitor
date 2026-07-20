"""Probe the Kimi Coding Plan internal usage endpoint to see the raw payload.

Run:  python3 probe.py
Reads KIMI_API_KEY / KIMI_CODING_API_KEY from .env (or env vars).

It tries, in order:
  1. https://api.kimi.com/coding/v1/usages
  2. https://api.kimi.com/coding/v1/usage   (older deployments)
and pretty-prints whatever comes back so we can verify the field mapping
used by fetcher.py.
"""

from __future__ import annotations

import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = (os.getenv("KIMI_API_KEY") or os.getenv("KIMI_CODING_API_KEY") or "").strip()

CANDIDATES = [
    "https://api.kimi.com/coding/v1/usages",
    "https://api.kimi.com/coding/v1/usage",
]


def headers_for(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "KimiCLI/1.6",
    }


def main() -> int:
    if not API_KEY:
        print("ERROR: set KIMI_API_KEY (sk-kimi-xxx) in .env first.", file=sys.stderr)
        return 2

    got = False
    with httpx.Client(http2=False, follow_redirects=True) as client:
        for url in CANDIDATES:
            print(f"\n{'=' * 70}\n>>> GET {url}\n{'=' * 70}")
            try:
                r = client.get(url, headers=headers_for(API_KEY), timeout=20)
            except httpx.RequestError as e:
                print(f"  [ERR] {e}")
                continue
            try:
                parsed = r.json()
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            except ValueError:
                parsed = None
                pretty = r.text[:2000]
            ok = r.is_success and isinstance(parsed, dict)
            flag = "OK " if ok else "FAIL"
            print(f"  [{flag}] http {r.status_code}")
            print("  " + pretty.replace("\n", "\n  ")[:4000])
            if ok:
                got = True
                break

    print("\n" + "=" * 70)
    if got:
        print("SUCCESS: endpoint returned data.")
        print("Check the fields against fetcher.py (_parse) if the shape changed.")
    else:
        print("NO SUCCESS. Likely causes:")
        print("  - Key is NOT a Kimi Code (Coding Plan) key (needs sk-kimi-xxx).")
        print("  - Key expired -> create a fresh one in the Kimi Code console.")
        print("  - Endpoint moved -> re-check https://www.kimi.com/code/docs/")
    return 0 if got else 1


if __name__ == "__main__":
    raise SystemExit(main())
