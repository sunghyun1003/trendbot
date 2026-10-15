"""'꼭 알아야 할 것' 판정: 확산 게이트(A/B/M 등급), 중복 제거, 채널 1위."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from trendbot.pipeline.cluster import Story

GRADE_ORDER = {"A": 0, "M": 1, "B": 2}
GRADE_LABEL = {"A": "전국 확산", "B": "확산 중", "M": "한 곳 대박"}


@dataclass
class Candidate:
    story: Story
    grade: str
    pods: set[str]
    community_pods: set[str]
    gender_cross: bool
    age_cross: bool
    s_level: int  # 0 없음, 1 있음, 2 강함
    traffic: int
    news_count: int
    yt_views: int
    score: float
    badges: list[str] = field(default_factory=list)
    update: bool = False
    first_date: str | None = None   # 예전 판에 처음 나온 날 (이어지는 이야기일 때)

    @property
    def id(self) -> str:
        key = "|".join(sorted(i.url or i.title for i in self.story.items))
        return hashlib.sha1(key.encode()).hexdigest()[:10]


def _pods_of(story: Story, src_pod: dict[str, str]) -> set[str]:
    pods = set()
    for it in story.items:
        if it.kind == "post" and it.source_id in src_pod:
            pods.add(src_pod[it.source_id])
        elif it.kind == "youtube" and (it.data.get("value") or 0) >= 100_000:
            pods.add("P7")
        elif it.kind in ("xtrend", "insta"):  # X 실시간 트렌드 키워드, 인스타 감시 계정의 튄 게시물 = SNS 반향
            pods.add("P8")
    return pods


def evaluate(story: Story, cfg: dict) -> Candidate | None:
    g = cfg["grading"]
    pods_cfg = cfg["pods"]
    src_pod = {s["id"]: s["pod"] for s in cfg["sources"]}
    src_power = {s["id"]: s.get("power", 1) for s in cfg["sources"]}
    pods = _pods_of(story, src_pod)
    community = {p for p in pods if not pods_cfg[p].get("platform")}
    genders = {pods_cfg[p]["gender"] for p in community}
    ages = {pods_cfg[p]["age"] for p in community}
    gender_cross = {"M", "F"} <= genders
    age_cross = "young" in ages and "old" in ages

    traffic = max([i.data.get("value") or 0 for i in story.items if i.kind == "trend"] or [0])
    news_count = sum(1 for i in story.items if i.kind == "news")
    yt = [i for i in story.items if i.kind == "youtube"]
    yt_views = max([i.data.get("value") or 0 for i in yt] or [0])
    s_level = 0
    if traffic >= g["s_traffic_strong"] or news_count >= 4:
        s_level = 2
    elif traffic >= g["s_traffic_min"] or news_count >= 2:
        s_level = 1
    platform = "P7" in pods or "P8" in pods

    grade = None
    if (len(community) >= g["a_min_pods"] and gender_cross) or (len(pods) >= g["a_alt_min_pods"] and s_level):
        grade = "A"
    elif (len(community) >= g["b_min_pods"] and (s_level or platform)) or (s_level == 2 and community):
        grade = "B"
    else:
        posts = story.posts
        yt_long = max([i.data.get("value") or 0 for i in yt if not i.data.get("extra", {}).get("shorts")] or [0])
        yt_shorts = max([i.data.get("value") or 0 for i in yt if i.data.get("extra", {}).get("shorts")] or [0])
        # 한 곳 대박: 화력 2 이상 사이트의 1위 글만 (작은 사이트 1위는 '커뮤니티별 1위' 탭에서)
        big = any(src_power.get(p.source_id, 1) >= 2 and (p.data.get("best_rank") or 99) <= g["m_rank_top"]
                  and (p.data.get("views") or 0) >= g["m_min_views"] for p in posts)
        if big or yt_long >= 1_000_000 or yt_shorts >= 3_000_000:
            grade = "M"
    if not grade:
        return None

    # 화력: 이야기가 올라온 사이트들의 화력 합 (디시·더쿠·펨코·인티처럼 큰 곳에 올라올수록 점수 ↑)
    power = sum(src_power.get(sid, 1) for sid in {p.source_id for p in story.posts})
    score = (12 * min(len(community), 6) + 8 * min(len(pods - community), 2) + 12 * gender_cross
             + 8 * age_cross + {0: 0, 1: 12, 2: 18}[s_level] + 3 * min(power, 12))
    badges = [GRADE_LABEL[grade]]
    if gender_cross:
        badges.append("남녀공통")
    return Candidate(story, grade, pods, community, gender_cross, age_cross, s_level, traffic, news_count,
                     yt_views, score, badges)


def _overlaps(c: Candidate, pub: dict) -> bool:
    urls = {i.url for i in c.story.posts}
    if urls & pub["post_urls"]:
        return True
    toks = c.story.toks
    shared = toks & pub["tokens"]
    union = toks | pub["tokens"]
    return len(shared) >= 2 and len(shared) / max(len(union), 1) >= 0.3


def dedupe_against_history(cands: list[Candidate], published: list[dict], cfg: dict) -> list[Candidate]:
    """어제·최근 7일에 나온 이야기는 숨김. 새 포드로 크게 번졌으면 '업데이트'로 한 번 더."""
    out = []
    for c in cands:
        prior = [p for p in published if _overlaps(c, p)]
        if not prior:
            c.badges.insert(0, "NEW")
            out.append(c)
            continue
        seen_pods = set().union(*(p["pods"] for p in prior))
        if len(c.pods - seen_pods) >= cfg["grading"]["update_new_pods"]:
            c.update = True
            c.first_date = min(p["date"] for p in prior)
            c.badges.insert(0, "업데이트")
            out.append(c)
    return out


def umbrella(cands: list[Candidate]) -> list[tuple[Candidate, list[Candidate]]]:
    """같은 큰 사건에서 갈라진 이야기를 카드 1장 + 하위 줄로 묶음."""
    cands = sorted(cands, key=lambda c: (GRADE_ORDER[c.grade], -c.score))
    groups: list[tuple[Candidate, list[Candidate]]] = []
    for c in cands:
        for head, subs in groups:
            shared = c.story.toks & head.story.toks
            small = min(len(c.story.toks), len(head.story.toks)) or 1
            if (c.story.anchor and c.story.anchor == head.story.anchor) or (
                len(shared) >= 3 and len(shared) / small >= 0.25
            ):
                if len(subs) < 3:
                    subs.append(c)
                break
        else:
            groups.append((c, []))
    return groups


def select(stories: list[Story], cfg: dict, published: list[dict]) -> list[tuple[Candidate, list[Candidate]]]:
    cands = [c for c in (evaluate(s, cfg) for s in stories) if c]
    cands = dedupe_against_history(cands, published, cfg)
    ms = [c for c in cands if c.grade == "M"]
    ms = sorted(ms, key=lambda c: -c.score)[cfg["grading"]["m_max_per_day"]:]
    cands = [c for c in cands if c not in ms]
    return umbrella(cands)


def _composite(p: dict) -> float:
    return (p.get("views") or 0) + 10 * (p.get("likes") or 0) + 20 * (p.get("comments") or 0)


def champions(posts: list[dict], cfg: dict, shown: set[tuple[str, str]], history: dict[str, list[float]]) -> list[dict]:
    """채널마다 종합 반응 1위 1개 (이미 1위로 보여 준 글은 제외)."""
    g = cfg["grading"]
    out = []
    for src in cfg["sources"]:
        if not (src.get("champion") and src.get("enabled", True)):
            continue
        mine = [p for p in posts if p["source_id"] == src["id"] and (src["id"], p["url"]) not in shown]
        if not mine:
            out.append({"source_id": src["id"], "name": src["name"], "post": None, "score": 0, "strength": None})
            continue
        best = max(mine, key=lambda p: (_composite(p), -(p.get("best_rank") or 99)))
        score = _composite(best)
        hist = sorted(history.get(src["id"], []))
        if len(hist) < 7:
            strength = "기록 쌓는 중"
        else:
            pct = sum(1 for h in hist if h < score) / len(hist)
            strength = "역대급" if pct >= g["champion_record_pct"] else "강함" if pct >= g["champion_strong_pct"] else "평소 수준"
        out.append({"source_id": src["id"], "name": src["name"], "post": best, "score": score, "strength": strength})
    return out
