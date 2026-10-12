// 피드백 버튼·'놓친 것' 저장. 로그인 확인은 _middleware.js 가 함 (data.email).
// 저장소: KV(FEEDBACK 이름으로 연결, '처음 설정'이 자동 연결). 발행 때 GitHub 서버가 가져가고 지웁니다.

export async function onRequestPost({ request, env, data }) {
  let body;
  try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
  const allowed = ["keep", "drop", "star", "unstar", "restore", "missed"];
  if (!allowed.includes(body.action)) return new Response("bad action", { status: 400 });
  const rec = {
    date: String(body.date || "").slice(0, 10), card: String(body.card || "").slice(0, 40),
    action: body.action, reason: String(body.reason || "").slice(0, 20), text: String(body.text || "").slice(0, 500),
    user: data.email, at: new Date().toISOString(),
  };
  await env.FEEDBACK.put(`fb:${rec.at}-${crypto.randomUUID()}`, JSON.stringify(rec), { expirationTtl: 60 * 60 * 24 * 90 });
  return Response.json({ ok: true });
}
