// 대시보드 '관리' 화면의 뒷단. 로그인 확인은 _middleware.js 가 함 (data.email).
// GitHub 토큰(DASHBOARD_TOKEN)으로: 지금 수집/발행 실행, 사이트 켜기·끄기(sources.yaml 수정), 키 상태 확인.
// 이 값들은 '처음 설정'이 Pages 환경변수로 넣어 줍니다: GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH.

import { sha256 } from "./agent.js";

export const KEYS = [
  { name: "ANTHROPIC_API_KEY", label: "AI 편집 (Anthropic)", required: true },
  { name: "CLOUDFLARE_ACCOUNT_ID", label: "Cloudflare 계정 ID", required: true },
  { name: "CLOUDFLARE_API_TOKEN", label: "Cloudflare 토큰", required: true },
  { name: "ALLOWED_EMAILS", label: "사이트를 볼 팀원 이메일", required: true },
  { name: "DASHBOARD_TOKEN", label: "대시보드 버튼용 GitHub 토큰", required: true },
  { name: "YOUTUBE_API_KEY", label: "유튜브 (선택)", required: false },
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

async function readSources(env) {
  const f = await gh(env, "GET", `/contents/config/sources.yaml?ref=${env.GITHUB_BRANCH}`);
  return { text: b64decode(f.content), sha: f.sha };
}

export function installer(site, token) {
  const ps = `$ErrorActionPreference='Stop'; $h=@{'X-Agent-Token'='${token}'}; $p=Join-Path $env:TEMP 'dsbg-install.ps1'; ` +
    `Invoke-WebRequest -UseBasicParsing -Headers $h -Uri '${site}/api/agent?get=install' -OutFile $p; ` +
    `& $p -Token '${token}' -Site '${site}'`;
  return ["@echo off", "chcp 65001 >nul", "echo ㄷㅅㅂㄱ 집 PC 도우미를 설치합니다. 창을 닫지 말고 기다려 주세요...",
          `powershell -NoProfile -ExecutionPolicy Bypass -Command "${ps}"`, "pause", ""].join("\r\n");
}

export async function onRequestGet({ env }) {
  const out = { keys: [], runs: [], sources: [], agent: null, repo: env.GITHUB_REPO || "", branch: env.GITHUB_BRANCH || "",
                ready: Boolean(env.GITHUB_TOKEN && env.GITHUB_REPO) };
  out.agent = JSON.parse((await env.FEEDBACK.get("agent:status")) || "null");
  if (!out.ready) return Response.json(out);
  const [secrets, runs, src] = await Promise.allSettled([
    gh(env, "GET", "/actions/secrets?per_page=100"),
    gh(env, "GET", "/actions/workflows/run.yml/runs?per_page=6"),
    readSources(env),
  ]);
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
    if (body.action === "helper") {  // 집 PC 도우미 설치 파일 (기기 토큰 포함)
      const token = [...crypto.getRandomValues(new Uint8Array(24))].map((b) => b.toString(16).padStart(2, "0")).join("");
      await env.FEEDBACK.put(`agent:device:${await sha256(token)}`, JSON.stringify({ by: data.email, at: new Date().toISOString() }));
      return new Response(installer(new URL(request.url).origin, token), {
        headers: { "content-type": "application/octet-stream", "content-disposition": 'attachment; filename="dsbg-setup.cmd"' },
      });
    }
    if (body.action === "naver_now") {
      await env.FEEDBACK.put("agent:cmd", "collect", { expirationTtl: 60 * 60 * 24 });
      return Response.json({ ok: true, message: "집 PC가 30분 안에 디젤매니아를 수집합니다" });
    }
    if (!env.GITHUB_TOKEN) return Response.json({ ok: false, message: "DASHBOARD_TOKEN 키를 넣고 '처음 설정'을 다시 실행해 주세요" }, { status: 400 });
    if (body.action === "run") {
      const task = body.task === "publish" ? "publish" : "collect";
      await gh(env, "POST", "/actions/workflows/run.yml/dispatches", { ref: env.GITHUB_BRANCH, inputs: { task } });
      return Response.json({ ok: true, message: task === "publish" ? "발행을 시작했어요 (약 5분)" : "수집을 시작했어요 (약 2분)" });
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
