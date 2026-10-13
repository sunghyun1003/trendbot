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
    assert lines[0] == "사이트 주소: https://trendbot.pages.dev"
    assert [n["title"] for n in fake.namespaces] == ["dsbg-store"]
    assert [i["type"] for i in fake.idps] == ["onetimepin"]
    main, agent = fake.apps
    assert main["self_hosted_domains"] == ["trendbot.pages.dev", "*.trendbot.pages.dev"]
    assert main["policies"][0]["include"] == [{"email": {"email": "me@team.com"}}, {"email": {"email": "you@team.com"}}]
    assert agent["domain"] == "trendbot.pages.dev/api/agent" and agent["policies"][0]["decision"] == "bypass"
    conf = fake.projects["trendbot"]["patches"][-1]["deployment_configs"]["production"]
    assert conf["kv_namespaces"]["FEEDBACK"]["namespace_id"] == "ns1"
    assert conf["env_vars"]["ACCESS_AUD"]["value"] == "aud1"
    assert conf["env_vars"]["GITHUB_TOKEN"] == {"type": "secret_text", "value": "github_pat_x"}

    monkeypatch.setenv("ALLOWED_EMAILS", "me@team.com")  # 다시 눌러도 중복 생성 없이 갱신
    cloud_setup.run(cf)
    assert len(fake.namespaces) == 1 and len(fake.apps) == 2 and len(fake.idps) == 1
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
    main, agent = fake.apps
    assert "dsbg.example.com" in main["self_hosted_domains"]           # 새 주소도 팀원만
    assert "dsbg.example.com/api/agent" in agent["self_hosted_domains"]
    assert fake.projects["trendbot"]["domains"] == [{"name": "dsbg.example.com", "status": "pending"}]
    assert any("내 도메인: https://dsbg.example.com" in l for l in lines)
    cloud_setup.run(client(fake, monkeypatch))                          # 다시 눌러도 중복 추가 없음
    assert len(fake.projects["trendbot"]["domains"]) == 1
    # 잠금이 도메인 연결보다 먼저
    calls = [c for c in fake.calls if c[1] in ("/access/apps", "/pages/projects/trendbot/domains") and c[0] == "POST"]
    assert calls[0][1] == "/access/apps"


def test_bad_domain_rejected(env, monkeypatch):
    monkeypatch.setenv("SITE_DOMAIN", "not a domain")
    with pytest.raises(cloud_setup.SetupError, match="SITE_DOMAIN"):
        cloud_setup.run(client(FakeCF(), monkeypatch))
