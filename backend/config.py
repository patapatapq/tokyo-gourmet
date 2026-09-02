"""設定ファイル読み込みと定数定義"""

import os
from pathlib import Path

import yaml

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

# データディレクトリ
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DATA_DIR = PROJECT_ROOT / "frontend" / "public" / "data"
PHOTOS_DIR = PROJECT_ROOT / "frontend" / "public" / "photos"

# データファイル
VISITED_FILE = DATA_DIR / "visited.json"
HISTORY_FILE = DATA_DIR / "history.json"
STATION_CACHE_FILE = DATA_DIR / "station_cache.json"

# 認証
# 機密はディレクトリごと隔離する（プロジェクト構成規約 3章）。
# 名前による .gitignore は改名した瞬間に破れるため .secrets/ を主とする。
# OAuth クライアントの credentials.json は Excel-spreadsheets と共用しており、
# 向こうも ISS-426 で .secrets/ へ移した。片方だけ直すと認証が落ちる。
SECRETS_DIR = PROJECT_ROOT / ".secrets"
CREDENTIALS_DIR = Path(
    os.environ.get(
        "CREDENTIALS_DIR", str(Path(r"D:\Claude\Excel-spreadsheets\.secrets"))
    )
)
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
# gmail_token.json は TOKEN_FILE.parent から組み立てられる（gmail_client.py / setup_auth.py）。
# ここを .secrets/ に向ければ両方まとめて付いてくる。
TOKEN_FILE = SECRETS_DIR / "token.json"

# Google API スコープ
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_config() -> dict:
    """config.yaml を読み込んで辞書として返す。"""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key() -> str:
    """Google API キーを環境変数から取得する。"""
    key = os.environ.get("GOOGLE_API_KEY", "")
    if not key:
        raise ValueError("GOOGLE_API_KEY 環境変数が設定されていません")
    return key
