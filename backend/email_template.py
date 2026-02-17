"""メール用HTMLテンプレート"""


def render_email(
    restaurants: list[dict],
    week_label: str,
    site_url: str,
) -> str:
    """推薦レストランのHTMLメールを生成する。"""

    restaurant_rows = ""
    for i, r in enumerate(restaurants, 1):
        travel_cost = ""
        if r.get("travel_cost_yen") is not None:
            travel_cost = f" / ¥{r['travel_cost_yen']:,}"

        travel_time = r.get("travel_summary", "")
        if r.get("travel_time_minutes") is not None:
            travel_time = f"{r['travel_time_minutes']}分"
            if r.get("travel_summary"):
                travel_time += f" ({r['travel_summary']})"

        reservable = ""
        if r.get("reservable") is True:
            reservable = "📞 予約可"
        elif r.get("reservable") is False:
            reservable = "🚶 予約不要"

        budget_icon = r.get("budget_icon", "💰")
        budget_label = r.get("budget_label", "")
        price_range = r.get("price_range", "")

        restaurant_rows += f"""
        <tr>
          <td style="padding: 16px 0; border-bottom: 1px solid #eee;">
            <table cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="vertical-align: top; padding-right: 12px; width: 30px;">
                  <span style="font-size: 20px; font-weight: bold; color: #f97316;">{i}</span>
                </td>
                <td>
                  <div style="font-size: 16px; font-weight: bold; color: #1f2937; margin-bottom: 4px;">
                    {r['name']}
                    <span style="font-size: 13px; font-weight: normal; color: #f59e0b;">
                      ★{r.get('rating', '-')}
                    </span>
                    <span style="font-size: 12px; font-weight: normal; color: #9ca3af;">
                      ({r.get('user_rating_count', 0)}件)
                    </span>
                  </div>
                  <div style="font-size: 13px; color: #6b7280; line-height: 1.6;">
                    {budget_icon} {budget_label} {f'| {price_range}' if price_range else ''}<br>
                    🚃 {travel_time}{travel_cost}<br>
                    📍 {r.get('address', '')}<br>
                    {f'{reservable}<br>' if reservable else ''}
                  </div>
                  <div style="margin-top: 6px;">
                    <a href="{r.get('google_maps_url', '#')}"
                       style="font-size: 12px; color: #3b82f6; text-decoration: none;">
                      Google Maps で開く →
                    </a>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
  <table cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #f97316, #ea580c); padding: 24px; text-align: center;">
        <div style="font-size: 24px; font-weight: bold; color: #ffffff;">
          🍽️ 今週のグルメおすすめ
        </div>
        <div style="font-size: 14px; color: #fed7aa; margin-top: 4px;">
          {week_label}
        </div>
      </td>
    </tr>

    <!-- CTA -->
    <tr>
      <td style="padding: 20px 24px 8px;">
        <div style="text-align: center; margin-bottom: 16px;">
          <a href="{site_url}"
             style="display: inline-block; background-color: #f97316; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px;">
            📸 写真付き詳細を見る
          </a>
        </div>
        <div style="font-size: 14px; color: #6b7280; text-align: center;">
          今週の {len(restaurants)} 軒をピックアップしました！
        </div>
      </td>
    </tr>

    <!-- Restaurant List -->
    <tr>
      <td style="padding: 8px 24px 24px;">
        <table cellpadding="0" cellspacing="0" width="100%">
          {restaurant_rows}
        </table>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="background-color: #f3f4f6; padding: 16px 24px; text-align: center;">
        <div style="font-size: 12px; color: #9ca3af;">
          Tokyo Gourmet Recommender<br>
          <a href="{site_url}" style="color: #6b7280;">Webサイトで詳細を確認</a>
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
"""
