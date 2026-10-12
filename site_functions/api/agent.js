// 집 PC 도우미 전용 창구. Access 로그인 대신 '기기 토큰'으로 확인합니다.
// 기기 토큰은 대시보드의 '집 PC 도우미 받기'가 만들고, KV에는 토큰의 해시만 저장합니다.

const MEDIA_NAME = /^\d{4}-\d{2}-\d{2}\/[\w-]+\.webp$/;
const WEEK = 60 * 60 * 24 * 7;

export async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function device(request, env) {
  const token = request.headers.get("X-Agent-Token") || "";
  if (token.length < 32) return null;
  const rec = await env.FEEDBACK.get(`agent:device:${await sha256(token)}`);
  return rec ? JSON.parse(rec) : null;
}

const asset = (env, request, path) => env.ASSETS.fetch(new URL(path, request.url));

export async function onRequestGet({ request, env }) {
  if (!(await device(request, env))) return new Response("unknown device", { status: 401 });
  const get = new URL(request.url).searchParams.get("get");
  if (get === "install") return asset(env, request, "/helper/install.ps1");
  if (get === "code") return asset(env, request, "/helper/helper.zip");
  if (get === "cmd") {  // 대시보드에서 누른 '디젤매니아 지금 수집'
    const cmd = await env.FEEDBACK.get("agent:cmd");
    if (cmd) await env.FEEDBACK.delete("agent:cmd");
    return Response.json({ cmd: cmd || null });
  }
  return new Response("bad request", { status: 400 });
}

export async function onRequestPost({ request, env }) {
  const dev = await device(request, env);
  if (!dev) return new Response("unknown device", { status: 401 });
  const url = new URL(request.url);
  const put = url.searchParams.get("put");
  const now = new Date().toISOString();
  if (put === "status") {
    let s;
    try { s = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
    const rec = { naver: String(s.naver || ""), message: String(s.message || "").slice(0, 200),
                  version: String(s.version || "").slice(0, 20), last_collect: s.last_collect || null, at: now };
    await env.FEEDBACK.put("agent:status", JSON.stringify(rec));
    return Response.json({ ok: true });
  }
  if (put === "batch") {
    const text = await request.text();
    if (text.length > 5_000_000) return new Response("too large", { status: 413 });
    try { JSON.parse(text); } catch { return new Response("bad json", { status: 400 }); }
    await env.FEEDBACK.put(`agent:batch:${now}`, text, { expirationTtl: WEEK });
    return Response.json({ ok: true });
  }
  if (put === "media") {
    const name = url.searchParams.get("name") || "";
    if (!MEDIA_NAME.test(name)) return new Response("bad name", { status: 400 });
    const body = await request.arrayBuffer();
    if (body.byteLength > 3_000_000) return new Response("too large", { status: 413 });
    await env.FEEDBACK.put(`agent:media:${name}`, body, { expirationTtl: WEEK });
    return Response.json({ ok: true });
  }
  return new Response("bad request", { status: 400 });
}
