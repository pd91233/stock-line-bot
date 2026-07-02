# -*- coding: utf-8 -*-
# =========================================================
# 📡 股海觀浪雲端探子母艦：防彈完全體戰情室 V100.0 (階段一：全市場基本面狙擊)
# 開發代號：botmain.py (雲端守護協定 - 100% 完整解碼不閹割版)
# =========================================================
from flask import Flask, request, abort, jsonify, make_response
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
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
        headers = {"User-Agent": "Mozilla/5.0"}
        class_res = requests.get("https://tw.stock.yahoo.com/class", headers=headers, timeout=8)
        soup = BeautifulSoup(class_res.text, 'html.parser')
        target_industries = ["半導體", "電腦週邊", "電子零組件", "通信網路", "光電業", "生技醫療", "金融保險", "鋼鐵工業", "航運業", "建材營造"]
        leaderboard = {}
        for ind in target_industries:
            ind_element = soup.find(text=re.compile(ind))
            if ind_element:
                pct_match = re.search(r'([+-]?\d+\.\d+)%', ind_element.find_parent().get_text())
                if pct_match: leaderboard[ind] = float(pct_match.group(1))
        if leaderboard:
            top = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[0]
            return f"🔥 資金主攻：【{top[0]}】({top[1]}%)"
    except: pass
    return "🔥 資金主攻：【半導體】"


app = Flask(__name__)

# 🛡️ 戰術快取配置
CACHE_FILE = "live_data_cache.json"

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
# ⚡ [升級修復版] 當沖雷達：5分K 盤中創高爆量突破偵測引擎
# ==========================================================
intraday_breakout_cache = [] # 儲存最新的爆量快訊

def detect_intraday_breakout(code, name):
    try:
        import requests
        import datetime
        headers = {"User-Agent": "Mozilla/5.0"}
        # 抓取近一天的 5 分K 數據
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?range=1d&interval=5m"
        res = requests.get(url, headers=headers, timeout=3).json()
        
        # 雙市場容錯切換 (上市轉上櫃)
        if not res.get('chart', {}).get('result'):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TWO?range=1d&interval=5m"
            res = requests.get(url, headers=headers, timeout=3).json()
            if not res.get('chart', {}).get('result'): return None
            
        result = res['chart']['result'][0]
        volumes = result['indicators']['quote'][0]['volume']
        closes = result['indicators']['quote'][0]['close']
        highs = result['indicators']['quote'][0]['high']
        
        # 過濾空值
        valid_vols = [v for v in volumes if v is not None]
        valid_closes = [c for c in closes if c is not None]
        valid_highs = [h for h in highs if h is not None]
        
        if len(valid_vols) > 5 and len(valid_highs) > 5:
            current_vol = valid_vols[-1]
            avg_vol_5 = sum(valid_vols[-6:-1]) / 5  # 前 25 分鐘均量
            current_px = valid_closes[-1]
            prev_px = valid_closes[-2]
            
            # 戰術升級：找出「今天開盤到上一根 K 棒為止」的盤中最高價
            intraday_high_before_now = max(valid_highs[:-1])
            
            # 條件 1：單根量大於前段均量 3 倍 (爆量)
            # 條件 2：收盤價大於上一根 (推升)
            # 條件 3：最新價突破今日前面的盤中高點 (創日高突破)
            if avg_vol_5 > 0 and current_vol > (avg_vol_5 * 3) and current_px > prev_px:
                if current_px >= intraday_high_before_now:
                    
                    # 💥 淨化 1：時區校正 (強制轉換為 UTC+8 台灣時間)
                    tz = datetime.timezone(datetime.timedelta(hours=8))
                    current_time = datetime.datetime.now(tz).strftime("%H:%M")
                    
                    # 💥 淨化 2：價格精準化 (四捨五入到小數點後 2 位)
                    safe_px = round(current_px, 2)
                    
                    # 💥 淨化 3：成交量微縮 (將 Yahoo 的股數除以 1000 轉換為張數)
                    safe_vol = int(current_vol / 1000)
                    
                    # 回傳完美格式的作戰電報 (廣播與推播會交由下方的 continuous_radar_loop 處理)
                    return f"[{current_time}] ⚡ {name}({code}) 帶量突破盤中新高！現價 {safe_px} (爆量 {safe_vol} 張)"
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
    global self_assessed_cache
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
                
                # 只要符合條件，立刻呼叫 Gemini 進行深度解析！
                if eps_val != 0.0 or "注意" in subject:
                    
                    print(f"🤖 [AI 啟動] 正在分析 {code} {name} 的重大訊息...", flush=True)
                    
                    ai_rating = "⚪ 中性看待"
                    ai_analysis = "系統正在讀取原始公告..."
                    last_year_eps = "-"
                    yoy_eps = "-"
                    turnaround = "-"
                    est_yearly = "-"
                    
                    try:
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
                        
                    except Exception as e:
                        print(f"⚠️ [AI 解析失敗] {e}", flush=True)

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

        def fetch_api_list(url):
            try:
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list): return data
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list): return v
            except: pass
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

        # 2. 資金流向排行
        try:
            class_res = requests.get("https://tw.stock.yahoo.com/class", headers=headers, timeout=8)
            if class_res.status_code == 200:
                soup = BeautifulSoup(class_res.text, 'html.parser')
                target_industries = ["半導體", "電腦週邊", "電子零組件", "通信網路", "光電業", "生技醫療", "金融保險", "鋼鐵工業", "航運業", "建材營造"]
                leaderboard = {}
                for ind in target_industries:
                    ind_element = soup.find(text=re.compile(ind))
                    if ind_element:
                        pct_match = re.search(r'([+-]?\d+\.\d+)%', ind_element.find_parent().get_text())
                        if pct_match: leaderboard[ind] = float(pct_match.group(1))
                if leaderboard:
                    top = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[0]
                    true_market_top_ind, true_market_top_chg = top[0], top[1]
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
    
    # 💥 偵測：如果記憶體是空的 (代表母艦剛睡醒)，立刻強制出動獵犬！
    if not self_assessed_cache or len(self_assessed_cache) == 0:
        print("⚠️ [緊急戰略] 母艦剛甦醒且無歷史情報，強制啟動解碼獵犬...", flush=True)
        fetch_material_info()
        
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    if user_msg == "大盤" or user_msg == "雷達":
        cache_data = read_cache()
        reply_text = f"{cache_data.get('fundsText', '')}\n\n精選標的流向：\n{cache_data.get('stocksText', '')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text[:5000]))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📡 看盤伺服器已收到指令：'{user_msg}'。即時數據定時同步中。"))

