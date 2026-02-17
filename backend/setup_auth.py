"""初回セットアップ: Gmail + Sheets の OAuth2 認証を実行する。

使い方:
  python -m backend.setup_auth

このスクリプトはローカルで1回だけ実行する。
ブラウザが開いて Google ログイン画面が表示されるので、
権限を許可すると token.json と gmail_token.json が生成される。
"""
import base64
import io
import pickle
import sys
from pathlib import Path

# Windows cp932 対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from backend.config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_TOKEN_FILE = TOKEN_FILE.parent / "gmail_token.json"


def setup_sheets_auth():
    """Google Sheets の認証を実行する。"""
    print("=" * 50)
    print("[1/2] Google Sheets 認証")
    print("=" * 50)

    if not CREDENTIALS_FILE.exists():
        print(f"エラー: {CREDENTIALS_FILE} が見つかりません。")
        print("Google Cloud Console から OAuth 2.0 クライアント ID をダウンロードしてください。")
        return False

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    print(f"✓ Sheets トークン保存: {TOKEN_FILE}")

    # GitHub Actions 用の base64 エンコード
    with open(TOKEN_FILE, "rb") as f:
        token_b64 = base64.b64encode(f.read()).decode()

    print(f"\n--- GitHub Secrets に設定 ---")
    print(f"SHEETS_TOKEN_JSON の値（以下をコピー）:")
    print(f"{token_b64[:80]}...")
    print(f"（全文は長いため、実際にはファイルから直接コピーしてください）")

    return True


def setup_gmail_auth():
    """Gmail の認証を実行する。"""
    print()
    print("=" * 50)
    print("[2/2] Gmail 認証")
    print("=" * 50)

    if not CREDENTIALS_FILE.exists():
        print(f"エラー: {CREDENTIALS_FILE} が見つかりません。")
        return False

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)

    with open(GMAIL_TOKEN_FILE, "wb") as f:
        pickle.dump(creds, f)

    print(f"✓ Gmail トークン保存: {GMAIL_TOKEN_FILE}")

    # GitHub Actions 用の情報
    print(f"\n--- GitHub Secrets に設定 ---")
    print(f"GMAIL_CLIENT_ID: {creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET: {creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN: {creds.refresh_token}")

    return True


def main():
    print("Tokyo Gourmet Recommender - 初回認証セットアップ")
    print(f"認証ファイル: {CREDENTIALS_FILE}")
    print()

    if not CREDENTIALS_FILE.exists():
        print(f"エラー: {CREDENTIALS_FILE} が見つかりません。")
        print()
        print("手順:")
        print("1. Google Cloud Console (https://console.cloud.google.com) にアクセス")
        print("2. 既存プロジェクト 'claude-485004' を選択")
        print("3. 「APIとサービス」→「ライブラリ」で以下を有効化:")
        print("   - Places API (New)")
        print("   - Routes API")
        print("   - Gmail API")
        print("   - Google Sheets API")
        print("4. 「APIとサービス」→「認証情報」→「OAuth 2.0 クライアントID」を作成")
        print(f"5. credentials.json を {CREDENTIALS_FILE} に配置")
        print("6. このスクリプトを再実行")
        sys.exit(1)

    ok1 = setup_sheets_auth()
    ok2 = setup_gmail_auth()

    print()
    print("=" * 50)
    if ok1 and ok2:
        print("✓ セットアップ完了!")
        print()
        print("次のステップ:")
        print("1. config.yaml のメールアドレスとスプレッドシートIDを設定")
        print("2. Google Cloud Console で API キーを作成")
        print("3. GitHub リポジトリを作成して Secrets を設定")
        print("4. python -m backend.run_weekly でテスト実行")
    else:
        print("✗ セットアップに失敗しました。エラーを確認してください。")
        sys.exit(1)


if __name__ == "__main__":
    main()
