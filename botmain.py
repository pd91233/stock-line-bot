# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
)
from google import genai
import requests
import os
import re
import itertools
import io
import base64
import datetime
import threading
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import mplfinance as mpf

app = Flask(__name__)

# ==========================================================
# 🔑 1. API 金鑰與通訊參數設定
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY') 

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

gemini_keys = []
if os.environ.get('GEMINI_API_KEY'): gemini_keys.append(os.environ.get('GEMINI_API_KEY'))
for i in range(1, 6):
    k = os.environ.get(f'GEMINI_API_KEY_{i}')
    if k: gemini_keys.append(k)
if gemini_keys: key_cycle = itertools.cycle(gemini_keys)

# ==========================================================
# 📚 2. 台股資料庫 (輕量化防爆模組)
# ==========================================================
global_stock_dict = {}
def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0: return global_stock_dict
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, headers=headers, timeout=3, verify=False).json()
        if res.get("msg") == "success":
            for item in res.get("data", []):
                name = item.get("stock_name")
                sid = item.get("stock_id")
                if name and sid and len(sid) <= 4: 
                    global_stock_dict[name.strip()] = sid.strip()
    except: pass
        
    if len(global_stock_dict) == 0:
        global_stock_dict = {"台積電": "2330", "鴻海": "2317", "聯發科": "2454", "廣達": "2382", "長榮": "2603"}
    return global_stock_dict

threading.Thread(target=get_stock_dict).start()

