"""状態API（Google Apps Script Web App）クライアント（ISS-475）

「行った」「たぶん行かない」の真実の源は Google Sheets で、書き込みも読み取りも
GAS の Web App（`gas/Code.gs`）を経由する。

以前は Python から gspread で直接読み書きする経路もあったが、OAuth トークン
（SHEETS_TOKEN_JSON）がクライアントシークレットの更新で失効し、2026-09 時点で毎週
黙って失敗していた。GAS なら合言葉トークン1つで読めるので、ISS-519 で gspread を撤去した。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from backend.config import PROJECT_ROOT
from backend.recommender import is_excluded_record, load_visited_ids

logger = logging.getLogger(__name__)

# フロント（Astro）と同じファイルを読む。URL を2か所に書かないため。
STATUS_API_FILE = PROJECT_ROOT / "status_api.json"


def load_status_api_url() -> str:
    """status_api.json から GAS Web App の URL を読む。未設定なら空文字。"""
    try:
        with open(STATUS_API_FILE, "r", encoding="utf-8") as f:
            return str(json.load(f).get("url") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def fetch_status_records(
    url: str, token: str, timeout: float = 30
) -> list[dict] | None:
    """GAS から全店の状態を取得する。失敗したら None（空リストと区別するため）。

    Content-Type を text/plain にしているのは、GAS が application/json の
    プリフライトに応答できないのに合わせてフロントと揃えたもの。
    GAS は 302 で googleusercontent へ飛ばすが、urllib は POST の 302 を GET に
    変えて追従するので、そのまま応答本文が取れる。
    """
    body = json.dumps({"action": "list", "token": token}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "text/plain;charset=utf-8",
            "User-Agent": "tokyo-gourmet-weekly/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning(f"状態API の取得に失敗しました: {e}")
        return None

    if not payload.get("ok"):
        # トークン不一致もここに来る。GAS 側は理由を細かく返さない。
        logger.warning(f"状態API がエラーを返しました: {payload.get('error')}")
        return None
    return list(payload.get("items") or [])


def fetch_excluded_ids() -> set[str] | None:
    """GAS から「推薦から除外する place_id」を取得する。未設定・失敗なら None。"""
    url = load_status_api_url()
    token = os.environ.get("SITE_GATE_TOKEN", "").strip()
    if not url or not token:
        logger.warning(
            "状態API が未設定です（status_api.json の url / 環境変数 SITE_GATE_TOKEN）。"
            "「行った/たぶん行かない」は除外に反映されません"
        )
        return None
    records = fetch_status_records(url, token)
    if records is None:
        return None
    return {
        str(r["place_id"])
        for r in records
        if r.get("place_id") and is_excluded_record(r)
    }


def merge_visited_sources() -> set[str]:
    """推薦から除外する place_id を2つの源から統合する。

    - ローカルの data/visited.json
    - 状態API（GAS 経由の Sheets）… 画面の「行った/たぶん行かない」はここに入る

    以前は gspread で Sheets を直接読む3つ目の源があったが、OAuth 失効で毎週空を
    返していたので ISS-519 で撤去した。Sheets を読むのは GAS だけにする。
    """
    local_ids = load_visited_ids()

    gas_ids = fetch_excluded_ids()
    if gas_ids is None:
        gas_ids = set()

    merged = local_ids | gas_ids
    logger.info(
        f"除外対象統合: ローカル {len(local_ids)}件 + 状態API {len(gas_ids)}件 "
        f"= {len(merged)}件（重複除去済み）"
    )
    return merged
