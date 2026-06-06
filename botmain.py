# -*- coding: utf-8 -*-
from flask import Flask, request, abort, send_file, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
)
from google import genai
import json
import requests
import os
import re
import itertools
import io
import base64
import datetime
import threading
import time
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
# 📚 2. 台股資料庫 
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
# 📊 3. 雙通道市場行情分析中心 (統一雲端報價引擎)
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0"}
    yahoo_ma = ""; yahoo_price = ""
    try:
        if stock_code == "^TWII":
            url = "https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=2mo&interval=1d"
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TW?range=2mo&interval=1d"
        res = requests.get(url, headers=headers, timeout=5).json()
        if not res.get('chart', {}).get('result') and stock_code != "^TWII":
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_code}.TWO?range=2mo&interval=1d"
            res = requests.get(url, headers=headers, timeout=5).json()

        result = res['chart']['result'][0]
        closes = result['indicators']['quote'][0]['close']
        volumes = result['indicators']['quote'][0]['volume']
        highs = result['indicators']['quote'][0]['high']
        lows = result['indicators']['quote'][0]['low']
        
        valid_closes = [c for c in closes if c is not None]
        valid_vols = [v for v in volumes if v is not None]
        valid_highs = [h for h in highs if h is not None]
        valid_lows = [l for l in lows if l is not None]
        
        if len(valid_closes) > 0:
            curr_price = round(valid_closes[-1], 2)
            curr_vol = int(valid_vols[-1] / 1000)
            curr_h = round(valid_highs[-1], 2)
            curr_l = round(valid_lows[-1], 2)
            
            # 🚀 直接從最新一根 K 線抓取即時報價，告別 0 張與盤前昨收
            yahoo_price = f"🔴雲端即時成交價: {curr_price} (最高:{curr_h} 最低:{curr_l} 總量:{curr_vol}張)"

            if len(valid_closes) >= 20:
                ma5 = round(sum(valid_closes[-5:]) / 5, 2)
                ma10 = round(sum(valid_closes[-10:]) / 10, 2)
                ma20 = round(sum(valid_closes[-20:]) / 20, 2)
                kd5 = round(valid_closes[-5], 2); kd10 = round(valid_closes[-10], 2); kd20 = round(valid_closes[-20], 2)
                vol_5ma = sum(valid_vols[-5:]) / 5
                
                # 修正籌碼動向邏輯，確保精準抓取異常放量
                if valid_vols[-1] > vol_5ma * 1.5: big_player = "🔥大戶放量攻擊"
                elif valid_vols[-1] < vol_5ma * 0.7: big_player = "🧊量縮散戶觀望"
                else: big_player = "⚖️籌碼動能平穩"
                
                yahoo_ma = f"📊均線數值(5/10/20): {ma5}, {ma10}, {ma20}\n扣抵價位: {kd5}, {kd10}, {kd20}\n籌碼動向: {big_player}"
            else: 
                yahoo_ma = "均線資料庫不足"
    except Exception as e: 
        yahoo_ma = "備援線路連線受阻"
        yahoo_price = "⚠️報價抓取失敗"

    return f"{yahoo_price}\n{yahoo_ma}"

