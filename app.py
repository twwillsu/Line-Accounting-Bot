import os
import re
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
from google_sheets import append_expense, get_summary
import json

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))

# 支出分類關鍵字對照
CATEGORIES = {
    "餐飲": ["早餐", "午餐", "晚餐", "飲料", "咖啡", "宵夜", "火鍋", "燒烤", "便當", "麵", "飯", "吃", "買咖啡"],
    "交通": ["uber", "計程車", "捷運", "公車", "油費", "停車", "高鐵", "火車"],
    "購物": ["超市", "全聯", "costco", "好市多", "購物", "衣服", "鞋子"],
    "娛樂": ["電影", "KTV", "遊戲", "票", "展覽"],
    "日用品": ["衛生紙", "清潔", "洗髮", "洗衣"],
    "醫療": ["藥", "診所", "醫院", "掛號"],
}

def detect_category(item_name):
    item_lower = item_name.lower()
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in item_lower:
                return category
    return "其他"

def get_user_name(event):
    """取得用戶 LINE 顯示名稱，支援群組/聊天室"""
    user_id = event.source.user_id
    try:
        source_type = event.source.type
        if source_type == "group":
            profile = line_bot_api.get_group_member_profile(event.source.group_id, user_id)
        elif source_type == "room":
            profile = line_bot_api.get_room_member_profile(event.source.room_id, user_id)
        else:
            profile = line_bot_api.get_profile(user_id)
        return profile.display_name
    except Exception:
        return "群組成員"

def parse_expense(text, user_name):
    text = text.strip()
    for prefix in ["/記帳", "/加", "/add"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    pattern = r'^(.+?)\s+(\d+(?:\.\d+)?)\s*(.*)$'
    match = re.match(pattern, text)
    if not match:
        return None

    item = match.group(1).strip()
    amount = float(match.group(2))
    date_str = match.group(3).strip()

    now = datetime.now()

    if date_str:
        for fmt in ["%Y/%m/%d", "%m/%d", "%Y-%m-%d", "%m-%d"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if fmt in ["%m/%d", "%m-%d"]:
                    parsed = parsed.replace(year=now.year)
                # 合併日期 + 當前時間
                expense_datetime = parsed.strftime("%Y/%m/%d") + now.strftime(" %H:%M")
                break
            except ValueError:
                continue
        else:
            expense_datetime = now.strftime("%Y/%m/%d %H:%M")
    else:
        expense_datetime = now.strftime("%Y/%m/%d %H:%M")

    category = detect_category(item)

    return {
        "datetime": expense_datetime,
        "item": item,
        "amount": amount,
        "category": category,
        "payer": user_name,
    }

def build_confirm_flex(expense):
    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": "✅ 記帳成功！", "weight": "bold", "color": "#ffffff", "size": "md"}],
            "backgroundColor": "#27ACB2"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "📅 時間", "size": "sm", "color": "#888888", "flex": 2},
                    {"type": "text", "text": expense["datetime"], "size": "sm", "flex": 3, "weight": "bold"}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "🛍️ 品項", "size": "sm", "color": "#888888", "flex": 2},
                    {"type": "text", "text": expense["item"], "size": "sm", "flex": 3, "weight": "bold"}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "🏷️ 分類", "size": "sm", "color": "#888888", "flex": 2},
                    {"type": "text", "text": expense["category"], "size": "sm", "flex": 3}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "💰 金額", "size": "sm", "color": "#888888", "flex": 2},
                    {"type": "text", "text": f"NT$ {expense['amount']:.0f}", "size": "sm", "flex": 3,
                     "weight": "bold", "color": "#E74C3C"}
                ]},
                {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
                    {"type": "text", "text": "👤 付款人", "size": "sm", "color": "#888888", "flex": 2},
                    {"type": "text", "text": expense["payer"], "size": "sm", "flex": 3}
                ]},
            ]
        },
        "footer": {
            "type": "box", "layout": "vertical",
            "contents": [{"type": "text", "text": "已同步至 Google Sheets 📊", "size": "xs", "color": "#888888", "align": "center"}]
        }
    }
    return FlexSendMessage(alt_text="記帳成功", contents=bubble)

def build_summary_flex(summary):
    items = []
    for cat, amt in summary["by_category"].items():
        items.append({
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                {"type": "text", "text": cat, "size": "sm", "flex": 3},
                {"type": "text", "text": f"NT$ {amt:.0f}", "size": "sm", "flex": 2, "align": "end", "weight": "bold"}
            ]
        })
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [{"type": "text", "text": f"📊 {summary['month']} 支出摘要", "weight": "bold", "color": "#ffffff", "size": "md"}],
            "backgroundColor": "#7B66FF"
        },
        "body": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"總支出：NT$ {summary['total']:.0f}", "weight": "bold", "size": "lg", "color": "#E74C3C", "margin": "md"},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": "分類明細", "size": "sm", "color": "#888888", "margin": "md"},
                *items,
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": f"筆數：{summary['count']} 筆", "size": "xs", "color": "#888888", "margin": "sm"}
            ]
        }
    }
    return FlexSendMessage(alt_text="本月支出摘要", contents=bubble)

HELP_TEXT = """💡 記帳機器人使用說明

【記帳格式】（日期可省略）
  午餐 150
  午餐 150 6/21
  /記帳 咖啡 75 2024/6/21

【查詢指令】
  /摘要 → 本月支出總覽
  /幫助 → 顯示此說明

【自動功能】
  ✅ 自動分類品項
  ✅ 同步 Google Sheets
  ✅ 圓餅圖＋折線圖自動更新
  ✅ 每月自動清除，存入歷史"""

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()

    user_name = get_user_name(event)

    if text in ["/幫助", "/help", "幫助", "說明"]:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

    if text in ["/摘要", "/summary", "摘要", "本月"]:
        summary = get_summary()
        if summary:
            line_bot_api.reply_message(event.reply_token, build_summary_flex(summary))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="本月尚無記帳資料 📭"))
        return

    expense = parse_expense(text, user_name)
    if expense:
        success = append_expense(expense)
        if success:
            line_bot_api.reply_message(event.reply_token, build_confirm_flex(expense))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 記帳失敗，請稍後再試"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
