# -*- coding: utf-8 -*-
from flask import Flask, request, abort, jsonify, make_response
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

# 🛡️ 戰術快取容器
# ✅ 替換為這段
CACHE_FILE = "live_data_cache.json"

def update_cache(data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except: pass

def read_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"fundsText": "⏳ 系統剛啟動，等待盤中數據同步...", "stocksText": "⏳ 系統剛啟動，等待盤中數據同步..."}

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
        global_stock_dict = {"台積電": "2330", "鴻海": "2317", "聯發科": "2454"}
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
            
            yahoo_price = f"🔴雲端即時成交價: {curr_price} (最高:{curr_h} 最低:{curr_l} 總量:{curr_vol}張)"

            if len(valid_closes) >= 20:
                ma5 = round(sum(valid_closes[-5:]) / 5, 2)
                ma10 = round(sum(valid_closes[-10:]) / 10, 2)
                ma20 = round(sum(valid_closes[-20:]) / 20, 2)
                kd5 = round(valid_closes[-5], 2); kd10 = round(valid_closes[-10], 2); kd20 = round(valid_closes[-20], 2)
                vol_5ma = sum(valid_vols[-5:]) / 5
                
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
# 🚀 專為開機與網頁探子設計的強制刷新引擎 (終極防護與除錯版)
# ==========================================================
def execute_force_refresh():
    global live_data_cache
    # 💥 換上最高級的真人瀏覽器偽裝裝甲
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        print("🕵️‍♂️ [偵蒐行動] 1. 準備抓取大盤...")
        twii_chg = 0.0
        try:
            yh_res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/^TWII?range=1d&interval=1d", headers=headers, timeout=5).json()
            twii_chg = ((yh_res['chart']['result'][0]['meta']['regularMarketPrice'] - yh_res['chart']['result'][0]['meta']['chartPreviousClose']) / yh_res['chart']['result'][0]['meta']['chartPreviousClose']) * 100
        except: pass

        print("🕵️‍♂️ [偵蒐行動] 2. 準備潛入 pCloud 下載名單...")
        timestamp_v = datetime.datetime.now().strftime("%H%M%S")
        json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={timestamp_v}"
        
        # 💥 關鍵修復：下載名單時「必須」掛上 headers，否則會被當成惡意爬蟲阻擋！
        res_json = requests.get(json_url, headers=headers, timeout=10)
        print(f"📡 pCloud 回應狀態碼: {res_json.status_code}")
        
        if res_json.status_code == 200:
            raw_data = res_json.json()
            print(f"📡 名單下載成功，長度: {len(raw_data)}")
            
            if isinstance(raw_data, list):
                monitor_data = {str(item.get("代碼")): {"name": item.get("商品", item.get("代碼"))} for item in raw_data if "代碼" in item}
            else: monitor_data = raw_data
            
            tmp_stocks = []
            print("🕵️‍♂️ [偵蒐行動] 3. 準備抓取 Yahoo 個股報價...")
            for code, info in list(monitor_data.items())[:5]:
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?range=1d&interval=1d"
                    res = requests.get(url, headers=headers, timeout=5).json()
                    if not res.get('chart', {}).get('result'): 
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TWO?range=1d&interval=1d"
                        res = requests.get(url, headers=headers, timeout=5).json()
                        
                    meta = res['chart']['result'][0]['meta']
                    z = meta['regularMarketPrice']
                    y = meta['chartPreviousClose']
                    chg = round(((z - y) / y) * 100, 2) if y > 0 else 0.0
                    tmp_stocks.append(f"{info.get('name', code)}({code}) {z}元 ({'+' if chg>0 else ''}{chg}%)")
                    print(f"✅ 成功獲取: {code}")
                except Exception as e: 
                    print(f"⚠️ 抓取 {code} 失敗: {e}")
                    continue
            
            # 💥 改為呼叫 update_cache 寫入實體檔案
            if tmp_stocks:
                update_cache({"fundsText": f"📊 加權指數 {round(twii_chg, 2)}% | 📡 全時相雷達聯網中", "stocksText": " | ".join(tmp_stocks)})
                print("✅ [戰術回報] 任務大獲全勝，實體檔案已更新！")
            else:
                # 💥 死亡回報：就算抓不到股票，也要寫入實體檔案
                update_cache({"fundsText": "⚠️ 報價異常", "stocksText": "Yahoo API 拒絕連線或查無資料"})
        else:
            # 💥 死亡回報：pCloud 擋住了，寫入實體檔案
            update_cache({"fundsText": "⚠️ 雲端阻擋", "stocksText": f"pCloud 拒絕連線 (HTTP狀態碼: {res_json.status_code})"})
            
    except Exception as e:
        # 💥 死亡回報：程式寫錯或網路斷線，寫入實體檔案
        update_cache({"fundsText": "❌ 嚴重當機", "stocksText": f"錯誤代碼: {str(e)}"})
        print(f"❌ 致命錯誤: {e}")

