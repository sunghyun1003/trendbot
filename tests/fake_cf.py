"""테스트용 가짜 Cloudflare API (httpx MockTransport)."""

import json
import re
from urllib.parse import unquote

import httpx


class FakeCF:
    def __init__(self):
        self.kv: dict[str, bytes] = {}
        self.namespaces: list[dict] = []
        self.projects: dict[str, dict] = {}
        self.org: dict | None = {"auth_domain": "team.cloudflareaccess.com"}
        self.apps: list[dict] = []
        self.idps: list[dict] = []
        self.calls: list[tuple[str, str]] = []

    def ok(self, result, info=None):
        return httpx.Response(200, json={"success": True, "result": result, "result_info": info or {}})

    def __call__(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path.split("/accounts/acc", 1)[-1]
        self.calls.append((req.method, path))
        try:
            body = json.loads(req.content) if req.content else None
        except ValueError:
            body = None
        if path == "/storage/kv/namespaces":
            if req.method == "POST":
                ns = {"id": f"ns{len(self.namespaces) + 1}", "title": body["title"]}
                self.namespaces.append(ns)
                return self.ok(ns)
            return self.ok(self.namespaces)
        if m := re.fullmatch(r"/storage/kv/namespaces/\w+/keys", path):
            p = req.url.params.get("prefix", "")
            return self.ok([{"name": k} for k in sorted(self.kv) if k.startswith(p)])
        if m := re.fullmatch(r"/storage/kv/namespaces/\w+/values/(.+)", path):
            k = unquote(m.group(1))
            return httpx.Response(200, content=self.kv[k]) if k in self.kv else httpx.Response(404)
        if re.fullmatch(r"/storage/kv/namespaces/\w+/bulk/delete", path):
            for k in body:
                self.kv.pop(k, None)
            return self.ok(None)
        if path == "/pages/projects" and req.method == "POST":
            self.projects[body["name"]] = body
            return self.ok({**body, "subdomain": body["name"] + ".pages.dev"})
        if m := re.fullmatch(r"/pages/projects/([\w-]+)", path):
            if req.method == "PATCH":
                self.projects[m.group(1)].setdefault("patches", []).append(body)
                return self.ok(self.projects[m.group(1)])
            if m.group(1) in self.projects:
                return self.ok({**self.projects[m.group(1)], "subdomain": m.group(1) + ".pages.dev"})
            return httpx.Response(404, json={"success": False, "errors": [{"message": "not found"}]})
        if path == "/access/organizations":
            return self.ok(self.org) if self.org else httpx.Response(404, json={"success": False, "errors": [{"message": "no org"}]})
        if path == "/access/identity_providers":
            if req.method == "POST":
                self.idps.append(body)
            return self.ok(self.idps)
        if path == "/access/apps":
            if req.method == "POST":
                app = {**body, "id": f"app{len(self.apps) + 1}", "aud": f"aud{len(self.apps) + 1}"}
                self.apps.append(app)
                return self.ok(app)
            return self.ok(self.apps)
        if m := re.fullmatch(r"/access/apps/(\w+)", path):
            app = next(a for a in self.apps if a["id"] == m.group(1))
            app.update(body)
            return self.ok(app)
        return httpx.Response(500, json={"success": False, "errors": [{"message": f"fake: {req.method} {path}"}]})


def client(fake: FakeCF, monkeypatch):
    from trendbot import cloudflare
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    return cloudflare.Client(httpx.Client(transport=httpx.MockTransport(fake)))

