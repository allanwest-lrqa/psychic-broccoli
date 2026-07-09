"""Tiny HTTP helper built on the standard library.

Keeps the project dependency-free. Handles JSON GETs, binary downloads, a
polite User-Agent, simple retry with backoff, and honouring HTTPS_PROXY /
custom CA bundles from the environment (needed in sandboxed runners).
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

USER_AGENT = "c64renamer/1.0 (+https://github.com/allanwest-lrqa/psychic-broccoli)"

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3


def _ssl_context() -> Optional[ssl.SSLContext]:
    """Build an SSL context, honouring a custom CA bundle if configured."""
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get(
        "SSL_CERT_FILE"
    )
    if ca_bundle and Path(ca_bundle).exists():
        return ssl.create_default_context(cafile=ca_bundle)
    return None


def _open(url: str, timeout: int) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


def get_json(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Dict[str, Any]:
    """GET a URL and parse the response as JSON, with retry/backoff."""
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with _open(url, timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            # Do not retry on client errors like 401/403/404.
            if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def get_text(url: str, timeout: int = DEFAULT_TIMEOUT,
             retries: int = DEFAULT_RETRIES) -> str:
    """GET a URL and return the decoded body as text."""
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with _open(url, timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def download(url: str, dest: Path, timeout: int = DEFAULT_TIMEOUT) -> Path:
    """Download a binary resource to ``dest``. Returns the path written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _open(url, timeout) as response:
        dest.write_bytes(response.read())
    return dest
