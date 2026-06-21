import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
DATA_SHEET = "記帳明細"

def get_service():
    """建立 Google Sheets API 連線"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise ValueError("缺少 GOOGLE_CREDENTIALS_JSON 環境變數")
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

def append_expense(expense: dict) -> bool:
    """
    寫入一筆支出記錄到 Google Sheets
    欄位順序：日期 | 品項 | 分類 | 金額 | 付款人 | 記錄時間
    """
    try:
        service = get_service()
        now = datetime.now().strftime("%Y/%m/%d %H:%M")
        row = [
            expense["date"],
            expense["item"],
            expense["category"],
            expense["amount"],
            expense["payer"],
            now,
        ]
        body = {"values": [row]}
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{DATA_SHEET}!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        return True
    except Exception as e:
        print(f"[Google Sheets Error] {e}")
        return False

def get_summary() -> dict | None:
    """取得本月支出摘要"""
    try:
        service = get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{DATA_SHEET}!A2:F",
        ).execute()
        rows = result.get("values", [])
        if not rows:
            return None

        current_month = datetime.now().strftime("%Y/%m")
        total = 0
        count = 0
        by_category = {}

        for row in rows:
            if len(row) < 4:
                continue
            date_str = row[0]
            if not date_str.startswith(current_month):
                continue
            try:
                amount = float(row[3])
                category = row[2] if len(row) > 2 else "其他"
                total += amount
                count += 1
                by_category[category] = by_category.get(category, 0) + amount
            except (ValueError, IndexError):
                continue

        if count == 0:
            return None

        # 依金額排序
        by_category = dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True))

        return {
            "month": current_month.replace("/", " 年 ") + " 月",
            "total": total,
            "count": count,
            "by_category": by_category,
        }
    except Exception as e:
        print(f"[Summary Error] {e}")
        return None
