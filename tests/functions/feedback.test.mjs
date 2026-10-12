// node --test tests/functions/*.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { onRequest } from "../../site_functions/api/_middleware.js";
import { onRequestPost } from "../../site_functions/api/feedback.js";
import { kv, accessKeys, otherKey, jwt, soon } from "./helpers.mjs";

const { privateKey, certs } = await accessKeys();
globalThis.fetch = async () => new Response(JSON.stringify(certs));
const env = () => ({ ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com", ACCESS_AUD: "aud1", FEEDBACK: kv() });

async function gate(path, token) {
  const ctx = { request: new Request(`https://x${path}`, { headers: token ? { "Cf-Access-Jwt-Assertion": token } : {} }),
                env: env(), data: {}, next: async () => new Response("passed") };
  const r = await onRequest(ctx);
  return { status: r.status, email: ctx.data.email };
}

test("관문: 토큰 없음·다른 키·만료·다른 앱은 401", async () => {
  assert.equal((await gate("/api/feedback", null)).status, 401);
  assert.equal((await gate("/api/feedback", await jwt({ aud: ["aud1"], exp: soon(), email: "a@b.c" }, await otherKey()))).status, 401);
  assert.equal((await gate("/api/feedback", await jwt({ aud: ["aud1"], exp: 1, email: "a@b.c" }, privateKey))).status, 401);
  assert.equal((await gate("/api/feedback", await jwt({ aud: ["zzz"], exp: soon(), email: "a@b.c" }, privateKey))).status, 401);
  assert.equal((await gate("/api/admin", "garbage.token.x")).status, 401);
});

test("관문: 정상 토큰이면 통과하고 이메일을 넘김, /api/agent 는 Access 없이 통과", async () => {
  const ok = await gate("/api/admin", await jwt({ aud: ["aud1"], exp: soon(), email: "me@team.com" }, privateKey));
  assert.equal(ok.status, 200);
  assert.equal(ok.email, "me@team.com");
  assert.equal((await gate("/api/agent?get=cmd", null)).status, 200);
});

test("피드백: fb: 접두어로 저장, 잘못된 동작은 400", async () => {
  const e = env();
  const post = (body) => new Request("https://x/api/feedback", { method: "POST", body: JSON.stringify(body) });
  const r = await onRequestPost({ request: post({ action: "drop", reason: "already", card: "c1", date: "2026-10-12" }), env: e, data: { email: "me@team.com" } });
  assert.equal(r.status, 200);
  assert.equal((await onRequestPost({ request: post({ action: "hack" }), env: e, data: { email: "me@team.com" } })).status, 400);
  const [key] = [...e.FEEDBACK.m.keys()];
  assert.match(key, /^fb:20\d\d-/);
  assert.equal(JSON.parse(e.FEEDBACK.m.get(key)).user, "me@team.com");
});
