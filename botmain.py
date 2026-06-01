# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, ImageSendMessage,
    QuickReply, QuickReplyButton, MessageAction
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
# 🔑 1. 金鑰設定
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
# 📚 2. 台股標的庫 (🌟極致輕量化防爆裝甲版)
# ==========================================================
global_stock_dict = {}
def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0: return global_stock_dict
    
    # 💥 不在開機主線程下載超大JSON，改用FinMind輕量化接口，且縮短超時，防止卡死
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, headers=headers, timeout=3, verify=False).json()
        if res.get("msg") == "success":
            for item in res.get("data", []):
                name = item.get("stock_name")
                sid = item.get("stock_id")
                if name and sid and len(sid) <= 4: # 只抓核心四大碼股票，極大節省記憶體
                    global_stock_dict[name.strip()] = sid.strip()
    except:
        pass
        
    # 備援防線：萬一完全斷網，手工內建幾檔核心主力，確保基本運作不崩潰
    if len(global_stock_dict) == 0:
        global_stock_dict = {"台積電": "2330", "鴻海": "2317", "聯發科": "2454", "廣達": "2382", "長榮": "2603"}
    return global_stock_dict

# 🚀 背景非同步預載，不阻礙開機進程
threading.Thread(target=get_stock_dict).start()

# ==========================================================
# 📊 3. 雙雷達情報中樞
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
            yahoo_ma = f"均線(5/10/20): {ma5}, {ma10}, {ma20} | 扣抵價: {kd5}, {kd10}, {kd20} | 籌碼: {big_player}"
            yahoo_price = f"報價:{round(valid_closes[-1], 2)} 量:{int(valid_vols[-1] / 1000)}"
        else: yahoo_ma = "均線不足"
    except: yahoo_ma = "連線受阻"

    if stock_code == "^TWII": return f"大盤備援數據 | {yahoo_price}。\n{yahoo_ma}"

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
                    twse_data = f"🔴即時 最新:{z} (高:{h} 低:{l} 量:{v})"
                    break
            except: continue 
        if twse_data: return f"{twse_data}\n📊{yahoo_ma}"
        else: return f"⚠️游擊隊受阻 | {yahoo_price}\n📊{yahoo_ma}"
    except: return f"⚠️游擊隊受阻 | {yahoo_price}\n📊{yahoo_ma}"

