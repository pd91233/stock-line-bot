# -*- coding: utf-8 -*-
# ==========================================================
# 🎧 股海觀浪前線偵察兵：botmain.py (直覺查詢 + Flex卡片 + 金鑰輪轉)
# ==========================================================
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import google.generativeai as genai
import requests
import os
import re
import itertools

app = Flask(__name__)

# ==========================================================
# 🔑 1. 金鑰設定區 (支援單把或多把金鑰自動輪轉)
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 🔄 建立 API 金鑰輪轉彈匣
gemini_keys = []
# 保留您原本設定的主金鑰
if os.environ.get('GEMINI_API_KEY'):
    gemini_keys.append(os.environ.get('GEMINI_API_KEY'))
# 自動尋找額外擴充的金鑰 (GEMINI_API_KEY_1 ~ 5)
for i in range(1, 6):
    k = os.environ.get(f'GEMINI_API_KEY_{i}')
    if k:
        gemini_keys.append(k)

# 啟動無限輪迴，如果保險箱沒放半把鑰匙則防呆
if gemini_keys:
    key_cycle = itertools.cycle(gemini_keys)
else:
    print("⚠️ 警告：雲端保險箱內未偵測到任何 GEMINI_API_KEY！")

# ==========================================================
# 📚 2. 台股標的庫與同步功能 (啟動 FinMind 備用雷達)
# ==========================================================
global_stock_dict = {}

def sync_stock_dict():
    global global_stock_dict
    print("🔄 [雷達] 啟動 FinMind 備用頻道，繞過證交所封鎖網...")
    try:
        # 改用對雲端主機友善的 FinMind API
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, timeout=15, verify=False)
        data = res.json()
        
        if data.get("msg") == "success":
            for item in data.get("data", []):
                stock_name = item.get("stock_name", "").strip()
                stock_id = item.get("stock_id", "").strip()
                # 排除空白並寫入字典
                if stock_name and stock_id:
                    global_stock_dict[stock_name] = stock_id
                    
            print(f"✅ [雷達] 突破封鎖！成功從備用頻道武裝 {len(global_stock_dict)} 檔標的。")
        else:
            print("⚠️ [雷達] 備用頻道資料異常")
    except Exception as e:
        print(f"⚠️ [雷達] 備用頻道連線失敗: {e}")

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
# 🧠 4. 智慧過濾與 Flex 被動回覆
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
        print(f"🎯 [雷達截獲] 群組有人正在查詢：{stock_query}") 
        
        success = False
        attempts = 0
        max_attempts = len(gemini_keys)
        ai_reply = ""

        # 🔄 啟動智慧彈匣：如果失敗，自動切換下一把金鑰重試
        while attempts < max_attempts:
            current_key = next(key_cycle)
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            sys_prompt = "你是一個台股助理，請用最簡短的白話文，分析這檔股票近期的市場概況。嚴禁長篇大論。"
            
            try:
                response = model.generate_content([sys_prompt, f"股友詢問：{stock_query}"])
                ai_reply = response.text.strip()
                success = True
                break  # 🎯 成功取得戰報，跳出重試迴圈
                
            except Exception as e:
                error_str = str(e).lower()
                # 偵測到 429 或是 quota 額度耗盡錯誤
                if "429" in error_str or "quota" in error_str:
                    print(f"⚠️ [彈匣警告] 某把 API 金鑰額度耗盡，自動切換下一把...")
                    attempts += 1
                else:
                    print(f"⚠️ [大腦異常] 非額度問題: {e}")
                    break # 其他嚴重錯誤，直接放棄

        # 判斷戰果並發射卡片
        if success:
            # 🎨 建立 Flex Message 變形卡片
            flex_content = {
                "type": "bubble",
                "styles": {
                    "header": {"backgroundColor": "#1A365D"}, # 深藍色裝甲
                    "body": {"backgroundColor": "#F7FAFC"}    # 乾淨灰白底
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

            # 🔘 建立快速回覆按鈕 (Quick Reply)
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="📈 大盤", text="大盤")),
                QuickReplyButton(action=MessageAction(label="🔥 台積電", text="2330")),
                QuickReplyButton(action=MessageAction(label="🚢 長榮", text="2603"))
            ])
            
            # 🚀 發射
            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content, quick_reply=quick_reply)
            )
        else:
            # 所有的鑰匙都試過了，全部乾涸
            line_bot_api.reply_message(
                event.reply_token, 
                TextSendMessage(text="⚠️ 報告統帥：所有 AI 金鑰彈匣均已打空，請擴充保險箱或等待明日配額恢復！")
            )

if __name__ == "__main__":
    # 啟動前先同步字典
    sync_stock_dict()
    print("🎧 前線偵察兵已上線，正在監聽群組動靜...")
    app.run(port=5000)
