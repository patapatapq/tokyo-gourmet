"""レストラン選定ロジック: フィルタリング・予算分類・重み付きランダム選定"""
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from backend.config import VISITED_FILE, HISTORY_FILE

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# Google Places API の priceLevel マッピング
PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def load_visited_ids() -> set[str]:
    """訪問済みレストランの place_id セットを読み込む。"""
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {v["place_id"] for v in data.get("visited", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def load_recent_history(weeks: int = 4) -> set[str]:
    """直近N週に推薦済みの place_id セットを読み込む。"""
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

    cutoff = datetime.now(JST) - timedelta(weeks=weeks)
    recent_ids = set()
    for week in data.get("weeks", []):
        week_date = datetime.fromisoformat(week["generated_at"])
        if week_date >= cutoff:
            for r in week.get("restaurants", []):
                recent_ids.add(r["place_id"])
    return recent_ids


def classify_budget(
    place: dict,
    budget_config: dict,
) -> dict:
    """レストランの予算を朝昼/夜それぞれで分類する。

    Returns:
        {
            "morning_lunch": {"tier": "kosupa|average|premium", "label": "...", "icon": "..."},
            "dinner": {"tier": "kosupa|average|premium", "label": "...", "icon": "..."},
        }
    """
    price_level = place.get("priceLevel", "PRICE_LEVEL_MODERATE")
    level_num = PRICE_LEVEL_MAP.get(price_level, 2)

    result = {}
    for meal_type in ["morning_lunch", "dinner"]:
        tiers = budget_config[meal_type]

        if level_num <= 1:
            tier_key = "kosupa"
        elif level_num == 2:
            tier_key = "average"
        else:
            tier_key = "premium"

        tier = tiers[tier_key]
        result[meal_type] = {
            "tier": tier_key,
            "label": tier["label"],
            "icon": tier["icon"],
        }

    return result


def estimate_price_range(price_level: str, meal_type: str, budget_config: dict) -> str:
    """price_level から推定価格帯文字列を生成する。"""
    level_num = PRICE_LEVEL_MAP.get(price_level, 2)

    if level_num <= 1:
        tier_key = "kosupa"
    elif level_num == 2:
        tier_key = "average"
    else:
        tier_key = "premium"

    tier = budget_config[meal_type][tier_key]
    min_val = tier.get("min", 0)
    max_val = tier.get("max")

    if max_val:
        return f"¥{min_val:,}〜¥{max_val:,}"
    else:
        return f"¥{min_val:,}〜"


def filter_candidates(
    places: list[dict],
    visited_ids: set[str],
    recent_ids: set[str],
    min_reviews: int = 50,
    max_travel_minutes: int = 90,
    travel_info: dict | None = None,
) -> list[dict]:
    """候補をフィルタリングする。

    Args:
        places: 検索結果のレストラン一覧
        visited_ids: 訪問済み place_id
        recent_ids: 直近推薦済み place_id
        min_reviews: 最低レビュー数
        max_travel_minutes: 最大移動時間（分）
        travel_info: {place_id: travel_info_dict} の辞書

    Returns:
        フィルタ後の候補リスト
    """
    travel_info = travel_info or {}
    filtered = []

    for place in places:
        place_id = place.get("id", "")

        # 訪問済みを除外
        if place_id in visited_ids:
            continue

        # 直近推薦済みを除外（ただし訪問済みでないもの）
        if place_id in recent_ids:
            continue

        # レビュー数チェック
        review_count = place.get("userRatingCount", 0)
        if review_count < min_reviews:
            continue

        # 移動時間チェック
        if place_id in travel_info:
            travel_mins = travel_info[place_id].get("travel_time_minutes")
            if travel_mins is not None and travel_mins > max_travel_minutes:
                continue

        filtered.append(place)

    logger.info(
        f"フィルタ結果: {len(places)}件 → {len(filtered)}件 "
        f"(訪問済み除外, レビュー{min_reviews}件以上, {max_travel_minutes}分以内)"
    )
    return filtered


def weighted_random_pick(candidates: list[dict], count: int) -> list[dict]:
    """評価で重み付けしたランダム選定。

    高評価ほど選ばれやすいが、完全に評価順ではない。
    """
    if len(candidates) <= count:
        return candidates

    # 重み: rating の2乗（高評価をやや優遇）
    weights = []
    for c in candidates:
        rating = c.get("rating", 4.0)
        weights.append(rating ** 2)

    selected = []
    remaining = list(range(len(candidates)))
    remaining_weights = list(weights)

    for _ in range(count):
        if not remaining:
            break
        chosen_idx = random.choices(
            remaining, weights=remaining_weights, k=1
        )[0]
        pos = remaining.index(chosen_idx)
        selected.append(candidates[chosen_idx])
        remaining.pop(pos)
        remaining_weights.pop(pos)

    return selected
