# -*- coding: utf-8 -*-
# =========================================================
# 📡 股海觀浪雲端探子母艦：防彈完全體戰情室 V100.0 (階段一：全市場基本面狙擊)
# 開發代號：botmain.py (雲端守護協定 - 100% 完整解碼不閹割版)
# =========================================================
from flask import Flask, request, abort, jsonify, make_response
from flask_socketio import SocketIO, emit
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, ImageSendMessage,
    JoinEvent, SourceGroup  # 💥 新增：群組加入事件偵測模組
)
from bs4 import BeautifulSoup
import json
import requests
import os
import google.generativeai as genai
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


# ==========================================================
# 📰 情報偵蒐引擎：新聞與市場流向 
# ==========================================================
def fetch_cnyes_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=3"
        res = requests.get(url, headers=headers, timeout=4).json()
        items = res.get("items", {}).get("data", [])
        news_list = []
        for item in items:
            title = item.get("title", "").strip()
            news_id = item.get("newsId")
            if title:
                clean_title = title.replace('"', '').replace("'", "")
                if news_id:
                    news_list.append(f"<a href='https://news.cnyes.com/news/id/{news_id}' target='_blank' style='color: #fda4af;'>📰 快訊：{clean_title}</a>")
                else:
                    news_list.append(f"<span style='color: #fda4af;'>📰 快訊：{clean_title}</span>")
        return " ｜ ".join(news_list) + " ｜ " if news_list else ""
    except: return ""

def get_market_leader():
    try:
        # 💥 升級頂級偽裝，徹底欺騙 Yahoo 防火牆
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        class_res = requests.get("https://tw.stock.yahoo.com/class-quote?sectorId=tw_stock_class", headers=headers, timeout=8)
        soup = BeautifulSoup(class_res.text, 'html.parser')
        
        target_industries = ["半導體", "電腦及週邊", "電子零組件", "通信網路", "光電業", "生技醫療", "金融保險", "鋼鐵工業", "航運業", "建材營造"]
        leaderboard = {}
        
        # 💥 終極殺招：把網頁所有可見文字抽出來排成一列！
        texts = list(soup.stripped_strings)
        
        for ind in target_industries:
            for i, text in enumerate(texts):
                if ind == text:
                    # 找到產業名稱後，直接往下檢查接下來的 15 個文字區塊
                    for j in range(1, 15):
                        if i + j < len(texts):
                            # 揪出包含 % 的漲跌幅數字
                            match = re.search(r'([+-]?\d+\.\d+)%', texts[i+j])
                            if match:
                                leaderboard[ind] = float(match.group(1))
                                break # 抓到數字就換下一個產業
                    if ind in leaderboard: break # 確保只抓一次
                    
        if leaderboard:
            top = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[0]
            ind_name = "電腦週邊" if "電腦" in top[0] else top[0]
            return f"🔥 資金主攻：【{ind_name}】({top[1]}%)"
    except: pass
    return "🔥 資金主攻：【半導體】(0.0%)"


app = Flask(__name__)

# 💥 啟動戰情大廳通訊樞紐
app.config['SECRET_KEY'] = 'shadow_base_secret_999'
socketio = SocketIO(app, cors_allowed_origins="*")

# 🛡️ 戰術快取配置
CACHE_FILE = "live_data_cache.json"
VIP_CACHE_FILE = "radar_vips.json"  # 💥 新增：特戰隊員點名簿

def update_cache(data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except:
        pass

def read_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"fundsText": "⏳ 系統剛啟動，等待盤中數據同步...", "stocksText": "⏳ 系統剛啟動，等待盤中數據同步..."}

# 💥 新增：讀取與寫入點名簿的專屬函數
def read_vips():
    if os.path.exists(VIP_CACHE_FILE):
        try:
            with open(VIP_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

def update_vips(data):
    try:
        with open(VIP_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass

# ==========================================================
# 🔑 1. API 金鑰與通訊參數設定
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'SMvkBhzw64RpFhLGsaDRfzqPVPkxAk8HYLz+Pvy/kiVG/n3XkSNWOcPPyQkSpWrCcAj3+SmAaM1iopF9dz6TJdo6xyQwBv0soAzdn+Wdn3GC2YS+4m16cEzIW5pUTqO12JC6grdw6ktZ4wh3arR5+gdB04t89/1O/w1cDnyilFU=')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '') 

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
# 📚 2. 台股資料庫初始化
# ==========================================================
global_stock_dict = {}
def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0: 
        return global_stock_dict
    
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
    except: 
        pass
        
    if len(global_stock_dict) == 0:
        global_stock_dict = {"台積電": "2330", "鴻海": "2317", "聯發科": "2454"}
    return global_stock_dict

threading.Thread(target=get_stock_dict).start()

# ==========================================================
# 📈 3. [新增] 全市場基本面動能掃描引擎 (階段一核心)
# ==========================================================
revenue_history_cache = {}  # 記憶體：負責存放每檔股票上一期的期別
fundamental_focus_cache = [] # 戰術狙擊區快取 (48小時內有變更)
fundamental_full_cache = []  # 全域戰略區快取 (全市場 2000 檔)



# ==========================================================
# ⚡ [雙層雷達版] 當沖雷達：破曉初升 vs 極限動能 雙重偵測引擎
# ==========================================================
intraday_breakout_cache = []   
intraday_alerted_codes = set() 
stock_tick_memory = {}         

