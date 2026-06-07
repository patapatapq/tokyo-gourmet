"""レストラン写真のダウンロードと保存"""
import io
import logging
from pathlib import Path

import requests
from PIL import Image

from backend.config import PHOTOS_DIR, get_api_key

BASE_URL = "https://places.googleapis.com/v1"

logger = logging.getLogger(__name__)


def compress_image(
    data: bytes,
    target_width: int = 640,
    quality: int = 65,
) -> bytes:
    """画像バイト列を再圧縮して軽量なJPEGバイト列を返す。

    - target_width より大きい画像は等比で縮小する。
    - RGB に変換して JPEG（最適化・プログレッシブ）で保存する。

    Args:
        data: 元画像のバイト列
        target_width: 保存時の最大幅（ピクセル）
        quality: JPEG品質（1〜95）

    Returns:
        圧縮後のJPEGバイト列。失敗時は元の data をそのまま返す。
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            # RGB に変換（メタ情報・アルファ・パレットを破棄）
            img = img.convert("RGB")

            if img.width > target_width:
                ratio = target_width / img.width
                new_size = (target_width, max(1, round(img.height * ratio)))
                img = img.resize(new_size, Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(
                buffer,
                format="JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
            )
            return buffer.getvalue()
    except Exception as e:
        logger.warning(f"画像圧縮に失敗したため元データを使用します: {e}")
        return data


def download_photos(
    place_id: str,
    photos: list[dict],
    max_photos: int = 2,
    max_width: int = 960,
    target_width: int = 640,
    jpeg_quality: int = 65,
) -> list[dict]:
    """Places API の写真をダウンロードし、圧縮してローカルに保存する。

    Args:
        place_id: Google Place ID
        photos: Places API から取得した photos 配列
        max_photos: 最大ダウンロード枚数
        max_width: Google API から取得する幅（縮小元）
        target_width: 保存時の最終的な最大幅（ピクセル）
        jpeg_quality: JPEG圧縮品質（1〜95）

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
            # 写真を直接ダウンロード（HTTPリダイレクトを追跡）
            media_url = f"{BASE_URL}/{photo_name}/media"
            params = {"maxWidthPx": max_width, "key": get_api_key()}
            resp = requests.get(media_url, params=params, timeout=30, allow_redirects=True)
            resp.raise_for_status()

            # 画像データであることを確認
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type:
                logger.warning(f"写真取得失敗（画像でない）: {photo_name} Content-Type={content_type}")
                continue

            original_kb = len(resp.content) // 1024
            compressed = compress_image(
                resp.content,
                target_width=target_width,
                quality=jpeg_quality,
            )

            with open(filepath, "wb") as f:
                f.write(compressed)

            # 帰属情報
            authors = photo.get("authorAttributions", [])
            attribution = authors[0].get("displayName", "") if authors else ""

            saved.append({
                "filename": filename,
                "attribution": attribution,
            })
            logger.info(
                f"写真保存: {filename} ({original_kb}KB → {len(compressed) // 1024}KB)"
            )

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
