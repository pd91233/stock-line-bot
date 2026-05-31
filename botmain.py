# -*- coding: utf-8 -*-
# ==========================================================
# 🎧 股海觀浪前線偵察兵：botmain.py (直覺查詢升級版)
# ==========================================================
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai
import requests
import re
import threading

app = Flask(__name__)

# ==========================================================
# 🔑 1. 金鑰設定區 (請確認這裡的金鑰正確)
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = 'SMvkBhzw64RpFhLGsaDRfzqPVPkxAk8HYLz+Pvy/kiVG/n3XkSNWOcPPyQkSpWrCcAj3+SmAaM1iopF9dz6TJdo6xyQwBv0soAzdn+Wdn3GC2YS+4m16cEzIW5pUTqO12JC6grdw6ktZ4wh3arR5+gdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '9d160bd7696bc116bead171fffc7ddb7' # 在 LINE Developer 後台的 Basic settings 裡
GEMINI_API_KEY = 'AIzaSyDGpHCEWUlWNcWPG6Td8tBzjPVz-n8erzQ'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================================
# 📚 2. 台股標的庫與同步功能 (移植舊系統邏輯)
# ==========================================================
global_stock_dict = {}

def sync_stock_dict():
    global global_stock_dict
    print("🔄 [雷達] 正在同步全台股標的庫...")
    try:
        # 抓取上市名單
        l_res = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", timeout=10, verify=False)
        for item in l_res.json():
            global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
        # 抓取上櫃名單
        o_res = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", timeout=10, verify=False)
        for item in o_res.json():
            global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
        print(f"✅ [雷達] 同步完成，武裝 {len(global_stock_dict)} 檔標的。")
    except Exception as e:
        print(f"⚠️ [雷達] 同步失敗: {e}")

# ==========================================================
# 📡 3. Webhook 接收通道
# ==========================================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ==========================================================
# 🧠 4. 智慧過濾與被動回覆
# ==========================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    # 防吵機制：字數大於 10 字的閒聊直接忽略
    if len(user_msg) > 10:
        return

    is_stock_query = False
    stock_query = ""

    # 🎯 條件 A：純數字 4~6 碼 (直接輸入代號)
    if re.fullmatch(r'\d{4,6}', user_msg):
        is_stock_query = True
        stock_query = user_msg

    # 🎯 條件 B：模糊搜尋 (中文字比對台股字典)
    else:
        matches = {n: c for n, c in global_stock_dict.items() if user_msg in n}
        if len(matches) == 1:
            # 精準命中一檔
            name = list(matches.keys())[0]
            code = list(matches.values())[0]
            is_stock_query = True
            stock_query = f"{name} ({code})"
        elif len(matches) > 1:
            # 命中多檔，列出清單防呆
            sorted_matches = sorted(matches.items(), key=lambda x: len(x[0]))[:10]
            choices = "\n".join([f"• {n} ({c})" for n, c in sorted_matches])
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"📍 找到多筆相符資料，請輸入更完整的名稱：\n{choices}")
            )
            return

    # 🚀 如果確認是股票查詢，發射給 Gemini 大腦
    if is_stock_query:
        print(f"🎯 [雷達截獲] 群組有人正在查詢：{stock_query}") # 👉 加上這一行
        try:
            sys_prompt = "你是一個台股助理，請用最簡短的白話文，分析這檔股票近期的市場概況。嚴禁長篇大論。"
            response = model.generate_content([sys_prompt, f"股友詢問：{stock_query}"])
            ai_reply = response.text.strip()
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"🤖 偵察兵回報【{stock_query}】：\n{ai_reply}")
            )
        except Exception as e:
            print(f"解析異常: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 偵察兵大腦連線異常，請稍後再試。")
            )

if __name__ == "__main__":
    # 啟動前先同步字典
    sync_stock_dict()
    print("🎧 前線偵察兵已上線，正在監聽群組動靜...")
    app.run(port=5000)
