"""週次グルメレコメンデーション パイプライン

毎週金曜日に GitHub Actions から実行される。
手動実行: python -m backend.run_weekly
"""
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

from backend.config import load_config, DATA_DIR, FRONTEND_DATA_DIR, PHOTOS_DIR
from backend.places_client import search_all_restaurants, get_place_details
from backend.routes_client import get_travel_info
from backend.recommender import (
    load_visited_ids,
    load_recent_history,
    classify_budget,
    estimate_price_range,
    filter_candidates,
    weighted_random_pick,
)
from backend.photo_downloader import download_photos
from backend.site_generator import (
    generate_current_json,
    update_archive,
    update_history,
    sync_visited_to_frontend,
)
from backend.gmail_client import send_email
from backend.email_template import render_email
from backend.sheets_client import merge_visited_sources, sync_recommendations_to_sheet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def main() -> int:
    """メインパイプラインを実行する。"""
    logger.info("=" * 60)
    logger.info("Tokyo Gourmet Recommender - 週次パイプライン開始")
    logger.info("=" * 60)

    # Step 1: 設定読み込み
    logger.info("[Step 1/10] 設定読み込み")
    config = load_config()
    origin = config["origin"]
    search_cfg = config["search"]
    budget_cfg = config["budget"]
    email_cfg = config["email"]
    sheets_cfg = config["sheets"]
    site_cfg = config["site"]
    cache_cfg = config["cache"]
    photos_cfg = config["photos"]

    now = datetime.now(JST)
    # 曜日の日本語マッピング
    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    week_label = f"{now.year}年{now.month}月{now.day}日（{weekday_ja[now.weekday()]}）"
    generated_date = now.strftime("%Y-%m-%d")

    # Step 2: 訪問済みレストランの読み込み
    logger.info("[Step 2/10] 訪問済みレストラン読み込み")
    visited_ids = merge_visited_sources(
        spreadsheet_id=sheets_cfg.get("spreadsheet_id", ""),
        worksheet_name=sheets_cfg.get("worksheet_name", "visited"),
    )
    recent_ids = load_recent_history(weeks=4)
    logger.info(f"  訪問済み: {len(visited_ids)}件, 直近推薦済み: {len(recent_ids)}件")

    # Step 3: レストラン検索
    logger.info("[Step 3/10] レストラン検索 (Places API)")
    candidates = search_all_restaurants(
        queries=search_cfg["queries"],
        lat=origin["lat"],
        lng=origin["lng"],
        radius_meters=search_cfg["search_radius_meters"],
        min_rating=search_cfg["min_rating"],
    )
    logger.info(f"  検索結果: {len(candidates)}件")

    if not candidates:
        logger.error("候補が0件です。検索条件を緩和してください。")
        return 1

    # Step 4: 移動時間の計算
    logger.info("[Step 4/10] 移動時間計算 (Routes API)")
    travel_data = {}
    for place in candidates:
        place_id = place.get("id", "")
        location = place.get("location", {})
        dest_lat = location.get("latitude")
        dest_lng = location.get("longitude")

        if not (place_id and dest_lat and dest_lng):
            continue

        # 訪問済み・直近推薦済みはスキップ（後でフィルタされるため）
        if place_id in visited_ids or place_id in recent_ids:
            continue

        try:
            travel_data[place_id] = get_travel_info(
                place_id=place_id,
                origin_lat=origin["lat"],
                origin_lng=origin["lng"],
                dest_lat=dest_lat,
                dest_lng=dest_lng,
                cache_expiry_days=cache_cfg["travel_time_expiry_days"],
            )
        except Exception as e:
            logger.warning(f"  移動時間取得失敗 ({place_id}): {e}")

    logger.info(f"  移動時間取得: {len(travel_data)}件")

    # Step 5: フィルタリング
    logger.info("[Step 5/10] 候補フィルタリング")
    filtered = filter_candidates(
        places=candidates,
        visited_ids=visited_ids,
        recent_ids=recent_ids,
        min_reviews=search_cfg["min_reviews"],
        max_travel_minutes=search_cfg["max_travel_minutes"],
        travel_info=travel_data,
    )

    if not filtered:
        logger.error("フィルタ後の候補が0件です。条件を緩和してください。")
        return 1

    # Step 6: ランダム選定
    logger.info("[Step 6/10] ランダム選定")
    selected = weighted_random_pick(filtered, search_cfg["pick_count"])
    logger.info(f"  選定: {len(selected)}件")

    # Step 7: 詳細情報取得 + 予算分類
    logger.info("[Step 7/10] 詳細情報取得 (Place Details)")
    restaurants = []
    for place in selected:
        place_id = place.get("id", "")
        try:
            details = get_place_details(place_id)
        except Exception as e:
            logger.warning(f"  詳細取得失敗 ({place_id}): {e}")
            details = place  # 検索結果をフォールバック

        # 予算分類
        budget_info = classify_budget(details, budget_cfg)
        # 朝昼/夜のどちらかを主要予算として設定（デフォルトは朝昼）
        primary_budget = budget_info["morning_lunch"]

        # 移動情報
        travel = travel_data.get(place_id, {})

        # 写真ダウンロード
        photos = details.get("photos", [])
        saved_photos = []
        if photos:
            saved_photos = download_photos(
                place_id=place_id,
                photos=photos,
                max_photos=photos_cfg["max_per_restaurant"],
                max_width=photos_cfg["max_width_px"],
            )

        # 営業時間
        opening_hours = details.get("regularOpeningHours", {})
        weekday_text = opening_hours.get("weekdayDescriptions", [])

        # レビューからおすすめメニューを抽出
        recommended_menu = _extract_menu_from_reviews(details.get("reviews", []))

        display_name = details.get("displayName", {})
        name = display_name.get("text", "") if isinstance(display_name, dict) else str(display_name)

        restaurant = {
            "place_id": place_id,
            "name": name,
            "rating": details.get("rating"),
            "user_rating_count": details.get("userRatingCount", 0),
            "budget_tier": primary_budget["tier"],
            "budget_label": primary_budget["label"],
            "budget_icon": primary_budget["icon"],
            "budget_morning_lunch": budget_info["morning_lunch"],
            "budget_dinner": budget_info["dinner"],
            "price_range": estimate_price_range(
                details.get("priceLevel", "PRICE_LEVEL_MODERATE"),
                "morning_lunch",
                budget_cfg,
            ),
            "price_range_dinner": estimate_price_range(
                details.get("priceLevel", "PRICE_LEVEL_MODERATE"),
                "dinner",
                budget_cfg,
            ),
            "address": details.get("formattedAddress", ""),
            "travel_time_minutes": travel.get("travel_time_minutes"),
            "travel_cost_yen": travel.get("travel_cost_yen"),
            "travel_summary": travel.get("travel_summary", ""),
            "reservable": details.get("reservable"),
            "opening_hours": weekday_text,
            "photos": saved_photos,
            "google_maps_url": details.get("googleMapsUri", ""),
            "website": details.get("websiteUri", ""),
            "phone": details.get("nationalPhoneNumber", ""),
            "primary_type": details.get("primaryType", ""),
            "recommended_menu": recommended_menu,
        }
        restaurants.append(restaurant)
        time.sleep(0.3)

    logger.info(f"  レストラン情報構築完了: {len(restaurants)}件")

    # Step 8: JSON生成
    logger.info("[Step 8/10] JSONデータ生成")
    current_data = generate_current_json(restaurants, week_label)
    update_archive(current_data)
    update_history(current_data)
    sync_visited_to_frontend()

    # Step 9: メール送信
    logger.info("[Step 9/10] メール送信")
    if email_cfg.get("recipient"):
        site_url = site_cfg.get("base_url", "")
        subject = email_cfg["subject_template"].format(date=week_label)
        html_body = render_email(restaurants, week_label, site_url)

        success = send_email(
            to=email_cfg["recipient"],
            subject=subject,
            html_body=html_body,
            sender=email_cfg.get("sender", ""),
        )
        if not success:
            logger.warning("メール送信に失敗しました")
    else:
        logger.warning("メール送信先が未設定です (config.yaml: email.recipient)")

    # Step 10: Sheets同期
    logger.info("[Step 10/10] Google Sheets 同期")
    if sheets_cfg.get("spreadsheet_id"):
        sync_recommendations_to_sheet(
            spreadsheet_id=sheets_cfg["spreadsheet_id"],
            restaurants=restaurants,
            generated_date=generated_date,
            worksheet_name=sheets_cfg.get("worksheet_name", "visited"),
        )

    logger.info("=" * 60)
    logger.info("パイプライン完了!")
    logger.info(f"  推薦レストラン: {len(restaurants)}件")
    logger.info(f"  サイトURL: {site_cfg.get('base_url', '未設定')}")
    logger.info("=" * 60)

    return 0


def _extract_menu_from_reviews(reviews: list[dict]) -> str | None:
    """レビューからおすすめメニューを簡易的に抽出する。

    レビューテキストから頻出する料理名らしき単語を抽出する簡易実装。
    """
    if not reviews:
        return None

    # レビューの中から最も評価が高いものの一部を返す
    best_review = None
    best_rating = 0
    for review in reviews[:5]:
        rating = review.get("rating", 0)
        if rating > best_rating:
            best_rating = rating
            text = review.get("text", {})
            if isinstance(text, dict):
                best_review = text.get("text", "")
            else:
                best_review = str(text)

    if best_review and len(best_review) > 100:
        best_review = best_review[:100] + "..."

    return best_review


if __name__ == "__main__":
    sys.exit(main())