# ==========================================================
# 💥 4. 技術圖表生成中心
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
# 💥 5. 背景非同步交易運算中心 
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
            ai_error_msg = ""

            if gemini_keys:
                while attempts < max_attempts:
                    current_key = next(key_cycle)
                    try:
                        client = genai.Client(api_key=current_key)
                        
                        # 🌟 基礎核心指令：全域統一排版、小白用語、強制空行
                        base_prompt = (
                            f"你是頂尖台股操盤參謀兼新手導師。請根據即時報價與數據【{real_data}】為【{stock_query}】制定分析。\n"
                            f"【最高排版指令】：段落之間「必須要有空白行」分隔，嚴禁文字全部擠在一起！\n"
                            f"【語氣指令】：必須包含「專業術語 (小白白話文解釋)」的格式，例如：多頭排列(均線像爬樓梯一樣健康向上)、大戶鎖碼(主力把籌碼藏口袋不賣)。適時加入紀律警告如「嚴禁剁手追高」、「破線請像機器人一樣無情停損」。\n\n"
                            f"請完全依照下方三段式結構輸出：\n\n"
                        )

                        if analysis_type == "大盤":
                            prompt = base_prompt + (
                                "💡 1. 【大盤多空透視】\n判斷目前大盤多空趨勢與量價結構。\n\n"
                                "🎯 2. 【全軍資金控管指令】\n給出目前適合的持股水位(%)，以及對進場與防守的總體建議。\n\n"
                                "💰 3. 【大盤攻防點位】\n🚀 突破天花板 (壓力)：XXXXX點 (簡短說明)\n🛒 鐵板防守區 (支撐)：XXXXX點 (簡短說明)\n\n"
                                "⚠️ 數值絕對禁令：防守點不可高於現價！嚴禁輸出思考過程。"
                            )
                        elif analysis_type == "技術面":
                            prompt = base_prompt + (
                                "💡 1. 【技術線型透視】\n專注分析均線排列、扣抵位置預判與乖離率，給出白話文解釋。\n\n"
                                "🎯 2. 【兩棲作戰行動指令】\n🏃‍♂️ 空手觀望者：(告知該耐心等拉回還是可進場)\n🛡️ 已抱持股者：(告知該續抱、減碼還是停損)\n\n"
                                "💰 3. 【關鍵攻防點位】\n🚀 突破天花板 (壓力)：XX.X元\n🛒 低接甜蜜點 (支撐)：XX.X元\n🩸 最後逃生門 (停損)：XX.X元\n\n"
                                "⚠️ 數值絕對禁令：低接與停損點【絕對不可高於】現價！嚴禁輸出思考過程。"
                            )
                        elif analysis_type == "籌碼面":
                            prompt = base_prompt + (
                                "💡 1. 【主力籌碼透視】\n專注分析大戶資金進出意圖、成交量變化與散戶心理狀態，給出白話文解釋。\n\n"
                                "🎯 2. 【兩棲作戰行動指令】\n🏃‍♂️ 空手觀望者：(根據籌碼狀況給出進場或觀望建議)\n🛡️ 已抱持股者：(根據主力動向給出續抱或逃跑建議)\n\n"
                                "💰 3. 【關鍵攻防點位】\n🚀 突破天花板 (壓力)：XX.X元\n🛒 低接甜蜜點 (支撐)：XX.X元\n🩸 最後逃生門 (停損)：XX.X元\n\n"
                                "⚠️ 數值絕對禁令：低接與停損點【絕對不可高於】現價！嚴禁輸出思考過程。"
                            )
                        else:  # 涵蓋「劇本」與一般「綜合」查詢
                            prompt = base_prompt + (
                                "💡 1. 【盤勢透視與主力動向】\n綜合判斷趨勢與籌碼狀況，給出白話文解釋。\n\n"
                                "🎯 2. 【兩棲作戰行動指令】\n🏃‍♂️ 空手觀望者：(嚴禁追高，告知適合的低接時機)\n🛡️ 已抱持股者：(告知該續抱、減碼還是停損)\n\n"
                                "💰 3. 【關鍵攻防點位】\n🚀 突破天花板 (壓力)：XX.X元 (站穩這裡會再噴一段)\n🛒 低接甜蜜點 (支撐)：XX.X元 (買進的最佳甜蜜點)\n🩸 最後逃生門 (停損)：XX.X元 (破線請像機器人一樣無情停損)\n\n"
                                "⚠️ 數值絕對禁令：低接與停損防線【絕對不可高於】現價！嚴禁輸出思考過程。"
                            )

                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        if response.text: 
                            ai_reply = response.text.strip()
                            success = True
                            break 
                    except Exception as e: 
                        attempts += 1
                        ai_error_msg = str(e)
                        # 🛡️ 429 資源耗盡防禦網：指數退避冷卻機制
                        if "429" in ai_error_msg:
                            time.sleep(2 ** attempts) # 等待 2, 4, 8... 秒後再換下一把鑰匙繼續撞
                            continue
            else:
                ai_error_msg = "系統未配置有效的 Gemini API Key。"

            def get_color(t): return "🔵" if analysis_type == t else "⚪"
            row_btns = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label=f"{get_color('技術面')}技術分析預判", text=f"技術面 {stock_code}")),
                QuickReplyButton(action=MessageAction(label=f"{get_color('籌碼面')}籌碼資金追蹤", text=f"籌碼面 {stock_code}")),
                QuickReplyButton(action=MessageAction(label=f"{get_color('劇本')}絕對行動決策指示", text=f"劇本 {stock_code}")),
                QuickReplyButton(action=MessageAction(label="📊 呼叫 K線圖", text=f"K線圖 {stock_code}"))
            ])

            if success:
                header_text = f"📊 【市場全景分析・個股盤勢診斷】\n🎯 追蹤標的：{stock_query}\n\n{real_data}\n====================\n{ai_reply}"
                line_bot_api.push_message(user_id, TextSendMessage(text=header_text, quick_reply=row_btns))
            else:
                fallback_text = f"📊 【市場全景分析・個股盤勢診斷】\n🎯 追蹤標的：{stock_query}\n\n{real_data}\n====================\n⚠️ AI 雲端大腦連線失敗或超載！\n請直接參考上方數據操作，或稍後再點擊按鈕重試。\n(偵錯碼: {ai_error_msg[:30]})"
                line_bot_api.push_message(user_id, TextSendMessage(text=fallback_text, quick_reply=row_btns))

    except Exception as e: 
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=f"⚠️ 系統嚴重異常：\n執行指令時發生崩潰，請回報管理員。\n錯誤：{str(e)[:50]}"))
        except: pass

