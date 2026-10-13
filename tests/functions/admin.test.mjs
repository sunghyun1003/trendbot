import { test } from "node:test";
import assert from "node:assert/strict";
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
  - id: newsite
    name: 새 게시판
    kind: rss
signals:
  google_trends: {}
`;

test("sources.yaml 읽기·켜기끄기: 주석과 다른 줄은 그대로", () => {
  const s = admin.parseSources(SOURCES);
  assert.deepEqual(s.map((x) => [x.id, x.name, x.enabled, x.kind]),
    [["dcbest", "디시 실시간 베스트", true, "html_list"], ["clien", "클리앙 추천글", false, "html_list"], ["newsite", "새 게시판", true, "rss"]]);
  const off = admin.setEnabled(SOURCES, "dcbest", false);
  assert.ok(off.includes("    enabled: false   # 메모"));
  assert.equal(off.split("\n").length, SOURCES.split("\n").length);
  const on = admin.setEnabled(SOURCES, "newsite", false);  // enabled 줄이 없으면 추가
  assert.equal(admin.parseSources(on).find((x) => x.id === "newsite").enabled, false);
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

test("관리: 상태 조회 (키 ✓/✗, 실행 기록, 사이트 목록)", async () => {
  const e = env();
  ghFake(e);
  const r = await (await admin.onRequestGet({ env: e })).json();
  assert.equal(r.keys.find((k) => k.name === "ANTHROPIC_API_KEY").ok, true);
  assert.equal(r.keys.find((k) => k.name === "CLOUDFLARE_API_TOKEN").ok, false);
  assert.equal(r.runs[0].conclusion, "success");
  assert.equal(r.sources.length, 3);
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

test("인스타 감시 계정: 주석 유지, 이상한 값·중복 제거", () => {
  const out = admin.setWatchlist("# 설명\n# 둘째\nold_one\n", ["@good.acct", "good.acct", "bad acct!", "", "two_2"]);
  assert.equal(out, "# 설명\n# 둘째\ngood.acct\ntwo_2\n");
});