def detect_intraday_breakout(code, name, ind="未知"):
    import requests, time, datetime
    
    # 🛡️ 單日冷卻防護：今天已經通報過，直接跳過
    if code in intraday_alerted_codes:
        return None

    try:
        # 直連證交所，獲取當下 0 秒延遲的最新報價
        req = requests.Session()
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{code}.tw&_={int(time.time() * 1000)}"
        res = req.get(url, timeout=3).json()
        if not res.get('msgArray'):
            url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=otc_{code}.tw&_={int(time.time() * 1000)}"
            res = req.get(url, timeout=3).json()

        if res.get('msgArray'):
            data = res['msgArray'][0]
            z = float(data.get('z', 0) if data.get('z', '-') != '-' else data.get('y', 0)) # 現價
            o = float(data.get('o', 0) if data.get('o', '-') != '-' else z) # 開盤
            h = float(data.get('h', 0) if data.get('h', '-') != '-' else 0) # 最高
            l = float(data.get('l', 0) if data.get('l', '-') != '-' else z) # 最低
            y = float(data.get('y', 0)) # 昨收
            v = float(data.get('v', 0) if data.get('v', '-') != '-' else 0) # 總量

            if z <= 0 or y <= 0: return None
            
            chg_pct = round(((z - y) / y) * 100, 2)
            vwap_est = round((o + h + l + z * 2) / 5, 2)
            now_ts = time.time()

            # 🧠 寫入動態矩陣記憶體
            if code not in stock_tick_memory:
                stock_tick_memory[code] = []
            
            stock_tick_memory[code].append((now_ts, z, v, h))
            
            # 只保留最近 10 分鐘的記憶，避免拖慢雲端效能
            if len(stock_tick_memory[code]) > 10:
                stock_tick_memory[code].pop(0)

            ticks = stock_tick_memory[code]
            
            # 必須收集滿 5 分鐘 (約 6 個點) 才能進行雙週期比對
            if len(ticks) >= 6:
                current_z, current_v, current_h = ticks[-1][1], ticks[-1][2], ticks[-1][3]
                z_1m_ago, v_1m_ago = ticks[-2][1], ticks[-2][2]
                z_5m_ago, v_5m_ago = ticks[-6][1], ticks[-6][2]

                # 🔫 算出版機：最近 1 分鐘的瞬間成交量
                vol_1m = current_v - v_1m_ago
                # 🛡️ 算出大局：最近 5 分鐘的總成交量，並推算平均每分鐘是多少
                vol_5m = current_v - v_5m_ago
                avg_1m_vol_in_5m = vol_5m / 5 if vol_5m > 0 else 1.0

                # 💥 【全新雙層防線濾網】💥
                
                # 1. 均價線防護與短趨勢向上 (確保多方控盤)
                is_above_vwap = current_z >= vwap_est
                is_trend_up = current_z >= z_5m_ago
                
                # 2. 降門檻點火偵測 (1.5倍爆量 + 300萬台幣資金)
                is_volume_surge = vol_1m >= (avg_1m_vol_in_5m * 1.5)
                is_ignited = (vol_1m * current_z * 1000) >= 3000000 
                
                if is_above_vwap and is_trend_up and is_volume_surge and is_ignited:
                    
                    # 3. 雙層警戒線判斷
                    alert_type = None
                    if 1.0 <= chg_pct <= 4.5:
                        alert_type = "🌅 【破曉初升】安全起漲區 (適合佈局)"
                    elif 4.5 < chg_pct <= 7.0:
                        alert_type = "⚠️ 【極限動能】高風險誘多區 (請縮小部位)"
                        
                    # 只要落入兩大射擊區間，立刻擊發警報！
                    if alert_type:
                        tz = datetime.timezone(datetime.timedelta(hours=8))
                        time_str = datetime.datetime.now(tz).strftime("%H:%M:%S")
                        
                        intraday_alerted_codes.add(code) # 鎖上保險栓
                        
                        # 💥 加上主流族群的專屬視覺標記
                        hot_tag = "👑 [主流領頭羊]" if "半導體" in ind else f"🏷️ [{ind}]"
                        
                        return f"[{time_str}] ⚡ {name}({code}) {alert_type}\n{hot_tag} | 現價：{current_z} (均價線:{vwap_est})\n漲幅：{chg_pct}%\n🔥 1分爆量：{int(vol_1m)} 張 (達5分均速 {round(vol_1m/avg_1m_vol_in_5m, 1)}倍)"

    except Exception as e:
        pass
    return None


# ==========================================================
# 🧠 [終極防空版] 重大訊息解碼獵犬 (金鑰與模型智慧防錯安全對接)
# ==========================================================
self_assessed_cache = []

# 💥 設定 Gemini API (確保抓取 Render 環境變數)
gemini_key = os.environ.get("GEMINI_API_KEY", "")
if not gemini_key or "請將您的" in gemini_key:
    print("⚠️ [致命警告] Render 環境變數中的 GEMINI_API_KEY 似乎為空或未正確設定！", flush=True)
else:
    genai.configure(api_key=gemini_key)

def init_strategic_ai():
    """💥 智慧型模型掛載引擎：多波段嘗試，全面封殺 404 錯誤"""
    # 按照 2026 最新標準、相容性、歷史穩健度排序的代號陣列
    model_candidates = [
        'gemini-1.5-flash',       # 優先順位 1：目前最高效、最廣泛支援的 Flash 模型
        'gemini-1.5-pro',         # 優先順位 2：高階分析模型
        'gemini-2.5-flash',       # 優先順位 3：新世代 Flash 規格
        'gemini-pro'              # 優先順位 4：經典款相容模型
    ]
    
    # 戰術偵察：嘗試列出所有官方授權給這把金鑰的武器清單
    try:
        print("🔍 [AI 兵器庫掃描] 正在盤點當前金鑰可用模型...", flush=True)
        available_list = []
        for m in genai.list_models():
            if 'generateContent' in getattr(m, 'supported_generation_methods', []):
                clean_name = m.name.replace('models/', '')
                available_list.append(clean_name)
                print(f"  ✅ 官方授權武器: {clean_name}", flush=True)
        
        # 如果官方清單有東西，直接用清單裡最匹配的
        for candidate in model_candidates:
            if candidate in available_list:
                print(f"🎯 [自動尋標成功] 優先匹配到授權清單中的引擎: {candidate}", flush=True)
                return genai.GenerativeModel(candidate)
    except Exception as e:
        print(f"⚠️ [兵器庫掃描受阻] 無法讀取官方清單 ({e})，轉入強制暴力掛載程序...", flush=True)

    # 暴力掛載程序：如果清單讀不到，就由程式碼一個一個去敲門，直到成功為止
    for model_name in model_candidates:
        try:
            print(f"🚀 正在嘗試強行掛載型號: {model_name} ...", flush=True)
            test_model = genai.GenerativeModel(model_name)
            # 發射一發極短的空包彈，測試 Google 伺服器會不會報 404
            test_model.generate_content("ping", generation_config={"max_output_tokens": 1})
            print(f"🔥 [強行掛載成功] 引擎 {model_name} 通訊測試完全正常！", flush=True)
            return test_model
        except Exception as e:
            print(f"  ❌ 型號 {model_name} 宣告失敗或不支援: {e}", flush=True)
            
    # 最終防線：如果全部慘遭拒絕，預設掛載最基礎的 flash，避免後續程式碼死機
    print("🚨 [嚴重警報] 所有候選模型皆無法通過通訊測試！強制掛載預設防護裝甲。", flush=True)
    return genai.GenerativeModel('gemini-1.5-flash')

