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
matplotlib.use('Agg')
import mplfinance as mpf

app = Flask(__name__)

# ==========================================================
# 🔑 1. 金鑰設定與輪轉彈匣
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY') 

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
# 📊 3. 雙雷達情報中樞 (TWSE 即時偷價 + Yahoo 均線備援)
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0"}
    yahoo_ma = ""
    yahoo_price = ""
    
    # [第一階段] 取得 Yahoo 宏觀均線數據
    try:
        if stock_code == "^TWII":
            url = "https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5).json()
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TW?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5).json()
            if not res.get('chart', {}).get('result'):
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range=2mo&interval=1d"
                res = requests.get(url, headers=headers, timeout=5).json()

        result = res['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        volumes = result['indicators']['quote'][0]['volume']
        valid_closes = [c for c in closes if c is not None]
        valid_vols = [v for v in volumes if v is not None]
        
        if len(valid_closes) >= 20:
            ma5 = round(sum(valid_closes[-5:]) / 5, 2)
            ma10 = round(sum(valid_closes[-10:]) / 10, 2)
            ma20 = round(sum(valid_closes[-20:]) / 20, 2)
            yahoo_ma = f"5MA={ma5}, 10MA={ma10}, 20MA={ma20}"
            yahoo_price = f"報價:{round(valid_closes[-1], 2)} 量:{int(valid_vols[-1] / 1000)}"
        else:
            yahoo_ma = "均線不足"
    except:
        yahoo_ma = "連線受阻"

    if stock_code == "^TWII":
        return f"大盤備援數據 | {yahoo_price}。{yahoo_ma}"

    # [第二階段] 派出游擊隊潛入證交所偷取「絕對即時微觀數據」
    try:
        req = requests.Session()
        # 先打招呼拿通行證
        req.get('https://mis.twse.com.tw/stock/index.jsp', headers=headers, timeout=3)
        
        twse_data = None
        for market in ['tse', 'otc']:
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{stock_code}.tw"
            res = req.get(url, timeout=3).json()
            if res.get('msgArray'):
                data = res['msgArray'][0]
                z = data.get('z', '-') # 最新成交價
                if z == '-': z = data.get('y', '-') # 若無交易或盤前，用昨收取代
                h = data.get('h', '-')
                l = data.get('l', '-')
                o = data.get('o', '-')
                v = data.get('v', '-')
                twse_data = f"🔴證交所即時 最新:{z} (開:{o} 高:{h} 低:{l} 量:{v})"
                break
                
        if twse_data:
            return f"{twse_data}\n📊Yahoo{yahoo_ma}"
        else:
            return f"⚠️游擊隊失聯(備援啟動) | {yahoo_price}。{yahoo_ma}"
    except:
        return f"⚠️游擊隊失聯(備援啟動) | {yahoo_price}。{yahoo_ma}"

# ==========================================================
# 💥 4. K線圖繪製與 ImgBB 空投引擎 (夜間塗裝版)
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
        
        buf = io.BytesIO()
        mc = mpf.make_marketcolors(up='#ef4444', down='#22c55e', edge='inherit', wick='inherit', volume='inherit')
        s = mpf.make_mpf_style(
            marketcolors=mc, facecolor='#020617', figcolor='#0f172a', gridcolor='#1e293b', gridstyle='--',
            rc={'text.color': '#f8fafc', 'axes.labelcolor': '#f8fafc', 'xtick.color': '#94a3b8', 'ytick.color': '#94a3b8', 'axes.edgecolor': '#334155'}
        )
        
        title_str = "Index ^TWII" if stock_code == "^TWII" else f"Stock {stock_code}"
        mpf.plot(df, type='candle', style=s, volume=True, mav=(5, 10, 20), title=f"{title_str} (3 Months)", savefig=dict(fname=buf, dpi=150, bbox_inches='tight', facecolor='#0f172a'))
        buf.seek(0)
        
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        img_url = "https://api.imgbb.com/1/upload"
        payload = {"key": IMGBB_API_KEY, "image": img_b64}
        
        upload_res = requests.post(img_url, data=payload, timeout=15)
        if upload_res.status_code == 200:
            return upload_res.json()['data']['url']
        return None
    except Exception as e:
        return None

# ==========================================================
# 📡 5. Webhook 與過濾中樞 (實戰劇本模組啟動)
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
        
        # 🌟 攔截新指令：劇本
        if user_msg == "大盤": analysis_type = "大盤"
        elif "K線圖" in user_msg: analysis_type, user_msg = "K線圖", user_msg.replace("K線圖", "").strip()
        elif "劇本" in user_msg or "實戰劇本" in user_msg: analysis_type, user_msg = "劇本", user_msg.replace("實戰劇本", "").replace("劇本", "").strip()
        elif "技術面" in user_msg: analysis_type, user_msg = "技術面", user_msg.replace("技術面", "").strip()
        elif "籌碼面" in user_msg: analysis_type, user_msg = "籌碼面", user_msg.replace("籌碼面", "").strip()
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
                    elif analysis_type == "題材面":
                        prompt = f"你是台股操盤手。分析【{stock_query}】市場題材。150字內：1.強勢概念分類 2.近期利多動能 3.資金關注度。無免責聲明。"
                        card_title = "🔥 題材面動能解析"
                    elif analysis_type == "同族群":
                        prompt = f"你是台股操盤手。尋找【{stock_query}】同族群。150字內：1.列出3~5檔戰友(含代號) 2.族群產業趨勢。無免責聲明。"
                        card_title = "🤝 同族群戰友雷達"
                    elif analysis_type == "劇本":
                        # 🌟 專為統帥量身打造的劇本提示詞 (植入扣抵與大戶心理觀念)
                        prompt = f"你是台股操盤手。請利用均線扣抵觀念與主力籌碼心理，根據即時數據【{real_data}】推演【{stock_query}】實戰劇本。150字內給出具體價位：1.🔥向上突破追擊條件與壓力點 2.🛡️拉回低接防守支撐點 3.☠️跌破停損撤退底線。無免責聲明。"
                        card_title = "📝 實戰劇本推演"
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
                    
                    # 🌟 將第一排的「基本」替換成高價值的「📝劇本」
                    row1 = {
                        "type": "box", "layout": "horizontal", "spacing": "sm",
                        "contents": [
                            create_btn("技術", "技術面", f"技術面 {stock_code}"),
                            create_btn("籌碼", "籌碼面", f"籌碼面 {stock_code}"),
                            create_btn("📝劇本", "劇本", f"劇本 {stock_code}")
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
