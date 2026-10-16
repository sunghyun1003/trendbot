// 대시보드 '관리' 화면의 뒷단. 로그인 확인은 _middleware.js 가 함 (data.email).
// GitHub 토큰(DASHBOARD_TOKEN)으로: 지금 수집/발행 실행, 사이트 켜기·끄기(sources.yaml 수정), 키 상태 확인.
// 이 값들은 '처음 설정'이 Pages 환경변수로 넣어 줍니다: GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH.

export const KEYS = [
  { name: "ANTHROPIC_API_KEY", label: "AI 편집 (Anthropic)", required: true },
  { name: "CLOUDFLARE_ACCOUNT_ID", label: "Cloudflare 계정 ID", required: true },
  { name: "CLOUDFLARE_API_TOKEN", label: "Cloudflare 토큰", required: true },
  { name: "ALLOWED_EMAILS", label: "사이트를 볼 팀원 이메일", required: true },
  { name: "DASHBOARD_TOKEN", label: "대시보드 버튼용 GitHub 토큰", required: true },
  { name: "YOUTUBE_API_KEY", label: "유튜브 (선택)", required: false },
  { name: "SITE_DOMAIN", label: "내 도메인 (선택)", required: false },
  { name: "META_ACCESS_TOKEN", label: "인스타 토큰 (선택)", required: false },
  { name: "IG_USER_ID", label: "인스타 계정 번호 (선택)", required: false },
  { name: "GMAIL_ADDRESS", label: "아침 메일 보내는 Gmail (선택)", required: false },
  { name: "GMAIL_APP_PASSWORD", label: "Gmail 앱 비밀번호 (선택)", required: false },
  { name: "NAVER_CLIENT_ID", label: "네이버 검색 API ID (선택)", required: false },
  { name: "NAVER_CLIENT_SECRET", label: "네이버 검색 API Secret (선택)", required: false },
];

