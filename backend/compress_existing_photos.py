"""既存の写真を一括再圧縮するメンテナンススクリプト。

frontend/public/photos 配下の .jpg をすべて読み込み、
config.yaml の photos 設定（target_width_px / jpeg_quality）に従って再圧縮し、
その場で上書き保存する。

使い方:
    python -m backend.compress_existing_photos          # 実行
    python -m backend.compress_existing_photos --dry-run  # 集計のみ（書き込まない）

実行前に必ずバックアップを取ること（このスクリプトは上書きする）。
"""
import argparse
import logging
import sys

from backend.config import PHOTOS_DIR, load_config
from backend.photo_downloader import compress_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="既存写真を一括再圧縮する")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="書き込まずに削減見込みだけ表示する",
    )
    args = parser.parse_args()

    config = load_config()
    photos_cfg = config.get("photos", {})
    target_width = photos_cfg.get("target_width_px", 640)
    quality = photos_cfg.get("jpeg_quality", 65)

    if not PHOTOS_DIR.exists():
        logger.error(f"写真ディレクトリが見つかりません: {PHOTOS_DIR}")
        return 1

    files = sorted(PHOTOS_DIR.glob("*.jpg"))
    logger.info(f"対象: {len(files)}枚 / target_width={target_width}px quality={quality}")
    if args.dry_run:
        logger.info("[DRY-RUN] ファイルは書き換えません")

    total_before = 0
    total_after = 0
    skipped = 0

    for i, filepath in enumerate(files, 1):
        try:
            original = filepath.read_bytes()
        except Exception as e:
            logger.warning(f"読み込み失敗 ({filepath.name}): {e}")
            skipped += 1
            continue

        compressed = compress_image(original, target_width=target_width, quality=quality)
        total_before += len(original)

        # 圧縮で逆に大きくなる場合は元を維持
        if len(compressed) >= len(original):
            total_after += len(original)
            skipped += 1
        else:
            total_after += len(compressed)
            if not args.dry_run:
                filepath.write_bytes(compressed)

        if i % 100 == 0 or i == len(files):
            logger.info(f"  {i}/{len(files)} 処理済み")

    mb = 1024 * 1024
    reduction = (1 - total_after / total_before) * 100 if total_before else 0
    logger.info("=" * 50)
    logger.info(f"圧縮前: {total_before / mb:.1f}MB")
    logger.info(f"圧縮後: {total_after / mb:.1f}MB")
    logger.info(f"削減率: {reduction:.1f}%  (据え置き: {skipped}枚)")
    if args.dry_run:
        logger.info("[DRY-RUN] 実際の書き込みは行っていません")
    logger.info("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
