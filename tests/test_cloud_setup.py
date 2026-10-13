import pytest

from tests.fake_cf import FakeCF, client
from trendbot import cloud_setup


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "Me@Team.com, you@team.com")
    monkeypatch.setenv("DASHBOARD_TOKEN", "github_pat_x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "me/trendbot")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")


def test_setup_creates_everything_and_is_rerunnable(env, monkeypatch):
    fake = FakeCF()
    cf = client(fake, monkeypatch)
    lines = cloud_setup.run(cf)
    assert lines[0] == "사이트 주소: https://dsbg.pages.dev"
    assert [n["title"] for n in fake.namespaces] == ["dsbg-store"]
    assert [i["type"] for i in fake.idps] == ["onetimepin"]
    (main,) = fake.apps  # 잠금 예외 앱은 더 이상 만들지 않음
    assert main["self_hosted_domains"] == ["dsbg.pages.dev", "*.dsbg.pages.dev"]
    assert main["policies"][0]["include"] == [{"email": {"email": "me@team.com"}}, {"email": {"email": "you@team.com"}}]
    conf = fake.projects["dsbg"]["patches"][-1]["deployment_configs"]["production"]
    assert conf["kv_namespaces"]["FEEDBACK"]["namespace_id"] == "ns1"
    assert conf["env_vars"]["ACCESS_AUD"]["value"] == "aud1"
    assert conf["env_vars"]["GITHUB_TOKEN"] == {"type": "secret_text", "value": "github_pat_x"}

    monkeypatch.setenv("ALLOWED_EMAILS", "me@team.com")  # 다시 눌러도 중복 생성 없이 갱신
    cloud_setup.run(cf)
    assert len(fake.namespaces) == 1 and len(fake.apps) == 1 and len(fake.idps) == 1
    assert fake.apps[0]["policies"][0]["include"] == [{"email": {"email": "me@team.com"}}]


def test_setup_explains_missing_pieces(env, monkeypatch):
    fake = FakeCF()
    fake.org = None
    with pytest.raises(cloud_setup.SetupError, match="Zero Trust"):
        cloud_setup.run(client(fake, monkeypatch))
    monkeypatch.setenv("ALLOWED_EMAILS", "not-an-email")
    with pytest.raises(cloud_setup.SetupError, match="ALLOWED_EMAILS"):
        cloud_setup.run(client(FakeCF(), monkeypatch))


def test_custom_domain_is_locked_too(env, monkeypatch):
    monkeypatch.setenv("SITE_DOMAIN", "https://DSBG.example.com/")
    fake = FakeCF()
    lines = cloud_setup.run(client(fake, monkeypatch))
    (main,) = fake.apps
    assert "dsbg.example.com" in main["self_hosted_domains"]           # 새 주소도 팀원만
    assert fake.projects["dsbg"]["domains"] == [{"name": "dsbg.example.com", "status": "pending"}]
    assert any("내 도메인: https://dsbg.example.com" in l for l in lines)
    cloud_setup.run(client(fake, monkeypatch))                          # 다시 눌러도 중복 추가 없음
    assert len(fake.projects["dsbg"]["domains"]) == 1
    # 잠금이 도메인 연결보다 먼저
    calls = [c for c in fake.calls if c[1] in ("/access/apps", "/pages/projects/dsbg/domains") and c[0] == "POST"]
    assert calls[0][1] == "/access/apps"


def test_bad_domain_rejected(env, monkeypatch):
    monkeypatch.setenv("SITE_DOMAIN", "not a domain")
    with pytest.raises(cloud_setup.SetupError, match="SITE_DOMAIN"):
        cloud_setup.run(client(FakeCF(), monkeypatch))


def test_old_helper_bypass_app_is_removed(env, monkeypatch):
    fake = FakeCF()
    fake.apps.append({"id": "old1", "name": "ㄷㅅㅂㄱ 집 PC 도우미 창구", "domain": "trendbot.pages.dev/api/agent"})
    cloud_setup.run(client(fake, monkeypatch))
    assert [a["name"] for a in fake.apps] == ["ㄷㅅㅂㄱ"]


def test_scheduler_worker_installed(env, monkeypatch):
    fake = FakeCF()
    lines = cloud_setup.run(client(fake, monkeypatch))
    w = fake.workers["dsbg-scheduler"]
    assert [c["cron"] for c in w["schedules"]] == ["30 21 * * *", "7 */2 * * *"]
    assert b"github_pat_x" in w["upload"] and b"export default" in w["upload"]
    assert any(l.startswith("정시 실행기: 매일 06:30") for l in lines)


def test_scheduler_permission_missing_is_explained_not_fatal(env, monkeypatch):
    fake = FakeCF()
    fake.worker_denied = True
    lines = cloud_setup.run(client(fake, monkeypatch))
    assert any("Workers Scripts: Edit" in l for l in lines)
    assert fake.apps  # 나머지 설정은 그대로 진행


def test_old_trendbot_site_is_removed_or_kept_locked(env, monkeypatch):
    fake = FakeCF()
    fake.projects["trendbot"] = {"name": "trendbot"}
    cloud_setup.run(client(fake, monkeypatch))
    assert "trendbot" not in fake.projects and "dsbg" in fake.projects   # 예전 주소 삭제, 새 주소 생성

    fake = FakeCF()
    fake.projects["trendbot"] = {"name": "trendbot"}
    fake.delete_denied = True
    lines = cloud_setup.run(client(fake, monkeypatch))
    (main,) = fake.apps
    assert "trendbot.pages.dev" in main["self_hosted_domains"]           # 못 지우면 잠금은 유지
    assert any("예전 주소" in l for l in lines)
