"""Google Places API (New) クライアント"""
import logging
import time
from typing import Optional

import requests

from backend.config import get_api_key

logger = logging.getLogger(__name__)

BASE_URL = "https://places.googleapis.com/v1"

# Places API (New) で取得するフィールド
SEARCH_FIELDS = [
    "places.id",
    "places.displayName",
    "places.rating",
    "places.userRatingCount",
    "places.priceLevel",
    "places.priceRange",
    "places.formattedAddress",
    "places.location",
    "places.primaryType",
    "places.googleMapsUri",
]

DETAIL_FIELDS = [
    "id",
    "displayName",
    "rating",
    "userRatingCount",
    "priceLevel",
    "priceRange",
    "formattedAddress",
    "location",
    "primaryType",
    "googleMapsUri",
    "photos",
    "regularOpeningHours",
    "reservable",
    "websiteUri",
    "nationalPhoneNumber",
    "reviews",
]


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": get_api_key(),
    }


def search_restaurants(
    query: str,
    lat: float,
    lng: float,
    radius_meters: int = 30000,
    min_rating: float = 4.0,
    page_token: Optional[str] = None,
) -> dict:
    """Text Search (New) でレストランを検索する。

    Returns:
        dict with "places" list and optional "nextPageToken"
    """
    url = f"{BASE_URL}/places:searchText"
    headers = _headers()
    headers["X-Goog-FieldMask"] = ",".join(SEARCH_FIELDS) + ",nextPageToken"

    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_meters),
            }
        },
        "includedType": "restaurant",
        "languageCode": "ja",
        "minRating": min_rating,
        "maxResultCount": 20,
    }
    if page_token:
        body["pageToken"] = page_token

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def search_all_restaurants(
    queries: list[str],
    lat: float,
    lng: float,
    radius_meters: int = 30000,
    min_rating: float = 4.0,
    max_pages_per_query: int = 3,
) -> list[dict]:
    """複数クエリで検索し、重複を除いた全候補を返す。"""
    seen_ids = set()
    all_places = []

    for query in queries:
        logger.info(f"検索中: '{query}'")
        page_token = None

        for page in range(max_pages_per_query):
            try:
                result = search_restaurants(
                    query=query,
                    lat=lat,
                    lng=lng,
                    radius_meters=radius_meters,
                    min_rating=min_rating,
                    page_token=page_token,
                )
            except Exception as e:
                logger.warning(f"  検索エラー ('{query}' page {page}): {e}")
                break

            places = result.get("places", [])
            for place in places:
                place_id = place.get("id", "")
                if place_id and place_id not in seen_ids:
                    seen_ids.add(place_id)
                    all_places.append(place)

            page_token = result.get("nextPageToken")
            if not page_token:
                break
            time.sleep(0.5)

        logger.info(f"  → {len(places)}件取得 (累計ユニーク: {len(all_places)}件)")
        time.sleep(1)  # クエリ間のウェイト

    logger.info(f"検索完了: 合計 {len(all_places)} 件のユニーク候補")
    return all_places


def get_place_details(place_id: str) -> dict:
    """Place Details (New) で詳細情報を取得する。"""
    url = f"{BASE_URL}/places/{place_id}"
    headers = _headers()
    headers["X-Goog-FieldMask"] = ",".join(DETAIL_FIELDS)

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_photo_url(photo_name: str, max_width: int = 800) -> str:
    """写真のダウンロードURLを取得する。

    Args:
        photo_name: "places/{place_id}/photos/{photo_ref}" 形式
        max_width: 最大幅（ピクセル）

    Returns:
        写真のURL文字列
    """
    url = f"{BASE_URL}/{photo_name}/media"
    params = {
        "maxWidthPx": max_width,
        "key": get_api_key(),
    }
    # skipHttpRedirect=true で URL を JSON で取得
    params["skipHttpRedirect"] = "true"

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("photoUri", "")
