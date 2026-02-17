"""Google Routes API クライアント（移動時間計算 + キャッシュ）

TRANSIT モードは日本地域で空レスポンスを返すため、
DRIVE モードの所要時間 × 1.5 で公共交通機関の目安を推定する。
"""
import json
import logging
import math
import time
from datetime import datetime, timedelta, timezone

import requests

from backend.config import get_api_key, STATION_CACHE_FILE

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# 車での所要時間に対する公共交通機関の係数
TRANSIT_MULTIPLIER = 1.5


def _load_cache() -> dict:
    """キャッシュファイルを読み込む。"""
    try:
        with open(STATION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    """キャッシュファイルに書き込む。"""
    with open(STATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _is_cache_valid(entry: dict, expiry_days: int) -> bool:
    """キャッシュエントリが有効期限内かを判定する。"""
    cached_at = entry.get("cached_at", "")
    if not cached_at:
        return False
    cached_time = datetime.fromisoformat(cached_at)
    return datetime.now(JST) - cached_time < timedelta(days=expiry_days)


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間の直線距離（km）を計算する。"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def compute_travel_time(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict:
    """Routes API (DRIVE) で移動時間を計算し、公共交通機関の目安に変換する。

    Returns:
        {
            "travel_time_minutes": int,
            "travel_cost_yen": int | None,
            "travel_summary": str,
        }
    """
    distance_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)

    # 徒歩圏内（1.5km以内）
    if distance_km <= 1.5:
        walk_minutes = round(distance_km / 0.08)  # 時速4.8km = 分速0.08km
        return {
            "travel_time_minutes": walk_minutes,
            "travel_cost_yen": 0,
            "travel_summary": f"徒歩 {walk_minutes}分",
        }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": get_api_key(),
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
    }

    body = {
        "origin": {
            "location": {
                "latLng": {"latitude": origin_lat, "longitude": origin_lng}
            }
        },
        "destination": {
            "location": {
                "latLng": {"latitude": dest_lat, "longitude": dest_lng}
            }
        },
        "travelMode": "DRIVE",
        "languageCode": "ja",
    }

    resp = requests.post(ROUTES_URL, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    routes = data.get("routes", [])
    if not routes:
        # フォールバック: 直線距離から推定
        est_minutes = round(distance_km * 3)  # 1km あたり約3分（電車）
        return {
            "travel_time_minutes": est_minutes,
            "travel_cost_yen": None,
            "travel_summary": f"推定 {est_minutes}分（直線{distance_km:.1f}km）",
        }

    route = routes[0]
    duration_str = route.get("duration", "0s")
    drive_seconds = int(duration_str.rstrip("s"))
    # 車の所要時間 × 係数 = 公共交通機関の推定
    transit_minutes = round(drive_seconds / 60 * TRANSIT_MULTIPLIER)

    distance_m = route.get("distanceMeters", 0)
    distance_km_road = distance_m / 1000

    # 運賃の推定（距離ベース）
    # 東京近郊の電車: 初乗り~140円、10km~200円、20km~400円、30km~500円
    if distance_km_road <= 5:
        fare_estimate = 180
    elif distance_km_road <= 15:
        fare_estimate = round(150 + distance_km_road * 15)
    elif distance_km_road <= 30:
        fare_estimate = round(200 + distance_km_road * 12)
    else:
        fare_estimate = round(250 + distance_km_road * 10)
    # 10円単位に丸め
    fare_estimate = round(fare_estimate / 10) * 10

    return {
        "travel_time_minutes": transit_minutes,
        "travel_cost_yen": fare_estimate,
        "travel_summary": f"公共交通機関 約{transit_minutes}分（{distance_km_road:.0f}km）",
    }


def get_travel_info(
    place_id: str,
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    cache_expiry_days: int = 90,
) -> dict:
    """キャッシュ付きで移動時間情報を取得する。"""
    cache = _load_cache()

    # キャッシュチェック（travel_time_minutes が null のエントリはリトライ）
    if place_id in cache:
        entry = cache[place_id]
        if (_is_cache_valid(entry, cache_expiry_days)
                and entry.get("travel_time_minutes") is not None):
            logger.debug(f"キャッシュヒット: {place_id}")
            return entry

    # API呼び出し
    logger.info(f"Routes API 呼び出し: {place_id}")
    result = compute_travel_time(origin_lat, origin_lng, dest_lat, dest_lng)
    result["cached_at"] = datetime.now(JST).isoformat()

    # キャッシュ保存
    cache[place_id] = result
    _save_cache(cache)

    time.sleep(0.2)  # レート制限対策
    return result
