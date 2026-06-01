"""config.load_search_config 測試：jobcats 解析與預設。"""
from __future__ import annotations

from pathlib import Path

from job_ops.config import load_search_config


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "search.yml"
    p.write_text(body, encoding="utf-8")
    return p


def test_jobcats_parsed_as_str_list(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
jobcats:
  - "2004003009"
  - 2004003004
"""))
    # 數字與字串混寫都正規化成 str（104 API 需要字串代碼）
    assert cfg.jobcats == ["2004003009", "2004003004"]


def test_jobcats_defaults_to_empty_when_absent(tmp_path: Path):
    cfg = load_search_config(_write(tmp_path, """
keywords: [產品經理]
areas: [台北市]
"""))
    assert cfg.jobcats == []
