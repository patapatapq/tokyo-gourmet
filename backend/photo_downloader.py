"""レストラン写真のダウンロードと保存"""
import logging
from pathlib import Path

import requests

from backend.config import PHOTOS_DIR
from backend.places_client import get_photo_url

logger = logging.getLogger(__name__)


def download_photos(
    place_id: str,
    photos: list[dict],
    max_photos: int = 2,
    max_width: int = 800,
) -> list[dict]:
    """Places API の写真をダウンロードしてローカルに保存する。

    Args:
        place_id: Google Place ID
        photos: Places API から取得した photos 配列
        max_photos: 最大ダウンロード枚数
        max_width: 最大幅（ピクセル）

    Returns:
        保存した写真情報のリスト:
        [{"filename": "xxx.jpg", "attribution": "..."}]
    """
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []

    for i, photo in enumerate(photos[:max_photos]):
        photo_name = photo.get("name", "")
        if not photo_name:
            continue

        filename = f"{place_id}_{i}.jpg"
        filepath = PHOTOS_DIR / filename

        try:
            # 写真URLを取得
            photo_url = get_photo_url(photo_name, max_width=max_width)
            if not photo_url:
                logger.warning(f"写真URL取得失敗: {photo_name}")
                continue

            # ダウンロード
            resp = requests.get(photo_url, timeout=30)
            resp.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(resp.content)

            # 帰属情報
            authors = photo.get("authorAttributions", [])
            attribution = authors[0].get("displayName", "") if authors else ""

            saved.append({
                "filename": filename,
                "attribution": attribution,
            })
            logger.info(f"写真保存: {filename} ({len(resp.content) // 1024}KB)")

        except Exception as e:
            logger.warning(f"写真ダウンロード失敗 ({photo_name}): {e}")

    return saved


def cleanup_old_photos(keep_place_ids: set[str]) -> int:
    """不要な写真を削除する。

    Args:
        keep_place_ids: 残すべき place_id のセット

    Returns:
        削除したファイル数
    """
    if not PHOTOS_DIR.exists():
        return 0

    deleted = 0
    for filepath in PHOTOS_DIR.glob("*.jpg"):
        # ファイル名形式: {place_id}_{index}.jpg
        place_id = filepath.stem.rsplit("_", 1)[0]
        if place_id not in keep_place_ids:
            filepath.unlink()
            deleted += 1

    if deleted:
        logger.info(f"古い写真を {deleted} 件削除しました")
    return deleted