# ==========================================================
# 🌟 7. 🚀 雲端全時相決策中心
# ==========================================================
def market_patrol_loop():
    last_triggered_date = ""
    triggered_phases = set()
    
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
                    continue

                json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={timestamp_v}"
                res_json = requests.get(json_url, timeout=5)
                
                if res_json.status_code == 200 and res_json.text:
                    raw_data = res_json.json()
                    if raw_data:
                        if isinstance(raw_data, list):
                            monitor_data = {str(item.get("代碼")): {"name": item.get("商品", item.get("代碼")), "ind": str(item.get("ind", item.get("產業", "")))} for item in raw_data if "代碼" in item}
                        else:
                            monitor_data = raw_data

                        headers = {"User-Agent": "Mozilla/5.0"}
                        req = requests.Session()
                        
                        twii_chg = 0.0
                        try:
                            yh_res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?range=1d&interval=1d", headers=headers, timeout=5).json()
                            yh_meta = yh_res['chart']['result'][0]['meta']
                            curr_idx = yh_meta['regularMarketPrice']
                            prev_idx = yh_meta['chartPreviousClose']
                            if prev_idx > 0: 
                                twii_chg = ((curr_idx - prev_idx) / prev_idx) * 100
                        except: 
                            pass

                        # 💥 1. 建立戰報標題
                        broadcast_msg = f"{phase_title}\n時間：{now.strftime('%H:%M')} (大盤即時：{round(twii_chg, 2)}%)\n====================\n"
                        ai_payload = []
                        alert_stocks_text = "" # 💥 2. 準備收集異常個股名單

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
                                        veto_reason = f"大盤跌破防線，請嚴守 {ma5_val}元 或 {ma10_val}元 停損點"

                                    # 💥 3. 將異常動態寫入戰報內文
                                    if veto_triggered:
                                        alert_stocks_text += f"⚠️ {name}: {veto_reason}\n"
                                    elif is_overheated_tr:
                                        alert_stocks_text += f"🔥 {name}: 漲幅 {chg}%, 預估量達 {v_ratio} 倍 (短線過熱)\n"

                                    stock_payload = {
                                        "code": code, "name": name, "type": info.get('type', 'core'),
                                        "ind": info.get('ind', ''), 
                                        "z": z, "chg": chg, "vwap": vwap, "v_ratio": v_ratio, "shadow_pct": shadow_pct,
                                        "ma5": ma5_val, "ma10": ma10_val, "ma20": info.get('ma20', z), "kd5": info.get('kd5', z),
                                        "veto_triggered": veto_triggered, "veto_reason": veto_reason
                                    }
                                    ai_payload.append(stock_payload)

                                time.sleep(1) 
                            except: 
                                continue

                        # 💥 4. 準備發射定時戰報！
                        if alert_stocks_text == "":
                            alert_stocks_text = "✅ 目前監控名單內無異常暴動或跌破防線之標的。\n"
                        
                        broadcast_msg += alert_stocks_text

                        try:
                            from linebot.models import TextSendMessage
                            line_bot_api.broadcast(TextSendMessage(text=broadcast_msg))
                            print(f"✅ 已成功發送定時戰報：{current_phase}")
                        except Exception as push_err:
                            print(f"⚠️ 定時戰報發射失敗: {push_err}")


                        # 5. 更新前端 JSON 快取 (保留您的交集過濾邏輯)
                        if len(ai_payload) > 0:
                            flow_text = get_market_leader()
                            match = re.search(r'【(.*?)】', flow_text)
                            top_ind = match.group(1) if match else "半導體"
                            
                            matched_payload = [s for s in ai_payload if top_ind in s.get('ind', '')]
                            final_display_list = matched_payload if len(matched_payload) > 0 else ai_payload[:15]

                            news_headline = fetch_cnyes_news()
                            update_cache({
                                "fundsText": f"📊 加權指數 {round(twii_chg, 2)}% ｜ {flow_text} ｜ {news_headline}",
                                "stocksText": " ｜ ".join([f"{s['name']}({s['code']}) {s['z']}元 ({'+' if s['chg']>0 else ''}{s['chg']}%)" for s in final_display_list]),
                                "fundamental_focus": fundamental_focus_cache,
                                "fundamental_full": fundamental_full_cache,
                                "intraday_alerts": intraday_breakout_cache[:10] 
                            })

                time.sleep(60)


