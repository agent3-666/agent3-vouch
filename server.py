"""Serves the generated page. The page itself is built by scripts/build_site.py."""

from __future__ import annotations

import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).parent / "site"


def main() -> None:
    port = int(os.environ.get("PORT", "4300"))
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
    print(f"serving {SITE} on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()


if __name__ == "__main__":
    main()