async function gh(env, method, path, body) {
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}${path}`, {
    method,
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
               "User-Agent": "dsbg-dashboard", "X-GitHub-Api-Version": "2022-11-28" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`GitHub ${method} ${path} → ${r.status}`);
  return r.status === 204 ? null : r.json();
}

// sources.yaml 의 sources: 목록에서 id/name/enabled/kind 만 읽음 (주석·순서 보존을 위해 글자 단위로 다룸)
export function parseSources(text) {
  const lines = text.split("\n");
  const start = lines.findIndex((l) => l.startsWith("sources:"));
  const out = [];
  if (start < 0) return out;
  for (let i = start + 1; i < lines.length && !/^\S/.test(lines[i]); i++) {
    const m = lines[i].match(/^  - id:\s*([\w-]+)/);
    if (m) out.push({ id: m[1], name: m[1], enabled: true, kind: "html_list", line: i });
    const cur = out[out.length - 1];
    if (!cur || m) continue;
    const f = lines[i].match(/^    (name|enabled|kind):\s*([^#]*?)\s*(#.*)?$/);
    if (f) cur[f[1]] = f[1] === "enabled" ? f[2] === "true" : f[2];
  }
  return out;
}

export function setEnabled(text, id, enabled) {
  const lines = text.split("\n");
  const src = parseSources(text).find((s) => s.id === id);
  if (!src) throw new Error(`없는 사이트: ${id}`);
  for (let i = src.line + 1; i < lines.length && !/^  - |^\S/.test(lines[i]); i++) {
    if (/^    enabled:/.test(lines[i])) {
      lines[i] = lines[i].replace(/enabled:\s*(true|false)/, `enabled: ${enabled}`);
      return lines.join("\n");
    }
  }
  lines.splice(src.line + 1, 0, `    enabled: ${enabled}`);
  return lines.join("\n");
}

const b64decode = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
const b64encode = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));

const WATCHLIST = "config/watchlists/instagram.txt";

async function readFile(env, path) {
  const f = await gh(env, "GET", `/contents/${path}?ref=${env.GITHUB_BRANCH}`);
  return { text: b64decode(f.content), sha: f.sha };
}

// 인스타 감시 계정: 설명 주석은 그대로 두고 계정 줄만 바꿈
export function setWatchlist(text, accounts) {
  const head = text.split("\n").filter((l) => l.startsWith("#"));
  const clean = [...new Set(accounts.map((a) => a.trim().replace(/^@/, "")).filter((a) => /^[\w.]{1,30}$/.test(a)))];
  return [...head, ...clean].join("\n") + "\n";
}

async function readSources(env) {
  const f = await gh(env, "GET", `/contents/config/sources.yaml?ref=${env.GITHUB_BRANCH}`);
  return { text: b64decode(f.content), sha: f.sha };
}

export async function onRequestGet({ env }) {
  const out = { keys: [], runs: [], sources: [], repo: env.GITHUB_REPO || "", branch: env.GITHUB_BRANCH || "",
                ready: Boolean(env.GITHUB_TOKEN && env.GITHUB_REPO) };
  if (!out.ready) return Response.json(out);
  const [secrets, runs, src, wl] = await Promise.allSettled([
    gh(env, "GET", "/actions/secrets?per_page=100"),
    gh(env, "GET", "/actions/workflows/run.yml/runs?per_page=6"),
    readSources(env),
    readFile(env, WATCHLIST),
  ]);
  if (wl.status === "fulfilled") out.instagram = wl.value.text.split("\n").filter((l) => l.trim() && !l.startsWith("#"));
  const have = new Set(secrets.status === "fulfilled" ? secrets.value.secrets.map((s) => s.name) : []);
  out.keys = KEYS.map((k) => ({ ...k, ok: secrets.status === "fulfilled" ? have.has(k.name) : null }));
  if (runs.status === "fulfilled") {
    out.runs = runs.value.workflow_runs.map((r) => ({ status: r.status, conclusion: r.conclusion, event: r.event,
                                                     at: r.created_at, url: r.html_url }));
  }
  if (src.status === "fulfilled") out.sources = parseSources(src.value.text).map(({ line, ...s }) => s);
  return Response.json(out);
}

export async function onRequestPost({ request, env, data }) {
  let body;
  try { body = await request.json(); } catch { return new Response("bad json", { status: 400 }); }
  try {
    if (!env.GITHUB_TOKEN) return Response.json({ ok: false, message: "DASHBOARD_TOKEN 키를 넣고 '처음 설정'을 다시 실행해 주세요" }, { status: 400 });
    if (body.action === "run") {
      const task = body.task === "publish" ? "publish" : "collect";
      await gh(env, "POST", "/actions/workflows/run.yml/dispatches", { ref: env.GITHUB_BRANCH, inputs: { task } });
      return Response.json({ ok: true, message: task === "publish" ? "발행을 시작했어요 (약 5분)" : "수집을 시작했어요 (약 2분)" });
    }
    if (body.action === "watchlist") {
      const { text, sha } = await readFile(env, WATCHLIST);
      const next = setWatchlist(text, Array.isArray(body.accounts) ? body.accounts.map(String) : []);
      await gh(env, "PUT", `/contents/${WATCHLIST}`, {
        message: `대시보드: 인스타 감시 계정 수정 (${data.email})`, content: b64encode(next), sha, branch: env.GITHUB_BRANCH,
      });
      return Response.json({ ok: true, message: "저장했어요. 다음 수집부터 반영" });
    }
    if (body.action === "toggle") {
      const { text, sha } = await readSources(env);
      const next = setEnabled(text, String(body.id), Boolean(body.enabled));
      await gh(env, "PUT", "/contents/config/sources.yaml", {
        message: `대시보드: ${body.id} ${body.enabled ? "켜기" : "끄기"} (${data.email})`,
        content: b64encode(next), sha, branch: env.GITHUB_BRANCH,
      });
      return Response.json({ ok: true, message: body.enabled ? "켰어요. 다음 수집부터 반영" : "껐어요. 다음 수집부터 반영" });
    }
  } catch (e) {
    return Response.json({ ok: false, message: String(e.message || e) }, { status: 502 });
  }
  return new Response("bad action", { status: 400 });
}
