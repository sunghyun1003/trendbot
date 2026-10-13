// ㄷㅅㅂㄱ 정시 실행기 (Cloudflare Worker, 무료).
// GitHub 자체 예약은 붐비면 1~2시간씩 늦어서, 정해진 시각에 GitHub '지금 실행' 버튼을 대신 누릅니다.
// - 발행: 매일 06:30, 07:30에 한 번 더 확인 (이미 발행됐으면 건너뜀)  /  수집: 2시간마다
// '처음 설정'이 자동으로 올리고 시각을 등록합니다. 값: GITHUB_TOKEN(비밀), GITHUB_REPO, GITHUB_BRANCH, PUBLISH_CRON.

export async function dispatch(env, task) {
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/run.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
               "User-Agent": "dsbg-scheduler", "X-GitHub-Api-Version": "2022-11-28" },
    body: JSON.stringify({ ref: env.GITHUB_BRANCH, inputs: { task } }),
  });
  if (!r.ok) throw new Error(`GitHub 실행 요청 실패 ${r.status}`);
}

export default {
  async scheduled(event, env, ctx) {
    const publish = (env.PUBLISH_CRON || "").split(",").includes(event.cron);
    ctx.waitUntil(dispatch(env, publish ? "publish_auto" : "collect"));
  },
};