# 💥 執行智慧掛載，並將結果交付給戰情室主要 AI 大腦
ai_model = init_strategic_ai()




def fetch_material_info():
    global self_assessed_cache, ai_model  # 💥 修正：允許函數內部重新組裝 AI 槍管
    print("🕵️‍♂️ [AI 獵犬] 開始掃描全市場重大訊息...", flush=True)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        urls = [
            "https://openapi.twse.com.tw/v1/opendata/t187ap04_L", 
            "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O" 
        ]
        
        raw_data = []
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    raw_data.extend(res.json())
            except: pass

        news_list = []
        for item in raw_data:
            # 無塵室淨化欄位
            clean_item = {str(k).strip(): v for k, v in item.items()}
            
            subject = str(clean_item.get("主旨", clean_item.get("Subject", clean_item.get("SPOKE_TITLE", ""))))
            desc = str(clean_item.get("說明", clean_item.get("Description", clean_item.get("CONTENT", ""))))
            code = str(clean_item.get("公司代號", clean_item.get("Code", clean_item.get("CO_ID", ""))))
            name = str(clean_item.get("公司名稱", clean_item.get("Name", clean_item.get("CO_NAME", ""))))
            date_str = str(clean_item.get('發言日期', clean_item.get('SpkDate', clean_item.get('SPOKE_DATE', ''))))
            time_str = str(clean_item.get('發言時間', clean_item.get('SpkTime', clean_item.get('SPOKE_TIME', ''))))
            full_date = f"{date_str} {time_str}".strip()
            
            # 🛡️ 戰術過濾：精準鎖定「注意股」與「自結財報」
            if "注意" in subject or "自結" in subject or "EPS" in subject or "盈餘" in subject:
                eps_match = re.search(r'(?:每股盈餘|EPS|每股虧損|每股盈餘\(虧損\)).*?([+-]?\d+\.\d+)', desc, re.IGNORECASE)
                eps_val = float(eps_match.group(1)) if eps_match else 0.0

                
                # 💥 新增：防空攔截網，如果股票代碼是空白的，直接跳過不浪費子彈！
                if not code.strip():
                    continue

                # 只要符合條件，立刻呼叫 Gemini 進行深度解析！
                if eps_val != 0.0 or "注意" in subject:
                    
                    print(f"🤖 [AI 啟動] 正在分析 {code} {name} 的重大訊息...", flush=True)
                    
                    ai_rating = "⚪ 中性看待"
                    ai_analysis = "系統正在讀取原始公告..."
                    last_year_eps = "-"
                    yoy_eps = "-"
                    turnaround = "-"
                    est_yearly = "-"
                    
                    # 💥 這裡開始是全新的：重試機制與自動換彈匣系統
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            import time
                            # 將基礎冷卻時間稍微拉長至 6 秒，穩定射速
                            time.sleep(6) 
                            
                            # 💥 對 Gemini 下達戰術萃取指令
                            prompt = f"""
                            你是一位頂尖台股分析師。請閱讀以下重大訊息，並以 JSON 格式輸出萃取結果。
                            如果內文中找不到對應數字，請填 "-"。務必只輸出 JSON 格式，不要其他廢話。
                            格式要求：
                            {{
                              "last_year_eps": "去年同月或同期EPS(數字)",
                              "yoy_eps_growth": "EPS年增率(字串，包含%)",
                              "turnaround": "是否轉虧為盈(是/否/持續虧損/持續獲利)",
                              "est_yearly_eps": "預估全年EPS(數字或字串)",
                              "ai_rating": "評級(🔴 強烈買進 / 🟡 值得觀察 / 🟢 需要小心 / ⚪ 中性看待)",
                              "ai_analysis": "用四個段落(營運現況、獲利分析、產業風險、綜合評估)撰寫約200字白話文解析"
                            }}
                            重大訊息內容：{desc}
                            """
                            response = ai_model.generate_content(prompt)
                            
                            # 嘗試解析 AI 回傳的 JSON (去除可能的 markdown 標記)
                            res_text = response.text.replace('```json', '').replace('```', '').strip()
                            ai_data = json.loads(res_text)
                            
                            ai_rating = ai_data.get("ai_rating", ai_rating)
                            ai_analysis = ai_data.get("ai_analysis", ai_analysis)
                            last_year_eps = ai_data.get("last_year_eps", "-")
                            yoy_eps = ai_data.get("yoy_eps_growth", "-")
                            turnaround = ai_data.get("turnaround", "-")
                            est_yearly = ai_data.get("est_yearly_eps", "-")
                            print(f"✅ [AI 成功] {code} 財報數據萃取完畢！", flush=True)
                            
                            break # 💥 成功萃取，跳出重試迴圈
                            
                        except Exception as e:
                            err_str = str(e)
                            if "429" in err_str:
                                print(f"⚠️ [429 資源耗盡] 第 {attempt+1} 次嘗試失敗。自動切換備用金鑰...", flush=True)
                                try:
                                    # 抓取下一把備用金鑰並重新配置
                                    next_key = next(key_cycle)
                                    genai.configure(api_key=next_key)
                                    
                                    # 📍 統帥，就是這一行！重新上膛！拿新的金鑰重新組裝槍管！
                                    ai_model = genai.GenerativeModel('gemini-2.5-flash')
                                    
                                    time.sleep(2) # 換彈匣稍等 2 秒
                                except:
                                    print("⚠️ [彈匣警告] 無法切換，請確保 Render 已設定 GEMINI_API_KEY_1~5", flush=True)
                                    time.sleep(5) # 沒子彈只能硬等冷卻
                            else:
                                print(f"⚠️ [AI 解析失敗] {e}", flush=True)
                                break # 若非 429 錯誤，直接放棄這檔標的

                    news_list.append({
                        "date": full_date,
                        "code": code,
                        "name": name,
                        "subject": subject,
                        "eps": eps_val,
                        "desc": desc[:300],
                        # 💥 把 AI 算出來的精華數據包裝進去！
                        "ai_rating": ai_rating,
                        "ai_analysis": ai_analysis,
                        "last_year_eps": last_year_eps,
                        "yoy_eps": yoy_eps,
                        "turnaround": turnaround,
                        "est_yearly": est_yearly
                    })
                    
        # 歷史記憶裝甲
        existing_subjects = [item["subject"] for item in self_assessed_cache]
        for new_item in news_list:
            if new_item["subject"] not in existing_subjects:
                self_assessed_cache.insert(0, new_item)
                
        self_assessed_cache = self_assessed_cache[:60]
        
    except Exception as e:
        print(f"⚠️ [解碼獵犬] 執行異常: {e}", flush=True)