# ==========================================================
# 💥 4. 多維度 K線圖繪製引擎
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
# 💥 5. 背景重裝重火力計算與推送艙
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
                line_bot_api.push_message(user_id, TextSendMessage(text=f"📍 找到多筆資料，請確認：\n{choices}"))
                return
            else:
                try:
                    current_key = next(key_cycle)
                    client = genai.Client(api_key=current_key)
                    prompt = f"你是台股操盤手，以果斷軍事口吻簡短回應這句話，100字內：{user_msg}"
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if response.text:
                        line_bot_api.push_message(user_id, TextSendMessage(text=response.text.strip()))
                except: pass
                return

        if is_stock_query:
            if analysis_type == "K線圖":
                img_url = generate_and_upload_kline(stock_code, period_arg)
                if img_url: 
                    quick_reply_btns = QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="🕐 1日分時", text=f"K線圖 {stock_code} 1日")),
                        QuickReplyButton(action=MessageAction(label="🕒 5日", text=f"K線圖 {stock_code} 5日")),
                        QuickReplyButton(action=MessageAction(label="📅 1個月", text=f"K線圖 {stock_code} 1月")),
                        QuickReplyButton(action=MessageAction(label="📅 6個月", text=f"K線圖 {stock_code} 6月")),
                        QuickReplyButton(action=MessageAction(label="📆 1年(週K)", text=f"K線圖 {stock_code} 1年")),
                        QuickReplyButton(action=MessageAction(label="🗺️ 5年(月K)", text=f"K線圖 {stock_code} 5年"))
                    ])
                    line_bot_api.push_message(user_id, ImageSendMessage(original_content_url=img_url, preview_image_url=img_url, quick_reply=quick_reply_btns))
                else: line_bot_api.push_message(user_id, TextSendMessage(text="⚠️ 報告統帥：K線圖空投失敗"))
                return

            real_data = fetch_realtime_data(stock_code)
            success = False; attempts = 0; max_attempts = len(gemini_keys) if gemini_keys else 1
            ai_reply = ""; card_title = "🎯 綜合戰術推演"

            while attempts < max_attempts and gemini_keys:
                current_key = next(key_cycle)
                try:
                    client = genai.Client(api_key=current_key)
                    base_prompt = "你是台股操盤手，以直接、果斷的軍事化口吻下達指令。絕不可輸出任何思考過程或廢話。"
                    if analysis_type == "大盤": prompt = f"{base_prompt}根據數據【{real_data}】分析大盤。150字內：1.多空趨勢 2.支撐壓力 3.行動建議(加碼/減碼/觀望)。無免責聲明。"; card_title = "📉 大盤多空雷達"
                    elif analysis_type == "技術面": prompt = f"{base_prompt}根據數據【{real_data}】分析【{stock_query}】技術面。150字內：1.扣抵預判 2.支撐壓力 3.明確指示。無免責聲明。"; card_title = "📈 技術面深度解析"
                    elif analysis_type == "籌碼面": prompt = f"{base_prompt}根據數據【{real_data}】分析【{stock_query}】籌碼面。150字內：1.大戶動能 2.散戶心理 3.明確跟單指示。無免責聲明。"; card_title = "🕵️ 籌碼面深度解析"
                    elif analysis_type == "劇本": 
                        prompt = f"{base_prompt}根據最新報價、均線、扣抵價與量能【{real_data}】，為【{stock_query}】制定作戰計畫。150字內給出：1. 🎯明確行動(例：現價進場/空手觀望/逢高停利/破線停損) 2. 🔥攻擊點位(過X元追擊) 3. 🛡️防守點位(破Y元撤退)。必須有絕對數字，不可含糊其辭。無免責聲明。"
                        card_title = "📝 絕對行動劇本"
                    else: prompt = f"{base_prompt}根據數據【{real_data}】分析【{stock_query}】。150字內：1.均線趨勢 2.籌碼推測 3.具體防守點。無免責聲明。"; card_title = "🎯 綜合戰術推演"

                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if not response.text: raise ValueError("空白")
                    ai_reply = response.text.strip(); success = True; break 
                except: attempts += 1

            if success:
                footer_contents = []
                if analysis_type == "大盤":
                    footer_contents = [{"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [{"type": "button", "style": "primary", "color": "#1E3A8A", "height": "sm", "action": {"type": "message", "label": "📊 K線", "text": "K線圖 大盤"}}, {"type": "button", "style": "primary", "color": "#1E3A8A", "height": "sm", "action": {"type": "message", "label": "台積電", "text": "2330"}}]}]
                else:
                    def get_color(t): return "#2563EB" if analysis_type == t else "#475569"
                    def create_btn(lbl, t, cmd): return {"type": "button", "style": "primary", "color": get_color(t), "height": "sm", "action": {"type": "message", "label": lbl, "text": cmd}}
                    row1 = {"type": "box", "layout": "horizontal", "spacing": "sm", "contents": [create_btn("技術", "技術面", f"技術面 {stock_code}"), create_btn("籌碼", "籌碼面", f"籌碼面 {stock_code}"), create_btn("🎯指示", "劇本", f"劇本 {stock_code}")]}
                    row2 = {"type": "box", "layout": "horizontal", "spacing": "sm", "margin": "md", "contents": [create_btn("題材", "題材面", f"題材面 {stock_code}"), create_btn("族群", "同族群", f"同族群 {stock_code}"), {"type": "button", "style": "primary", "color": "#334155", "height": "sm", "action": {"type": "message", "label": "大盤", "text": "大盤"}}]}
                    row3 = {"type": "box", "layout": "horizontal", "spacing": "sm", "margin": "md", "contents": [{"type": "button", "style": "primary", "color": "#B91C1C", "height": "sm", "action": {"type": "message", "label": "📊 呼叫 K線圖", "text": f"K線圖 {stock_code}"}}]}
                    footer_contents = [row1, row2, row3]

                flex_content = {"type": "bubble", "styles": {"header": {"backgroundColor": "#1A365D"}, "body": {"backgroundColor": "#F7FAFC"}, "footer": {"backgroundColor": "#0F172A"}}, "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": card_title, "color": "#D69E2E", "weight": "bold", "size": "sm"}, {"type": "text", "text": stock_query, "color": "#FFFFFF", "weight": "bold", "size": "xl", "margin": "md"}]}, "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": f"📊 雷達數據：\n{real_data}", "color": "#1A365D", "size": "xs", "weight": "bold", "wrap": True}, {"type": "separator", "margin": "md"}, {"type": "text", "text": ai_reply, "color": "#2D3748", "wrap": True, "size": "sm", "margin": "md"}]}, "footer": {"type": "box", "layout": "vertical", "paddingAll": "md", "contents": footer_contents}}
                line_bot_api.push_message(user_id, FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content))
            else:
                line_bot_api.push_message(user_id, TextSendMessage(text="⚠️ 報告統帥：AI 金鑰連線異常！"))
    except: pass

# ==========================================================
# 📡 6. Webhook 與過濾中樞 (秒回機制)
# ==========================================================
@app.route("/", methods=['GET'])
def home(): return "前線偵察兵：戰備狀態正常，未休眠！"

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
        
        # 👑 【第一擊：搶先秒回安撫文字】
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🛰️ 雷達已鎖定目標，正全速調閱軍情，請統帥稍候..."))

        # 👑 【純淨版・當日最新戰報直接攔截】
        if user_msg in ["最新戰報", "調閱戰報", "戰報"]:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            report_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html?v={timestamp}"

            flex_report = {
                "type": "bubble", "styles": {"header": {"backgroundColor": "#1E1B4B"}, "body": {"backgroundColor": "#0F172A"}, "footer": {"backgroundColor": "#020617"}},
                "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "⚔️ 股海觀浪・最新戰報", "color": "#FBBF24", "weight": "bold", "size": "lg"}]},
                "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "📡 雲端即時連線成功", "color": "#38BDF8", "weight": "bold", "size": "xs"}, {"type": "text", "text": "大本營主控台已將本日最新選股策略歸檔至雲端，請立刻點擊查閱軍情。", "color": "#94A3B8", "size": "sm", "margin": "md", "wrap": True}]},
                "footer": {"type": "box", "layout": "vertical", "contents": [{"type": "button", "style": "primary", "color": "#B45309", "action": {"type": "uri", "label": "🔓 解鎖本日最新戰報", "url": report_url}}]}
            }
            line_bot_api.push_message(user_id, FlexSendMessage(alt_text="指揮部：最新戰報調閱令", contents=flex_report))
            return

        # 解析 K 線或 AI 模式
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

        # 🚀 【多執行緒出擊】：將沉重的數據運算與 AI 劇本推演包，丟到背景默默執行
        threading.Thread(target=background_async_task, args=(user_id, user_msg, analysis_type, period_arg)).start()

    except: pass

if __name__ == "__main__":
    app.run(port=5000)
