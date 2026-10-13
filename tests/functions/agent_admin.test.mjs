import { test } from "node:test";
import assert from "node:assert/strict";
import * as agent from "../../site_functions/api/agent.js";
import * as admin from "../../site_functions/api/admin.js";
import { kv } from "./helpers.mjs";

const SOURCES = `pods: {}
sources:
  - id: dcbest
    name: 디시 실시간 베스트
    enabled: true   # 메모
    url: x
  - id: clien
    name: 클리앙 추천글
    enabled: false
  - id: dieselmania
    name: 디젤매니아
    kind: naver_cafe
signals:
  google_trends: {}
`;

test("sources.yaml 읽기·켜기끄기: 주석과 다른 줄은 그대로", () => {
  const s = admin.parseSources(SOURCES);
  assert.deepEqual(s.map((x) => [x.id, x.name, x.enabled, x.kind]),
    [["dcbest", "디시 실시간 베스트", true, "html_list"], ["clien", "클리앙 추천글", false, "html_list"], ["dieselmania", "디젤매니아", true, "naver_cafe"]]);
  const off = admin.setEnabled(SOURCES, "dcbest", false);
  assert.ok(off.includes("    enabled: false   # 메모"));
  assert.equal(off.split("\n").length, SOURCES.split("\n").length);
  const on = admin.setEnabled(SOURCES, "dieselmania", false);  // enabled 줄이 없으면 추가
  assert.equal(admin.parseSources(on).find((x) => x.id === "dieselmania").enabled, false);
  assert.throws(() => admin.setEnabled(SOURCES, "nope", true));
});

function ghFake(env) {
  const calls = [];
  let file = SOURCES;
  globalThis.fetch = async (url, opt = {}) => {
    const u = new URL(url);
    calls.push([opt.method || "GET", u.pathname, opt.body ? JSON.parse(opt.body) : null, opt.headers?.Authorization]);
    if (u.pathname.endsWith("/actions/secrets")) return Response.json({ secrets: [{ name: "ANTHROPIC_API_KEY" }, { name: "DASHBOARD_TOKEN" }] });
    if (u.pathname.endsWith("/runs")) return Response.json({ workflow_runs: [{ status: "completed", conclusion: "success", event: "schedule", created_at: "t", html_url: "h" }] });
    if (u.pathname.endsWith("/dispatches")) return new Response(null, { status: 204 });
    if (u.pathname.endsWith("/contents/config/sources.yaml")) {
      if (opt.method === "PUT") { file = Buffer.from(JSON.parse(opt.body).content, "base64").toString(); return Response.json({}); }
      return Response.json({ content: Buffer.from(file).toString("base64"), sha: "s1" });
    }
    return new Response("nope", { status: 404 });
  };
  return { calls, file: () => file };
}

const env = () => ({ FEEDBACK: kv(), GITHUB_TOKEN: "ghp", GITHUB_REPO: "me/trendbot", GITHUB_BRANCH: "main" });
const post = (body) => new Request("https://dsbg.pages.dev/api/admin", { method: "POST", body: JSON.stringify(body) });

test("관리: 상태 조회 (키 ✓/✗, 실행 기록, 사이트 목록, 집 PC 상태)", async () => {
  const e = env();
  ghFake(e);
  await e.FEEDBACK.put("agent:status", JSON.stringify({ naver: "login", at: "t" }));
  const r = await (await admin.onRequestGet({ env: e })).json();
  assert.equal(r.keys.find((k) => k.name === "ANTHROPIC_API_KEY").ok, true);
  assert.equal(r.keys.find((k) => k.name === "CLOUDFLARE_API_TOKEN").ok, false);
  assert.equal(r.runs[0].conclusion, "success");
  assert.equal(r.sources.length, 3);
  assert.equal(r.agent.naver, "login");
});

test("관리: 지금 발행·켜기끄기는 GitHub API로", async () => {
  const e = env();
  const g = ghFake(e);
  const data = { email: "me@team.com" };
  assert.equal((await admin.onRequestPost({ request: post({ action: "run", task: "publish" }), env: e, data })).status, 200);
  const d = g.calls.find((c) => c[1].endsWith("/dispatches"));
  assert.deepEqual(d[2], { ref: "main", inputs: { task: "publish" } });
  assert.equal(d[3], "Bearer ghp");
  assert.equal((await admin.onRequestPost({ request: post({ action: "toggle", id: "clien", enabled: true }), env: e, data })).status, 200);
  assert.equal(admin.parseSources(g.file()).find((x) => x.id === "clien").enabled, true);
  assert.match(g.calls.find((c) => c[0] === "PUT")[2].message, /clien 켜기 \(me@team.com\)/);
});

test("도우미: 설치 파일 받기 → 그 토큰으로만 도우미 창구 사용", async () => {
  const e = env();
  e.ASSETS = { fetch: async (u) => new Response(`asset:${new URL(u).pathname}`) };
  const r = await admin.onRequestPost({ request: post({ action: "helper" }), env: e, data: { email: "me@team.com" } });
  const cmd = await r.text();
  assert.match(r.headers.get("content-disposition"), /dsbg-setup\.cmd/);
  assert.match(cmd, /\r\n/);
  const token = cmd.match(/X-Agent-Token'='([0-9a-f]{48})'/)[1];
  assert.ok(cmd.includes("https://dsbg.pages.dev/api/agent?get=install"));
  assert.ok(![...e.FEEDBACK.m.keys()].some((k) => k.includes(token)));  // 토큰 원문은 저장하지 않음

  const req = (q, opt = {}, t = token) => new Request(`https://dsbg.pages.dev/api/agent?${q}`, { ...opt, headers: { "X-Agent-Token": t } });
  assert.equal((await agent.onRequestGet({ request: req("get=code", {}, "x".repeat(48)), env: e })).status, 401);
  assert.equal(await (await agent.onRequestGet({ request: req("get=code"), env: e })).text(), "asset:/helper/helper.zip");

  await admin.onRequestPost({ request: post({ action: "naver_now" }), env: e, data: { email: "me@team.com" } });
  assert.deepEqual(await (await agent.onRequestGet({ request: req("get=cmd"), env: e })).json(), { cmd: "collect" });
  assert.deepEqual(await (await agent.onRequestGet({ request: req("get=cmd"), env: e })).json(), { cmd: null });

  assert.equal((await agent.onRequestPost({ request: req("put=status", { method: "POST", body: JSON.stringify({ naver: "ok", version: "1" }) }), env: e })).status, 200);
  assert.equal(JSON.parse(e.FEEDBACK.m.get("agent:status")).naver, "ok");
  assert.equal((await agent.onRequestPost({ request: req("put=batch", { method: "POST", body: "{\"ok\":true}" }), env: e })).status, 200);
  assert.ok([...e.FEEDBACK.m.keys()].some((k) => k.startsWith("agent:batch:")));
  assert.equal((await agent.onRequestPost({ request: req("put=media&name=2026-10-12/abc.webp", { method: "POST", body: new Uint8Array([1, 2]) }), env: e })).status, 200);
  assert.equal((await agent.onRequestPost({ request: req("put=media&name=../x.webp", { method: "POST", body: "x" }), env: e })).status, 400);
});

test("인스타 감시 계정: 주석 유지, 이상한 값·중복 제거", () => {
  const out = admin.setWatchlist("# 설명\n# 둘째\nold_one\n", ["@good.acct", "good.acct", "bad acct!", "", "two_2"]);
  assert.equal(out, "# 설명\n# 둘째\ngood.acct\ntwo_2\n");
});