def fetch_fundamental_data():
    global revenue_history_cache, fundamental_focus_cache, fundamental_full_cache
    import sys
    import time
    try:
        print("📡 [基本面引擎] 啟動全市場財報與估值掃描 (終極雙向逆向演算版)...", flush=True) 
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Connection": "keep-alive"
        }


# 🛡️ 將您剛剛複製的 Google Apps Script 網址貼在下方引號內
        GAS_URL = "https://script.google.com/macros/s/AKfycbxaWJMbteJXq-rOwT7r6dlXq1rDSPgL6hoO2djKoregMZZIWx8WZjadMI9fnTKjTDOCXg/exec"

        def fetch_api_list(url):
            try:
                # 🎯 戰術判定：若是證交所 (上市) 網址，啟動 Google 跳板隱形滲透
                if "openapi.twse.com.tw" in url:
                    request_url = f"{GAS_URL}?url={url}"
                else:
                    request_url = url # 上櫃 (TPEX) 不會擋，直接連線

                res = requests.get(request_url, headers=headers, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list): return data
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list): return v
            except Exception as e: 
                print(f"⚠️ API 請求異常 ({url}): {e}", flush=True)
            return []


        # 1. 抓取營收
        twse_data = fetch_api_list("https://openapi.twse.com.tw/v1/opendata/t187ap05_L")
        for d in twse_data: d["市場別"] = "上市"
        time.sleep(0.5)

        tpex_data = fetch_api_list("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O")
        for d in tpex_data: d["市場別"] = "上櫃"
        time.sleep(0.5)
        
        all_data = twse_data + tpex_data
        
        # 2. 抓取 EPS、季營收、EPS期別 (💥 加入萬能模糊掃描)
        eps_map = {}
        eps_period_map = {}
        q_rev_map = {}
        
        def extract_eps_info(e):
            c = ""
            for k in ["公司代號", "SecuritiesCompanyCode", "Code", "code"]:
                if k in e: c = str(e[k]).strip(); break
            if not c: return
            
            eps = "-"
            for k in ["基本每股盈餘（元）", "基本每股盈餘(元)", "基本每股盈餘", "EPS", "eps"]:
                if k in e: eps = str(e[k]).strip(); break
                    
            y = ""; q = ""
            for k in ["年度", "year", "Year"]:
                if k in e: y = str(e[k]).strip(); break
            for k in ["季別", "quarter", "Quarter", "Q"]:
                if k in e: q = str(e[k]).strip(); break
                
            period = f"{y}Q{q}" if y and q else "-"
            
            q_rev = "-"
            for k in ["營業收入", "Revenue", "revenue"]:
                if k in e: q_rev = str(e[k]).strip(); break
            
            if eps != "-": eps_map[c] = eps
            if period != "-": eps_period_map[c] = period
            if q_rev != "-": q_rev_map[c] = q_rev

        for e in fetch_api_list("https://openapi.twse.com.tw/v1/opendata/t187ap14_L"): extract_eps_info(e)
        time.sleep(0.5)
        for e in fetch_api_list("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O"): extract_eps_info(e)
        time.sleep(0.5)

        # 3. 抓取本益比 (💥 加入萬能大小寫相容)
        pe_map = {}
        for p in fetch_api_list("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"):
            c = str(p.get("Code", "")).strip()
            for k in ["PEratio", "PERatio", "PeRatio", "本益比"]:
                if k in p: pe_map[c] = str(p[k]).strip(); break
        time.sleep(0.5)
        
        for p in fetch_api_list("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"):
            c = ""
            for k in ["SecuritiesCompanyCode", "公司代號", "Code"]:
                if k in p: c = str(p[k]).strip(); break
            if c:
                for k in ["PERatio", "PEratio", "PeRatio", "本益比"]:
                    if k in p: pe_map[c] = str(p[k]).strip(); break
        time.sleep(0.5)

        # 4. 抓取全市場今日收盤價與起漲價
        price_map = {}
        chg_pct_map = {}
        open_map = {}
        
        for p in fetch_api_list("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"):
            c = str(p.get("Code", "")).strip()
            try:
                cp = float(p.get("ClosingPrice", 0))
                cv = float(p.get("Change", 0))
                op = str(p.get("OpeningPrice", "-"))
                prev = cp - cv
                pct = round((cv / prev) * 100, 2) if prev > 0 else 0
                price_map[c] = f"{cp:.2f}"
                chg_pct_map[c] = f"{pct}"
                open_map[c] = op if op.strip() != "" else "-"
            except: pass
        time.sleep(0.5)
                
        for p in fetch_api_list("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"):
            c = ""
            for k in ["SecuritiesCompanyCode", "公司代號", "Code"]:
                if k in p: c = str(p[k]).strip(); break
            if c:
                try:
                    cp = float(p.get("Close", 0))
                    cv = float(p.get("Change", 0))
                    op = str(p.get("Open", "-"))
                    prev = cp - cv
                    pct = round((cv / prev) * 100, 2) if prev > 0 else 0
                    price_map[c] = f"{cp:.2f}"
                    chg_pct_map[c] = f"{pct}"
                    open_map[c] = op if op.strip() != "" else "-"
                except: pass


        # ==========================================================
        # 👇 動作 1 (修正版)：抓取證交所官方月均價 (20MA近似值)
        # ==========================================================
        ma20_map = {}
        for p in fetch_api_list("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"):
            c = str(p.get("Code", "")).strip()
            # 官方正確的月均價欄位名稱為 MonthlyAveragePrice
            ma20_map[c] = str(p.get("MonthlyAveragePrice", "-")).strip()
        time.sleep(0.5)

        # ==========================================================
        # 👆 👆 👆 動作 1：插入結束 👆 👆 👆
        # ==========================================================



        # ==========================================================
        # 💥 動作 1.5 (本機算力流)：讀取統帥從本機送上來的 pCloud 上櫃均線補給包
        # ==========================================================
        try:
            # 加入時間戳防止雲端快取抓到舊檔
            pcloud_ma20_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/ma20_cache.json?t={int(time.time())}"
            res_ma20 = requests.get(pcloud_ma20_url, headers=headers, timeout=5)
            if res_ma20.status_code == 200:
                local_ma20_data = res_ma20.json()
                # 將本機算出來的數值，融合進字典中 (不覆蓋已有的上市準確資料)
                for code, val in local_ma20_data.items():
                    if code not in ma20_map or ma20_map[code] == "-":
                        ma20_map[code] = val
                print(f"✅ [本機支援成功] 成功從 pCloud 讀取並融合了 {len(local_ma20_data)} 筆均線資料！", flush=True)
        except Exception as e:
            print(f"⚠️ [本機支援未連線] 無法讀取 pCloud 均線補給包: {e}", flush=True)
        # ==========================================================


        temp_focus = []
        temp_full = []
        
        for item in all_data:
            code = str(item.get("公司代號", "")).strip()
            if not code: continue
            
            period = item.get("資料年月", "") 
            raw_date = item.get("出表日期", "-") 
            
            # 強制將分頁六的資料日期，更新為系統最新掃描的今天日期
            import datetime
            data_date = datetime.datetime.now().strftime("%Y-%m-%d")

            rev_current = item.get("營業收入-當月營收", item.get("當月營收", "0"))
            mom = item.get("營業收入-上月比較增減(%)", item.get("上月比較增減(%)", "0"))
            yoy = item.get("營業收入-去年同月增減(%)", item.get("去年同月增減(%)", "0"))
            
            is_new_release = False
            if revenue_history_cache.get(code) is not None and revenue_history_cache.get(code) != period:
                is_new_release = True
            revenue_history_cache[code] = period
            
            pe_str = pe_map.get(code, "-")
            eps_str = eps_map.get(code, "-")
            eps_period_str = eps_period_map.get(code, "-")
            close_str = price_map.get(code, "-")


            # 👇 動作 2：在這裡補上演算法 👇
            # 💥 神級虧轉盈判定演算法 (本季賺錢，但四季總和為負無本益比)
            is_turnaround = False
            try:
                if eps_str != "-" and float(eps_str) > 0 and pe_str == "-":
                    is_turnaround = True
            except:
                pass
            
            ma20_str = ma20_map.get(code, "-")
            # 👆 動作 2 結束 👆


            # 💥 終極雙向逆向演算：你沒給資料，我系統自己算！
            # 1. 政府沒給 EPS，用「收盤價 ÷ 本益比」硬算！
            if eps_str == "-" and pe_str != "-" and close_str != "-":
                try:
                    pe_val = float(pe_str)
                    close_val = float(close_str)
                    if pe_val > 0:
                        eps_str = f"{(close_val / pe_val):.2f}"
                except: pass
                
            # 💥 2. 政府沒給本益比，用「收盤價 ÷ EPS」硬算！
            if pe_str == "-" and eps_str != "-" and close_str != "-":
                try:
                    eps_val = float(eps_str)
                    close_val = float(close_str)
                    if eps_val > 0:
                        pe_str = f"{(close_val / eps_val):.2f}"
                except: pass

            # 💥 3. 容錯填補：如果算出了 EPS 但期別漏了，補上文字
            if eps_period_str == "-" and eps_str != "-":
                eps_period_str = "最新財報"

            stock_info = {
                "code": code,
                "name": item.get("公司名稱", ""),
                "ind": item.get("產業別", "未知產業"),
                "market": item.get("市場別", "未知"),
                "period": period,
                "data_date": data_date,             
                "revenue": rev_current,
                "q_rev": q_rev_map.get(code, "-"),  
                "mom": mom,
                "yoy": yoy,
                "eps": eps_str,
                "eps_period": eps_period_str,       
                "pe": pe_str,
                "close": close_str,
                "open": open_map.get(code, "-"),
                "chg": chg_pct_map.get(code, "-"),
                "is_new": is_new_release,
                # 👇 動作 3：補上這兩行 👇
                "turnaround": is_turnaround,  # 💥 新增虧轉盈標記
                "ma20": ma20_str              # 💥 新增 20MA 數值
            }
            
            temp_full.append(stock_info)
            if is_new_release: temp_focus.append(stock_info)
                
        fundamental_full_cache.clear()
        fundamental_full_cache.extend(temp_full)
        if len(temp_focus) > 0: fundamental_focus_cache = temp_focus

        current_cache = read_cache()
        current_cache["fundamental_focus"] = fundamental_focus_cache
        current_cache["fundamental_full"] = fundamental_full_cache
        update_cache(current_cache)
        print("✅ [基本面引擎] 財報與股價數據已成功寫入！", flush=True)
        
    except Exception as e:
        print(f"❌ [基本面引擎] 發生嚴重錯誤: {e}", flush=True)

