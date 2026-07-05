"""Check that the local model stack is reachable and dimensioned correctly.

Exits 0 on full pass, 1 on any failure. Used by `rdos doctor models` and as
a standalone script for ops.

Env vars (with defaults):
    RDOS_LOCAL_CHAT_BASE_URL      http://localhost:8080
    RDOS_LOCAL_CHAT_MODEL         qwythos-9b-q4
    RDOS_LOCAL_EMBEDDING_BASE_URL http://localhost:8081
    RDOS_LOCAL_EMBEDDING_MODEL    bge-m3-q8_0
    RDOS_LOCAL_MODEL_API_KEY      local-dev-key
    RDOS_LOCAL_EMBEDDING_DIM      1024
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import requests


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def check_chat_health(base_url: str) -> Check:
    try:
        r = requests.get(f"{base_url.rstrip('/').removesuffix('/v1')}/health", timeout=10)
        return Check("chat_health", r.status_code == 200, f"status={r.status_code}")
    except requests.RequestException as exc:
        return Check("chat_health", False, str(exc)[:200])


def check_chat_generate(base_url: str, model: str, api_key: str) -> Check:
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            return Check("chat_generate", False, f"status={r.status_code} body={r.text[:200]}")
        data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return Check("chat_generate", True, f"echo={text[:60]!r}")
    except requests.RequestException as exc:
        return Check("chat_generate", False, str(exc)[:200])


def check_embedding_health(base_url: str) -> Check:
    try:
        r = requests.get(f"{base_url.rstrip('/').removesuffix('/v1')}/health", timeout=10)
        return Check("embedding_health", r.status_code == 200, f"status={r.status_code}")
    except requests.RequestException as exc:
        return Check("embedding_health", False, str(exc)[:200])


def check_embedding_dim(base_url: str, model: str, api_key: str, expected_dim: int) -> Check:
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/v1/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"model": model, "input": ["dimension probe"]},
            timeout=30,
        )
        if r.status_code != 200:
            return Check("embedding_dim", False, f"status={r.status_code} body={r.text[:200]}")
        data = r.json()
        vec = (data.get("data") or [{}])[0].get("embedding", [])
        actual_dim = len(vec)
        if actual_dim != expected_dim:
            return Check(
                "embedding_dim",
                False,
                f"expected={expected_dim} actual={actual_dim}",
            )
        return Check("embedding_dim", True, f"dim={actual_dim}")
    except requests.RequestException as exc:
        return Check("embedding_dim", False, str(exc)[:200])


def check_embedding_batch(base_url: str, model: str, api_key: str) -> Check:
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/v1/embeddings",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={"model": model, "input": ["alpha", "beta", "gamma"]},
            timeout=30,
        )
        if r.status_code != 200:
            return Check("embedding_batch", False, f"status={r.status_code}")
        data = r.json()
        n = len(data.get("data") or [])
        return Check("embedding_batch", n == 3, f"got={n}")
    except requests.RequestException as exc:
        return Check("embedding_batch", False, str(exc)[:200])


def run_all() -> int:
    chat_base = _env("RDOS_LOCAL_CHAT_BASE_URL", "http://localhost:8080")
    chat_model = _env("RDOS_LOCAL_CHAT_MODEL", "qwythos-9b-q4")
    embed_base = _env("RDOS_LOCAL_EMBEDDING_BASE_URL", "http://localhost:8081")
    embed_model = _env("RDOS_LOCAL_EMBEDDING_MODEL", "bge-m3-q8_0")
    api_key = _env("RDOS_LOCAL_MODEL_API_KEY", "local-dev-key")
    embed_dim = int(os.environ.get("RDOS_LOCAL_EMBEDDING_DIM", "1024"))

    checks: list[Check] = [
        check_chat_health(chat_base),
        check_chat_generate(chat_base, chat_model, api_key),
        check_embedding_health(embed_base),
        check_embedding_dim(embed_base, embed_model, api_key, embed_dim),
        check_embedding_batch(embed_base, embed_model, api_key),
    ]

    print("Local model stack check")
    print(f"  chat:      {chat_base} model={chat_model}")
    print(f"  embedding: {embed_base} model={embed_model} dim={embed_dim}")
    print("-" * 60)
    for c in checks:
        marker = "PASS" if c.ok else "FAIL"
        print(f"  {marker:4} {c.name:18} {c.detail}")
    print("-" * 60)
    fails = [c for c in checks if not c.ok]
    n_pass = len(checks) - len(fails)
    print(f"  {n_pass}/{len(checks)} passed")
    return 1 if fails else 0


def main() -> int:
    code = run_all()
    sys.exit(code)


if __name__ == "__main__":
    main()