# ==========================================================
# 📡 6. Webhook 通道
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
       


        
        if user_msg == "獲取系統ID":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"您的專屬使用者 ID 為：\n{user_id}\n\n請將此代碼填入系統後台的 ADMIN_LINE_ID 環境變數中。"
            ))
            return

        if user_msg.startswith("問題回報 ") or user_msg.startswith("回報 "):
            issue_content = user_msg.replace("問題回報 ", "").replace("回報 ", "").strip()
            if not issue_content:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text="⚠️ 格式錯誤：請在「問題回報」後方加上空格，並說明您遇到的狀況。\n範例：問題回報 K線圖無法顯示"
                ))
                return
            
            reply_text = f"✅ 已收到您的系統反饋：\n「{issue_content}」\n管理員將盡快查閱並維護交易環境。"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            
            admin_id = os.environ.get('ADMIN_LINE_ID')
            if admin_id:
                try:
                    alert_msg = f"🚨 【看盤系統異常回報】\n發送用戶 ID: {user_id}\n問題內容：\n{issue_content}"
                    line_bot_api.push_message(admin_id, TextSendMessage(text=alert_msg))
                except: pass
            return

        if user_msg in ["最新戰報", "調閱戰報", "戰報"]:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            report_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html?v={timestamp}"
            broadcast_text = f"📊 【策略選股大師・當日最新特報】\n========================\n主控台已將本日最新核心選股策略網頁歸檔至雲端補給線！\n\n🔗 點擊解鎖本日最新網頁戰報 (跳出獨立瀏覽器新視窗)：\n{report_url}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=broadcast_text))
            return

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
# 📡 新增：給網頁探子抓取的戰情接口 (加入跨域 CORS 通行證)
# ==========================================================
from flask import jsonify

@app.route("/live_data.json", methods=['GET'])
def get_live_data():
    from flask import make_response, send_file
    import os
    try:
        file_path = os.path.join(os.getcwd(), "live_data.json")
        # 建立回應物件
        response = make_response(send_file(file_path))
        # 🔑 給予網頁通行證，解除瀏覽器阻擋 (CORS)
        response.headers['Access-Control-Allow-Origin'] = '*'
        # 🚫 禁用快取，確保網頁每次都抓到最新戰況
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    except Exception:
        # 若檔案尚未產生 (例如週末或開盤前)，回傳此錯誤訊息
        return {"error": "戰情包尚未生成 (系統待命)"}, 404

