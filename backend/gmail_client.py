"""Gmail API クライアント（OAuth2 メール送信）"""
import base64
import logging
import os
import pickle
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from backend.config import CREDENTIALS_FILE, TOKEN_FILE

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _get_gmail_credentials() -> Credentials:
    """Gmail API の認証情報を取得する。"""
    creds = None

    # GitHub Actions: 環境変数からリフレッシュトークンを使用
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "")
    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")

    if refresh_token and client_id and client_secret:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=GMAIL_SCOPES,
        )
        creds.refresh(Request())
        return creds

    # ローカル: token.json から読み込み
    gmail_token = TOKEN_FILE.parent / "gmail_token.json"
    if gmail_token.exists():
        with open(gmail_token, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", str(CREDENTIALS_FILE))
            if not Path(creds_file).exists():
                raise FileNotFoundError(f"認証ファイルが見つかりません: {creds_file}")
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        with open(gmail_token, "wb") as f:
            pickle.dump(creds, f)

    return creds


def send_email(
    to: str,
    subject: str,
    html_body: str,
    sender: str = "",
) -> bool:
    """Gmail API でHTMLメールを送信する。

    Args:
        to: 送信先メールアドレス
        subject: 件名
        html_body: HTML本文
        sender: 送信元（空の場合は認証アカウント）

    Returns:
        送信成功ならTrue
    """
    try:
        creds = _get_gmail_credentials()
        service = build("gmail", "v1", credentials=creds)

        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject
        if sender:
            msg["From"] = sender

        # プレーンテキスト版（フォールバック）
        plain_text = html_body.replace("<br>", "\n").replace("</p>", "\n")
        import re
        plain_text = re.sub(r"<[^>]+>", "", plain_text)
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))

        # HTML版
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        logger.info(f"メール送信成功: {to}")
        return True

    except Exception as e:
        logger.error(f"メール送信失敗: {e}")
        return False
