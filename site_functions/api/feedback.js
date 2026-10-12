// Cloudflare Pages Function: 피드백 버튼·'놓친 것'을 저장합니다.
// 사이트 전체가 Cloudflare Access(회사 이메일 로그인) 뒤에 있으므로, 로그인한 사람만 여기에 닿습니다.
// 저장소: Pages 프로젝트 설정에서 KV 네임스페이스를 FEEDBACK 이름으로 연결해야 합니다.

async function verifiedEmail(request, env) {
  // Access가 붙여 주는 JWT의 서명을 확인한 뒤 이메일을 꺼냄
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return null;
  const [h, p, s] = token.split(".");
  const header = JSON.parse(atob(h.replace(/-/g, "+").replace(/_/g, "/")));
  const payload = JSON.parse(atob(p.replace(/-/g, "+").replace(/_/g, "/")));
  if (!payload.aud || !payload.aud.includes(env.ACCESS_AUD)) return null;
  if (payload.exp * 1000 < Date.now()) return null;
  const certs = await (await fetch(`https://${env.ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`)).json();
  const jwk = certs.keys.find((k) => k.kid === header.kid);
  if (!jwk) return null;
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const sig = Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, sig, new TextEncoder().encode(`${h}.${p}`));
  return ok ? payload.email : null;
}

export async function onRequestPost({ request, env }) {
  const email = await verifiedEmail(request, env);
  if (!email) return new Response("unauthorized", { status: 401 });
  let body;
  try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
  const allowed = ["keep", "drop", "star", "unstar", "restore", "missed"];
  if (!allowed.includes(body.action)) return new Response("bad action", { status: 400 });
  const rec = {
    date: String(body.date || "").slice(0, 10), card: String(body.card || "").slice(0, 40),
    action: body.action, reason: String(body.reason || "").slice(0, 20), text: String(body.text || "").slice(0, 500),
    user: email, at: new Date().toISOString(),
  };
  await env.FEEDBACK.put(`${rec.at}-${crypto.randomUUID()}`, JSON.stringify(rec), { expirationTtl: 60 * 60 * 24 * 400 });
  return Response.json({ ok: true });
}

export async function onRequestGet({ request, env }) {
  // 집 PC가 피드백을 가져갈 때 사용 (EXPORT_TOKEN 필요)
  const url = new URL(request.url);
  if (!env.EXPORT_TOKEN || url.searchParams.get("token") !== env.EXPORT_TOKEN) return new Response("forbidden", { status: 403 });
  // since(예: 2026-10-12) 이후 기록만. 키가 저장 시각으로 시작하므로 문자열 비교로 거름
  const since = url.searchParams.get("since") || "";
  const out = [];
  let cursor;
  do {
    const page = await env.FEEDBACK.list({ cursor });
    for (const k of page.keys) if (k.name >= since) out.push(JSON.parse(await env.FEEDBACK.get(k.name)));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return Response.json(out);
}
