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
# 📊 3. 戰場即時數據探測儀 (直連底層 API)
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0"}
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TW?range=2mo&interval=1d"
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        
        if not data.get('chart', {}).get('result'):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()

        result = data['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        volumes = result['indicators']['quote'][0]['volume']
        
        valid_closes = [c for c in closes if c is not None]
        valid_vols = [v for v in volumes if v is not None]
        
        if len(valid_closes) < 20:
            return "⚠️ 歷史數據不足，無法計算均線。"
            
        latest_close = round(valid_closes[-1], 2)
        latest_vol = int(valid_vols[-1] / 1000)
        ma5 = round(sum(valid_closes[-5:]) / 5, 2)
        ma10 = round(sum(valid_closes[-10:]) / 10, 2)
        ma20 = round(sum(valid_closes[-20:]) / 20, 2)
        
        return f"收盤價 {latest_close}元，成交量 {latest_vol}張。5MA={ma5}，10MA={ma10}，20MA={ma20}。"
    except Exception as e:
        return "⚠️ 雷達連線受阻，無法取得數字。"

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
    
    if len(user_msg) > 15:
        return

    is_stock_query = False
    stock_query = ""
    stock_code = ""
    analysis_type = "綜合" # 🌟 新增：判斷使用者要看哪種分析

    # 🌟 攔截戰術連擊指令 (例如：技術面 2330)
    if user_msg.startswith("技術面 ") or user_msg.startswith("籌碼面 "):
        analysis_type = user_msg[:3] # 取出 "技術面" 或 "籌碼面"
        user_msg = user_msg[4:]      # 剩下的當作股票代號

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
        real_data = fetch_realtime_data(stock_code)
        
        success = False
        attempts = 0
        max_attempts = len(gemini_keys) if gemini_keys else 1
        ai_reply = ""

        while attempts < max_attempts and gemini_keys:
            current_key = next(key_cycle)
            try:
                client = genai.Client(api_key=current_key)
                
                # 🌟 [動態大腦] 根據分析類型，給予不同的戰術指令
                if analysis_type == "技術面":
                    prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】的純技術面。請直接給出結論(150字內)：
1. 均線排列與乖離狀況。
2. 支撐壓力推演。
3. 技術面短線進出建議。
絕對不要有免責聲明與內心戲。"""
                    card_title = "📈 技術面深度解析"
                elif analysis_type == "籌碼面":
                    prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】的籌碼與主力心理。請直接給出結論(150字內)：
1. 根據目前價位與成交量，推測主力意圖(洗盤/出貨/吃貨)。
2. 散戶目前可能的心理狀態。
3. 籌碼面跟單建議。
絕對不要有免責聲明與內心戲。"""
                    card_title = "🕵️ 籌碼面深度解析"
                else:
                    prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】。請直接給出結論(150字內)：
1. 📈 均線與趨勢。
2. 🕵️ 籌碼與心理推測。
3. ⚔️ 短線戰術建議。
絕對不要有免責聲明與內心戲。"""
                    card_title = "🎯 綜合戰術推演"

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                ai_reply = response.text.strip()
                success = True
                break 
            except Exception as e:
                attempts += 1

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
                        {"type": "text", "text": card_title, "color": "#D69E2E", "weight": "bold", "size": "sm"},
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

            # 🌟 【戰術連擊選單實裝】底下浮出專屬這檔股票的深度挖掘按鈕！
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="📈 深挖技術面", text=f"技術面 {stock_code}")),
                QuickReplyButton(action=MessageAction(label="🕵️ 深挖籌碼面", text=f"籌碼面 {stock_code}")),
                QuickReplyButton(action=MessageAction(label="🔙 查詢大盤", text="大盤"))
            ])
            
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content, quick_reply=quick_reply))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 警告：AI 金鑰連線異常或彈匣已空！請重新輸入"))

if __name__ == "__main__":
    app.run(port=5000)