# 每 60 分鐘掃描一次政府資料庫
def fundamental_patrol_loop():
    while True:
        fetch_fundamental_data()
        fetch_material_info() # 💥 放狗咬人！抓取重大訊息
        
        # 💥 將獵犬抓到的資料，寫入 live_data_cache.json 給前端讀取
        current_cache = read_cache()
        current_cache["self_assessed_news"] = self_assessed_cache
        update_cache(current_cache)
        
        time.sleep(3600)

# ==========================================================
# 📊 4. 雙通道個股即時行情分析中心
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0"}
    yahoo_ma = ""; yahoo_price = ""
    try:
        if stock_code == "^TWII":
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?range=2mo&interval=1d"
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
                
                if valid_vols[-1] > vol_5ma * 1.5: 
                    big_player = "🔥大戶放量攻擊"
                elif valid_vols[-1] < vol_5ma * 0.7: 
                    big_player = "🧊量縮散戶觀望"
                else: 
                    big_player = "⚖️籌碼動能平穩"
                
                yahoo_ma = f"📊均線數值(5/10/20): {ma5}, {ma10}, {ma20}\n扣抵價位: {kd5}, {kd10}, {kd20}\n籌碼動向: {big_player}"
            else: 
                yahoo_ma = "均線資料庫不足"
    except Exception as e: 
        yahoo_ma = "備援線路連線受阻"
        yahoo_price = "⚠️報價抓取失敗"

    return f"{yahoo_price}\n{yahoo_ma}"

