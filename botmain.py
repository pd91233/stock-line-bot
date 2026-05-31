# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from google import genai
import requests
import os
import re
import itertools
import yfinance as yf
import pandas as pd

app = Flask(__name__)

# ==========================================================
# 💓 0. 督戰隊心跳接收點 
# ==========================================================
@app.route("/", methods=['GET'])
def home():
    return "前線偵察兵：戰備狀態正常，未休眠！"

# ==========================================================
# 🔑 1. 金鑰設定與輪轉彈匣
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

gemini_keys = []
if os.environ.get('GEMINI_API_KEY'):
    gemini_keys.append(os.environ.get('GEMINI_API_KEY'))
for i in range(1, 6):
    k = os.environ.get(f'GEMINI_API_KEY_{i}')
    if k:
        gemini_keys.append(k)

if gemini_keys:
    key_cycle = itertools.cycle(gemini_keys)
else:
    print("⚠️ 警告：雲端保險箱內未偵測到任何 GEMINI_API_KEY！")

# ==========================================================
# 📚 2. 台股標的庫 (動態雙雷達系統)
# ==========================================================
global_stock_dict = {}

def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0:
        return global_stock_dict
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        l_res = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=10, verify=False)
        if l_res.status_code == 200:
            for item in l_res.json():
                global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
                
        o_res = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", headers=headers, timeout=10, verify=False)
        if o_res.status_code == 200:
            for item in o_res.json():
                global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
    except:
        pass

    if len(global_stock_dict) == 0:
        try:
            url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
            res = requests.get(url, timeout=10, verify=False).json()
            if res.get("msg") == "success":
                for item in res.get("data", []):
                    if item.get("stock_name") and item.get("stock_id"):
                        global_stock_dict[item.get("stock_name").strip()] = item.get("stock_id").strip()
        except:
            pass
            
    return global_stock_dict

# ==========================================================
# 📊 3. 戰場即時數據探測儀 (yfinance)
# ==========================================================
def fetch_realtime_data(stock_code):
    try:
        # 嘗試上市代碼
        tk = yf.Ticker(f"{stock_code}.TW")
        hist = tk.history(period="2mo") # 抓兩個月來算 20MA
        if hist.empty:
            # 嘗試上櫃代碼
            tk = yf.Ticker(f"{stock_code}.TWO")
            hist = tk.history(period="2mo")
            
        if hist.empty:
            return "⚠️ 無法取得最新交易數據。"
            
        # 計算均線與最新戰況
        latest_close = round(hist['Close'].iloc[-1], 2)
        latest_vol = int(hist['Volume'].iloc[-1] / 1000)
        ma5 = round(hist['Close'].rolling(window=5).mean().iloc[-1], 2)
        ma10 = round(hist['Close'].rolling(window=10).mean().iloc[-1], 2)
        ma20 = round(hist['Close'].rolling(window=20).mean().iloc[-1], 2)
        
        return f"收盤價 {latest_close}元，成交量 {latest_vol}張。5MA={ma5}，10MA={ma10}，20MA={ma20}。"
    except Exception as e:
        return f"數據抓取異常"

# ==========================================================
# 📡 4. Webhook 接收通道
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
# 🧠 5. 智慧過濾與戰略卡片發射
# ==========================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    if len(user_msg) > 10:
        return

    is_stock_query = False
    stock_query = ""
    stock_code = ""

    if re.fullmatch(r'\d{4,6}', user_msg):
        is_stock_query = True
        stock_query = user_msg
        stock_code = user_msg
    else:
        stock_dict = get_stock_dict()
        matches = {n: c for n, c in stock_dict.items() if user_msg in n}
        
        if len(matches) == 1:
            name = list(matches.keys())[0]
            stock_code = list(matches.values())[0]
            is_stock_query = True
            stock_query = f"{name} ({stock_code})"
        elif len(matches) > 1:
            sorted_matches = sorted(matches.items(), key=lambda x: len(x[0]))[:10]
            choices = "\n".join([f"• {n} ({c})" for n, c in sorted_matches])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📍 找到多筆資料，請確認：\n{choices}"))
            return
        else:
            if "查詢" in user_msg or len(user_msg) >= 2:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠️ 找不到符合「{user_msg}」的標的。"))
            return

    if is_stock_query:
        print(f"🎯 [雷達截獲] 群組查詢：{stock_query}") 
        
        # 🚀 呼叫探測儀，抓取真實數字
        real_data = fetch_realtime_data(stock_code)
        
        success = False
        attempts = 0
        max_attempts = len(gemini_keys) if gemini_keys else 1
        ai_reply = ""

        while attempts < max_attempts and gemini_keys:
            current_key = next(key_cycle)
            try:
                client = genai.Client(api_key=current_key)
                
                # 🌟 [究極武裝] 將真實數據塞入戰術指令中！
                prompt = f"""你是一位擁有十年實戰經驗的台股操盤手，請以冷靜、俐落的語氣回報。
嚴格遵守以下指令：絕對不要輸出任何內心思考過程、推演邏輯或免責聲明，直接給出結論。
請根據我方雷達探測到的【{stock_query}】最新真實戰況：
【{real_data}】

請提供以下精簡戰報，用條列式排版，總字數控制在 150 字以內：
1. 📈 均線與趨勢：根據我方提供的均線價格(5/10/20MA)與收盤價比對，判斷目前股價的支撐與壓力防線。
2. 🕵️ 籌碼與心理：推測目前主力可能的洗盤或拉抬意圖。
3. ⚔️ 短線戰術：給出明確的進出場觀察建議。"""
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                ai_reply = response.text.strip()
                success = True
                break 
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str:
                    print(f"⚠️ [彈匣警告] 金鑰額度耗盡，自動切換...")
                    attempts += 1
                else:
                    print(f"⚠️ [大腦異常] 非額度問題: {e}")
                    break 

        if success:
            flex_content = {
                "type": "bubble",
                "styles": {
                    "header": {"backgroundColor": "#1A365D"}, 
                    "body": {"backgroundColor": "#F7FAFC"}    
                },
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": "🎯 戰術推演回報", "color": "#D69E2E", "weight": "bold", "size": "sm"},
                        {"type": "text", "text": stock_query, "color": "#FFFFFF", "weight": "bold", "size": "xl", "margin": "md"}
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": f"📊 雷達數據：\n{real_data}", "color": "#1A365D", "size": "xs", "weight": "bold", "wrap": True},
                        {"type": "separator", "margin": "md"},
                        {"type": "text", "text": ai_reply, "color": "#2D3748", "wrap": True, "size": "sm", "margin": "md"}
                    ]
                }
            }

            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="📈 大盤", text="大盤")),
                QuickReplyButton(action=MessageAction(label="🔥 台積電", text="2330")),
                QuickReplyButton(action=MessageAction(label="🚢 長榮", text="2603"))
            ])
            
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content, quick_reply=quick_reply))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 報告統帥：AI 金鑰連線異常或彈匣已空！"))

if __name__ == "__main__":
    app.run(port=5000)
