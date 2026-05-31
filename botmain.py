# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, ImageSendMessage
)
from google import genai
import requests
import os
import re
import itertools
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg') # 🚀 無頭模式 (伺服器專用，不跳出視窗)
import mplfinance as mpf

app = Flask(__name__)

# ==========================================================
# 🔑 1. 金鑰設定與輪轉彈匣
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY') # 🌟 切換為 ImgBB 圖床金鑰

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
# 📚 2. 台股標的庫 
# ==========================================================
global_stock_dict = {}
def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0: return global_stock_dict
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        l_res = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=10, verify=False)
        if l_res.status_code == 200:
            for item in l_res.json(): global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
        o_res = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", headers=headers, timeout=10, verify=False)
        if o_res.status_code == 200:
            for item in o_res.json(): global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
    except: pass
    if len(global_stock_dict) == 0:
        try:
            url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
            res = requests.get(url, timeout=10, verify=False).json()
            if res.get("msg") == "success":
                for item in res.get("data", []):
                    if item.get("stock_name") and item.get("stock_id"):
                        global_stock_dict[item.get("stock_name").strip()] = item.get("stock_id").strip()
        except: pass
    return global_stock_dict

# ==========================================================
# 📊 3. 戰場即時數據 (文字版)
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        if stock_code == "^TWII":
            url = "https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()
        else:
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
        if len(valid_closes) < 20: return "⚠️ 歷史數據不足。"
        ma5 = round(sum(valid_closes[-5:]) / 5, 2)
        ma10 = round(sum(valid_closes[-10:]) / 10, 2)
        ma20 = round(sum(valid_closes[-20:]) / 20, 2)
        return f"最新報價 {round(valid_closes[-1], 2)}，成交量 {int(valid_vols[-1] / 1000)}。5MA={ma5}，10MA={ma10}，20MA={ma20}。"
    except: return "⚠️ 雷達連線受阻。"

# ==========================================================
# 💥 4. 【重裝火力】K線圖繪製與 ImgBB 空投引擎
# ==========================================================
def generate_and_upload_kline(stock_code):
    if not IMGBB_API_KEY:
        return None
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        suffix = "" if stock_code == "^TWII" else ".TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}{suffix}?range=3mo&interval=1d"
        res = requests.get(url, headers=headers, timeout=5).json()
        
        if not res.get('chart', {}).get('result') and stock_code != "^TWII":
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range=3mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5).json()
            
        result = res['chart']['result'][0]
        timestamps = result['timestamp']
        quote = result['indicators']['quote'][0]
        
        # 轉換成 mplfinance 規定的 Pandas 格式
        df = pd.DataFrame({
            'Date': pd.to_datetime(timestamps, unit='s'),
            'Open': quote['open'],
            'High': quote['high'],
            'Low': quote['low'],
            'Close': quote['close'],
            'Volume': quote['volume']
        })
        df.set_index('Date', inplace=True)
        df.dropna(inplace=True)
        
        # 在記憶體中作圖 
        buf = io.BytesIO()
        mc = mpf.make_marketcolors(up='r', down='g', inherit=True) 
        s  = mpf.make_mpf_style(marketcolors=mc, gridstyle=':')
        mpf.plot(df, type='candle', style=s, volume=True, 
                 mav=(5, 10, 20), title=f"Stock {stock_code} (3 Months)", 
                 savefig=dict(fname=buf, dpi=120, bbox_inches='tight'))
        buf.seek(0)
        
        # 🚀 發射至 ImgBB 取得公開網址 (使用 Base64 編碼上傳更穩定)
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        img_url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": img_b64
        }
        
        upload_res = requests.post(img_url, data=payload, timeout=15)
        
        if upload_res.status_code == 200:
            return upload_res.json()['data']['url'] # ImgBB 網址欄位是 url
        return None
    except Exception as e:
        print(f"繪圖引擎故障: {e}")
        return None

