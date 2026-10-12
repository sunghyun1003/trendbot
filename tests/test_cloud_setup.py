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