# ==========================================================
# 📡 6. Webhook 通道與戰情接口
# ==========================================================
@app.route("/", methods=['GET'])
def home(): return "前線看盤伺服器：交易連線狀態正常，常駐清醒中！"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']; body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

@app.route("/live_data.json", methods=['GET'])
def get_live_data():
    response = make_response(jsonify(read_cache())) # 💥 改為讀取實體檔案
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    pass # 省略純文字互動區段，保留原有架構

# ==========================================================
# 🌟 7. 🚀 雲端全時相決策中心 (加裝防呆裝甲)
# ==========================================================
def market_patrol_loop():
    last_triggered_date = ""
    triggered_phases = set()
    
    # 💥 開機首發彈
    print("📡 [總部軍令] 偵蒐引擎初始化，發動開機首次盤面刷新...")
    threading.Thread(target=lambda: execute_force_refresh()).start()

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
                    # 夜盤邏輯省略
                    continue

                json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={timestamp_v}"
                res_json = requests.get(json_url, timeout=5)
                
                if res_json.status_code == 200 and res_json.text:
                    raw_data = res_json.json()
                    if raw_data:
                        # 💥 【戰術修正 2：翻譯官機制】
                        if isinstance(raw_data, list):
                            monitor_data = {str(item.get("代碼")): {"name": item.get("商品", item.get("代碼"))} for item in raw_data if "代碼" in item}
                        else:
                            monitor_data = raw_data

                        headers = {"User-Agent": "Mozilla/5.0"}
                        req = requests.Session()
                        
                        twii_chg = 0.0
                        try:
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
                                    
                                    # 💥 【戰術修正 3：防呆裝甲】 即使 JSON 沒有這些均線參數，系統也不會崩潰
                                    v_5ma_val = info.get('v_5ma', 1.0)
                                    v_ratio = round(est_vol / v_5ma_val, 1) if v_5ma_val > 0 else 1.0
                                    
                                    amp = h - l if h - l > 0 else 1.0
                                    upper_shadow = h - max(o, z)
                                    shadow_pct = round((upper_shadow / amp) * 100, 1)
                                    is_overheated_tr = (v_ratio > 2.5 and chg > 5)

                                    veto_triggered = False
                                    veto_reason = ""
                                    
                                    ma5_val = info.get('ma5', z)
                                    ma10_val = info.get('ma10', z)
                                    
                                    if twii_chg <= -1.0:
                                        veto_triggered = True
                                        veto_reason = f"🚨 大盤目前跌幅 {round(twii_chg,2)}% 觸發環境崩塌警報。持股者請死守防守價 {ma5_val}元 (5MA) 或 {ma10_val}元 (10MA)。"
                                    # 省略其它 veto 細節，保護核心功能...

                                    stock_payload = {
                                        "code": code, "name": name, "type": info.get('type', 'core'),
                                        "z": z, "chg": chg, "vwap": vwap, "v_ratio": v_ratio, "shadow_pct": shadow_pct,
                                        "ma5": ma5_val, "ma10": ma10_val, "ma20": info.get('ma20', z), "kd5": info.get('kd5', z),
                                        "veto_triggered": veto_triggered, "veto_reason": veto_reason
                                    }
                                    ai_payload.append(stock_payload)
                                time.sleep(1) 
                            except: continue

                        if len(ai_payload) > 0:
                            # 💥 改為呼叫 update_cache 寫入實體檔案
                            update_cache({
                                "fundsText": f"📊 加權指數 {round(twii_chg, 2)}% | {phase_title}",
                                "stocksText": " | ".join([f"{s['name']}({s['code']}) {s['z']}元 ({'+' if s['chg']>0 else ''}{s['chg']}%)" for s in ai_payload])
                            })

                time.sleep(60) 
            else:
                time.sleep(15) 
        except Exception as e:
            time.sleep(30)

threading.Thread(target=market_patrol_loop, daemon=True).start()

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
