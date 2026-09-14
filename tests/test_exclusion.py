"""「行った/たぶん行かない」の除外判定と、メールの目隠しリンクのテスト（ISS-475 / ISS-518）"""

from __future__ import annotations

import json

import pytest

from backend import gas_client, recommender
from backend.email_template import build_gate_link, render_email


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"place_id": "a", "status": "visited"}, True),
        ({"place_id": "a", "status": "skipped"}, True),
        ({"place_id": "a", "status": "none"}, False),
        # status が入っていれば visited 列より優先（解除したのに旧列の TRUE で除外され続けない）
        ({"place_id": "a", "status": "none", "visited": "TRUE"}, False),
        # status 列を足す前の既存行は visited 列で判定する
        ({"place_id": "a", "status": "", "visited": "TRUE"}, True),
        ({"place_id": "a", "visited": "○"}, True),
        ({"place_id": "a", "visited": "FALSE"}, False),
        # visited.json の旧形式（place_id だけ）は「行った」
        ({"place_id": "a"}, True),
    ],
)
def test_is_excluded_record(record: dict, expected: bool) -> None:
    assert recommender.is_excluded_record(record) is expected


def test_load_visited_ids_reads_status(tmp_path, monkeypatch) -> None:
    """旧形式と status 付きが混在しても、除外対象だけを拾う。"""
    f = tmp_path / "visited.json"
    f.write_text(
        json.dumps(
            {
                "visited": [
                    {"place_id": "old"},
                    {"place_id": "go", "status": "visited"},
                    {"place_id": "skip", "status": "skipped"},
                    {"place_id": "undone", "status": "none"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(recommender, "VISITED_FILE", f)
    assert recommender.load_visited_ids() == {"old", "go", "skip"}


def test_filter_candidates_drops_excluded() -> None:
    places = [
        {"id": "go", "userRatingCount": 100},
        {"id": "skip", "userRatingCount": 100},
        {"id": "keep", "userRatingCount": 100},
    ]
    out = recommender.filter_candidates(places, {"go", "skip"}, set())
    assert [p["id"] for p in out] == ["keep"]


def test_fetch_excluded_ids_without_config_returns_none(monkeypatch, tmp_path) -> None:
    """未設定は None（空集合と区別する）。黙って「除外0件」に見せないため。"""
    monkeypatch.setattr(gas_client, "STATUS_API_FILE", tmp_path / "missing.json")
    monkeypatch.setenv("SITE_GATE_TOKEN", "x")
    assert gas_client.fetch_excluded_ids() is None


def test_fetch_excluded_ids_applies_status(monkeypatch, tmp_path) -> None:
    cfg = tmp_path / "status_api.json"
    cfg.write_text(
        json.dumps({"url": "https://example.invalid/exec"}), encoding="utf-8"
    )
    monkeypatch.setattr(gas_client, "STATUS_API_FILE", cfg)
    monkeypatch.setenv("SITE_GATE_TOKEN", "secret")
    seen = {}

    def fake_fetch(url: str, token: str):
        seen["args"] = (url, token)
        return [
            {"place_id": "go", "status": "visited", "visited": "TRUE"},
            {"place_id": "skip", "status": "skipped", "visited": "FALSE"},
            {"place_id": "undone", "status": "none", "visited": "FALSE"},
            {"place_id": "legacy", "status": "", "visited": "TRUE"},
        ]

    monkeypatch.setattr(gas_client, "fetch_status_records", fake_fetch)
    assert gas_client.fetch_excluded_ids() == {"go", "skip", "legacy"}
    assert seen["args"] == ("https://example.invalid/exec", "secret")


def test_merge_visited_sources_survives_gas_failure(monkeypatch) -> None:
    """GAS が失敗（None）してもローカル分だけで除外を続ける。gspread 撤去（ISS-519）後の2源統合。"""
    monkeypatch.setattr(gas_client, "load_visited_ids", lambda: {"local"})
    monkeypatch.setattr(gas_client, "fetch_excluded_ids", lambda: None)
    assert gas_client.merge_visited_sources() == {"local"}

    monkeypatch.setattr(gas_client, "fetch_excluded_ids", lambda: {"gas", "local"})
    assert gas_client.merge_visited_sources() == {"local", "gas"}


def test_gate_link_uses_fragment() -> None:
    """トークンは ?t= ではなく #t=（サーバーのログ・リファラに残さない）。"""
    url = build_gate_link("https://example.github.io/tokyo-gourmet", "abc123")
    assert url == "https://example.github.io/tokyo-gourmet/#t=abc123"
    assert "?" not in url


def test_gate_link_without_token() -> None:
    assert build_gate_link("https://x/y/", "") == "https://x/y/"


def test_email_links_carry_token_but_text_does_not() -> None:
    html = render_email([], "今週", "https://x/tg", gate_token="tok")
    assert html.count('href="https://x/tg/#t=tok"') == 2
    # 画面に見える文字列にはトークンを出さない
    assert ">\n            https://x/tg\n" in html
