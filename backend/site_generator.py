"""フロントエンド用JSONデータ生成"""
import json
import logging
import shutil
from datetime import datetime, timedelta, timezone

from backend.config import (
    DATA_DIR, FRONTEND_DATA_DIR, VISITED_FILE,
)

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def generate_current_json(
    restaurants: list[dict],
    week_label: str,
) -> dict:
    """今週のおすすめ JSON を生成する。"""
    data = {
        "generated_at": datetime.now(JST).isoformat(),
        "week_label": week_label,
        "restaurants": restaurants,
    }

    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = FRONTEND_DATA_DIR / "current.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"current.json 生成: {len(restaurants)}件")
    return data


def update_archive(current_data: dict) -> None:
    """アーカイブ JSON に今週分を追記する。"""
    archive_path = FRONTEND_DATA_DIR / "archive.json"
    try:
        with open(archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {"weeks": []}

    archive["weeks"].insert(0, current_data)

    # 最大52週（1年分）保持
    archive["weeks"] = archive["weeks"][:52]

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    logger.info(f"archive.json 更新: 計{len(archive['weeks'])}週分")


def update_history(current_data: dict) -> None:
    """永続的な履歴 JSON を更新する（data/ 配下）。"""
    history_path = DATA_DIR / "history.json"
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {"weeks": []}

    history["weeks"].insert(0, {
        "generated_at": current_data["generated_at"],
        "week_label": current_data["week_label"],
        "restaurants": [
            {
                "place_id": r["place_id"],
                "name": r["name"],
                "rating": r.get("rating"),
            }
            for r in current_data["restaurants"]
        ],
    })

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    logger.info("history.json 更新")


def sync_visited_to_frontend() -> None:
    """visited.json をフロントエンド用にコピーする。"""
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    src = VISITED_FILE
    dst = FRONTEND_DATA_DIR / "visited.json"

    if src.exists():
        shutil.copy2(src, dst)
        logger.info("visited.json をフロントエンドにコピー")
    else:
        with open(dst, "w", encoding="utf-8") as f:
            json.dump({"visited": []}, f)
