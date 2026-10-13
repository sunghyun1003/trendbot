import { test } from "node:test";
import assert from "node:assert/strict";
import scheduler from "../../worker/scheduler.js";

test("정시 실행기: 발행 시각엔 publish_auto, 그 외엔 collect 로 GitHub 실행", async () => {
  const sent = [];
  globalThis.fetch = async (url, opt) => { sent.push([url, JSON.parse(opt.body), opt.headers.Authorization]); return new Response(null, { status: 204 }); };
  const env = { GITHUB_TOKEN: "t", GITHUB_REPO: "me/trendbot", GITHUB_BRANCH: "main", PUBLISH_CRON: "30 21 * * *" };
  const run = async (cron) => { let p; await scheduler.scheduled({ cron }, env, { waitUntil: (x) => { p = x; } }); await p; };
  await run("30 21 * * *");
  await run("7 */2 * * *");
  assert.deepEqual(sent.map((s) => s[1].inputs.task), ["publish_auto", "collect"]);
  assert.equal(sent[0][0], "https://api.github.com/repos/me/trendbot/actions/workflows/run.yml/dispatches");
  assert.equal(sent[0][1].ref, "main");
  assert.equal(sent[0][2], "Bearer t");
});

test("정시 실행기: GitHub가 거절하면 실패로 남김 (Cloudflare 기록에 보임)", async () => {
  globalThis.fetch = async () => new Response("no", { status: 401 });
  const env = { GITHUB_TOKEN: "t", GITHUB_REPO: "me/trendbot", GITHUB_BRANCH: "main", PUBLISH_CRON: "x" };
  let p;
  await scheduler.scheduled({ cron: "y" }, env, { waitUntil: (x) => { p = x; } });
  await assert.rejects(p, /401/);
});
