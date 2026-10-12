// 피드백 Pages Function 테스트: node --test tests/functions
// 가짜 Access 인증서와 가짜 KV로, 로그인 확인·저장·내보내기를 확인합니다.
import { test } from "node:test";
import assert from "node:assert/strict";
import { onRequestPost, onRequestGet } from "../../site_functions/api/feedback.js";

const b64url = (buf) => Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const { privateKey, publicKey } = await crypto.subtle.generateKey(
  { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
  true, ["sign", "verify"]);
const jwk = { ...(await crypto.subtle.exportKey("jwk", publicKey)), kid: "k1" };
globalThis.fetch = async () => new Response(JSON.stringify({ keys: [jwk] }));

async function jwt(payload, key = privateKey) {
  const h = b64url(JSON.stringify({ alg: "RS256", kid: "k1" }));
  const p = b64url(JSON.stringify(payload));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${h}.${p}`));
  return `${h}.${p}.${b64url(sig)}`;
}

function kv() {
  const m = new Map();
  return {
    m,
    put: async (k, v) => m.set(k, v),
    get: async (k) => m.get(k),
    list: async () => ({ keys: [...m.keys()].sort().map((name) => ({ name })), list_complete: true }),
  };
}

const env = () => ({ ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com", ACCESS_AUD: "aud1", EXPORT_TOKEN: "t0ken", FEEDBACK: kv() });
const post = (token, body) => new Request("https://x/api/feedback", {
  method: "POST", headers: token ? { "Cf-Access-Jwt-Assertion": token } : {}, body: JSON.stringify(body) });
const soon = () => Math.floor(Date.now() / 1000) + 600;

test("로그인 토큰이 없으면 거절", async () => {
  const r = await onRequestPost({ request: post(null, { action: "keep" }), env: env() });
  assert.equal(r.status, 401);
});

test("다른 키로 서명한 토큰은 거절", async () => {
  const other = await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign"]);
  const t = await jwt({ aud: ["aud1"], exp: soon(), email: "a@b.c" }, other.privateKey);
  assert.equal((await onRequestPost({ request: post(t, { action: "keep" }), env: env() })).status, 401);
});

test("만료·다른 앱 토큰은 거절", async () => {
  const e = env();
  assert.equal((await onRequestPost({ request: post(await jwt({ aud: ["aud1"], exp: 1, email: "a@b.c" }), { action: "keep" }), env: e })).status, 401);
  assert.equal((await onRequestPost({ request: post(await jwt({ aud: ["zzz"], exp: soon(), email: "a@b.c" }), { action: "keep" }), env: e })).status, 401);
});

test("정상 토큰이면 저장되고, 내보내기로 날짜 이후 기록을 받음", async () => {
  const e = env();
  const t = await jwt({ aud: ["aud1"], exp: soon(), email: "me@team.com" });
  const r = await onRequestPost({ request: post(t, { action: "drop", reason: "already", card: "c1", date: "2026-10-12" }), env: e });
  assert.equal(r.status, 200);
  assert.equal((await onRequestPost({ request: post(t, { action: "hack" }), env: e })).status, 400);
  e.FEEDBACK.m.set("2000-01-01T00:00:00Z-old", JSON.stringify({ action: "keep" }));

  assert.equal((await onRequestGet({ request: new Request("https://x/api/feedback?token=bad"), env: e })).status, 403);
  const rows = await (await onRequestGet({ request: new Request("https://x/api/feedback?token=t0ken&since=2020-01-01"), env: e })).json();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].user, "me@team.com");
  assert.equal(rows[0].reason, "already");
});
