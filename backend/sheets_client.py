"""Google Sheets クライアント（訪問済みレストラン管理）"""
import json
import logging
import os
import pickle
from pathlib import Path

import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from backend.config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES, VISITED_FILE

logger = logging.getLogger(__name__)

SHEET_HEADERS = [
    "place_id", "name", "date_recommended", "visited", "visited_date"
]


def authenticate() -> gspread.Client:
    """Google Sheets API に OAuth2 で接続する。"""
    creds = None

    # GitHub Actions ではシークレットから認証
    token_json = os.environ.get("SHEETS_TOKEN_JSON", "")
    if token_json:
        import base64
        token_data = base64.b64decode(token_json)
        creds = pickle.loads(token_data)
    elif TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", str(CREDENTIALS_FILE))
            if not Path(creds_file).exists():
                raise FileNotFoundError(
                    f"認証ファイルが見つかりません: {creds_file}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return gspread.authorize(creds)


def get_visited_from_sheet(spreadsheet_id: str, worksheet_name: str = "visited") -> set[str]:
    """Google Sheets から訪問済み place_id を取得する。"""
    try:
        client = authenticate()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        records = worksheet.get_all_records()

        visited_ids = set()
        for row in records:
            if str(row.get("visited", "")).upper() in ("TRUE", "YES", "1", "○"):
                visited_ids.add(str(row["place_id"]))

        logger.info(f"Sheets から訪問済み {len(visited_ids)} 件を取得")
        return visited_ids

    except Exception as e:
        logger.warning(f"Sheets 読み込み失敗（ローカルのvisited.jsonを使用）: {e}")
        return set()


def sync_recommendations_to_sheet(
    spreadsheet_id: str,
    restaurants: list[dict],
    generated_date: str,
    worksheet_name: str = "visited",
) -> None:
    """今週の推薦をスプレッドシートに追記する。"""
    try:
        client = authenticate()
        spreadsheet = client.open_by_key(spreadsheet_id)

        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=worksheet_name, rows=1000, cols=len(SHEET_HEADERS)
            )
            worksheet.append_row(SHEET_HEADERS)

        existing = worksheet.get_all_records()
        existing_ids = {str(r["place_id"]) for r in existing}

        new_rows = []
        for r in restaurants:
            if r["place_id"] not in existing_ids:
                new_rows.append([
                    r["place_id"],
                    r["name"],
                    generated_date,
                    "FALSE",
                    "",
                ])

        if new_rows:
            worksheet.append_rows(new_rows)
            logger.info(f"Sheets に {len(new_rows)} 件追記しました")
        else:
            logger.info("Sheets への追記なし（全て既存）")

    except Exception as e:
        logger.warning(f"Sheets 書き込み失敗: {e}")


def merge_visited_sources(
    spreadsheet_id: str,
    worksheet_name: str = "visited",
) -> set[str]:
    """ローカルの visited.json と Google Sheets の両方から訪問済みを統合する。"""
    # ローカル
    local_ids = set()
    try:
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        local_ids = {v["place_id"] for v in data.get("visited", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Sheets
    sheet_ids = set()
    if spreadsheet_id:
        sheet_ids = get_visited_from_sheet(spreadsheet_id, worksheet_name)

    merged = local_ids | sheet_ids
    logger.info(
        f"訪問済み統合: ローカル {len(local_ids)}件 + Sheets {len(sheet_ids)}件 "
        f"= {len(merged)}件（重複除去済み）"
    )
    return merged
