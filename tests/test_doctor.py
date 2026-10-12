from trendbot import doctor


def test_key_checks_empty_and_malformed():
    env = {"ANTHROPIC_API_KEY": "\"sk-ant-short\"", "CLOUDFLARE_ACCOUNT_ID": "0123456789abcdef0123456789abcdef"}
    res = {c.name: c for c in doctor.check_keys(env)}
    assert res["ANTHROPIC_API_KEY"].ok is False and "형식" in res["ANTHROPIC_API_KEY"].detail
    assert res["CLOUDFLARE_ACCOUNT_ID"].ok is True
    assert res["CLOUDFLARE_API_TOKEN"].ok is False          # 필수인데 비어 있음
    assert res["YOUTUBE_API_KEY"].ok is None                # 선택 항목은 경고만
    text = doctor.render(list(res.values()))
    assert "✗ ANTHROPIC_API_KEY" in text and "→" in text


def test_valid_keys_masked():
    env = {"ANTHROPIC_API_KEY": "sk-ant-api03-" + "a" * 40}
    c = {c.name: c for c in doctor.check_keys(env)}["ANTHROPIC_API_KEY"]
    assert c.ok and c.detail == "sk-ant…" and "a" * 10 not in c.detail
