// /api/* 공통 관문: Cloudflare Access 로그인 확인.
// 사이트 전체가 Access(팀원 이메일 로그인) 뒤에 있고, 여기서 한 번 더 서명을 검증해 이메일을 꺼냅니다.
// 예외: /api/agent 는 집 PC 도우미용이라 Access를 건너뛰고(처음 설정이 '통과' 규칙을 만듦) 기기 토큰으로 확인합니다.

const b64 = (s) => atob(s.replace(/-/g, "+").replace(/_/g, "/"));

export async function verifiedEmail(request, env) {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return null;
  try {
    const [h, p, s] = token.split(".");
    const header = JSON.parse(b64(h));
    const payload = JSON.parse(b64(p));
    if (!payload.aud || !payload.aud.includes(env.ACCESS_AUD)) return null;
    if (payload.exp * 1000 < Date.now()) return null;
    const certs = await (await fetch(`https://${env.ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs`)).json();
    const jwk = certs.keys.find((k) => k.kid === header.kid);
    if (!jwk) return null;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const sig = Uint8Array.from(b64(s), (c) => c.charCodeAt(0));
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, sig, new TextEncoder().encode(`${h}.${p}`));
    return ok ? payload.email : null;
  } catch {
    return null;
  }
}

export async function onRequest(context) {
  const { request, env, next, data } = context;
  if (new URL(request.url).pathname.startsWith("/api/agent")) return next();
  data.email = await verifiedEmail(request, env);
  if (!data.email) return new Response("unauthorized", { status: 401 });
  return next();
}