# ==========================================================
# 📊 3. 雙通道市場行情分析中心
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0"}
    yahoo_ma = ""; yahoo_price = ""
    try:
        if stock_code == "^TWII":
            url = "https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=2mo&interval=1d"
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TW?range=2mo&interval=1d"
        res = requests.get(url, headers=headers, timeout=2).json()
        if not res.get('chart', {}).get('result') and stock_code != "^TWII":
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=2).json()

        result = res['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        volumes = result['indicators']['quote'][0]['volume']
        valid_closes = [c for c in closes if c is not None]
        valid_vols = [v for v in volumes if v is not None]
        
        if len(valid_closes) >= 20:
            ma5 = round(sum(valid_closes[-5:]) / 5, 2)
            ma10 = round(sum(valid_closes[-10:]) / 10, 2)
            ma20 = round(sum(valid_closes[-20:]) / 20, 2)
            kd5 = round(valid_closes[-5], 2); kd10 = round(valid_closes[-10], 2); kd20 = round(valid_closes[-20], 2)
            vol_5ma = sum(valid_vols[-5:]) / 5; curr_vol = valid_vols[-1]
            if curr_vol > vol_5ma * 1.5: big_player = "🔥大戶放量攻擊"
            elif curr_vol < vol_5ma * 0.7: big_player = "🧊量縮散戶觀望"
            else: big_player = "⚖️籌碼動能平穩"
            yahoo_ma = f"均線數值(5/10/20): {ma5}, {ma10}, {ma20}\n扣抵價位: {kd5}, {kd10}, {kd20}\n籌碼動向: {big_player}"
            yahoo_price = f"最新收盤:{round(valid_closes[-1], 2)} 成交量:{int(valid_vols[-1] / 1000)}張"
        else: yahoo_ma = "均線資料庫不足"
    except: yahoo_ma = "備援線路連線受阻"

    if stock_code == "^TWII": return f"大盤歷史備援數據 | {yahoo_price}。\n{yahoo_ma}"

    try:
        req = requests.Session(); req.get('https://mis.twse.com.tw/stock/index.jsp', headers=headers, timeout=1) 
        twse_data = None
        for market in ['tse', 'otc']:
            try:
                url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{stock_code}.tw"
                res = req.get(url, timeout=1).json() 
                if res.get('msgArray'):
                    data = res['msgArray'][0]; z = data.get('z', '-')
                    if z == '-': z = data.get('y', '-') 
                    h = data.get('h', '-'); l = data.get('l', '-'); v = data.get('v', '-')
                    twse_data = f"🔴交易所即時成交價:{z} (今日最高:{h} 今日最低:{l} 即時個股量:{v}張)"
                    break
            except: continue 
        if twse_data: return f"{twse_data}\n📊{yahoo_ma}"
        else: return f"⚠️盤中即時報價受阻 | {yahoo_price}\n📊{yahoo_ma}"
    except: return f"⚠️盤中即時報價受阻 | {yahoo_price}\n📊{yahoo_ma}"

# ==========================================================
# 💥 4. 技術圖表（多維度K線圖）生成中心
# ==========================================================
def generate_and_upload_kline(stock_code, period="3月"):
    if not IMGBB_API_KEY: return None
    period_map = {"1日": ("1d", "5m"), "5日": ("5d", "15m"), "1月": ("1mo", "1d"), "3月": ("3mo", "1d"), "6月": ("6mo", "1d"), "1年": ("1y", "1wk"), "5年": ("5y", "1mo")}
    if period not in period_map: period = "3月"
    rng, intv = period_map[period]
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        suffix = "" if stock_code == "^TWII" else ".TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}{suffix}?range={rng}&interval={intv}"
        res = requests.get(url, headers=headers, timeout=5).json()
        if not res.get('chart', {}).get('result') and stock_code != "^TWII":
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range={rng}&interval={intv}"
            res = requests.get(url, headers=headers, timeout=5).json()
            
        result = res['chart']['result'][0]; timestamps = result['timestamp']; quote = result['indicators']['quote'][0]
        df = pd.DataFrame({'Date': pd.to_datetime(timestamps, unit='s') + pd.Timedelta(hours=8), 'Open': quote['open'], 'High': quote['high'], 'Low': quote['low'], 'Close': quote['close'], 'Volume': quote['volume']})
        df.set_index('Date', inplace=True); df.dropna(inplace=True)
        
        mav_setting = None if period in ["1日", "5日"] else (5, 10, 20)
        buf = io.BytesIO()
        mc = mpf.make_marketcolors(up='#ef4444', down='#22c55e', edge='inherit', wick='inherit', volume='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, facecolor='#020617', figcolor='#0f172a', gridcolor='#1e293b', gridstyle='--', rc={'text.color': '#f8fafc', 'axes.labelcolor': '#f8fafc', 'xtick.color': '#94a3b8', 'ytick.color': '#94a3b8', 'axes.edgecolor': '#334155'})
        
        title_str = "Index ^TWII" if stock_code == "^TWII" else f"Stock {stock_code}"
        if mav_setting: mpf.plot(df, type='candle', style=s, volume=True, mav=mav_setting, title=f"{title_str} ({period})", savefig=dict(fname=buf, dpi=150, bbox_inches='tight', facecolor='#0f172a'))
        else: mpf.plot(df, type='candle', style=s, volume=True, title=f"{title_str} ({period})", savefig=dict(fname=buf, dpi=150, bbox_inches='tight', facecolor='#0f172a'))
            
        buf.seek(0)
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        upload_res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY, "image": img_b64}, timeout=15)
        if upload_res.status_code == 200: return upload_res.json()['data']['url']
        return None
    except: return None