# ==========================================================
# 🚀 5. 全市場真實資金流向排行與精選戰報交集過濾引擎
# ==========================================================
def execute_force_refresh():
    headers = {"User-Agent": "Mozilla/5.0"}
    # 💥 預先定義所有變數，防止 NameError
    twii_chg = 0.0
    true_market_top_ind = "半導體"
    true_market_top_chg = 0.0
    ai_payload = [] # 確保它永遠存在，即使後面出錯也不會崩潰
    
    try:
        # 1. 大盤偵蒐
        try:
            yh_res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?range=1d&interval=1d", headers=headers, timeout=5).json()
            meta = yh_res['chart']['result'][0]['meta']
            twii_chg = ((meta['regularMarketPrice'] - meta['chartPreviousClose']) / meta['chartPreviousClose']) * 100
        except: pass

        # 2. 資金流向排行 (💥 升級：台灣證交所官方 API 直連引擎)
        try:
            # 官方各類股指數代碼對照表
            target_indices = {
                "t24": "半導體", "t25": "電腦週邊", "t28": "電子零組件", "t27": "通信網路",
                "t26": "光電業", "t22": "生技醫療", "t17": "金融保險", "t10": "鋼鐵工業",
                "t21": "航運業", "t20": "建材營造"
            }
            # 組合雷達頻道
            channels = "|".join([f"tse_{code}.tw" for code in target_indices.keys()])
            api_url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={channels}&_={int(time.time() * 1000)}"
            
            res = requests.get(api_url, timeout=5).json()
            leaderboard = {}
            
            if 'msgArray' in res:
                for data in res['msgArray']:
                    code = data.get('c') # 取得官方代號
                    name = target_indices.get(code)
                    z_str, y_str = data.get('z', '-'), data.get('y', '-')
                    
                    if name and z_str != '-' and y_str != '-':
                        z, y = float(z_str), float(y_str)
                        if y > 0:
                            # 精準計算漲跌幅
                            leaderboard[name] = round(((z - y) / y) * 100, 2)
                            
            if leaderboard:
                # 排序找出真正的資金主攻榜首
                top = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[0]
                true_market_top_ind = top[0]
                true_market_top_chg = top[1]
        except: pass    

        # 3. 戰報對齊與快取寫入 (技術面監控名單保持運作)
        json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={time.time()}"
        res_json = requests.get(json_url, headers=headers, timeout=10)
        
        if res_json.status_code == 200:
            raw_data = res_json.json()
            if isinstance(raw_data, list):
                # 💥 修正：進行「資金主攻族群」與「監控名單」的交集篩選
                matched_items = []
                for item in raw_data:
                    if "代碼" not in item: continue
                    # 抓取該股票的產業別 (相容 'ind' 或 '產業' 欄位)
                    stock_ind = str(item.get("ind", item.get("產業", "")))
                    if true_market_top_ind in stock_ind:
                        matched_items.append(item)
                
                # 如果交集成功，跑馬燈只顯示主攻部隊；若無交集，為避免空窗，顯示前 15 檔
                target_list = matched_items if len(matched_items) > 0 else raw_data[:15]
                ai_payload = [{"name": item.get("商品", item.get("代碼")), "code": item.get("代碼"), "z": 0.0, "chg": 0.0} for item in target_list]
            
            flow_text = f"🔥 資金主攻：【{true_market_top_ind}】({true_market_top_chg}%)"
            news_headline = fetch_cnyes_news()
            display_stocks = " ｜ ".join([f"{s['name']}({s['code']})" for s in ai_payload]) if ai_payload else "📡 監控中..."
            
            # 💥 階段一：將最新的 focus 與 full 財報數據，一併注入快取給前端 UI 讀取！
            update_cache({
                "fundsText": f"📊 加權指數 {round(twii_chg, 2)}% ｜ {flow_text} ｜ {news_headline}",
                "stocksText": display_stocks,
                "fundamental_focus": fundamental_focus_cache,
                "fundamental_full": fundamental_full_cache,
                "intraday_alerts": intraday_breakout_cache[:10] # 💥 裝載當沖快訊彈藥 (只保留最新10筆)
            })
            print("✅ [戰術回報] 變數防護版寫入成功，財報數據已同步封裝！")
            
    except Exception as e:
        print(f"❌ 致命錯誤: {e}")