# ==========================================================
# 🌟 7. 🚀 雲端全時相決策中心
# ==========================================================
def market_patrol_loop():
    last_triggered_date = ""
    triggered_phases = set()

    while True:
        try:
            now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            date_today = now.strftime("%Y%m%d")
            
            if date_today != last_triggered_date:
                last_triggered_date = date_today
                triggered_phases.clear()

            is_weekend = (now.weekday() >= 5)
            current_phase = None
            phase_title = ""
            
            if not is_weekend and now.hour == 9 and now.minute == 15 and "0915" not in triggered_phases:
                current_phase = "0915"; phase_title = "🌅 09:15 【早盤強勢突破與假開高篩選點】"
            elif not is_weekend and now.hour == 10 and now.minute == 0 and "1000" not in triggered_phases:
                current_phase = "1000"; phase_title = "📈 10:00 【早盤方向確認點】"
            elif not is_weekend and now.hour == 12 and now.minute == 30 and "1230" not in triggered_phases:
                current_phase = "1230"; phase_title = "⚖️ 12:30 【尾盤籌碼定調點】"
            elif not is_weekend and now.hour == 13 and now.minute == 15 and "1315" not in triggered_phases:
                current_phase = "1315"; phase_title = "👑 13:15 【終局之戰：主力作線與鎖碼確認點】"
            elif now.hour == 21 and now.minute == 0 and "2100" not in triggered_phases:
                current_phase = "2100"; phase_title = "📡 21:00 【夜間雷達：多空溫度計與美股期指共振】"

            if current_phase:
                triggered_phases.add(current_phase)
                timestamp_v = datetime.datetime.now().strftime("%H%M%S")

                if current_phase == "2100":
                    headers = {"User-Agent": "Mozilla/5.0"}
                    sox_pct = 0.0; tsm_pct = 0.0; night_p = "連線超時"
                    try:
                        req_sox = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ESOX?interval=1d&range=2d", headers=headers, timeout=5).json()
                        d = req_sox['chart']['result'][0]['meta']
                        sox_pct = round(((d['regularMarketPrice'] - d['chartPreviousClose']) / d['chartPreviousClose']) * 100, 2)
                        
                        req_tsm = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/TSM?interval=1d&range=2d", headers=headers, timeout=5).json()
                        d = req_tsm['chart']['result'][0]['meta']
                        tsm_pct = round(((d['regularMarketPrice'] - d['chartPreviousClose']) / d['chartPreviousClose']) * 100, 2)
                    except: pass
                    
                    try:
                        req_idx = requests.Session(); req_idx.get('https://mis.twse.com.tw/stock/index.jsp', headers=headers, timeout=2)
                        res_idx = req_idx.get("https://mis.twse.com.tw/stock/api/getMarketInfo.jsp", timeout=2).json()
                        if res_idx.get('msgArray'): night_p = f"{res_idx['msgArray'][0].get('z', '-')} 點"
                    except: pass
                    
                    ai_filter = "大盤夜盤平穩，隔日維持既定紀律操作。"
                    if gemini_keys:
                        try:
                            client = genai.Client(api_key=next(key_cycle))
                            prompt = f"你是頂尖風控長。美股盤前費半指數變動{sox_pct}%，台積電ADR變動{tsm_pct}%，台指夜盤現況{night_p}。請用客觀交易術語在80字內為明天的台股策略進行系統風險定調。嚴禁輸出任何思考思維。"
                            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                            if response.text: ai_filter = response.text.strip()
                        except: pass
                        
                    night_report = f"{phase_title}\n數據時間：{now.strftime('%Y-%m-%d %H:%M')}\n====================\n🇺🇸 費城半導體盤前: {sox_pct}%\n📉 台積電 ADR 盤前: {tsm_pct}%\n📊 台指期夜盤即時: {night_p}\n====================\n🛡️ 【風控長明日戰略環境預判】\n{ai_filter}\n====================\n⚠️ 【嚴格防守紀律宣告】\n本環境預判為國際量價共振之客觀追蹤，絕非獲利保證。市場具備隨時反轉風險，任何交易請務必嚴格控管資金成數，並預先掛好停損條件單。"
                    try: line_bot_api.broadcast(TextSendMessage(text=night_report))
                    except: pass
                    time.sleep(60)
                    continue

                json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={timestamp_v}"
                res_json = requests.get(json_url, timeout=5)
                
                if res_json.status_code == 200 and res_json.text:
                    monitor_data = res_json.json()
                    if monitor_data:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        req = requests.Session()
                        
                        twii_chg = 0.0
                        try:
                            # 🚀 [大盤] 改用穩定 Yahoo API 抓取加權指數
                            yh_res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=1d&interval=1d", headers=headers, timeout=5).json()
                            yh_meta = yh_res['chart']['result'][0]['meta']
                            curr_idx = yh_meta['regularMarketPrice']
                            prev_idx = yh_meta['chartPreviousClose']
                            if prev_idx > 0: 
                                twii_chg = ((curr_idx - prev_idx) / prev_idx) * 100
                        except: pass

                        broadcast_msg = f"{phase_title}\n時間：{now.strftime('%H:%M')} (大盤即時：{round(twii_chg, 2)}%)\n====================\n"
                        ai_payload = []

                        for code, info in monitor_data.items():
                            try:
                                url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{code}.tw&_={int(time.time() * 1000)}"
                                res = req.get(url, timeout=3).json() 
                                if not res.get('msgArray'):
                                    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=otc_{code}.tw&_={int(time.time() * 1000)}"
                                    res = req.get(url, timeout=3).json()
                                    
                                if res.get('msgArray'):
                                    data = res['msgArray'][0]
                                    name = info.get('name', code)
                                    
                                    z = float(data.get('z', 0) if data.get('z', '-') != '-' else data.get('y', 0)) 
                                    o = float(data.get('o', z) if data.get('o', '-') != '-' else z)                 
                                    h = float(data.get('h', z) if data.get('h', '-') != '-' else z)                 
                                    l = float(data.get('l', z) if data.get('l', '-') != '-' else z)                 
                                    v = float(data.get('v', 0) if data.get('v', '-') != '-' else 0)                 
                                    y = float(data.get('y', z))                                                     
                                    chg = round(((z - y) / y) * 100, 2) if y > 0 else 0.0
                                    
                                    vwap = round((o + h + l + z * 2) / 5, 2)
                                    elapsed_mins = 60 if current_phase == "0915" else (105 if current_phase == "1000" else (255 if current_phase == "1230" else 300))
                                    est_vol = v * (270 / elapsed_mins)
                                    v_ratio = round(est_vol / info['v_5ma'], 1) if info['v_5ma'] > 0 else 1.0
                                    
                                    amp = h - l if h - l > 0 else 1.0
                                    upper_shadow = h - max(o, z)
                                    shadow_pct = round((upper_shadow / amp) * 100, 1)
                                    is_overheated_tr = (v_ratio > 2.5 and chg > 5)

                                    veto_triggered = False
                                    veto_reason = ""
                                    
                                    if twii_chg <= -1.0:
                                        veto_triggered = True
                                        veto_reason = f"🚨 大盤目前跌幅 {round(twii_chg,2)}% 觸發環境崩塌警報。本檔被迫取消多方評估，禁止任何買進試單！持股者請死守防守價 {info['ma5']}元 (5MA) 或 {info['ma10']}元 (10MA)，一旦收盤跌破必須確實執行停損，保留資金實力。"
                                    elif z >= h * 0.99 and chg > 2 and v_ratio < 0.8:
                                        veto_triggered = True
                                        veto_reason = f"🚨 現價 {z}元 創高，但預估量僅達5日均量之 {v_ratio}倍 (量縮背離)。此為典型無量虛胖誘多陷阱，強烈建議空手者嚴格觀望，絕對禁止在現價追高買進！"
                                    elif z < vwap and chg > 1:
                                        veto_triggered = True
                                        veto_reason = f"🚨 股價現報 {z}元，仍受制於盤中大戶平均成本線 {vwap}元 (VWAP) 下方。在未能穩定站上 {vwap}元 之前，反彈皆為假象，嚴禁伸手接刀或盲目攤平。"
                                    elif chg > 3 and shadow_pct > 40.0:
                                        veto_triggered = True
                                        veto_reason = f"🚨 股價雖高達 {z}元，但盤中上影線比例已達 {shadow_pct}% (已超過40%出貨臨界點)。這代表買盤力道遭主力拋壓吞噬，型態轉為出貨K線，強烈警告空手者現價禁止接刀，持股者若跌破 {vwap}元 (盤中均價) 請立即減碼落跑。"
                                    elif is_overheated_tr:
                                        veto_triggered = True
                                        veto_reason = f"🚨 本標的量能爆發達 {v_ratio}倍，籌碼處於極度失控與過熱狀態。這種凌亂籌碼尾盤極容易引發人踩人多殺多跳水風險，軍令強制：此檔今日封鎖交易，嚴禁真金白銀進場搏鬥！"

                                    stock_payload = {
                                        "code": code, "name": name, "type": info.get('type', 'core'),
                                        "z": z, "chg": chg, "vwap": vwap, "v_ratio": v_ratio, "shadow_pct": shadow_pct,
                                        "ma5": info['ma5'], "ma10": info['ma10'], "ma20": info['ma20'], "kd5": info['kd5'],
                                        "veto_triggered": veto_triggered, "veto_reason": veto_reason
                                    }
                                    ai_payload.append(stock_payload)
                                time.sleep(1) 
                            except: continue

                        for s in ai_payload:
                            broadcast_msg += f"📌 **{s['name']} ({s['code']})** | 現價: {s['z']} ({'+' if s['chg']>0 else ''}{s['chg']}%)\n"
                            broadcast_msg += f"📊 盤中均價(VWAP): {s['vwap']}元 | 量能: 預估5MA之 {s['v_ratio']}倍\n"
                            
                            if s['veto_triggered']:
                                broadcast_msg += f"🎯 **行動指令：**\n   {s['veto_reason']}\n"
                            else:
                                ai_instruction = "根據既定防守價進行部位追蹤。"
                                if gemini_keys:
                                    try:
                                        client = genai.Client(api_key=next(key_cycle))
                                        prompt = (
                                            f"你是台股王牌操盤參謀。標的 {s['name']}({s['code']})，時相為【{current_phase}】。現價{s['z']}元，盤中均價VWAP為{s['vwap']}元，5MA為{s['ma5']}元，10MA為{s['ma10']}元，明日5MA扣抵{s['kd5']}元。"
                                            f"請根據上述絕對數字，直接在一句話內給出明確下一步行動指令（現價可逢低試單/強勢站穩XX元加碼/破XX元無條件砍單停損）。"
                                            f"【最高憲法】：必須包含絕對數字價位（如：{s['ma5']}元），嚴禁僅使用『月線』、『均線』、『前低』、『破線』或『均價線』等純文字代稱。嚴禁輸出思考過程，50字內。"
                                            f"⚠️【數值絕對禁令】：推算突破點【絕不可低於】現價，防守點【絕不可高於】現價！乖離過大請直接建議觀望。"
                                        )
                                        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                                        if response.text: ai_instruction = response.text.strip()
                                    except: pass
                                
                                time.sleep(5) 

                                broadcast_msg += f"🎯 **行動指令：**\n   {ai_instruction}\n"
                            broadcast_msg += f"--------------------\n"

                        # 🚀 智慧判斷：只有當真的有股票資訊時，才發送廣播！
                        if len(ai_payload) > 0:
                            # 📦 [戰術升級] 整理跑馬燈彈藥包
                            live_data = {
                                "fundsText": f"📊 加權指數 {round(twii_chg, 2)}% | {phase_title}",
                                "stocksText": " | ".join([f"{s['name']}({s['code']}) {s['z']}元 ({'+' if s['chg']>0 else ''}{s['chg']}%)" for s in ai_payload])
                            }
                            
                            # 💾 寫入 live_data.json (讓前端網頁來抓取)
                            try:
                                file_path = os.path.join(os.getcwd(), "live_data.json")
                                with open(file_path, "w", encoding="utf-8") as f:
                                    json.dump(live_data, f, ensure_ascii=False)
                            except Exception as e:
                                print(f"JSON 寫入失敗: {e}")

                            # 📢 原有的 LINE 廣播功能
                            broadcast_msg += "====================\n"
                            broadcast_msg += "⚠️ **【戰區紀律宣告】**\n"
                            broadcast_msg += "本訊號為客觀量價追蹤。嚴禁追高滿倉，新單上限1成。進場務必同步設定「觸價停損單」，留得青山在，不怕沒柴燒。"
                            try: line_bot_api.broadcast(TextSendMessage(text=broadcast_msg))
                            except Exception as e: print(f"雲端廣播失敗: {e}")
                        else:
                            print(f"{phase_title} - 目前無達標戰略目標，維持觀望。")
                        
                time.sleep(60) 
            else:
                time.sleep(15) 
        except Exception as e:
            time.sleep(30)

# 啟動背景全時相廣播巡邏雷達
threading.Thread(target=market_patrol_loop, daemon=True).start()

# ==========================================================
# 💥 Gunicorn 免改網頁開機超時配置嵌入 (完全保留)
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
    print("雷達掃描引擎已啟動")
