# -*- coding: utf-8 -*-
# ==========================================================
# 🎧 股海觀浪前線偵察兵：bot.py (負責 24 小時免費接收與回覆)
# ==========================================================
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import google.generativeai as genai

app = Flask(__name__)

# ==========================================================
# 🔑 1. 填寫您的通行證 (請填入您現有的金鑰)
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = 'SMvkBhzw64RpFhLGsaDRfzqPVPkxAk8HYLz+Pvy/kiVG/n3XkSNWOcPPyQkSpWrCcAj3+SmAaM1iopF9dz6TJdo6xyQwBv0soAzdn+Wdn3GC2YS+4m16cEzIW5pUTqO12JC6grdw6ktZ4wh3arR5+gdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '9d160bd7696bc116bead171fffc7ddb7' # 在 LINE Developer 後台的 Basic settings 裡
GEMINI_API_KEY = 'AIzaSyDGpHCEWUlWNcWPG6Td8tBzjPVz-n8erzQ'

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 設定 Gemini 大腦
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================================
# 📡 2. 建立 Webhook 接收通道 (LINE 官方敲門的入口)
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
# 🧠 3. 被動回覆核心邏輯 (🌟 這裡用 reply_message，完全免費無上限！)
# ==========================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text

    # 🛡️ 戰術過濾：避免機器人吵死人，規定要在群組輸入「/查詢 股票代號」才回覆
    if user_msg.startswith("/查詢"):
        stock_query = user_msg.replace("/查詢", "").strip()
        
        try:
            # 呼叫 Gemini 進行即時解析
            sys_prompt = "你是一個台股助理，請用最簡短的白話文，分析這檔股票近期的市場概況。嚴禁長篇大論。"
            response = model.generate_content([sys_prompt, f"股友詢問：{stock_query}"])
            ai_reply = response.text.strip()
            
            # 🚀 發射被動回覆 (不扣 LINE 的 200 則額度！)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"🤖 偵察兵回報【{stock_query}】：\n{ai_reply}")
            )
        except Exception as e:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 偵察兵大腦連線異常，請稍後再試。")
            )

if __name__ == "__main__":
    # 啟動微型伺服器，監聽 5000 port
    print("🎧 前線偵察兵已上線，正在監聽群組動靜...")
    app.run(port=5000)