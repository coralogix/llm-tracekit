from __future__ import annotations
import asyncio
from typing import Any, Callable, Awaitable
import httpx

from .error import APIConnectionError, APITimeoutError, APIResponseError

def _is_retryable(status: int) -> bool:
    # Retry on typical transient codes
    return status in (429, 500, 502, 503, 504)

async def _with_retries(
    fn: Callable[[], Awaitable[httpx.Response]],
    *,
    retries: int = 2,
    base_delay: float = 0.2,
) -> httpx.Response:
    attempt = 0
    while True:
        try:
            resp = await fn()
            if resp.status_code >= 400 and attempt < retries and _is_retryable(resp.status_code):
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                attempt += 1
                continue
            return resp
        except httpx.TimeoutException as e:
            if attempt < retries:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                attempt += 1
                continue
            raise APITimeoutError("Request timed out") from e
        except httpx.HTTPError as e:
            # Transport issues
            if attempt < retries:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                attempt += 1
                continue
            raise APIConnectionError(str(e)) from e

async def _parse_json(resp: httpx.Response) -> Any:
    if 200 <= resp.status_code < 300:
        if resp.headers.get("content-length") == "0":
            return None
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        # Attempt to parse anyway
        try:
            return resp.json()
        except Exception:
            return resp.text
    else:
        content = None
        try:
            content = resp.text
        except Exception:
            pass
        raise APIResponseError(resp.status_code, content)
