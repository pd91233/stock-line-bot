# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from google import genai  # 🌟 換裝 Google 最新火控系統
import requests
import os
import re
import itertools

app = Flask(__name__)

# ==========================================================
# 💓 0. 督戰隊心跳接收點 (解決 404 Not Found)
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
        
    print("🔄 [雷達] 字典為空，啟動緊急動態裝填...")
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
    except Exception as e:
        print(f"⚠️ 證交所雷達受阻: {e}")

    if len(global_stock_dict) == 0:
        print("🔄 [雷達] 切換至 FinMind 備用頻道...")
        try:
            url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
            res = requests.get(url, timeout=10, verify=False).json()
            if res.get("msg") == "success":
                for item in res.get("data", []):
                    if item.get("stock_name") and item.get("stock_id"):
                        global_stock_dict[item.get("stock_name").strip()] = item.get("stock_id").strip()
        except Exception as e:
            print(f"⚠️ FinMind 雷達受阻: {e}")
            
    print(f"✅ [雷達] 動態裝填完畢，目前武裝 {len(global_stock_dict)} 檔標的。")
    return global_stock_dict

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
# 🧠 4. 智慧過濾與戰略卡片發射
# ==========================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    
    if len(user_msg) > 10:
        return

    is_stock_query = False
    stock_query = ""

    if re.fullmatch(r'\d{4,6}', user_msg):
        is_stock_query = True
        stock_query = user_msg
    else:
        stock_dict = get_stock_dict()
        matches = {n: c for n, c in stock_dict.items() if user_msg in n}
        
        if len(matches) == 1:
            name = list(matches.keys())[0]
            code = list(matches.values())[0]
            is_stock_query = True
            stock_query = f"{name} ({code})"
        elif len(matches) > 1:
            sorted_matches = sorted(matches.items(), key=lambda x: len(x[0]))[:10]
            choices = "\n".join([f"• {n} ({c})" for n, c in sorted_matches])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📍 找到多筆相符資料，請確認：\n{choices}"))
            return
        else:
            if "查詢" in user_msg or len(user_msg) >= 2:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠️ 找不到符合「{user_msg}」的標的。"))
            return

    if is_stock_query:
        print(f"🎯 [雷達截獲] 群組查詢：{stock_query}") 
        success = False
        attempts = 0
        max_attempts = len(gemini_keys) if gemini_keys else 1
        ai_reply = ""

        while attempts < max_attempts and gemini_keys:
            current_key = next(key_cycle)
            try:
                # 🌟 [修復] 使用新版 SDK 的發射器
                client = genai.Client(api_key=current_key)
                # 🌟 [升級] 注入資深操盤手靈魂與嚴格的戰術框架
                prompt = f"""你是一位擁有十年實戰經驗的台股操盤手，請以冷靜、客觀、俐落的語氣回報。
嚴格遵守以下指令：絕對不要輸出任何內心思考過程、推演邏輯或免責聲明，直接給出最終結論。
請針對【{stock_query}】提供以下精簡戰報，請用條列式排版，總字數控制在 150 字以內：
1. 📈 趨勢與均線：目前整體趨勢偏多或偏空？均線扣抵的關鍵支撐與壓力防線在哪？
2. 🕵️ 主力與籌碼：近期大戶或法人可能的控盤動向與心理戰術預判。
3. ⚔️ 短線戰術：針對短線操作者的進出場觀察建議。"""
                
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
                        {"type": "text", "text": ai_reply, "color": "#2D3748", "wrap": True, "size": "md"}
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