# ==========================================================
# 💥 5. 背景非同步交易運算中心 (Push 推送機制)
# ==========================================================
def background_async_task(user_id, user_msg, analysis_type, period_arg):
    try:
        is_stock_query = False; stock_query = ""; stock_code = ""

        if analysis_type == "大盤" or user_msg == "大盤":
            is_stock_query = True; stock_query = "加權指數 (大盤)"; stock_code = "^TWII"
        elif re.fullmatch(r'\d{4,6}', user_msg):
            is_stock_query = True; stock_query = user_msg; stock_code = user_msg
        else:
            stock_dict = get_stock_dict()
            matches = {n: c for n, c in stock_dict.items() if user_msg in n}
            if len(matches) == 1:
                name = list(matches.keys())[0]; stock_code = list(matches.values())[0]
                is_stock_query = True; stock_query = f"{name} ({stock_code})"
            elif len(matches) > 1:
                choices = "\n".join([f"• {n} ({c})" for n, c in sorted(matches.items(), key=lambda x: len(x[0]))[:10]])
                line_bot_api.push_message(user_id, TextSendMessage(text=f"📍 找到多筆符合名稱，請確認輸入：\n{choices}"))
                return
            else:
                try:
                    current_key = next(key_cycle)
                    client = genai.Client(api_key=current_key)
                    prompt = f"你是資深證券分析師，請以專業、果斷的操盤手口吻精簡回應這句話，100字內：{user_msg}"
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if response.text: line_bot_api.push_message(user_id, TextSendMessage(text=response.text.strip()))
                except: pass
                return

        if is_stock_query:
            if analysis_type == "K線圖":
                img_url = generate_and_upload_kline(stock_code, period_arg)
                if img_url: 
                    quick_reply_btns = QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="🕐 1日分時線", text=f"K線圖 {stock_code} 1日")),
                        QuickReplyButton(action=MessageAction(label="🕒 5日線", text=f"K線圖 {stock_code} 5日")),
                        QuickReplyButton(action=MessageAction(label="📅 1個月日K", text=f"K線圖 {stock_code} 1月")),
                        QuickReplyButton(action=MessageAction(label="📅 6個月日K", text=f"K線圖 {stock_code} 6月")),
                        QuickReplyButton(action=MessageAction(label="📆 1年週K線", text=f"K線圖 {stock_code} 1年")),
                        QuickReplyButton(action=MessageAction(label="🗺️ 5年月K線", text=f"K線圖 {stock_code} 5年"))
                    ])
                    line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=img_url, preview_image_url=img_url, quick_reply=quick_reply_btns))
                else: line_bot_api.push_message(user_id, TextSendMessage(text="⚠️ 技術圖表繪製線路異常"))
                return

            real_data = fetch_realtime_data(stock_code)
            success = False; attempts = 0; max_attempts = len(gemini_keys) if gemini_keys else 1
            ai_reply = ""

            while attempts < max_attempts and gemini_keys:
                current_key = next(key_cycle)
                try:
                    client = genai.Client(api_key=current_key)
                    base_prompt = "你是專業台股操盤手，請以直接、果斷的市場交易術語下達具體點位指令。嚴禁輸出任何內部思考思維或冗贅廢話。"
                    if analysis_type == "大盤": prompt = f"{base_prompt}根據盤勢數據【{real_data}】進行加權指數多空評估。150字內包含：1.多空波段趨勢 2.關鍵支撐與壓力區間 3.交易部位控管策略建議。無須任何免責聲明。"
                    elif analysis_type == "技術面": prompt = f"{base_prompt}根據技術數據【{real_data}】分析【{stock_query}】技術面。150字內包含：1.均線扣抵位置預判 2.短線多空臨界點 3.明確指示。無須任何免責聲明。"
                    elif analysis_type == "籌碼面": prompt = f"{base_prompt}根據量能數據【{real_data}】分析【{stock_query}】籌碼面。150字內包含：1.大戶資金進出意圖 2.市場散戶心理狀態評估 3.明確跟單跟隨指示。無須任何免責聲明。"
                    elif analysis_type == "劇本": prompt = f"{base_prompt}根據最新即時成交價、均線排列、扣抵位置與成交量能數據【{real_data}】，為【{stock_query}】制定下一步明確交易決策。150字內給出：1.🎯明確行動指令(例：現價買進進場/空手觀望/逢高分批獲利入袋/跌破防守線確實停損) 2.🔥上攻突破追擊點位 3.🛡️拉回低接防守支撐點位。必須給出絕對數字價位。無須任何免責聲明。"
                    else: prompt = f"{base_prompt}根據報價數據【{real_data}】分析【{stock_query}】。150字內給出：1.均線趨勢方向 2.主力持股動向推測 3.關鍵支撐防守價位。無須任何免責聲明。"

                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if response.text: ai_reply = response.text.strip(); success = True; break 
                except: attempts += 1

            if success:
                def get_color(t): return "🔵" if analysis_type == t else "⚪"
                header_text = f"📊 【市場全景分析・個股盤勢診斷】\n🎯 追蹤標的：{stock_query}\n\n{real_data}\n====================\n{ai_reply}"
                
                # 下方附隨即時功能鍵
                row_btns = QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label=f"{get_color('技術面')}技術分析預判", text=f"技術面 {stock_code}")),
                    QuickReplyButton(action=MessageAction(label=f"{get_color('籌碼面')}籌碼資金追蹤", text=f"籌碼面 {stock_code}")),
                    QuickReplyButton(action=MessageAction(label=f"{get_color('劇本')}絕對行動決策指示", text=f"劇本 {stock_code}")),
                    QuickReplyButton(action=MessageAction(label="📊 呼叫 K線圖", text=f"K線圖 {stock_code}"))
                ])
                line_bot_api.push_message(user_id, TextSendMessage(text=header_text, quick_reply=row_btns))
    except: pass

