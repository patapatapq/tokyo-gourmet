"""メール用HTMLテンプレート"""


def render_email(
    restaurants: list[dict],
    week_label: str,
    site_url: str,
) -> str:
    """推薦レストランのHTMLメールを生成する。"""

    count = len(restaurants)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #0D0D1A;
             font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
  <table cellpadding="0" cellspacing="0" width="100%"
         style="max-width: 600px; margin: 0 auto;
                background-color: #0D0D1A;
                border-radius: 12px;
                overflow: hidden;">

    <!-- ヘッダー -->
    <tr>
      <td style="background: linear-gradient(135deg, #f97316, #ea580c);
                 padding: 32px 24px 28px; text-align: center;">
        <div style="font-size: 13px; letter-spacing: 0.12em;
                    color: rgba(255,255,255,0.75); margin-bottom: 10px;">
          TOKYO ぱたしー GOURMET
        </div>
        <div style="font-size: 26px; font-weight: bold; color: #ffffff; line-height: 1.3;">
          🍽️ 今週のグルメおすすめ
        </div>
        <div style="font-size: 13px; color: #fed7aa; margin-top: 8px;">
          {week_label}
        </div>
      </td>
    </tr>

    <!-- メイン -->
    <tr>
      <td style="padding: 48px 32px 40px; text-align: center;
                 background-color: #141428;">
        <div style="font-size: 15px; color: #CBD5E1; margin-bottom: 32px; line-height: 1.7;">
          1週間おつかれさま！<br>
          今週の {count} 件をピックアップしました。
        </div>
        <a href="{site_url}"
           style="display: inline-block;
                  background: linear-gradient(135deg, #f97316, #ea580c);
                  color: #ffffff;
                  text-decoration: none;
                  font-size: 16px;
                  font-weight: bold;
                  padding: 16px 40px;
                  border-radius: 50px;
                  letter-spacing: 0.04em;">
          写真付き詳細をみる
        </a>
      </td>
    </tr>

    <!-- セパレーター -->
    <tr>
      <td style="background-color: #141428; padding: 0 32px;">
        <div style="border-top: 1px solid rgba(255,255,255,0.08);"></div>
      </td>
    </tr>

    <!-- フッター -->
    <tr>
      <td style="background-color: #0D0D1A; padding: 20px 24px; text-align: center;">
        <div style="font-size: 11px; color: #94A3B8; line-height: 1.8;">
          Tokyo Patashī Gourmet<br>
          <a href="{site_url}" style="color: #f97316; text-decoration: none;">
            {site_url}
          </a>
        </div>
      </td>
    </tr>

  </table>
</body>
</html>"""
