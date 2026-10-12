"""config/sources.yaml 읽기와 검사. 잘못된 설정은 한국어 오류로 알려줌."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
RULES_PATH = ROOT / "config" / "editor_rules.md"
DATA_DIR = ROOT / "data"


class ConfigError(Exception):
    pass


def load_config(path: Path = CONFIG_PATH) -> dict:
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"설정 파일 문법 오류: {path.name} — {e}") from e
    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    for key in ("pods", "grading", "sources"):
        if key not in cfg:
            raise ConfigError(f"설정 파일에 '{key}' 항목이 없습니다.")
    seen = set()
    for src in cfg["sources"]:
        sid = src.get("id")
        if not sid:
            raise ConfigError("이름(id)이 없는 소스가 있습니다.")
        if sid in seen:
            raise ConfigError(f"소스 id '{sid}'가 두 번 나옵니다.")
        seen.add(sid)
        if src.get("pod") not in cfg["pods"]:
            raise ConfigError(f"소스 '{sid}'의 포드 '{src.get('pod')}'가 pods 목록에 없습니다.")
        if src.get("kind", "html_list") == "html_list":
            for k in ("url", "row", "fields"):
                if k not in src:
                    raise ConfigError(f"소스 '{sid}'에 '{k}' 항목이 없습니다.")
            if "title" not in src["fields"] or "link" not in src["fields"]:
                raise ConfigError(f"소스 '{sid}'에 제목(title)·링크(link) 선택자가 필요합니다.")


def sources_by_id(cfg: dict) -> dict[str, dict]:
    return {s["id"]: s for s in cfg["sources"]}