# ==========================================================
# 📡 6. Webhook 通道 (純文字秒回防線)
# ==========================================================
@app.route("/", methods=['GET'])
def home(): return "前線看盤伺服器：交易連線狀態正常，常駐清醒中！"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']; body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_msg = event.message.text.strip()
        user_id = event.source.user_id
        
        # 👑 【精準突圍：最新選股戰報一鍵速回超連結】
        if user_msg in ["最新戰報", "調閱戰報", "戰報"]:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            report_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html?v={timestamp}"
            
            broadcast_text = f"📊 【策略選股大師・當日最新特報】\n========================\n主控台已將本日最新核心選股策略網頁歸檔至雲端補給線！\n\n🔗 點擊解鎖本日最新網頁戰報 (跳出獨立瀏覽器新視窗)：\n{report_url}"
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=broadcast_text))
            return

        # 基礎個股查詢，第一擊搶先秒回，封鎖斷線風險
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🛰️ 系統已鎖定標的，正全速連線市場報價，請稍候..."))

        analysis_type = "綜合"; period_arg = "3月"
        if "K線圖" in user_msg: 
            analysis_type = "K線圖"; user_msg = user_msg.replace("K線圖", "").strip()
            for p in ["1日", "5日", "1月", "3月", "6月", "1年", "5年"]:
                if p in user_msg: period_arg = p; user_msg = user_msg.replace(p, "").strip()
        elif user_msg == "大盤": analysis_type = "大盤"
        elif "劇本" in user_msg or "實戰劇本" in user_msg: analysis_type, user_msg = "劇本", user_msg.replace("實戰劇本", "").replace("劇本", "").strip()
        elif "技術面" in user_msg: analysis_type, user_msg = "技術面", user_msg.replace("技術面", "").strip()
        elif "籌碼面" in user_msg: analysis_type, user_msg = "籌碼面", user_msg.replace("籌碼面", "").strip()
        elif "題材面" in user_msg: analysis_type, user_msg = "題材面", user_msg.replace("題材面", "").strip()
        elif "同族群" in user_msg: analysis_type, user_msg = "同族群", user_msg.replace("同族群", "").strip()

        if len(user_msg) > 15: return
        threading.Thread(target=background_async_task, args=(user_id, user_msg, analysis_type, period_arg)).start()

    except: pass

# ==========================================================
# 💥 Gunicorn 免改網頁開機超時配置嵌入
# ==========================================================
class StandaloneApplication:
    def __init__(self, app, options=None): self.options = options or {}; self.application = app
    def run(self):
        import gunicorn.app.base
        class FlaskGunicornApp(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options): self.options = options; self.application = app; super().__init__()
            def load_config(self):
                for key, value in self.options.items(): self.cfg.set(key.lower(), value)
            def load(self): return self.application
        FlaskGunicornApp(self.application, self.options).run()

if __name__ == "__main__":
    options = {'bind': '0.0.0.0:10000', 'workers': 1, 'threads': 2, 'timeout': 120}
    StandaloneApplication(app, options).run()