# ==========================================================
# 📡 5. Webhook 與過濾中樞
# ==========================================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_msg = event.message.text.strip()
        analysis_type = "綜合"
        
        if user_msg == "大盤": analysis_type = "大盤"
        elif "K線圖" in user_msg: analysis_type, user_msg = "K線圖", user_msg.replace("K線圖", "").strip()
        elif "技術面" in user_msg: analysis_type, user_msg = "技術面", user_msg.replace("技術面", "").strip()
        elif "籌碼面" in user_msg: analysis_type, user_msg = "籌碼面", user_msg.replace("籌碼面", "").strip()
        elif "基本面" in user_msg: analysis_type, user_msg = "基本面", user_msg.replace("基本面", "").strip()
        elif "題材面" in user_msg: analysis_type, user_msg = "題材面", user_msg.replace("題材面", "").strip()
        elif "同族群" in user_msg: analysis_type, user_msg = "同族群", user_msg.replace("同族群", "").strip()

        if len(user_msg) > 15: return
        is_stock_query = False
        stock_query = ""
        stock_code = ""

        if analysis_type == "大盤" or user_msg == "大盤":
            is_stock_query = True
            stock_query = "加權指數 (大盤)"
            stock_code = "^TWII"
        elif re.fullmatch(r'\d{4,6}', user_msg):
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
                choices = "\n".join([f"• {n} ({c})" for n, c in sorted(matches.items(), key=lambda x: len(x[0]))[:10]])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📍 找到多筆資料，請確認：\n{choices}"))
                return
            else:
                if "查詢" in user_msg or len(user_msg) >= 2:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠️ 找不到符合「{user_msg}」的標的。"))
                return

        if is_stock_query:
            # 💥 獨立處理 K 線圖空投任務
            if analysis_type == "K線圖":
                img_url = generate_and_upload_kline(stock_code)
                if img_url:
                    line_bot_api.reply_message(event.reply_token, ImageSendMessage(original_content_url=img_url, preview_image_url=img_url))
                else:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 報告統帥：K線圖空投失敗 (請確認 ImgBB 金鑰是否安裝正確)"))
                return

            real_data = fetch_realtime_data(stock_code)
            success = False
            attempts = 0
            max_attempts = len(gemini_keys) if gemini_keys else 1
            ai_reply = ""
            card_title = "🎯 綜合戰術推演"

            while attempts < max_attempts and gemini_keys:
                current_key = next(key_cycle)
                try:
                    client = genai.Client(api_key=current_key)
                    
                    if analysis_type == "大盤":
                        prompt = f"你是台股操盤手。根據數據【{real_data}】分析大盤。150字內：1.多空趨勢 2.支撐壓力 3.戰略建議。無免責聲明。"
                        card_title = "📉 大盤多空雷達"
                    elif analysis_type == "技術面":
                        prompt = f"你是台股操盤手。根據數據【{real_data}】分析【{stock_query}】技術面。150字內：1.均線乖離 2.支撐壓力 3.觀察重點。無免責聲明。"
                        card_title = "📈 技術面深度解析"
                    elif analysis_type == "籌碼面":
                        prompt = f"你是台股操盤手。根據數據【{real_data}】分析【{stock_query}】籌碼面。150字內：1.大戶意圖 2.散戶心理 3.觀察重點。無免責聲明。"
                        card_title = "🕵️ 籌碼面深度解析"
                    elif analysis_type == "基本面":
                        prompt = f"你是台股分析師。分析【{stock_query}】基本面。150字內：1.核心業務 2.產業地位 3.長線價值。無免責聲明。"
                        card_title = "🏢 基本面價值分析"
                    elif analysis_type == "題材面":
                        prompt = f"你是台股操盤手。分析【{stock_query}】市場題材。150字內：1.強勢概念分類 2.近期利多動能 3.資金關注度。無免責聲明。"
                        card_title = "🔥 題材面動能解析"
                    elif analysis_type == "同族群":
                        prompt = f"你是台股操盤手。尋找【{stock_query}】同族群。150字內：1.列出3~5檔戰友(含代號) 2.族群產業趨勢。無免責聲明。"
                        card_title = "🤝 同族群戰友雷達"
                    else:
                        prompt = f"你是台股操盤手。根據數據【{real_data}】分析【{stock_query}】。150字內：1.均線趨勢 2.籌碼推測 3.關鍵防守。無免責聲明。"
                        card_title = "🎯 綜合戰術推演"

                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if not response.text: raise ValueError("空白")
                    ai_reply = response.text.strip()
                    success = True
                    break 
                except Exception as e:
                    attempts += 1

            if success:
                footer_contents = []
                if analysis_type == "大盤":
                    footer_contents = [
                        {
                            "type": "box", "layout": "horizontal", "spacing": "sm",
                            "contents": [
                                {"type": "button", "style": "primary", "color": "#1E3A8A", "height": "sm", "action": {"type": "message", "label": "📊 K線", "text": "K線圖 大盤"}},
                                {"type": "button", "style": "primary", "color": "#1E3A8A", "height": "sm", "action": {"type": "message", "label": "台積電", "text": "2330"}}
                            ]
                        }
                    ]
                else:
                    def get_color(t): return "#2563EB" if analysis_type == t else "#475569"
                    def create_btn(lbl, t, cmd): return {"type": "button", "style": "primary", "color": get_color(t), "height": "sm", "action": {"type": "message", "label": lbl, "text": cmd}}
                    
                    row1 = {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "contents": [
                            create_btn("技術", "技術面", f"技術面 {stock_code}"),
                            create_btn("籌碼", "籌碼面", f"籌碼面 {stock_code}"),
                            create_btn("基本", "基本面", f"基本面 {stock_code}")
                        ]
                    }
                    row2 = {
                        "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "md",
                        "contents": [
                            create_btn("題材", "題材面", f"題材面 {stock_code}"),
                            create_btn("族群", "同族群", f"同族群 {stock_code}"),
                            {"type": "button", "style": "primary", "color": "#334155", "height": "sm", "action": {"type": "message", "label": "大盤", "text": "大盤"}}
                        ]
                    }
                    
                    # 獨立放置 📊 K線 按鈕，佔滿全寬，氣勢更強，避免跟小按鈕擠在一起
                    row3 = {
                        "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "md",
                        "contents": [
                            {"type": "button", "style": "primary", "color": "#B91C1C", "height": "sm", "action": {"type": "message", "label": "📊 呼叫 K線圖", "text": f"K線圖 {stock_code}"}}
                        ]
                    }
                    footer_contents = [row1, row2, row3]

                flex_content = {
                    "type": "bubble",
                    "styles": {"header": {"backgroundColor": "#1A365D"}, "body": {"backgroundColor": "#F7FAFC"}, "footer": {"backgroundColor": "#0F172A"}},
                    "header": {
                        "type": "box", "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": card_title, "color": "#D69E2E", "weight": "bold", "size": "sm"},
                            {"type": "text", "text": stock_query, "color": "#FFFFFF", "weight": "bold", "size": "xl", "margin": "md"}
                        ]
                    },
                    "body": {
                        "type": "box", "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": f"📊 雷達數據：\n{real_data}", "color": "#1A365D", "size": "xs", "weight": "bold", "wrap": True},
                            {"type": "separator", "margin": "md"},
                            {"type": "text", "text": ai_reply, "color": "#2D3748", "wrap": True, "size": "sm", "margin": "md"}
                        ]
                    },
                    "footer": {"type": "box", "layout": "vertical", "paddingAll": "md", "contents": footer_contents}
                }
                line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 報告統帥：AI 金鑰連線異常，或觸發金融防護限制！"))
    
    except Exception as e:
        print(f"致命錯誤: {e}")
        try: line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 系統發生不明錯誤，請稍後再試！"))
        except: pass

if __name__ == "__main__":
    app.run(port=5000)