# ==========================================================
# 📡 6. Webhook 通道與戰情接口
# ==========================================================
@app.route("/", methods=['GET'])
def home(): 
    return "前線看盤伺服器：交易連線狀態正常，常駐清醒中！"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: 
        handler.handle(body, signature)
    except InvalidSignatureError: 
        abort(400)
    return 'OK'

@app.route("/live_data.json", methods=['GET'])
def get_live_data():
    global self_assessed_cache
    
    # 💥 偵測：記憶體是空的，絕對不能卡死網頁！派背景線程去處理！
    if not self_assessed_cache or len(self_assessed_cache) == 0:
        print("⚠️ [緊急戰略] 派遣背景 AI 獵犬出動，避免網頁卡死...", flush=True)
        
        # 1. 先塞入一筆暫時的公告，安撫網頁端，這樣網頁就能瞬間載入成功！
        self_assessed_cache = [{
            "date": "剛剛", "code": "SYS", "name": "戰情室", 
            "subject": "📡 AI 獵犬剛甦醒，正在後台排隊解讀中...", 
            "desc": "", "eps": 0.0, "ai_rating": "⚪ 系統載入中", 
            "ai_analysis": "為了規避 Google 防火牆，AI 需要慢慢排隊讀取財報。請統帥先看別的數據，約 1~2 分鐘後重新整理網頁即可看到最新情報！",
            "last_year_eps": "-", "yoy_eps": "-", "turnaround": "-", "est_yearly": "-"
        }]
        
        # 2. 啟動背景獨立執行！獵犬在後台慢慢跑，完全不影響網頁運作！
        import threading
        threading.Thread(target=fetch_material_info, daemon=True).start()
        
    # 讀取現有快取，並將獵犬的情資寫入
    current_cache = read_cache()
    current_cache["self_assessed_news"] = self_assessed_cache
    
    # 順便存檔更新 (確保母艦內部資料同步)
    update_cache(current_cache)
    
    # 💥 建立回應，並保留統帥原本的 CORS 與反快取防護盾
    response = make_response(jsonify(current_cache))
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    
    return response


# ==========================================================
# 📡 中控台 VIP 權限管理通道 (供 main.py 讀寫與打勾)
# ==========================================================
@app.route("/vips", methods=['GET', 'POST'])
def manage_vips():
    if request.method == 'GET':
        return jsonify(read_vips())
    elif request.method == 'POST':
        data = request.json
        if data is not None:
            update_vips(data)
            return jsonify({"status": "success", "msg": "✅ 統帥權限已成功同步至雲端母艦！"})
        return jsonify({"status": "error"}), 400


# ==========================================================
# 🛡️ 專屬群組進駐雷達：自動捕捉並綁定 Group ID
# ==========================================================
@handler.add(JoinEvent)
def handle_join(event):
    if isinstance(event.source, SourceGroup):
        group_id = event.source.group_id
        print(f"✅ 成功潛入群組！群組 ID 為: {group_id}", flush=True)
        
        welcome_msg = (
            "🫡 報告統帥！股海觀浪戰情雷達已成功進駐本群組！\n\n"
            "🎯 本群組的專屬通訊代號為：\n"
            f"{group_id}\n\n"
            "請將此代號複製並記錄下來，日後只要統帥將此代號寫入中控台程式碼的發射目標中，每日戰報與緊急軍令就會全自動空投至此群組！"
        )
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_msg)
        )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    user_id = event.source.user_id  # 💥 瞬間攔截發送者的隱藏 User ID
    
    # 🎯 隱形招募處：攔截通關密語
    if user_msg == "雷達開通":
        try:
            profile = line_bot_api.get_profile(user_id)
            user_name = profile.display_name
        except:
            user_name = "未知特戰隊員"

        vips = read_vips()
        if user_id not in vips:
            # 💥 預設：新兵報到時，三個權限預設全開，統帥後續可從中控台關閉
            vips[user_id] = {
                "name": user_name,
                "perms": {"1min": True, "5min": True, "report": True}
            }
            update_vips(vips)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ 歡迎歸隊，{user_name}！\n您的專屬「當沖雷達與戰報」已成功列入發射名單。\n(※各項接收權限將由統帥於中控台統一調度)"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠️ {user_name}，您的通訊座標已經在作戰名單中，無須重複開通！"))
        return

    # 📊 原本的大盤或雷達查詢邏輯
    if user_msg == "大盤" or user_msg == "雷達":
        cache_data = read_cache()
        reply_text = f"{cache_data.get('fundsText', '')}\n\n精選標的流向：\n{cache_data.get('stocksText', '')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text[:5000]))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📡 看盤伺服器已收到指令：'{user_msg}'。即時數據定時同步中。"))


