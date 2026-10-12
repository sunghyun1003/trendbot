"""Cloudflare API 호출 모음 (GitHub 서버에서 실행).

키: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN (GitHub 비밀값).
KV 저장소 한 곳(이름 KV_TITLE)에 접두어로 나눠 담습니다.
- fb:     팀원 피드백 (사이트 버튼 → 저장, 발행 때 가져가고 지움)
- agent:  집 PC 도우미 (기기 토큰, 상태, 보낸 수집 결과)
"""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

API = "https://api.cloudflare.com/client/v4"
KV_TITLE = "dsbg-store"
PROJECT = os.environ.get("CF_PAGES_PROJECT", "trendbot")


class CloudflareError(Exception):
    pass


def configured() -> bool:
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))


class Client:
    def __init__(self, http: httpx.Client | None = None):
        self.account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        self.http = http or httpx.Client(timeout=30)
        self.headers = {"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"}
        self._kv: str | None = None

    def call(self, method: str, path: str, **kw) -> dict | list | None:
        r = self.http.request(method, f"{API}/accounts/{self.account}{path}", headers=self.headers, **kw)
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or (isinstance(body, dict) and body.get("success") is False):
            errs = body.get("errors") if isinstance(body, dict) else None
            msg = "; ".join(e.get("message", "") for e in errs or []) or r.text[:200]
            raise CloudflareError(f"{method} {path} → {r.status_code} {msg}")
        return body.get("result") if isinstance(body, dict) and "result" in body else body

    # ---- KV ----
    def kv_namespace(self, create: bool = False) -> str | None:
        if self._kv:
            return self._kv
        for ns in self.call("GET", "/storage/kv/namespaces", params={"per_page": 100}) or []:
            if ns["title"] == KV_TITLE:
                self._kv = ns["id"]
                return self._kv
        if create:
            self._kv = self.call("POST", "/storage/kv/namespaces", json={"title": KV_TITLE})["id"]
        return self._kv

    def kv_keys(self, prefix: str) -> list[str]:
        ns, keys, cursor = self.kv_namespace(), [], None
        if not ns:
            return []
        while True:
            params = {"prefix": prefix, "limit": 1000, **({"cursor": cursor} if cursor else {})}
            r = self.http.get(f"{API}/accounts/{self.account}/storage/kv/namespaces/{ns}/keys",
                              headers=self.headers, params=params)
            if r.status_code >= 400:
                raise CloudflareError(f"KV 목록 → {r.status_code}")
            body = r.json()
            keys += [k["name"] for k in body.get("result", [])]
            cursor = (body.get("result_info") or {}).get("cursor")
            if not cursor:
                return keys

    def kv_get(self, key: str) -> bytes:
        r = self.http.get(f"{API}/accounts/{self.account}/storage/kv/namespaces/{self.kv_namespace()}/values/{quote(key, safe='')}",
                          headers=self.headers)
        if r.status_code >= 400:
            raise CloudflareError(f"KV 읽기 {key} → {r.status_code}")
        return r.content

    def kv_delete(self, keys: list[str]) -> None:
        for i in range(0, len(keys), 1000):
            self.call("POST", f"/storage/kv/namespaces/{self.kv_namespace()}/bulk/delete", json=keys[i:i + 1000])