# ==========================================================
# ⚡ 8. [新增] 專屬當沖連續掃描引擎 (每分鐘無情掃描)
# ==========================================================
def continuous_radar_loop():
    print("📡 [當沖雷達] 連續掃描引擎啟動，每 60 秒巡邏一次...")
    while True:
        try:
            # 抓取您的監控清單
            headers = {"User-Agent": "Mozilla/5.0"}
            json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={int(time.time())}"
            res_json = requests.get(json_url, headers=headers, timeout=5)
            
            if res_json.status_code == 200:
                raw_data = res_json.json()
                
                for item in raw_data:
                    if "代碼" not in item: continue
                    code = str(item["代碼"])
                    name = item.get("商品", code)
                    
                    # 進行爆量偵測
                    alert_msg = detect_intraday_breakout(code, name)
                    

                    # 如果有快訊，且還沒報過
                    if alert_msg and alert_msg not in intraday_breakout_cache:
                        intraday_breakout_cache.insert(0, alert_msg)
                        
                        # 1. 寫入快取讓網頁跑馬燈更新
                        current_cache = read_cache()
                        current_cache["intraday_alerts"] = intraday_breakout_cache[:10]
                        update_cache(current_cache)
                        
                        # 2. 💥 LINE 實時全頻群發
                        try:
                            from linebot.models import TextSendMessage
                            line_bot_api.broadcast(TextSendMessage(text=f"🚨 【戰情室快訊】\n{alert_msg}"))
                            print(f"✅ 已全頻群發快訊：{name}")
                        except Exception as e:
                            print(f"⚠️ LINE 群發失敗: {e}")
                    
                    time.sleep(1) # 避免對 Yahoo 發送太快被鎖定
        except Exception as e:
            print(f"雷達巡邏異常: {e}")
        
        time.sleep(60) # 💥 核心：每 60 秒必定重新掃描一次！



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



if __name__ == "__main__":
    options = {'bind': '0.0.0.0:10000', 'workers': 1, 'threads': 2, 'timeout': 120}
    StandaloneApplication(app, options).run()
    print("雷達掃描引擎已啟動")