# ==========================================================
# 🌟 7. 🚀 雲端全時相決策中心 (靜默快取版 - 已廢除定時廣播)
# ==========================================================
def market_patrol_loop():
    import time
    import threading

    print("📡 [總部軍令] 靜默偵蒐引擎啟動，專心支援前端快取 (定時廣播已拔除)...", flush=True)
    # 開機時強制刷新一次大盤與資金流向
    threading.Thread(target=lambda: execute_force_refresh()).start()

    while True:
        try:
            # 💥 戰術變更：廢除所有定時的 LINE 廣播！
            # 僅保留每 300 秒 (5 分鐘) 在背景執行一次 execute_force_refresh() 
            # 讓網頁版戰情室的報價與資金流向保持最新狀態。
            time.sleep(300) 
            execute_force_refresh()
            
        except Exception as e:
            print(f"⚠️ 靜默巡邏異常: {e}", flush=True)
            time.sleep(30)



# ==========================================================
# ⚡ 8. 專屬當沖連續掃描引擎 (帶有盤中時間鎖定)
# ==========================================================
def continuous_radar_loop():
    print("📡 [當沖雷達] 雙週期共振掃描引擎啟動，直連證交所待命中...")
    import time
    import datetime
    import requests
    while True:
        try:
            now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute
            
            # 🔒 09:00 到 13:30 之間雷達才運作
            if not is_weekend and (900 <= current_time_num <= 1330):
                
                headers = {"User-Agent": "Mozilla/5.0"}
                json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={int(time.time())}"
                res_json = requests.get(json_url, headers=headers, timeout=5)
                
                if res_json.status_code == 200:
                    raw_data = res_json.json()
                    
                    if isinstance(raw_data, list):
                        target_dict = {str(item.get("代碼")): {"name": item.get("商品", item.get("代碼"))} for item in raw_data if "代碼" in item}
                    else:
                        target_dict = raw_data
                        
                    for code, info in target_dict.items():
                        name = info.get("name", code)
                        # 🎯 抓取這檔股票的產業別 (相容 ind 或 產業 欄位)
                        ind = str(info.get("ind", info.get("產業", "未知")))
                        
                        # 🎯 將 ind 一併傳送給雷達
                        alert_msg = detect_intraday_breakout(code, name, ind)
                        
                        if alert_msg and alert_msg not in intraday_breakout_cache:
                            intraday_breakout_cache.insert(0, alert_msg)
                            
                            current_cache = read_cache()
                            current_cache["intraday_alerts"] = intraday_breakout_cache[:10]
                            update_cache(current_cache)
                            
                            # 💥 讀取最新權限名單，準備精準發射！
                            try:
                                from linebot.models import TextSendMessage
                                vips = read_vips()
                                target_ids = []
                                
                                # 🔍 過濾權限：如果是「破曉初升(安全區)」，需要有 5min 權限
                                # 🔍 過濾權限：如果是「極限動能(高風險)」，需要有 1min 權限
                                for uid, info in vips.items():
                                    perms = info.get("perms", {})
                                    if "極限動能" in alert_type:
                                        if perms.get("1min", False): target_ids.append(uid)
                                    else:
                                        if perms.get("5min", False): target_ids.append(uid)

                                if target_ids:
                                    # Multicast 最大上限 500 人
                                    line_bot_api.multicast(target_ids, TextSendMessage(text=f"🚨 【戰情室快訊】\n{alert_msg}"))
                                    print(f"✅ 已對 {len(target_ids)} 名擁有權限之隊員精準群發：{name}")
                                else:
                                    print(f"⚠️ 掃到 {name}，但目前無人符合該項雷達權限。")
                            except Exception as e:
                                print(f"⚠️ LINE 精準多播失敗: {e}")
                        
                        time.sleep(1) # 1 秒測 1 檔，完美閃避證交所封鎖
            else:
                pass
                
        except Exception as e:
            print(f"雷達巡邏異常: {e}")
        
        time.sleep(60) # 每分鐘掃描一次




# 啟動盤中巡邏引擎
threading.Thread(target=market_patrol_loop, daemon=True).start()
# 啟動基本面情報掃描引擎
threading.Thread(target=fundamental_patrol_loop, daemon=True).start()
# 💥 啟動當沖雷達連續掃描引擎
threading.Thread(target=continuous_radar_loop, daemon=True).start()

class StandaloneApplication:
    def __init__(self, app, options=None): 
        self.options = options or {}
        self.application = app
    def run(self):
        import gunicorn.app.base
        class FlaskGunicornApp(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options): 
                self.options = options
                self.application = app
                super().__init__()
            def load_config(self):
                for key, value in self.options.items(): 
                    self.cfg.set(key.lower(), value)
            def load(self): 
                return self.application
        FlaskGunicornApp(self.application, self.options).run()

# 💓 戰情室心跳維持引擎：每 5 分鐘對自己戳一下，防止被 Render 強制休眠
def keep_alive():
    while True:
        try:
            requests.get("https://stock-line-bot-c8em.onrender.com")
            print("💓 心跳送出，戰情室保持清醒中...")
        except:
            pass
        time.sleep(300) # 每 300 秒 (5分鐘) 戳一次

# 啟動心跳線
threading.Thread(target=keep_alive, daemon=True).start()


# ==========================================================
# 💬 戰情大廳：WebSocket 即時通訊樞紐
# ==========================================================
@socketio.on('connect')
def handle_connect():
    print("✅ [戰情大廳] 一名戰友已成功連線進入大廳！", flush=True)

@socketio.on('send_message')
def handle_client_message(data):
    # 攔截戰友發送的訊息
    sender = data.get('sender', '游擊兵')
    msg = data.get('msg', '')
    print(f"💬 [大廳廣播] {sender}: {msg}", flush=True)
    
    # 瞬間將訊息無延遲空投給所有連線中的戰友
    emit('receive_message', {'sender': sender, 'msg': msg}, broadcast=True)


if __name__ == "__main__":
    print("🚀 戰情室與雷達掃描引擎全面啟動 (含 WebSocket 即時通訊裝甲)...", flush=True)
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
