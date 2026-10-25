import eventlet
eventlet.monkey_patch()
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

    JoinEvent, SourceGroup, FlexSendMessage, BubbleContainer, BoxComponent, ButtonComponent

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


import csv

# ==========================================
# 📊 盤後戰情 CSV 資料庫自動記錄晶片 (不死鳥重生版 - 時差校正修復)
# ==========================================
import csv
import threading
import datetime
import time
import requests
import os

def get_today_csv_name():
    """💥 動態獲取台灣時間 (UTC+8) 的正確檔名，拒絕被開機時間鎖死"""
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    return f"trading_log_{datetime.datetime.now(tz_tw).strftime('%Y%m%d')}.csv"

def restore_csv_on_boot():
    """💥 浴火重生：開機時立刻去 pCloud 尋找今天遺失的紀錄檔並下載回本機"""
    csv_name = get_today_csv_name()
    try:
        public_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/{csv_name}?t={int(time.time())}"
        res = requests.get(public_url, timeout=5)
        if res.status_code == 200:
            with open(csv_name, 'wb') as f:
                f.write(res.content)
            print(f"✅ [浴火重生] 母艦重啟！已成功從 pCloud 救回今日斷點 CSV 戰績: {csv_name}", flush=True)
    except:
        pass

# 開機第一件事：嘗試找回記憶
restore_csv_on_boot()

def init_csv():
    """初始化 CSV 檔案標頭"""
    csv_name = get_today_csv_name()
    if not os.path.exists(csv_name):
        try:
            with open(csv_name, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Trigger_Time", "Stock_ID", "Stock_Name", "Time_Zone", 
                    "Ignition_Funds", "Price_Change_Pct", "Deviation_Rate", 
                    "System_Decision", "Suggested_Entry", "Stop_Loss_Line", 
                    "Close_Price", "Trade_Result"
                ])
        except Exception as e:
            print(f"⚠️ CSV 初始化失敗: {e}")

def backup_csv_to_pcloud_async():
    """背景小幫手：極速 Token 直連版 (含 pCloud JSON 除錯升級)"""
    def task():
        csv_name = get_today_csv_name()
        try:
            token = os.environ.get('PCLOUD_AUTH_TOKEN', '')
            folder_id = os.environ.get('PCLOUD_HISTORY_FOLDER_ID', '33133582905')
            if not token:
                print("⚠️ [背景備份] 找不到 PCLOUD_AUTH_TOKEN", flush=True)
                return
            if os.path.exists(csv_name):
                with open(csv_name, 'rb') as f_csv:
                    file_csv = {'file': (csv_name, f_csv, 'text/csv')}
                    res = requests.post(f"https://api.pcloud.com/uploadfile?auth={token}&folderid={folder_id}", files=file_csv, timeout=15)
                    
                    # 💡 解析 pCloud 的 JSON 回應，確保不是「假成功」
                    try:
                        res_json = res.json()
                        if res_json.get("result") == 0:
                            print(f"☁️ [背景備份] {csv_name} 成功寫入 pCloud 雲端！", flush=True)
                        else:
                            print(f"⚠️ [背景備份警告] pCloud 伺服器拒絕: {res_json}", flush=True)
                    except:
                        print(f"☁️ [背景備份] 上傳執行完畢！HTTP 狀態碼: {res.status_code}", flush=True)
        except Exception as e:
            print(f"⚠️ [背景備份出錯] 發生異常: {e}", flush=True)
            
    threading.Thread(target=task, daemon=True).start()

def log_event(data):
    """逐行追加寫入事件，並即時啟動雲端備份"""
    try:
        init_csv()
        csv_name = get_today_csv_name()
        with open(csv_name, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                data.get("time"), data.get("id"), data.get("name"), data.get("zone"),
                data.get("funds"), data.get("change_pct"), data.get("deviation"),
                data.get("decision"), data.get("entry"), data.get("stop_loss"),
                data.get("close_price", ""), data.get("result", "")
            ])
        
        # 本機寫入完成後，呼叫背景小幫手傳上 pCloud
        backup_csv_to_pcloud_async()
        
    except Exception as e:
        print(f"⚠️ CSV 寫入失敗: {e}")

init_csv()


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
# 🌐 全球跨國動態資金矩陣：24小時全景完全體爬蟲引擎 (含時間與戰報標籤)
# ==========================================================
MATRIX_CACHE_FILE = "global_matrix_cache.json"

def fetch_global_matrix_data():
    """ 24小時全天候抓取美股四大指數、ADR與十二大戰區龍頭即時數據 """
    tickers = {
        # 🌐 頂級天候儀表板
        "SOX": "^SOX", "IXIC": "^IXIC", "DJI": "^DJI", "INX": "^GSPC",
        "TSM": "TSM", "VIX": "^VIX", "DXY": "DX-Y.NYB", "US10Y": "^TNX",

        # ⚙️ 戰區一：半導體與晶片
        "NVDA": "NVDA", "AMD": "AMD", "INTC": "INTC", "QCOM": "QCOM", "AVGO": "AVGO",
        "ARM": "ARM", "TXN": "TXN", "NXPI": "NXPI",

        # 🖥️ 戰區二：AI 伺服器
        "SMCI": "SMCI", "DELL": "DELL", "VRT": "VRT", "HPE": "HPE", "ANET": "ANET",

        # 📦 戰區三：先進封裝與設備
        "ASML": "ASML", "AMAT": "AMAT", "LRCX": "LRCX", "KLAC": "KLAC", "TER": "TER",

        # 📡 戰區四：光通訊與網通
        "MRVL": "MRVL", "LITE": "LITE", "CSCO": "CSCO", "COHR": "COHR",

        # 🛰️ 戰區五：低軌衛星
        "ASTS": "ASTS", "IRDM": "IRDM", "LMT": "LMT", "RKLB": "RKLB",

        # 💾 戰區六：記憶體
        "MU": "MU", "WDC": "WDC", "STX": "STX",

        # ☁️ 戰區七：雲端巨頭與軟體
        "AAPL": "AAPL", "GOOG": "GOOG", "META": "META", "AMZN": "AMZN",
        "MSFT": "MSFT", "NFLX": "NFLX", "ORCL": "ORCL", "CRM": "CRM", "PLTR": "PLTR",

        # ⚡ 戰區八：重電與能源
        "GE": "GE", "CAT": "CAT", "NEE": "NEE", "DOW": "DOW", "ETN": "ETN", "PWR": "PWR",

        # 🚗 戰區九：汽車與消費
        "TSLA": "TSLA", "GM": "GM", "F": "F", "NIKE": "NKE", "RIVN": "RIVN", "TM": "TM",

        # 🚢 戰區十：航運與原物料
        "ZIM": "ZIM", "XOM": "XOM", "CVX": "CVX", "BA": "BA", "UPS": "UPS", "FDX": "FDX",

        # 🏦 戰區十一：金融與支付
        "BRK-B": "BRK-B", "GS": "GS", "JPM": "JPM", "BAC": "BAC",
        "C": "C", "AXP": "AXP", "WFC": "WFC", "V": "V", "MA": "MA", "MS": "MS", "XLF": "XLF",

        # 🏥 戰區十二：生技與民生防禦
        "NBI": "^NBI", "JNJ": "JNJ", "MRK": "MRK", "PFE": "PFE",
        "UNH": "UNH", "PG": "PG", "WMT": "WMT", "HD": "HD",
        "KO": "KO", "MCD": "MCD", "DIS": "DIS", "MMM": "MMM", "LLY": "LLY", "COST": "COST",

        # 📈 期貨與加密貨幣
        "NQ": "NQ=F", "YM": "YM=F", "GC": "MGC=F", "CL": "MCL=F",
        "BTC": "BTC-USD", "ETH": "ETH-USD"
    }
    
    matrix_results = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for key, symbol in tickers.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
            res = requests.get(url, headers=headers, timeout=5).json()
            
            result_node = res['chart']['result'][0]
            meta = result_node['meta']
            
            # 🎯 直接從 K 線真實收盤價陣列抓取，徹底排除 meta 欄位錯亂問題
            quotes = result_node['indicators']['quote'][0]
            closes = [c for c in quotes.get('close', []) if c is not None]
            
            curr_p = meta.get('regularMarketPrice', 0)
            if len(closes) >= 1:
                curr_p = closes[-1]  # 最新真實收盤/現價
                
            prev_p = meta.get('chartPreviousClose', 0)
            if len(closes) >= 2:
                prev_p = closes[-2]     # 昨天真實收盤價
            elif prev_p == 0 and len(closes) == 1:
                prev_p = curr_p

            if prev_p > 0:
                chg_pct = round(((curr_p - prev_p) / prev_p) * 100, 2)
            else:
                chg_pct = 0.0
                
            matrix_results[key] = {
                "price": round(curr_p, 2),
                "chg": chg_pct
            }
        except Exception as e:
            matrix_results[key] = {"price": 0.0, "chg": 0.0}
            
    # 讀取當日戰報入選名單 (monitor_list.json) 以便前端進行點燈高亮
    monitor_tags_map = {}
    try:
        if os.path.exists("monitor_list.json"):
            with open("monitor_list.json", "r", encoding="utf-8") as f:
                m_data = json.load(f)
                if isinstance(m_data, list):
                    for item in m_data:
                        code = str(item.get("代碼", item.get("code", ""))).strip()
                        stype = str(item.get("type", "general")).lower()
                        if code:
                            monitor_tags_map[code] = stype
                elif isinstance(m_data, dict):
                    for code, item in m_data.items():
                        stype = str(item.get("type", "general")).lower()
                        monitor_tags_map[str(code)] = stype
    except:
        pass

    # 💥 強制使用台灣台北時間 (UTC+8)，徹底校正伺服器時差
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    tw_now_str = datetime.datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")

    # 將市場數據、時間戳記與戰報標籤完整打包
    payload = {
        "timestamp": tw_now_str,
        "quotes": matrix_results,
        "monitor_tags": monitor_tags_map
    }
    
    try:
        with open(MATRIX_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
        print("✅ [美股夜盤風向] 完全體戰情數據與時間戳記已成功同步至快取！", flush=True)
    except Exception as e:
        print(f"⚠️ [美股夜盤風向] 快取寫入失敗: {e}", flush=True)

@app.route("/global_matrix.json", methods=['GET'])
def get_global_matrix():
    """ 提供前端跨國資金矩陣的即時數據 API """
    if os.path.exists(MATRIX_CACHE_FILE):
        try:
            with open(MATRIX_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            response = make_response(jsonify(data))
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return response
        except:
            pass
    return jsonify({}), 404

# ==========================================================

# 👇 請將這段「pCloud 雲端讀取當沖歷史」貼在這裡 👇

# ==========================================================

PCLOUD_INTRADAY_URL = "https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/intraday_cache.json"



def read_intraday_cache():

    try:

        res = requests.get(f"{PCLOUD_INTRADAY_URL}?t={int(time.time())}", timeout=5)

        if res.status_code == 200:

            data = res.json()

            if isinstance(data, list):

                print(f"✅ [pCloud 補給成功] 成功從雲端載入 {len(data)} 筆當沖發報歷史紀錄！", flush=True)

                return data

    except Exception as e:

        print(f"⚠️ [pCloud 讀取提醒] 目前雲端尚無歷史紀錄或連線中斷: {e}", flush=True)

    return []



# 啟動時從 pCloud 載入今日舊有的發報紀錄

intraday_breakout_cache = read_intraday_cache()



# ==========================================================

# 🔑 1. API 金鑰與通訊參數設定 (雙彈匣火力升級)

# ==========================================================

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'SMvkBhzw64RpFhLGsaDRfzqPVPkxAk8HYLz+Pvy/kiVG/n3XkSNWOcPPyQkSpWrCcAj3+SmAaM1iopF9dz6TJdo6xyQwBv0soAzdn+Wdn3GC2YS+4m16cEzIW5pUTqO12JC6grdw6ktZ4wh3arR5+gdB04t89/1O/w1cDnyilFU=')

LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')

IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', '') 



# 💥 裝載二號機彈藥庫

LINE_CHANNEL_ACCESS_TOKEN_2 = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_2', 'cN+RyHUSVPVjN2E2pf7UZZXdE5Y/vX0fBU7YvOecr1EbEaJpIOn9Z/EVpquq5alZjD5FrCapigoT7Pjm4ibi/Rekp67d+h1NlFqV/okLDWQvhR9bUWp50YaoB0NKNQjUb1w2kt57uig9EGO3YkyLjAdB04t89/1O/w1cDnyilFU=')

LINE_CHANNEL_SECRET_2 = os.environ.get('LINE_CHANNEL_SECRET_2', 'c5bed42c2d36c3f26d15a02e20439953')



# 初始化兩把通訊槍管

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)     # 一號主戰機

line_bot_api_2 = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN_2) # 二號備用機



# 💥 雙彈匣自動切換發射引擎

def smart_push_message(group_id, message):

    try:

        # 優先使用一號機發射

        line_bot_api.push_message(group_id, message)

    except Exception as e:

        print(f"⚠️ 一號機發射受阻 ({e})，自動切換二號機發射！", flush=True)

        try:

            # 一號機沒子彈或發生錯誤時，瞬間切換二號機補槍

            line_bot_api_2.push_message(group_id, message)

            print("🚀 二號機補槍發射成功！", flush=True)

        except Exception as e2:

            print(f"❌ 雙機皆發射失敗: {e2}", flush=True)





# ==========================================================

# 🌐 雲端動態彈藥庫同步器：從 pCloud 載入最新 tokens.json

# ==========================================================

PCLOUD_TOKENS_URL = "https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/tokens.json"



def fetch_cloud_tokens():

    """讓雲端母艦動態從 pCloud 下載統帥在電腦新增的機器人清單"""

    try:

        res = requests.get(f"{PCLOUD_TOKENS_URL}?t={int(time.time())}", timeout=5)

        if res.status_code == 200:

            tokens_data = res.json()

            if isinstance(tokens_data, list) and len(tokens_data) > 0:

                print(f"✅ [雲端彈藥庫同步] 成功從 pCloud 載入 {len(tokens_data)} 筆機器人金鑰！", flush=True)

                return tokens_data

    except Exception as e:

        print(f"⚠️ [雲端彈藥庫警告] 無法從 pCloud 讀取 tokens.json，改用 Render 環境變數備援: {e}", flush=True)

    

    # 若雲端下載失敗的備援：讀取 Render 原本的環境變數

    fallback_tokens = []

    t1 = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

    if t1: fallback_tokens.append({"name": "一號機", "token": t1})

    t2 = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_2', '')

    if t2: fallback_tokens.append({"name": "二號機", "token": t2})

    return fallback_tokens





# 升級版：支援 pCloud 動態無限擴編與「群組自動偵測 (跨版本相容)」的發射樞紐

def smart_push_with_menu(group_id, message_text):

    menu_quick_reply = QuickReply(

        items=[

            QuickReplyButton(action=MessageAction(label="🌍 國際夜盤", text="夜盤")),

            QuickReplyButton(action=MessageAction(label="🎯 尋找買點", text="尋找買點")),

            QuickReplyButton(action=MessageAction(label="🧠 AI 盤勢講評", text="今日盤勢")),

            QuickReplyButton(action=MessageAction(label="📊 盤後選股", text="盤後選股")),
            
            QuickReplyButton(action=MessageAction(label="🛡️ 盤後覆盤", text="盤後覆盤"))

        ]

    )

    push_msg = TextSendMessage(

        text=str(message_text)[:4000],  

        quick_reply=menu_quick_reply

    )

    

    # 🎯 每次要發送爆量通知前，自動去 pCloud 抓取最新金鑰清單！

    tokens_data = fetch_cloud_tokens()

    

    success_sent = False

    for idx, item in enumerate(tokens_data, start=1):

        token = item.get("token", "").strip()

        bot_name = item.get("name", f"第 {idx} 號機")

        if not token: continue

        

        try:

            temp_api = LineBotApi(token)

            

            # 💥 【神級雷達防線：開槍前先查水表 (跨套件版本相容)】

            try:

                # 自動偵測並相容不同版本的 LINE 套件函數名稱

                if hasattr(temp_api, 'get_group_summary'):

                    temp_api.get_group_summary(group_id)

                else:

                    temp_api.get_group_members_count(group_id)

            except Exception as check_err:

                # 如果發生錯誤，代表機器人不在群組內 (或是被官方阻擋)！

                print(f"⚠️ [跳過] {bot_name} 不在目標群組中，尋找下一台... ({check_err})", flush=True)

                continue  # 👈 直接跳過，不浪費子彈，換下一隻！

            

            # 確定在群組裡面，才真正對目標群組使用「精準導彈 (push_message)」開槍！

            temp_api.push_message(group_id, push_msg)

            print(f"🚀 [雲端彈藥庫] {bot_name} 帶選單推播成功！", flush=True)

            success_sent = True

            break # 發射成功，任務完成，跳出迴圈！

            

        except Exception as api_err:

            err_str = str(api_err)

            if "429" in err_str or "limit" in err_str.lower() or "LineBotApiError" in err_str:

                print(f"⚠️ [{bot_name} 額度耗盡/429] 雲端自動切換下一台機器人...", flush=True)

                continue

            else:

                print(f"⚠️ {bot_name} 發射受阻 ({err_str})，嘗試切換...", flush=True)

                continue

                

    if not success_sent:

        print(f"❌ [發射崩潰] 群組 {group_id} 查無可用的機器人，或所有駐紮機器人彈藥皆已耗盡！", flush=True)

# ==========================================================

# 💎 升級版：雙排高質感戰情快捷面板 (通用的 Flex 產生器)

# ==========================================================

def create_flex_menu_message(message_text):

    flex_content = BubbleContainer(

        body=BoxComponent(

            layout='vertical',

            contents=[

                # 訊息本文

                BoxComponent(

                    layout='vertical',

                    contents=[{

                        "type": "text",

                        "text": str(message_text)[:3000],

                        "wrap": True,

                        "size": "sm",

                        "color": "#f8fafc"

                    }],

                    padding_bottom="12px"

                ),

                # 第一排按鈕 (國際夜盤、尋找買點)

                BoxComponent(

                    layout='horizontal',

                    spacing='sm',

                    contents=[

                        ButtonComponent(

                            action=MessageAction(label="🌍 國際夜盤", text="夜盤"),

                            style="secondary",

                            height="sm"

                        ),

                        ButtonComponent(

                            action=MessageAction(label="🎯 尋找買點", text="尋找買點"),

                            style="secondary",

                            height="sm"

                        )

                    ]

                ),

                # 第二排按鈕 (AI盤勢講評、盤後選股)

                BoxComponent(

                    layout='horizontal',

                    spacing='sm',

                    margin="sm",

                    contents=[

                        ButtonComponent(

                            action=MessageAction(label="🧠 AI 盤勢講評", text="今日盤勢"),

                            style="secondary",

                            height="sm"

                        ),

                        ButtonComponent(

                            action=MessageAction(label="📊 盤後選股", text="盤後選股"),

                            style="secondary",

                            height="sm"
                        )
                    ]
                ),
                # 💥 新增第三排按鈕 (專屬盤後覆盤通道)
                BoxComponent(
                    layout='horizontal',
                    spacing='sm',
                    margin="sm",
                    contents=[
                        ButtonComponent(
                            action=MessageAction(label="🛡️ 盤後覆盤 (13:40)", text="盤後覆盤"),
                            style="primary",
                            color="#2ea043",
                            height="sm"

                        )

                    ]

                )

            ],

            background_color="#0f172a",

            padding_all="15px"

        )

    )

    return FlexSendMessage(alt_text="📊 股海觀浪戰情選單", contents=flex_content)



# 🛡️ 統一回覆中繼站 (支援動態切換槍管)
from flask import g

def smart_reply_with_menu(event, message_text):
    if isinstance(message_text, str):
        flex_msg = create_flex_menu_message(message_text)
    else:
        flex_msg = message_text 
    try:
        # 瞬間從記憶庫抽出本次對話專屬的槍管
        active_token = getattr(g, 'active_token', LINE_CHANNEL_ACCESS_TOKEN)
        dynamic_api = LineBotApi(active_token)
        
        # 使用對應的槍管開火！
        dynamic_api.reply_message(event.reply_token, flex_msg)
    except Exception as e:
        print(f"⚠️ 回覆發送受阻: {e}", flush=True)

        

        





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

# 📚 2. 台股資料庫初始化 (本地 JSON 優先版)

# ==========================================================

global_stock_dict = {}

global_full_stock_list = []



def get_stock_dict():

    global global_stock_dict, global_full_stock_list

    if len(global_stock_dict) > 0: 

        return global_stock_dict, global_full_stock_list

    

    # 1. 優先讀取與 botmain.py 同目錄的 all_stocks.json 檔案

    if os.path.exists("all_stocks.json"):

        try:

            with open("all_stocks.json", "r", encoding="utf-8") as f:

                all_list = json.load(f)

                for item in all_list:

                    sid = str(item.get("code", "")).strip()

                    name = str(item.get("name", "")).strip()

                    if sid and name:

                        global_stock_dict[name] = sid

                        global_stock_dict[sid] = sid

                        global_full_stock_list.append({"code": sid, "name": name})

                print(f"✅ 成功從本地 JSON 載入全市場股票共 {len(global_full_stock_list)} 筆", flush=True)

                return global_stock_dict, global_full_stock_list

        except Exception as e:

            print(f"⚠️ 讀取本地 all_stocks.json 失敗: {e}", flush=True)



    # 2. 如果本地檔案讀取失敗的備用防呆

    if len(global_stock_dict) == 0:

        backup_data = {

            "台積電": "2330", "鴻海": "2317", "聯發科": "2454", "群創": "3481",

            "台肥": "1722", "聯合再生": "3576", "友達": "2409", "長榮": "2603",

            "陽明": "2609", "萬海": "2615", "中鋼": "2002", "聯電": "2303"

        }

        for name, sid in backup_data.items():

            global_stock_dict[name] = sid

            global_stock_dict[sid] = sid

            global_full_stock_list.append({"code": sid, "name": name})

            

    return global_stock_dict, global_full_stock_list



# 啟動時在背景預先載入全市場

threading.Thread(target=get_stock_dict, daemon=True).start()



# ==========================================================

# 📈 3. [新增] 全市場基本面動能掃描引擎 (階段一核心)

# ==========================================================

revenue_history_cache = {}  # 記憶體：負責存放每檔股票上一期的期別

fundamental_focus_cache = [] # 戰術狙擊區快取 (48小時內有變更)

fundamental_full_cache = []  # 全域戰略區快取 (全市場 2000 檔)







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
            import time
            import requests
            import urllib3
            # 🛡️ 關閉煩人的 SSL 不安全警告
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # 💥 終極防斷線裝甲：強制關閉 keep-alive，要求伺服器傳完就放手
            safe_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Connection": "close"  # 👈 關鍵防斷線設定
            }
            
            for attempt in range(3):
                try:
                    # 🚀 終極戰術：不分上市上櫃，全部透過 Google 星鏈跳板 (GAS) 進行全域代理！
                    request_url = f"{GAS_URL}?url={url}"

                    res = requests.get(request_url, headers=safe_headers, timeout=45, verify=False)
                    
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list): return data
                        if isinstance(data, dict):
                            for k, v in data.items():
                                if isinstance(v, list): return v
                except Exception as e: 
                    print(f"⚠️ API 請求異常 ({url}) [第 {attempt+1} 次嘗試]: {e}", flush=True)
                    time.sleep(3) # 失敗後冷卻 3 秒再發動下一次衝鋒
            
            # 如果 3 次衝鋒都失敗，才宣告撤退
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

# ⚖️LINE群組 回應股票查詢 多維度動態計分（趨勢結構、籌碼量價、風險評估）與操盤手戰略方針的核心邏輯

# ==========================================================



def generate_professional_analysis(stock_name, stock_code, realtime_str, current_price, ma5, ma20, volume, chip_status):

    score = 50 

    signals = []

    

    # 追蹤各項目的得分/扣分明細以供顯示

    trend_score_text = "0 分（均線糾結 / 震盪整理）"

    chip_score_text = "0 分（籌碼結構相對平穩）"

    volume_score_text = "0 分（量能相對沉寂）"



    # 1. 均線與趨勢結構判斷

    if current_price > ma5 and ma5 > ma20:

        score += 20

        trend_text = "🟢 多頭排列（短中均線向上，強勢格局）"

        trend_score_text = "+20 分（多頭排列）"

    elif current_price < ma5 and ma5 < ma20:

        score -= 20

        trend_text = "🔴 空頭排列（均線下彎，短線弱勢）"

        trend_score_text = "-20 分（空頭排列）"

    else:

        trend_text = "🟡 均線糾結 / 震盪整理格局"

        

    # 2. 籌碼與主力意圖判斷

    if "大戶放量攻擊" in chip_status or "強勢" in chip_status:

        score += 25

        signals.append("🔥 主力大戶積極進駐，具備上攻動能")

        chip_score_text = "+25 分（大戶放量攻擊）"

    elif "鬆動" in chip_status:

        score -= 15

        signals.append("⚠️ 籌碼有鬆動跡象，留意短線賣壓")

        chip_score_text = "-15 分（籌碼鬆動）"

    else:

        signals.append("⚖️ 籌碼結構相對平穩，多空拔河中")

        

    # 3. 量價結構評估

    if volume > 100000: 

        signals.append("📊 量能顯著放大，市場關注度高")

        volume_score_text = "+15 分（量能顯著放大）"

        score += 15 

    else:

        signals.append("💤 量能相對沉寂，處於等待變盤階段")



    score = max(0, min(100, score))



    # 4. 智慧支撐壓力計算

    if current_price > 0:

        pivot = current_price

        resistance_1 = round(pivot * 1.015, 2)  # 上檔壓力 (+1.5%)

        support_1 = round(pivot * 0.985, 2)     # 下檔支撐 (-1.5%)

    else:

        resistance_1, support_1 = 0, 0



    # 5. 綜合操盤手建議產出

    if score >= 75:

        action_advice = "🔥 【操盤手戰略：偏多狙擊】多方結構扎實，可沿關鍵支撐分批佈局，嚴守停損。"

    elif score <= 40:

        action_advice = "🛑 【操盤手戰略：保守觀望】短線趨勢偏弱，切勿盲目接刀，建議等帶量突破再說。"

    else:

        action_advice = "⚖️ 【操盤手戰略：區間應對】目前多空不明、處於橫盤整理，適合在上下檔支撐壓力間操作。"



    report = (

        f"🎯 【專業操盤手立體戰情室】\n"

        f"📌 標的：{stock_name} ({stock_code})\n"

        f"--------------------------\n"

        f"{realtime_str}\n"

        f"--------------------------\n"

        f"🔍 【多維度深度審查與計分明細】\n"

        f"• 趨勢結構：{trend_text} ｜ {trend_score_text}\n"

        f"• 籌碼動向：{chip_score_text}\n"

        f"• 量能狀態：{volume_score_text}\n"

        f"• 籌碼量價細節：{' ｜ '.join(signals)}\n"

        f"• 實戰攻防：上檔壓力約 {resistance_1} ｜ 下檔支撐約 {support_1}\n"

        f"• 綜合評分：{score} 分（基準 50 分 ｜ 中立區）\n"

        f"--------------------------\n"

        f"💡 【評分說明】：本系統以 50 分為多空分水嶺（>75分偏多狙擊，<40分保守觀望）。50 分代表當下多空膠著、處於平衡或整理期，非系統故障。\n"

        f"--------------------------\n"

        f"{action_advice}"

    )

    return report





# ==========================================================

# 🚀 5. 全市場真實資金流向排行與精選戰報交集過濾引擎

# ==========================================================

# 新增一個全域變數來儲存今日資金主攻族群

global_true_market_top_ind = ""



def execute_force_refresh():

    global global_true_market_top_ind # 宣告使用全域變數

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



from flask import g  # 👈 第一行引入 Flask 的全域變數字典
import hmac
import hashlib
import base64
from linebot import WebhookHandler

handler = WebhookHandler('dummy_secret_for_init')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    all_secrets = []
    secret_token_map = {} # 👈 新增：暗號與槍管的對應表
    
    try:
        tokens_data = fetch_cloud_tokens()
        for item in tokens_data:
            sec = item.get("secret", "").strip()
            tok = item.get("token", "").strip()
            if sec and sec not in all_secrets:
                all_secrets.append(sec)
                secret_token_map[sec] = tok  # 將暗號與 Token 配對
    except: pass

    if not all_secrets:
        if LINE_CHANNEL_SECRET: 
            all_secrets.append(LINE_CHANNEL_SECRET)
            secret_token_map[LINE_CHANNEL_SECRET] = LINE_CHANNEL_ACCESS_TOKEN
        if LINE_CHANNEL_SECRET_2: 
            all_secrets.append(LINE_CHANNEL_SECRET_2)
            secret_token_map[LINE_CHANNEL_SECRET_2] = LINE_CHANNEL_ACCESS_TOKEN_2
            
    matched_secret = None
    for secret in all_secrets:
        hash_val = hmac.new(secret.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
        if base64.b64encode(hash_val).decode('utf-8') == signature:
            matched_secret = secret
            break
            
    if not matched_secret:
        abort(400)
        
    # 💡 終極魔法：把對應的 Token 存進這回合的記憶庫 (g) 裡！
    g.active_token = secret_token_map.get(matched_secret, LINE_CHANNEL_ACCESS_TOKEN)
    
    handler.parser.signature_validator.channel_secret = matched_secret.encode('utf-8')
    try: 
        handler.handle(body, signature)
    except InvalidSignatureError: 
        abort(400)
        
    return 'OK'



# 🎯 建立全域記憶體快取，對抗 Render 洗檔機制
war_room_memory_cache = {}
war_room_summary_cache = {}

@app.route("/war_room_<date_str>.html", methods=['GET'])
def serve_war_room(date_str):
    import os
    import time
    import requests
    # 1. 優先從記憶體直接提取（最快，絕對不會被系統洗掉）
    if date_str in war_room_memory_cache:
        return war_room_memory_cache[date_str]
    
    # 2. 備用方案：如果記憶體沒有，再去硬碟找實體檔案
    file_path = f"war_room_{date_str}.html"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                war_room_memory_cache[date_str] = content
                return content
        except:
            pass

    # 3. 雲端自癒方案：若 Render 休眠重啟洗掉檔案，自動去 pCloud 抓回歷史 HTML
    try:
        pcloud_html_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/war_room_{date_str}.html?t={int(time.time())}"
        res = requests.get(pcloud_html_url, timeout=6)
        if res.status_code == 200 and "<!DOCTYPE html>" in res.text:
            war_room_memory_cache[date_str] = res.text
            return res.text
    except:
        pass

    # 4. 終極現場重算：若連 HTML 都還沒生成，直接調閱該日 CSV 現場生成！
    try:
        html_out, _ = build_war_room_report(target_date_str=date_str, push_to_groups=False)
        if html_out:
            return html_out
    except Exception as e:
        print(f"⚠️ 現場重算戰情室失敗 ({date_str}): {e}", flush=True)
            
    return "戰情室尚未生成，或查無該日歷史戰績紀錄", 404


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

        

        smart_reply_with_menu(
			event,
			TextSendMessage(text=welcome_msg)
		)







# ==========================================================

# LINE群組查詢股票 💡 最完美的智慧過濾邏輯

# ==========================================================



@handler.add(MessageEvent, message=TextMessage)

def handle_message(event):

    user_msg = event.message.text.strip()

    user_id = event.source.user_id  

    

    # 💥 新增：讓使用者隨時點名查詢當日已被系統鎖定的標的清單

    if user_msg in ["今日雷達", "今日飆股", "雷達清單"]:

        try:

            try:

                profile = line_bot_api.get_profile(user_id)

                user_name = profile.display_name

            except:

                user_name = "戰友"



            if intraday_breakout_cache and len(intraday_breakout_cache) > 0:

                recent_alerts = intraday_breakout_cache[:5]

                reply_lines = [

                    f"📈 【盤中選股雷達・今日飆股追蹤紀錄】",

                    f"報告 {user_name}，以下為今日盤中已被系統鎖定的完整實戰紀錄：\n",

                    "======================"

                ]

                for alert in recent_alerts:

                    clean_alert = alert.replace("群組同步跟單急報", "實戰發報通知").replace("小白當沖實戰指令", "操作指引")

                    reply_lines.append(clean_alert)

                    reply_lines.append("----------------------")

                

                reply_lines.append("💡 提示：以上為今日發報之歷史軌跡，實際進出場請依當下盤勢與風險控制為準！")

                reply_msg = "\n".join(reply_lines)

            else:

                reply_msg = f"🔍 報告 {user_name}，今日盤中目前尚無符合條件的標的。系統正嚴格過濾盤勢、避開假突破中，請耐心等候主流資金表態！"

        except Exception as e:

            reply_msg = f"⚠️ 查詢今日雷達清單異常：{e}"



        smart_reply_with_menu(event, reply_msg[:4000])

        return



    # 支援大盤、雷達或戰報的即時行情查詢

    if user_msg in ["大盤", "雷達", "戰報"]:

        cache_data = read_cache()

        reply_text = f"{cache_data.get('fundsText', '')}\n\n精選標的流向：\n{cache_data.get('stocksText', '')}"

        smart_reply_with_menu(event, reply_text[:4000])

        return





# 💥 新增模組：AI 總結今日盤勢與收盤講評

    if user_msg in ["今日盤勢", "AI講評", "盤勢分析", "收盤講評"]:
        # 1. 光速秒回，破解 5 秒死線 (升級動態槍管)
        smart_reply_with_menu(event, TextSendMessage(text="🧠 收到指令！AI 正在彙整今日大盤與主流資金流向，約需 5 秒鐘，請稍候..."))
        
        # 2. 建立背景分身
        def process_ai_summary():
            try:
                target_id = event.source.group_id if hasattr(event.source, 'group_id') else event.source.user_id
                
                try:
                    profile = line_bot_api.get_profile(event.source.user_id)
                    user_name = profile.display_name
                except:
                    user_name = "戰友"

                cache_data = read_cache()
                funds_summary = cache_data.get('fundsText', '目前無大盤數據')
                stocks_summary = cache_data.get('stocksText', '目前無主流數據')

                prompt = f"""
                你是一位頂尖的台股操盤手與總體經濟分析師。請根據以下今日的盤勢數據與資金流向，為戰友寫一篇精簡有力、專業且具備前瞻性的「今日盤勢總結與明日觀盤重點」（大約150-200字，分段清晰，帶有股市實戰風格）：
                - 大盤與資金流向摘要：{funds_summary}
                - 盤面主流族群/精選標的：{stocks_summary}
                """
                response = ai_model.generate_content(prompt)
                ai_commentary = response.text.strip() if response and response.text else "目前 AI 大腦正在冷卻中，請稍後再試。"

                reply_msg = (
                    f"🧠 【股海觀浪・AI 每日盤勢總結】\n"
                    f"報告 {user_name}，今日戰情剖析如下：\n"
                    f"----------------------\n"
                    f"{ai_commentary}\n"
                    f"----------------------\n"
                    f"💡 提醒：盤勢瞬息萬變，操作請嚴格執行資金控管與停損紀律！"
                )
                # 算完後，用原本的雙排面板主動推播回群組！
                smart_push_with_menu(target_id, reply_msg[:4000])
            except Exception as e:
                print(f"AI盤勢背景處理失敗: {e}")

        # 3. 發射分身！
        import eventlet
        eventlet.spawn(process_ai_summary)
        return





    # 💥 盤後選股 (雙彈齊發版)
    if user_msg in ["盤後選股", "選股策略", "最新選股"]:
        report_url = "https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html"
        reply_msg = "📊 【股海觀浪】最新盤後選股策略：\n系統已為您產出最新報告，請點擊下方專屬連結前往觀看！"
        
        # 1. 第一發：帶有按鈕的深色面板
        flex_msg = create_flex_menu_message(reply_msg)
        # 2. 第二發：純文字網址 (LINE會自動轉成可點擊連結)
        link_msg = TextSendMessage(text=report_url)
        
        # 3. 包裝成陣列 [ ] 一次發射兩發！
        smart_reply_with_menu(event, [flex_msg, link_msg])
        return





    # ==========================================

    # 🛡️ 新增模組：戰情室盤後結算與防禦覆盤

    # ==========================================

    # 💥 盤後覆盤 (支援「無參數自動回溯前一日」＋「指定歷史日期調閱：如 覆盤 20261023 或 覆盤 1023」)
    cmd_review_match = re.match(r'^(?:盤後覆盤|防禦報告|攔截清單|強制結算|重新結算|覆盤)(?:\s*[-/:]?\s*(\d{4,8}))?$', user_msg)
    if cmd_review_match:
        try:
            raw_date_arg = cmd_review_match.group(1)
            force_rebuild = user_msg.startswith(("強制結算", "重新結算"))
            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            now_tw = datetime.datetime.now(tz_tw)

            if raw_date_arg:
                # 使用者有指定日期：支援 4 碼 (如 1023 -> 20261023) 或 8 碼 (如 20261023)
                if len(raw_date_arg) == 4:
                    target_date_str = f"{now_tw.strftime('%Y')}{raw_date_arg}"
                elif len(raw_date_arg) == 8:
                    target_date_str = raw_date_arg
                else:
                    smart_reply_with_menu(event, "⚠️ 日期格式請輸入 8 碼（例如：`覆盤 20261023`）或 4 碼月日（例如：`覆盤 1023`）！")
                    return
                is_fallback = False
                custom_date_mode = True
            else:
                # 使用者未指定日期：自動檢查今日，若休市或無紀錄則回溯最近一個交易日
                target_date_str, is_fallback = resolve_latest_trading_date()
                custom_date_mode = False

            render_url = f"https://stock-line-bot-c8em.onrender.com/war_room_{target_date_str}.html"
            date_label = f"{target_date_str[:4]}/{target_date_str[4:6]}/{target_date_str[6:]}"
            
            if custom_date_mode:
                header_note = f"📅（指定調閱歷史交易日：{date_label} 戰報）"
            elif is_fallback:
                header_note = f"🔄（今日休市或尚無紀錄，已自動調閱最近交易日：{date_label} 戰報）"
            else:
                header_note = f"⚡（{date_label} 當日最新戰報）"

            # 情況 A：記憶體中已有編譯好的報告且非強制重算 -> 0.1 秒瞬間雙彈秒回
            if (not force_rebuild) and (target_date_str in war_room_memory_cache) and (target_date_str in war_room_summary_cache):
                reply_msg = f"🛡️ 【機構級盤後覆盤】\n{header_note}\n\n{war_room_summary_cache[target_date_str]}"
                flex_msg = create_flex_menu_message(reply_msg[:3000])
                link_msg = TextSendMessage(text=render_url)
                smart_reply_with_menu(event, [flex_msg, link_msg])
                return

            # 情況 B：尚未編譯或指定調閱歷史檔案 -> 先秒回破除 LINE 5秒限制，再由背景分身從 pCloud 調閱並生成
            smart_reply_with_menu(
                event,
                TextSendMessage(text=f"🛡️ 收到指令！正在從雲端戰史庫調閱【{date_label}】交易紀錄並啟動 MFE/MAE 歸因引擎編譯網頁，約需 5~10 秒，請稍候...")
            )

            def process_on_demand_war_room():
                try:
                    target_id = event.source.group_id if hasattr(event.source, 'group_id') else event.source.user_id
                    _, summary_text = build_war_room_report(target_date_str=target_date_str, push_to_groups=False)
                    full_msg = f"🛡️ 【機構級盤後覆盤結算完畢】\n{header_note}\n\n{summary_text}"
                    smart_push_with_menu(target_id, full_msg[:4000])
                except Exception as ex:
                    print(f"⚠️ 指定日期盤後覆盤背景異常: {ex}", flush=True)

            import eventlet
            eventlet.spawn(process_on_demand_war_room)

        except Exception as e:
            smart_reply_with_menu(event, f"⚠️ 查詢防禦報告異常：{e}")
        return


# ==========================================================

    # 👇 手調收盤戰報指令

    # ==========================================================

    if user_msg in ["收盤戰報", "收盤結算", "今日結算"]:

        try:

            try:

                profile = line_bot_api.get_profile(user_id)

                user_name = profile.display_name

            except Exception:

                user_name = "戰友"



            review_lines = [f"📊 【股海觀浪・全方位戰場鑑識與分頁驗證】\n報告 {user_name}，為您即時調閱今日結算戰報：\n----------------------"]

            

            # ==========================================

            # 🛠️ 區塊一：盤中 1分/5分爆量雷達標的驗證結算

            # ==========================================

            if intraday_breakout_cache:

                stock_records = {}

                for alert in intraday_breakout_cache:

                    try:

                        time_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', alert)

                        code_match = re.search(r'\((\d{4})\)', alert)

                        name_match = re.search(r'⚡\s*([^(]+)\(', alert)

                        price_match = re.search(r'現價\s*[:：]\s*([\d\.]+)', alert)

                        

                        if code_match:

                            alert_time = time_match.group(1) if time_match else "09:00"

                            code = code_match.group(1)

                            name = name_match.group(1).strip() if name_match else code

                            alert_price = float(price_match.group(1)) if price_match else 0.0

                            

                            if code not in stock_records:

                                stock_records[code] = {

                                    "name": name,

                                    "alert_time": alert_time,

                                    "alert_price": alert_price

                                }

                    except:

                        pass

                

                settle_count = 0

                win_count = 0

                

                for code, data in stock_records.items():

                    try:

                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?range=1d&interval=1d"

                        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()

                        meta = res['chart']['result'][0]['meta']

                        indicators = res['chart']['result'][0]['indicators']['quote'][0]

                        

                        close_p = meta.get('regularMarketPrice', 0)

                        highs = [h for h in indicators.get('high', []) if h is not None]

                        lows = [l for l in indicators.get('low', []) if l is not None]

                        

                        day_high = max(highs) if highs else close_p

                        day_low = min(lows) if lows else close_p

                        

                        ap = data["alert_price"]

                        if ap > 0 and close_p > 0:

                            max_surge = round(((day_high - ap) / ap) * 100, 2)

                            after_chg = round(((close_p - ap) / ap) * 100, 2)

                            

                            if after_chg > 0: win_count += 1

                            settle_count += 1

                            

                            status_tag = "🔥 主升續強" if after_chg > 1.0 else ("⚠️ 沖高壓回" if max_surge > 2.0 and after_chg <= 0 else "💤 區間震盪")

                            

                            review_lines.append(

                                f"• {data['name']}({code}) ｜ 發報@{ap} [{data['alert_time']}]\n"

                                f"  ╰ 收盤:{close_p} ({after_chg:+.2f}%) ｜ 盤中最高衝刺: +{max_surge}%\n"

                                f"  ╰ 戰術判定：{status_tag}"

                            )

                    except:

                        pass

                

                if settle_count > 0:

                    win_rate = round((win_count / settle_count) * 100, 1)

                    review_lines.append(f"🎯 【盤中爆量雷達】鑑識標的：{settle_count} 檔 ｜ 收盤收紅：{win_count} 檔 (勝率 {win_rate}%)")

                else:

                    review_lines.append("🎯 【盤中爆量雷達】今日無有效發報標的。")

            else:

                review_lines.append("🎯 【盤中爆量雷達】今日無發報紀錄。")

            

            review_lines.append("----------------------")



            # ==========================================

            # 🛠️ 區塊二：各策略分頁選股戰報績效與明細驗證

            # ==========================================

            try:

                res_json = requests.get("https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json", timeout=5).json()

            except:

                res_json = {}



            strat_groups = {

                "🎯 MTS 完美共振區": [],

                "🎖️ S級肥羊特戰區": [],

                "👑 S級核心波段區": [],

                "⚡ 當沖/隔日游擊區": []

            }

            

            items_to_process = []

            if isinstance(res_json, dict):

                for k, v in res_json.items():

                    if isinstance(v, dict):

                        v["code"] = k

                        items_to_process.append(v)

            elif isinstance(res_json, list):

                items_to_process = res_json



            for info in items_to_process:

                try:

                    code = str(info.get("代碼", info.get("code", ""))).strip()

                    name = info.get("name", info.get("商品", code))

                    stype = str(info.get("type", "general"))

                    

                    if not code: continue



                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?range=1d&interval=1d"

                    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()

                    if not res.get('chart', {}).get('result'):

                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TWO?range=1d&interval=1d"

                        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()



                    meta = res['chart']['result'][0]['meta']

                    close_p = meta.get('regularMarketPrice', 0)

                    prev_close = meta.get('chartPreviousClose', close_p)

                    

                    if close_p > 0 and prev_close > 0:

                        chg_pct = round(((close_p - prev_close) / prev_close) * 100, 2)

                        item_data = {"name": name, "code": code, "close": close_p, "chg": chg_pct, "is_win": chg_pct > 0}

                        

                        if stype == "mts":

                            strat_groups["🎯 MTS 完美共振區"].append(item_data)

                        elif stype == "b":

                            strat_groups["🎖️ S級肥羊特戰區"].append(item_data)

                        elif stype == "s":

                            strat_groups["👑 S級核心波段區"].append(item_data)

                        else:

                            strat_groups["⚡ 當沖/隔日游擊區"].append(item_data)

                except:

                    pass

            

            review_lines.append("📊 【選股策略各分頁獨立績效與明細驗證】")

            for group_name, stocks in strat_groups.items():

                if not stocks:

                    continue

                count = len(stocks)

                wins = sum(1 for s in stocks if s["is_win"])

                win_rate = round((wins / count) * 100, 1)

                avg_chg = round(sum(s["chg"] for s in stocks) / count, 2)

                

                review_lines.append(f"• {group_name} (追蹤 {count} 檔 ｜ 勝率 {win_rate}% ｜ 平均 {avg_chg:+.2f}%)")

                

                for s in stocks:

                    sign = "📈 +" if s["chg"] > 0 else ("📉 " if s["chg"] < 0 else "➖ ")

                    review_lines.append(f"   - {s['name']}({s['code']}) ｜ 收盤:{s['close']} ({sign}{s['chg']:+.2f}%)")

                

                review_lines.append("----------------------")

            

            review_lines.append("💡 參謀總結：完整記錄盤中爆量衝刺與各策略分頁表現，作為優化次日選股模型的黃金依據。")

            

            reply_msg = "\n".join(review_lines)

        except Exception as e:

            reply_msg = f"⚠️ 手調收盤戰報異常：{e}"



        smart_reply_with_menu(event, reply_msg[:4000])

        return





    # ==========================================================

    # 🧮 💥 升級模組：LINE 當月發射次數動態查詢 (支援無限彈藥庫)

    # ==========================================================

    if user_msg in ["次數", "額度", "剩餘發數", "子彈"]:

        try:

            # 🎯 直接向 pCloud 呼叫最新擴編的機器人清單

            tokens_data = fetch_cloud_tokens()

            

            reply_lines = ["📊 【股海觀浪・彈藥庫實時庫存】", "----------------------"]

            active_gun = "無 (彈藥全部耗盡)"

            

            # 動態巡航：有幾隻就查幾隻！

            for idx, item in enumerate(tokens_data, start=1):

                name = item.get("name", f"第 {idx} 號機")

                token = item.get("token", "").strip()

                if not token: continue

                

                try:

                    temp_api = LineBotApi(token)

                    used = temp_api.get_message_quota_consumption().total_usage

                    remain = 200 - used

                    reply_lines.append(f"🔫 {name}：已用 {used}/200 則 (剩 {remain} 則)")

                    

                    # 抓出第一隻還有子彈的機器人當作主力火線

                    if remain > 0 and active_gun == "無 (彈藥全部耗盡)":

                        active_gun = f"{name} (發射中)"

                except Exception as api_err:

                    reply_lines.append(f"🔫 {name}：連線讀取失敗")

                    

            reply_lines.append("----------------------")

            reply_lines.append(f"🎯 目前主力火線：{active_gun}")

            reply_lines.append("💡 備註：每月 1 號系統將自動重置免費發射額度。")

            

            reply_msg = "\n".join(reply_lines)

            

        except Exception as e:

            reply_msg = f"⚠️ 彈藥庫數據連線受阻: {e}"

            

        smart_reply_with_menu(event, reply_msg)

        return







    # 1. 取得股票資料庫

    res_data = get_stock_dict()

    if isinstance(res_data, tuple):

        stock_dict, full_list = res_data

    else:

        stock_dict = res_data

        full_list = [{"code": c, "name": n} for n, c in stock_dict.items()]



    target_code = ""

    target_name = user_msg  # 預設名稱



    if user_msg.isdigit() and len(user_msg) <= 6:

        target_code = user_msg

        # 如果輸入的是代號，自動反查對應的中文名稱

        for item in full_list:

            if str(item.get("code", "")).strip() == target_code:

                target_name = str(item.get("name", "")).strip()

                break

    elif user_msg in stock_dict:

        target_code = stock_dict[user_msg]

        target_name = user_msg  # 輸入的就是中文名稱



    # 2. 如果直接命中代號或精確名稱，直接回傳專業操盤手級別的立體戰情

    if target_code:

        realtime_info = fetch_realtime_data(target_code)

        

        # 🛡️ 智慧解析即時數據以供操盤手評分函數使用

        current_price = 0.0

        ma5 = 0.0

        ma20 = 0.0

        volume = 0

        chip_status = "平穩"

        

        try:

            # 從 realtime_info 字串中把關鍵數值解析出來

            for line in realtime_info.split('\n'):

                if "雲端即時成交價" in line:

                    # 擷取成交價與總量

                    p_match = re.search(r'成交價:\s*([0-9.]+)', line)

                    if p_match: current_price = float(p_match.group(1))

                    v_match = re.search(r'總量:\s*([0-9,]+)張', line)

                    if v_match: volume = int(v_match.group(1).replace(',', ''))

                elif "均線數值" in line:

                    m_match = re.findall(r'([0-9.]+)', line)

                    if len(m_match) >= 3:

                        ma5 = float(m_match[0])

                        ma20 = float(m_match[2])

                elif "籌碼動向" in line:

                    chip_status = line

        except:

            pass



        # 呼叫專業操盤手動態分析引擎

        reply_msg = generate_professional_analysis(

            target_name, target_code, realtime_info, current_price, ma5, ma20, volume, chip_status

        )

        

        smart_reply_with_menu(event, reply_msg[:4000])

        return



    # 3. 模糊比對：檢查這段文字是不是在股票名稱中出現過

    matched_stocks = []

    for item in full_list:

        c = str(item.get("code", "")).strip()

        n = str(item.get("name", "")).strip()

        if user_msg in n or user_msg in c:

            matched_stocks.append(f"{n}({c})")



    # 4. 關鍵防護罩：如果有找到相關股票，才回傳清單；如果是日常對話（找不到任何股票），直接靜默 pass！

    if matched_stocks:

        display_list = matched_stocks[:30]

        more_text = f"\n...(還有 {len(matched_stocks) - 30} 筆)" if len(matched_stocks) > 30 else ""

        reply_msg = f"🔍 找到包含「{user_msg}」的股票共 {len(matched_stocks)} 筆：\n" + " | ".join(display_list) + more_text

        smart_reply_with_menu(event, reply_msg[:4000])

    else:

        # 找不到股票（代表這是一般聊天對話，如「謝謝」、「好」、「該吃飯囉」），直接安靜不回應！

        pass





    # ==========================================================

    # 💥 新增模組 1：國際夜盤與期貨速報

    # 💥 新增模組 2：均線扣抵轉折預告

    # ==========================================================

    if user_msg in ["夜盤", "國際局勢", "期貨", "虛擬貨幣"]:

        try:

            tickers = {
        # 🌐 頂級天候儀表板
        "SOX": "^SOX", "IXIC": "^IXIC", "DJI": "^DJI", "INX": "^GSPC",
        "TSM": "TSM", "VIX": "^VIX", "DXY": "DX-Y.NYB", "US10Y": "^TNX",

        # ⚙️ 戰區一：半導體與晶片
        "NVDA": "NVDA", "AMD": "AMD", "INTC": "INTC", "QCOM": "QCOM", "AVGO": "AVGO",

        # 🖥️ 戰區二：AI 伺服器
        "SMCI": "SMCI", "DELL": "DELL", "VRT": "VRT",

        # 📦 戰區三：先進封裝與設備
        "ASML": "ASML", "AMAT": "AMAT",

        # 📡 戰區四：光通訊與網通
        "MRVL": "MRVL", "LITE": "LITE", "CSCO": "CSCO",

        # 🛰️ 戰區五：低軌衛星
        "ASTS": "ASTS", "IRDM": "IRDM",

        # 💾 戰區六：記憶體
        "MU": "MU",

        # ☁️ 戰區七：雲端巨頭與軟體
        "AAPL": "AAPL", "GOOG": "GOOG", "META": "META", "AMZN": "AMZN",
        "MSFT": "MSFT", "NFLX": "NFLX", "ORCL": "ORCL",

        # 🔮 戰區八：次世代封裝與玻璃基板 (新增 GLW 與 ONTO)
        "GLW": "GLW", "ONTO": "ONTO",
        # (註：INTC, AMAT, LRCX, KLAC, COHR 等巨頭已在前方戰區，系統會自動共用報價)

        # ⚡ 戰區九：重電與能源
        "GE": "GE", "CAT": "CAT", "NEE": "NEE", "DOW": "DOW",

        # 🚗 戰區十：汽車與消費
        "TSLA": "TSLA", "GM": "GM", "F": "F", "NIKE": "NKE",

        # 🚢 戰區十一：航運與原物料
        "ZIM": "ZIM", "XOM": "XOM", "CVX": "CVX", "BA": "BA",

        # 🏦 戰區十二：金融與支付
        "BRK-B": "BRK-B", "GS": "GS", "JPM": "JPM", "BAC": "BAC",
        "C": "C", "AXP": "AXP", "WFC": "WFC", "V": "V", "MA": "MA", "XLF": "XLF",

        # 🏥 戰區十三：生技與民生防禦
        "NBI": "^NBI", "JNJ": "JNJ", "MRK": "MRK", "PFE": "PFE",
        "UNH": "UNH", "PG": "PG", "WMT": "WMT", "HD": "HD",
        "KO": "KO", "MCD": "MCD", "DIS": "DIS", "MMM": "MMM", "LLY": "LLY", "COST": "COST",

        # 📈 期貨與加密貨幣
        "NQ": "NQ=F", "YM": "YM=F", "GC": "MGC=F", "CL": "MCL=F",
        "BTC": "BTC-USD", "ETH": "ETH-USD"
    }

            reply_lines = ["🌍 【股海觀浪・全球資金與科技領頭羊速報】\n"]

            summary_data_for_ai = []

            

            for name, ticker in tickers.items():

                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=20d&includePrePost=true"

                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()

                

                if not res.get('chart', {}).get('result'):

                    reply_lines.append(f"⚠️ {name}：訊號中斷")

                    continue

                    

                meta = res['chart']['result'][0]['meta']

                indicators = res['chart']['result'][0]['indicators']['quote'][0]

                closes = indicators.get('close', [])

                valid_closes = [c for c in closes if c is not None]

                

                curr_p = meta.get('postMarketPrice', meta.get('regularMarketPrice'))

                curr_p = round(curr_p, 2) if curr_p else 0.0

                

                prev_p = meta.get('chartPreviousClose', 0.0)

                

                if prev_p > 0:

                    chg_pct = round(((curr_p - prev_p) / prev_p) * 100, 2)

                else:

                    chg_pct = 0.0

                

                ema5 = round(sum(valid_closes[-5:]) / 5, 2) if len(valid_closes) >= 5 else curr_p

                

                sign = "📈 +" if chg_pct > 0 else "📉 "

                reply_lines.append(f"• {name} ｜ {sign}{chg_pct}%")

                reply_lines.append(f"    現價: {curr_p} (短線支撐/壓力: {ema5})")

                

                summary_data_for_ai.append(f"{name}: {chg_pct:+.2f}%")



            # 🧠 AI 動態生成：採用專業台股期貨操盤用語

            ai_insight = "市場多空拔河，操作宜嚴守停損紀律。"

            try:

                prompt = f"""

                你是一位頂尖台股與期貨實戰操盤手。以下是今日全球主要期貨指數、日韓股市、加密貨幣與美股 AI 巨頭的最新漲跌幅數據：

                {", ".join(summary_data_for_ai)}

                

                請根據以上數據，寫一段道地的「實戰操盤點評」（大約 40-60 字），必須使用如：提款、撐盤力道、拔河格局、追高搶短、低基期、資金控管等股市期貨用語，直接給出結論與對次日台股的啟示，絕對不要有任何廢話或稱呼。

                """

                response = ai_model.generate_content(prompt)

                if response and response.text:

                    ai_insight = response.text.strip()

            except:

                pass



            reply_lines.append(f"\n🎯 操盤手點評：{ai_insight}")

            reply_msg = "\n".join(reply_lines)

            

        except Exception as e:

            reply_msg = f"⚠️ 全球雷達連線異常：{e}"

            

        smart_reply_with_menu(event, reply_msg)

        return







    # 💥 優化版：盤中技術面轉折與買點即時篩選（與爆量通知互補）

    if any(keyword in user_msg for keyword in ["轉折", "起漲", "發動", "轉強", "找買點", "尋找買點", "扣抵"]):

        try:

            try:

                profile = line_bot_api.get_profile(user_id)

                user_name = profile.display_name

            except Exception:

                user_name = "戰友"



            json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={int(time.time())}"

            res_json = requests.get(json_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()



            qualified_picks = []

            target_dict = {}

            if isinstance(res_json, list):

                for item in res_json:

                    code = str(item.get("代碼", item.get("code", "")))

                    if code:

                        target_dict[code] = item

            else:

                target_dict = res_json



            for code, info in target_dict.items():

                name = info.get('name', info.get('商品', '未知'))

                ind = info.get('ind', info.get('產業', ''))

                y_close = float(info.get("y_close", 0))

                ma5 = float(info.get("ma5", 0))



                if y_close > 0 and ma5 > 0 and y_close >= ma5:

                    qualified_picks.append({

                        "id": code,

                        "name": name,

                        "ind": ind,

                        "price": y_close,

                        "ma5": ma5,

                        "reason": "均線之上穩健排列，多方主導中"

                    })



            if qualified_picks and len(qualified_picks) > 0:

                top_picks = qualified_picks[:5]

                reply_lines = [

                    "📊 【盤中技術面即時篩選・買點雷達】",

                    f"報告 {user_name}，系統已完成盤中多維度技術篩選，目前符合轉折與穩健排列的標的如下：\n",

                    "======================"

                ]

                for p in top_picks:

                    reply_lines.append(f"🔹 {p['name']}({p['id']}) ｜ {p['ind']}\n現價：{p['price']} (5MA: {p['ma5']})\n💡 狀態：{p['reason']}")

                    reply_lines.append("----------------------")

                

                reply_lines.append("📌 提示：此清單為技術面即時篩選結果，請搭配當下大盤走勢與個人風險承受度評估進出！")

                reply_msg = "\n".join(reply_lines)

            else:

                reply_msg = f"🔍 報告 {user_name}，目前盤中多空拉鋸，系統暫未篩選出符合嚴格均線轉折條件的標的。建議先觀望、等待主流資金明確表態！"

        except Exception as e:

            reply_msg = f"⚠️ 盤中技術篩選異常：{e}"



        smart_reply_with_menu(event, reply_msg[:4000])

        return





    # ==========================================================

# 💎 升級版：雙排高質感戰情快捷面板 (通用的 Flex 產生器)

# ==========================================================

def create_flex_menu_message(message_text):

    flex_content = BubbleContainer(

        body=BoxComponent(

            layout='vertical',

            contents=[

                # 訊息本文

                BoxComponent(

                    layout='vertical',

                    contents=[{

                        "type": "text",

                        "text": str(message_text)[:3000],

                        "wrap": True,

                        "size": "sm",

                        "color": "#f8fafc"

                    }],

                    padding_bottom="12px"

                ),

                # 第一排按鈕 (國際夜盤、尋找買點)

                BoxComponent(

                    layout='horizontal',

                    spacing='sm',

                    contents=[

                        ButtonComponent(

                            action=MessageAction(label="🌍 國際夜盤", text="夜盤"),

                            style="secondary",

                            height="sm"

                        ),

                        ButtonComponent(

                            action=MessageAction(label="🎯 尋找買點", text="尋找買點"),

                            style="secondary",

                            height="sm"

                        )

                    ]

                ),

                # 第二排按鈕 (AI盤勢講評、盤後選股)

                BoxComponent(

                    layout='horizontal',

                    spacing='sm',

                    margin="sm",

                    contents=[

                        ButtonComponent(

                            action=MessageAction(label="🧠 AI 盤勢講評", text="今日盤勢"),

                            style="secondary",

                            height="sm"

                        ),

                        ButtonComponent(

                            action=MessageAction(label="📊 盤後選股", text="盤後選股"),

                            style="secondary",

                            height="sm"
                        )
                    ]
                ),
                # 💥 新增第三排按鈕 (專屬盤後覆盤通道)
                BoxComponent(
                    layout='horizontal',
                    spacing='sm',
                    margin="sm",
                    contents=[
                        ButtonComponent(
                            action=MessageAction(label="🛡️ 盤後覆盤 (13:40)", text="盤後覆盤"),
                            style="primary",
                            color="#2ea043",
                            height="sm"

                        )

                    ]

                )

            ],

            background_color="#0f172a",

            padding_all="15px"

        )

    )

    return FlexSendMessage(alt_text="📊 股海觀浪戰情選單", contents=flex_content)



# 🛡️ 統一回覆中繼站 (任何文字回覆透過此函數送出，都會自動夾帶雙排面板)

# 🛡️ 統一回覆中繼站 (支援動態切換槍管)
from flask import g

def smart_reply_with_menu(event, message_text):
    if isinstance(message_text, str):
        flex_msg = create_flex_menu_message(message_text)
    else:
        flex_msg = message_text 
    try:
        # 瞬間從記憶庫抽出本次對話專屬的槍管
        active_token = getattr(g, 'active_token', LINE_CHANNEL_ACCESS_TOKEN)
        dynamic_api = LineBotApi(active_token)
        
        # 使用對應的槍管開火！
        dynamic_api.reply_message(event.reply_token, flex_msg)
    except Exception as e:
        print(f"⚠️ 回覆發送受阻: {e}", flush=True)



# ==========================================================

# 🌟 7. 🚀 雲端全時相決策中心 (全自動 5 分鐘循環更新)

# ==========================================================

def market_patrol_loop():

    import time

    import threading



    print("📡 [總部軍令] 全自動資金矩陣與大盤偵蒐迴圈已啟動...", flush=True)

    

    # 開機時強制立即執行一次

    try:

        execute_force_refresh()

    except Exception as e:

        print(f"⚠️ 開機大盤偵蒐初次執行異常: {e}", flush=True)

        

    try:

        fetch_global_matrix_data()

    except Exception as e:

        print(f"⚠️ 開機全球矩陣初次執行異常: {e}", flush=True)



    while True:

        try:

            # 每 300 秒 (5 分鐘) 自動在背景執行一次，更新資料與最新時間戳記

            time.sleep(300)  

            

            print("🔄 [自動化排程] 正在背景自動更新大盤資金流向...", flush=True)

            execute_force_refresh()

            

            print("🔄 [自動化排程] 正在背景自動更新全球跨國資金矩陣與即時時間...", flush=True)

            fetch_global_matrix_data()

            

        except Exception as e:

            print(f"⚠️ 自動化巡邏循環異常: {e}", flush=True)

            time.sleep(30)









# ==========================================================

# ⚡ 8. 專屬當沖連續掃描引擎 (全市場 2000 檔批次陣列雷達)

# ==========================================================



# 🛡️ 戰情室防禦黑盒子：記錄被攔截的主力陷阱
intercepted_traps_log = []

stock_tick_memory = {}
intraday_alerted_codes = set()

# 💥 新增：用來記錄「盤中真實被系統攔截過濾」的股票集合
filtered_funds_codes = set()
filtered_overheated_codes = set()
last_clear_date = ""

def process_tick_data(data, meta_info, top_ind):
    import time, datetime, requests
    global stock_tick_memory, intraday_alerted_codes, intercepted_traps_log
    global filtered_funds_codes, filtered_overheated_codes, last_clear_date
    
    code = data.get('c')
    
    # 換日自動清空昨天的過濾紀錄
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_dt = datetime.datetime.now(tz)
    now_date_str = now_dt.strftime("%Y-%m-%d")
    if last_clear_date != now_date_str:
        filtered_funds_codes.clear()
        filtered_overheated_codes.clear()
        intercepted_traps_log.clear()
        last_clear_date = now_date_str

    if not code or code in intraday_alerted_codes: return None
    
    try:
        name = meta_info.get('name', code)
        ind = meta_info.get('ind', '未知')
        ma20 = float(meta_info.get('ma20', 0) if meta_info.get('ma20', '-') != '-' else 0)
        
        z = float(data.get('z', 0) if data.get('z', '-') != '-' else data.get('y', 0))
        o = float(data.get('o', 0) if data.get('o', '-') != '-' else z)
        h = float(data.get('h', 0) if data.get('h', '-') != '-' else 0)
        l = float(data.get('l', 0) if data.get('l', '-') != '-' else z)
        y = float(data.get('y', 0))
        v = float(data.get('v', 0) if data.get('v', '-') != '-' else 0)
        
        if z <= 0 or y <= 0: return None
        if v < 0.5: return None
        
        chg_pct = round(((z - y) / y) * 100, 2)
        
        try:
            vwap_est = round((o + h + l + (z * v / (v if v > 0 else 1))) / 4, 2) if v > 0 else round((o + h + l + z * 2) / 5, 2)
            if abs(vwap_est - z) / z > 0.07: vwap_est = round((o + h + l + z * 2) / 5, 2)
        except:
            vwap_est = round((o + h + l + z * 2) / 5, 2)

        now_ts = time.time()
        time_str = now_dt.strftime("%H:%M:%S")
        current_time_num = now_dt.hour * 100 + now_dt.minute

        if 900 <= current_time_num < 1000: time_status = "golden"
        elif 1000 <= current_time_num < 1100: time_status = "cooling"
        else: time_status = "dead_water"

        if code not in stock_tick_memory: stock_tick_memory[code] = []
        stock_tick_memory[code].append((now_ts, z, v, h, l))
        
        if len(stock_tick_memory[code]) > 30: stock_tick_memory[code].pop(0)

        ticks = stock_tick_memory[code]
        if len(ticks) >= 6:
            current_ts, current_z, current_v = ticks[-1][0], ticks[-1][1], ticks[-1][2]
            
            past_tick = ticks[0] 
            for t in reversed(ticks):
                if current_ts - t[0] >= 50: 
                    past_tick = t
                    break
            
            if current_ts - ticks[0][0] < 40:
                return None

            z_1m_ago, v_1m_ago = past_tick[1], past_tick[2]
            vol_1m = current_v - v_1m_ago
            ignite_value = vol_1m * current_z * 1000

            is_real_attack = current_z >= z_1m_ago
            is_volume_surge = False

            # 💥 [統帥校準] 嚴格把關主力真實點火資金
            if time_status == "golden":
                if vol_1m >= 50 and ignite_value >= 50000000: is_volume_surge = True
            elif time_status == "cooling":
                if vol_1m >= 100 and ignite_value >= 80000000: is_volume_surge = True
            elif time_status == "dead_water":
                if vol_1m >= 150 and ignite_value >= 100000000: is_volume_surge = True

            # 🛡️ 數據採集 1：資金不足過濾 (有一分鐘爆量>50張，但資金/張數未達嚴格標準)
            if vol_1m >= 50 and current_z >= z_1m_ago and not is_volume_surge:
                filtered_funds_codes.add(code)
                return None

            if not (is_volume_surge and is_real_attack): return None



            ma5_now = sum([t[1] for t in ticks[-5:]]) / 5

            ma5_prev = sum([t[1] for t in ticks[-6:-1]]) / 5

            

            is_ma_up = ma5_now > ma5_prev

            is_cross_vwap = (z_1m_ago < vwap_est and current_z >= vwap_est)

            

            if not is_ma_up and not is_cross_vwap: return None



            is_below_20ma = (ma20 > 0 and current_z < ma20)

            if is_below_20ma: return None

            

            alert_type = ""

            action_guide = ""

            

            if not is_ma_up and is_cross_vwap:

                alert_type = "💥 【破底翻突襲】爆量貫穿均價線！"

                action_guide = f"🎯 【實戰戰術：低檔 V 轉搶短】\n👉 戰況解讀：主力瞬間爆量強攻站上均價線！\n🛡️ 生死防線：以均價線 {vwap_est} 為絕對防禦，跌破立刻撤退！"

            elif is_ma_up and current_z >= vwap_est:

                alert_type = "🚀 【主升段點火】均線多頭強勢推升！"

                action_guide = f"🎯 【實戰戰術：右側順勢加碼】\n👉 戰況解讀：短均線上揚，趨勢極度健康！\n🛡️ 移動防線：沿著上揚走勢操作，爆量跌破 {vwap_est} 則拔檔！"

            else:

                return None 



            bias = ((current_z - vwap_est) / vwap_est) * 100 if vwap_est > 0 else 0
            if bias >= 2.5:
                # 🛡️ 數據採集 2：將過熱標的記錄進真實數據庫
                filtered_overheated_codes.add(code)
                
                alert_type = "⚠️ 【高檔爆量・極端過熱】"

                action_guide = f"🎯 【操盤手強制指令：嚴禁追高】\n👉 戰況解讀：正乖離達 {bias:+.1f}%，瞬間漲幅過大！\n🔪 動作：切勿市價追高！靜待量縮拉回測試。"











            is_resonance = (top_ind != "" and top_ind in ind)

            hot_tag = f"🌟 [主流資金共振：{ind}]" if is_resonance else f"🏷️ [{ind}]"

            resonance_text = " (🔥主攻部隊)" if is_resonance else ""

            intraday_alerted_codes.add(code)
                
            # 🎯 [統帥加裝] 計算無腦進場價 (+2檔) 並寫入 CSV 資料庫
            tick_size = 0.05 if current_z < 50 else (0.1 if current_z < 100 else (0.5 if current_z < 500 else 1.0))
            suggested_entry = round(current_z + (tick_size * 2), 2)
            
            csv_payload = {
                "time": time_str,
                "id": code,
                "name": name,
                "zone": "早盤" if time_status == "golden" else ("盤中" if time_status == "cooling" else "尾盤"),
                "funds": int(ignite_value / 10000), # 萬元
                "change_pct": f"{chg_pct:+.2f}%",
                "deviation": f"{bias:+.1f}%",
                "decision": "強勢達標_發送 🔔",
                "entry": suggested_entry,
                "stop_loss": vwap_est
            }
            log_event(csv_payload)
            
            
            # 註冊進入盤中即時風控監控網格
            intraday_live_monitors[code] = {
                "name": name,
                "entry": suggested_entry,
                "vwap": vwap_est,
                "alerted_mfe3": False,
                "alerted_break": False
            }
            

            # 💡 請保留您原本這段完整、豐富的回傳字串，一絲一毫都不少！
            return (
                f"[{time_str}] ⚡ {name}({code}) {alert_type}\n"
                f"{hot_tag} | 現價：{current_z} (均價線:{vwap_est})\n"
                f"漲幅：{chg_pct:+.2f}% | 均價乖離：{bias:+.1f}%\n"
                f"🔥 絕對爆量：{int(vol_1m)} 張 (點火資金 {int(ignite_value/10000)}萬){resonance_text}\n"
                f"----------------------\n"
                f"{action_guide}"
            )
    except Exception:
        pass
    return None



# 🎯 獨立異步擊發彈匣

instant_fire_queue = []



def instant_dispatcher_loop():

    """背景擊發手：每 3.5 秒巡視一次彈匣，確保雷達掃完一輪後完美打包擊發！"""

    import time

    while True:

        time.sleep(3.5)  # 💥 這裡改為 3.5 秒

        if len(instant_fire_queue) > 0:

            # 瞬間抽出彈匣裡所有的飆股情報

            bullets = instant_fire_queue[:]

            instant_fire_queue.clear()

            

            # 打包發射

            combined_msg = "🚨 【全市場同步跟單急報】\n\n" + "\n\n======================\n\n".join(bullets)

            TARGET_GROUP_IDS = [

                "C0481b44935888bb1dc20dfd52a675e8a", 

                "C47bfa8e16a7216bd54dceb3b5e90cfa0"  

            ]

            for group_id in TARGET_GROUP_IDS:

                try:

                    smart_push_with_menu(group_id, combined_msg[:4500])

                except: pass

            print(f"🚀 [異步擊發手] 已將 {len(bullets)} 檔飆股零時差空投至前線！", flush=True)



# ==========================================================
# 🚨 盤中即時停利與破線警報巡邏手 (監控 MFE >= +3% 或 跌破 VWAP)
# ==========================================================
intraday_live_monitors = {}  # 格式: { code: { "name": name, "entry": entry, "vwap": vwap, "alerted_mfe3": False, "alerted_break": False } }

def intraday_live_alarm_loop():
    import time, datetime, requests
    print("📡 [即時風控哨] 盤中停利與破線警報巡邏引擎已啟動...", flush=True)
    while True:
        try:
            time.sleep(15)  # 每 15 秒巡視一次盤中已發報標的
            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            now_dt = datetime.datetime.now(tz_tw)
            is_weekend = now_dt.weekday() >= 5
            curr_hhmm = now_dt.hour * 100 + now_dt.minute

            # 僅在盤中 09:00 ~ 13:25 進行即時風控監控
            if is_weekend or not (900 <= curr_hhmm <= 1325):
                continue

            if not intraday_live_monitors:
                continue

            TARGET_GROUP_IDS = [
                "C0481b44935888bb1dc20dfd52a675e8a", 
                "C47bfa8e16a7216bd54dceb3b5e90cfa0"  
            ]

            for code, info in list(intraday_live_monitors.items()):
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?range=1d&interval=1m"
                    res = requests.get(url, headers={ "User-Agent": "Mozilla/5.0" }, timeout=4).json()
                    if not res.get('chart', {}).get('result'):
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TWO?range=1d&interval=1m"
                        res = requests.get(url, headers={ "User-Agent": "Mozilla/5.0" }, timeout=4).json()

                    node = res['chart']['result'][0]
                    meta = node['meta']
                    curr_z = float(meta.get('regularMarketPrice', 0) or 0)
                    if curr_z <= 0:
                        continue

                    quotes = node['indicators']['quote'][0]
                    highs = [float(x) for x in quotes.get('high', []) if x is not None]
                    day_high = max(highs) if highs else curr_z

                    entry_p = info["entry"]
                    vwap_line = info["vwap"]
                    name = info["name"]

                    # 1. 檢測 MFE 衝過 +3% 停利提示
                    if entry_p > 0 and not info["alerted_mfe3"]:
                        mfe_est = ((day_high - entry_p) / entry_p) * 100
                        if mfe_est >= 3.0:
                            info["alerted_mfe3"] = True
                            msg = (
                                f"🎯 【即時停利捷報】{name}({code})\n"
                                f"----------------------\n"
                                f"🚀 盤中最高衝刺已達 +{mfe_est:.2f}% (超越 +3% 停利標準)！\n"
                                f"💡 操盤建議：建議分批獲利入袋，或將移動停利上移至進場價防守！"
                            )
                            for g_id in TARGET_GROUP_IDS:
                                try: smart_push_with_menu(g_id, msg)
                                except: pass

                    # 2. 檢測盤中跌破 VWAP 停損防線警報
                    if vwap_line > 0 and not info["alerted_break"]:
                        if curr_z < vwap_line * 0.995:
                            info["alerted_break"] = True
                            msg = (
                                f"🛑 【即時破線警報】{name}({code})\n"
                                f"----------------------\n"
                                f"⚠️ 注意！現價 {curr_z} 已跌破絕對防禦 VWAP 線 ({vwap_line})\n"
                                f"🔪 操盤建議：多方動能暫失，請依紀律執行風險控制或停損出場！"
                            )
                            for g_id in TARGET_GROUP_IDS:
                                try: smart_push_with_menu(g_id, msg)
                                except: pass
                except:
                    pass
        except Exception as e_alarm:
            print(f"⚠️ 即時風控巡邏異常: {e_alarm}", flush=True)

# 啟動即時風控巡邏執行緒
threading.Thread(target=intraday_live_alarm_loop, daemon=True).start()





# 啟動背景擊發手

import threading

threading.Thread(target=instant_dispatcher_loop, daemon=True).start()





def continuous_radar_loop():
    global instant_fire_queue
    print("📡 [當沖雷達] 啟動統帥認證版【Yahoo雙節點 + 證交所MIS官方雙通道防封鎖雷達】...", flush=True)
    import time, datetime, requests, urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    yahoo_session = requests.Session()
    yahoo_session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*"
    })
    yahoo_crumb = ""

    def refresh_yahoo_crumb():
        nonlocal yahoo_crumb
        for host in ["query2.finance.yahoo.com", "query1.finance.yahoo.com"]:
            try:
                yahoo_session.get("https://fc.yahoo.com", timeout=4)
                c_res = yahoo_session.get(f"https://{host}/v1/test/getcrumb", timeout=4)
                cand = c_res.text.strip()
                # 嚴格驗證 Crumb 格式，避免把 "Too Many Requests" 或 HTML 錯誤當成憑證
                if c_res.status_code == 200 and 4 <= len(cand) <= 25 and ("<" not in cand) and ("Too Many" not in cand):
                    yahoo_crumb = cand
                    print(f"✅ [破甲成功] 已從 {host} 取得有效 Yahoo 憑證: {yahoo_crumb}", flush=True)
                    return True
            except Exception:
                pass
        return False

    refresh_yahoo_crumb()

    # 建立證交所/櫃買中心官方 MIS 專用 Session (第二通道備援主力)
    mis_session = requests.Session()
    mis_session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://mis.twse.com.tw/stock/fibest.jsp"
    })

    def parse_mis_first_price(val_str):
        """從證交所五檔字串 (如 '105.50_105.00_...') 提取第一檔有效價格"""
        if not val_str or val_str == '-':
            return 0.0
        for part in str(val_str).split('_'):
            try:
                p = float(part)
                if p > 0:
                    return p
            except:
                pass
        return 0.0

    # --- 雷達主迴圈 ---
    while True:
        try:
            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            now = datetime.datetime.now(tz_tw)
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute

            # 強制在 09:00 ~ 13:24 執行，避開 13:25 收盤試撮大單
            if not is_weekend and (900 <= current_time_num <= 1324):
                current_cache = read_cache()
                full_stocks = current_cache.get("fundamental_full", [])

                # 🛡️ 防空保護：若剛開機 fundamental_full 尚未抓完，立即從本地 all_stocks.json 備援載入
                if not full_stocks:
                    _, local_list = get_stock_dict()
                    if local_list:
                        full_stocks = [{"code": item["code"], "name": item["name"], "market": "上市", "ind": "未分類", "ma20": "-"} for item in local_list]
                    else:
                        time.sleep(5)
                        continue

                valid_symbols = []
                stock_data_map = {}

                for s in full_stocks:
                    code = str(s.get('code', '')).strip()
                    market = str(s.get('market', '上市')).strip()
                    suffix = ".TWO" if "櫃" in market else ".TW"
                    if code and len(code) == 4 and code.isdigit():
                        valid_symbols.append(f"{code}{suffix}")
                        stock_data_map[code] = s

                chunk_size = 90
                successful_count = 0
                yahoo_blocked = (not yahoo_crumb)

                for i in range(0, len(valid_symbols), chunk_size):
                    chunk_symbols = valid_symbols[i : i + chunk_size]
                    chunk_quotes_standardized = []

                    # ==========================================
                    # 🚀 通道一：嘗試 Yahoo Finance 極速批次接口 (query2 / query1)
                    # ==========================================
                    if not yahoo_blocked:
                        symbols_str = ",".join(chunk_symbols)
                        for y_host in ["query2.finance.yahoo.com", "query1.finance.yahoo.com"]:
                            try:
                                url = f"https://{y_host}/v7/finance/quote?symbols={symbols_str}&crumb={yahoo_crumb}"
                                res = yahoo_session.get(url, timeout=4)
                                if res.status_code == 200:
                                    quotes = res.json().get('quoteResponse', {}).get('result', [])
                                    for q in quotes:
                                        c_code = q.get('symbol', '').split('.')[0]
                                        z_val = float(q.get('regularMarketPrice', 0) or 0)
                                        y_val = float(q.get('regularMarketPreviousClose', z_val) or z_val)
                                        v_val = float(q.get('regularMarketVolume', 0) or 0) / 1000.0
                                        if z_val > 0 and v_val > 0 and c_code in stock_data_map:
                                            chunk_quotes_standardized.append({
                                                'c': c_code,
                                                'z': z_val,
                                                'y': y_val,
                                                'o': float(q.get('regularMarketOpen', z_val) or z_val),
                                                'h': float(q.get('regularMarketDayHigh', z_val) or z_val),
                                                'l': float(q.get('regularMarketDayLow', z_val) or z_val),
                                                'v': v_val
                                            })
                                    break  # 成功拿到即跳出 host 迴圈
                                elif res.status_code in [401, 403, 429]:
                                    # 若遭遇封鎖或憑證失效，嘗試刷新一次 Crumb；若仍失敗則本輪直接切換至證交所 MIS 通道
                                    if not refresh_yahoo_crumb():
                                        yahoo_blocked = True
                                        break
                            except Exception:
                                pass

                    # ==========================================
                    # 🛡️ 通道二 (防封鎖主力備援)：台灣證交所/櫃買中心 MIS 官方批次直連
                    # 當 Yahoo 被擋或該批抓不到任何報價時，自動無縫接管！
                    # ==========================================
                    if len(chunk_quotes_standardized) == 0:
                        try:
                            ex_ch_list = []
                            for sym in chunk_symbols:
                                c_code, sfx = sym.split('.')
                                prefix = "otc" if sfx == "TWO" else "tse"
                                ex_ch_list.append(f"{prefix}_{c_code}.tw")

                            mis_url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={'|'.join(ex_ch_list)}&_={int(time.time() * 1000)}"
                            m_res = mis_session.get(mis_url, timeout=5, verify=False)
                            if m_res.status_code == 200:
                                msg_array = m_res.json().get('msgArray', [])
                                for item in msg_array:
                                    c_code = str(item.get('c', '')).strip()
                                    if c_code not in stock_data_map:
                                        continue
                                    try:
                                        v_val = float(item.get('v', 0) if item.get('v', '-') not in ['-', ''] else 0)
                                        y_val = float(item.get('y', 0) if item.get('y', '-') not in ['-', ''] else 0)
                                        if v_val <= 0 or y_val <= 0:
                                            continue

                                        # 盤中某秒若無單筆成交 (z 為 '-')，自動以最佳買價一檔或開盤價補位，徹底解決開盤 0 報價！
                                        z_raw = item.get('z', '-')
                                        if z_raw not in ['-', '']:
                                            z_val = float(z_raw)
                                        else:
                                            z_val = parse_mis_first_price(item.get('b', '')) or parse_mis_first_price(item.get('a', ''))
                                            if z_val <= 0 and item.get('o', '-') not in ['-', '']:
                                                z_val = float(item.get('o'))

                                        if z_val <= 0:
                                            continue

                                        o_val = float(item.get('o', z_val)) if item.get('o', '-') not in ['-', ''] else z_val
                                        h_val = float(item.get('h', z_val)) if item.get('h', '-') not in ['-', ''] else z_val
                                        l_val = float(item.get('l', z_val)) if item.get('l', '-') not in ['-', ''] else z_val

                                        chunk_quotes_standardized.append({
                                            'c': c_code,
                                            'z': z_val,
                                            'y': y_val,
                                            'o': o_val,
                                            'h': h_val,
                                            'l': l_val,
                                            'v': v_val
                                        })
                                    except Exception:
                                        pass
                            # 官方 MIS 通道溫和限速保護 (避免過快被證交所短暫阻擋)
                            time.sleep(0.15)
                        except Exception:
                            pass

                    # ==========================================
                    # 🎯 將標準化報價送入 process_tick_data 進行點火鑑識
                    # ==========================================
                    for formatted_data in chunk_quotes_standardized:
                        code = formatted_data['c']
                        stock_data = stock_data_map[code]
                        alert_msg = process_tick_data(formatted_data, stock_data, global_true_market_top_ind)
                        successful_count += 1

                        if alert_msg and alert_msg not in intraday_breakout_cache:
                            intraday_breakout_cache.insert(0, alert_msg)
                            instant_fire_queue.append(alert_msg)

                            new_cache = read_cache()
                            new_cache["intraday_alerts"] = intraday_breakout_cache
                            update_cache(new_cache)

                            try:
                                trigger_air_raid_alarm(f"🔥 {stock_data.get('name', code)} 爆量點火！", alert_msg)
                            except:
                                pass

                now_str = datetime.datetime.now(tz_tw).strftime("%H:%M:%S")
                channel_tag = "MIS官方備援" if yahoo_blocked else "Yahoo+MIS雙通道"
                print(f"👁️ [{now_str}] 全市場批量掃描完畢 ({channel_tag} 本輪精準抓取 {successful_count} 檔報價)。", flush=True)

                time.sleep(3)
            else:
                time.sleep(60)
        except Exception as e:
            print(f"⚠️ 雷達主迴圈異常: {e}", flush=True)
            time.sleep(15)



# ==========================================================
# 📊 13:40 雲端收盤自動戰情與 HTML 網頁生成引擎 (支援休市自動回溯前一日)
# ==========================================================
def _csv_has_data_rows(filepath):
    """檢查 CSV 是否包含至少 1 筆實質交易資料列 (排除開機 init_csv 產生的空標題檔)"""
    import os, csv
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            first_row = next(reader, None)
            return first_row is not None and len(first_row) > 0
    except:
        return False

def resolve_latest_trading_date():
    """
    🎯 智慧跨日回溯器：
    1. 先檢查今日是否有實質交易紀錄。
    2. 若今天是週末、國定假日、開盤前、或今日尚無觸發紀錄，自動往前回溯最近 10 天，
       從本機或 pCloud 雲端歷史庫找回「最近一個有紀錄的交易日 CSV」。
    回傳: (target_date_str 'YYYYMMDD', is_fallback bool)
    """
    import datetime, time, requests
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)
    today_str = now.strftime('%Y%m%d')

    for days_back in range(0, 10):
        cand_dt = now - datetime.timedelta(days=days_back)
        cand_str = cand_dt.strftime('%Y%m%d')
        csv_name = f"trading_log_{cand_str}.csv"

        # 1. 先檢查本機是否有含實質資料的 CSV
        if _csv_has_data_rows(csv_name):
            return cand_str, (days_back > 0)

        # 2. 本機沒有或為空標題檔 -> 嘗試從 pCloud 歷史資料夾拉取該日 CSV
        try:
            public_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/{csv_name}?t={int(time.time())}"
            res = requests.get(public_url, timeout=5)
            if res.status_code == 200 and ("Trigger_Time" in res.text or "Stock_ID" in res.text):
                lines = [line.strip() for line in res.text.splitlines() if line.strip()]
                if len(lines) >= 2:  # 至少有標題列 + 1筆資料列
                    with open(csv_name, 'wb') as f:
                        f.write(res.content)
                    print(f"✅ [跨日回溯成功] 已從 pCloud 調閱 {cand_str} 歷史戰績 CSV ({len(lines)-1} 筆)！", flush=True)
                    return cand_str, (days_back > 0)
        except:
            pass

    # 若近 10 天皆無 CSV 檔案，若今天為週末則退回最近一個週五，否則回傳今日
    if now.weekday() == 5:  # 週六 -> 週五
        return (now - datetime.timedelta(days=1)).strftime('%Y%m%d'), True
    elif now.weekday() == 6:  # 週日 -> 週五
        return (now - datetime.timedelta(days=2)).strftime('%Y%m%d'), True
    return today_str, False


def build_war_room_report(target_date_str=None, push_to_groups=False):
    """
    🎯 機構級盤後歸因與 HTML 戰情室核心建構引擎 (含歷史 Alpha 衰退趨勢追蹤)
    """
    import time, datetime, csv, os, json, requests
    global filtered_funds_codes, filtered_overheated_codes, war_room_memory_cache, war_room_summary_cache, global_true_market_top_ind

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)

    if not target_date_str:
        target_date_str, _ = resolve_latest_trading_date()

    csv_filename = f"trading_log_{target_date_str}.csv"
    if not _csv_has_data_rows(csv_filename):
        try:
            public_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/{csv_filename}?t={int(time.time())}"
            res = requests.get(public_url, timeout=5)
            if res.status_code == 200 and ("Trigger_Time" in res.text or "Stock_ID" in res.text):
                with open(csv_filename, 'wb') as f:
                    f.write(res.content)
        except:
            pass

    output_html_name = f"war_room_{target_date_str}.html"
    target_dt_obj = datetime.datetime.strptime(target_date_str, "%Y%m%d")
    display_date = target_dt_obj.strftime("%Y.%m.%d (%a)")
    target_date_slash = target_dt_obj.strftime("%Y/%m/%d")

    real_funds_filtered = len(filtered_funds_codes)
    real_overheated_filtered = len(filtered_overheated_codes)

    total_scans = 0
    sent_count = 0
    win_count = 0
    lose_count = 0
    giveback_count = 0

    net_returns = []
    mfe_list = []
    mae_list = []
    zone_stats = {
        "早盤": {"total": 0, "win": 0, "ret_sum": 0.0},
        "盤中": {"total": 0, "win": 0, "ret_sum": 0.0},
        "尾盤": {"total": 0, "win": 0, "ret_sum": 0.0}
    }

    chart_stock_names = []
    chart_mfe_data = []
    chart_mae_data = []
    chart_net_data = []

    master_table_rows_html = ""
    sniper_cards_html = ""
    embedded_kbars = {}
    embedded_intraday = {}
    updated_csv_rows = []
    csv_fieldnames = []

    # ==========================================
    # 📈 【新功能】歷史多日勝率與 Alpha 衰退趨勢追蹤運算 (近 10 日)
    # ==========================================
    history_trend_dates = []
    history_trend_winrates = []
    history_trend_avgrets = []

    for d_back in range(9, -1, -1):
        past_dt = target_dt_obj - datetime.timedelta(days=d_back)
        past_str = past_dt.strftime('%Y%m%d')
        past_csv = f"trading_log_{past_str}.csv"
        
        p_total = 0
        p_wins = 0
        p_rets = []

        if not _csv_has_data_rows(past_csv):
            try:
                p_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/{past_csv}?t={int(time.time())}"
                r_p = requests.get(p_url, timeout=3)
                if r_p.status_code == 200 and ("Trigger_Time" in r_p.text or "Stock_ID" in r_p.text):
                    with open(past_csv, 'wb') as pf:
                        pf.write(r_p.content)
            except:
                pass

        if _csv_has_data_rows(past_csv):
            try:
                with open(past_csv, mode='r', encoding='utf-8-sig') as pf_r:
                    p_reader = csv.DictReader(pf_r)
                    for prow in p_reader:
                        if "強勢達標_發送" in prow.get("System_Decision", ""):
                            p_total += 1
                            net_str = prow.get("Net_Return_Pct", "").strip()
                            try:
                                if net_str:
                                    val_r = float(net_str.replace('%', '').replace('+', ''))
                                    p_rets.append(val_r)
                                    if val_r > 0: p_wins += 1
                            except:
                                pass
            except:
                pass

        if p_total > 0:
            history_trend_dates.append(past_dt.strftime('%m/%d'))
            history_trend_winrates.append(round((p_wins / p_total) * 100, 1))
            history_trend_avgrets.append(round(sum(p_rets) / len(p_rets), 2) if p_rets else 0.0)

    history_trend_dates_json = json.dumps(history_trend_dates, ensure_ascii=False)
    history_trend_wr_json = json.dumps(history_trend_winrates)
    history_trend_ret_json = json.dumps(history_trend_avgrets)

    if os.path.exists(csv_filename):
        with open(csv_filename, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            csv_fieldnames = list(reader.fieldnames) if reader.fieldnames else []
            for extra_col in ["MFE_Pct", "MAE_Pct", "Net_Return_Pct", "Above_Entry_Mins", "Pathology_Tag"]:
                if extra_col not in csv_fieldnames:
                    csv_fieldnames.append(extra_col)

            is_first_card = True

            for row in reader:
                total_scans += 1
                decision = row.get("System_Decision", "")
                stock_n = row.get("Stock_Name", "未知").strip()
                stock_c = row.get("Stock_ID", "0000").strip()
                t_time = row.get("Trigger_Time", "09:00:00").strip()
                t_zone = row.get("Time_Zone", "早盤").strip()
                funds_str = row.get("Ignition_Funds", "0").strip()
                dev_str = row.get("Deviation_Rate", "+0.0%").strip()

                try:
                    entry_val = float(row.get("Suggested_Entry", 0) or 0)
                except:
                    entry_val = 0.0
                try:
                    stop_val = float(row.get("Stop_Loss_Line", 0) or 0)
                except:
                    stop_val = 0.0

                tick_unit = 0.05 if entry_val < 50 else (0.1 if entry_val < 100 else (0.5 if entry_val < 500 else 1.0))
                trig_val = round(entry_val - (tick_unit * 2), 2) if entry_val > 0 else 0.0
                slip_pct = round(((entry_val - trig_val) / trig_val) * 100, 2) if trig_val > 0 else 0.0

                if "強勢達標_發送" in decision and stock_c:
                    sent_count += 1
                    close_p = 0.0
                    mfe_pct = 0.0
                    mae_pct = 0.0
                    net_ret_pct = 0.0
                    above_mins = 0
                    hit_stop = False
                    pathology_tag = "⏳ 資料同步中"
                    badge_class = "yellow"

                    try:
                        url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_c}.TW?range=2mo&interval=1d"
                        res_1d = requests.get(url_1d, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
                        if not res_1d.get('chart', {}).get('result'):
                            url_1d = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_c}.TWO?range=2mo&interval=1d"
                            res_1d = requests.get(url_1d, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()

                        res_node_1d = res_1d['chart']['result'][0]
                        ts_1d = res_node_1d.get('timestamp', [])
                        ind_1d = res_node_1d['indicators']['quote'][0]
                        kbars_dict = {}
                        for i_d in range(len(ts_1d)):
                            if ind_1d.get('close', [])[i_d] is not None:
                                dt_str = datetime.datetime.fromtimestamp(ts_1d[i_d], tz_tw).strftime('%Y/%m/%d')
                                kbars_dict[dt_str] = {
                                    "o": ind_1d['open'][i_d],
                                    "c": ind_1d['close'][i_d],
                                    "h": ind_1d['high'][i_d],
                                    "l": ind_1d['low'][i_d],
                                    "v": ind_1d.get('volume', [])[i_d] if ind_1d.get('volume') else 0
                                }
                        embedded_kbars[stock_c] = kbars_dict
                        if target_date_slash in kbars_dict and kbars_dict[target_date_slash]["c"]:
                            close_p = round(float(kbars_dict[target_date_slash]["c"]), 2)
                    except Exception as e_1d:
                        print(f"⚠️ 抓取 {stock_c} 日K失敗: {e_1d}", flush=True)

                    try:
                        url_5m = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_c}.TW?range=5d&interval=5m"
                        res_5m = requests.get(url_5m, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
                        if not res_5m.get('chart', {}).get('result'):
                            url_5m = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_c}.TWO?range=5d&interval=5m"
                            res_5m = requests.get(url_5m, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()

                        res_node = res_5m['chart']['result'][0]
                        meta_5m = res_node['meta']
                        if close_p <= 0:
                            close_p = round(float(meta_5m.get('regularMarketPrice', 0) or 0), 2)

                        ts_list = res_node.get('timestamp', [])
                        q_5m = res_node['indicators']['quote'][0]
                        h_list = q_5m.get('high', [])
                        l_list = q_5m.get('low', [])
                        o_list = q_5m.get('open', [])
                        c_list = q_5m.get('close', [])
                        v_list = q_5m.get('volume', [])

                        t_parts = t_time.split(':')
                        trig_hhmm = int(t_parts[0]) * 100 + int(t_parts[1]) if len(t_parts) >= 2 else 900

                        available_dates = []
                        for ts_val in ts_list:
                            d_s = datetime.datetime.fromtimestamp(ts_val, tz_tw).strftime('%Y%m%d')
                            if d_s not in available_dates:
                                available_dates.append(d_s)
                        active_5m_date = target_date_str if target_date_str in available_dates else (available_dates[-1] if available_dates else target_date_str)

                        post_highs = []
                        post_lows = []
                        intraday_bars = []

                        for idx_bar in range(len(ts_list)):
                            c_bar = c_list[idx_bar] if idx_bar < len(c_list) else None
                            if c_bar is None:
                                continue
                            dt_bar = datetime.datetime.fromtimestamp(ts_list[idx_bar], tz_tw)
                            if dt_bar.strftime('%Y%m%d') != active_5m_date:
                                continue

                            bar_hhmm = dt_bar.hour * 100 + dt_bar.minute
                            time_label = dt_bar.strftime('%H:%M')

                            o_bar = round(float(o_list[idx_bar] or c_bar), 2)
                            c_bar_f = round(float(c_bar), 2)
                            h_bar = round(float(h_list[idx_bar] or c_bar), 2)
                            l_bar = round(float(l_list[idx_bar] or c_bar), 2)
                            v_bar = int((v_list[idx_bar] or 0) / 1000)

                            intraday_bars.append({
                                "t": time_label, "o": o_bar, "c": c_bar_f, "h": h_bar, "l": l_bar, "v": v_bar
                            })

                            if bar_hhmm >= trig_hhmm:
                                post_highs.append(h_bar)
                                post_lows.append(l_bar)
                                if stop_val > 0 and l_bar < stop_val:
                                    hit_stop = True
                                if entry_val > 0 and c_bar_f >= entry_val:
                                    above_mins += 5

                        if intraday_bars:
                            close_p = intraday_bars[-1]["c"]

                        embedded_intraday[stock_c] = {
                            "entry": entry_val,
                            "stop": stop_val,
                            "trig_time": t_time[:5],
                            "bars": intraday_bars
                        }

                        if not post_highs and intraday_bars:
                            post_highs = [b["h"] for b in intraday_bars]
                        if not post_lows and intraday_bars:
                            post_lows = [b["l"] for b in intraday_bars]

                        if entry_val > 0 and post_highs and post_lows:
                            mfe_pct = round(((max(post_highs) - entry_val) / entry_val) * 100, 2)
                            mae_pct = round(((min(post_lows) - entry_val) / entry_val) * 100, 2)
                        if entry_val > 0 and close_p > 0:
                            net_ret_pct = round(((close_p - entry_val) / entry_val) * 100, 2)

                    except Exception as e_5m:
                        print(f"⚠️ 抓取 {stock_c} 5分K歸因異常: {e_5m}", flush=True)

                    PATHOLOGY_CONFIG = {
                        "BIG_WIN_MFE": 3.0,
                        "BIG_WIN_NET": 2.0,
                        "GIVEBACK_MFE": 2.5,
                        "GIVEBACK_KEEP": 0.8,
                        "WHIPSAW_MAX_MINS": 10
                    }

                    is_win = net_ret_pct > 0
                    if is_win:
                        win_count += 1
                        trade_res_str = f"🔴 獲利 ({net_ret_pct:+.2f}%)"
                        val_color = "red"
                        if mfe_pct >= PATHOLOGY_CONFIG["BIG_WIN_MFE"] and net_ret_pct >= PATHOLOGY_CONFIG["BIG_WIN_NET"]:
                            pathology_tag = "🎯 衝高抱牢大勝 (主升鎖定)"
                            badge_class = "red"
                        elif hit_stop:
                            pathology_tag = f"🛡️ 先洗後拉 (曾破VWAP回撤 {mae_pct:.2f}%)"
                            badge_class = "yellow"
                        elif mfe_pct >= PATHOLOGY_CONFIG["GIVEBACK_MFE"] and net_ret_pct < PATHOLOGY_CONFIG["GIVEBACK_KEEP"]:
                            pathology_tag = f"⚠️ 大幅獲利回吐 (最高曾賺 +{mfe_pct:.2f}%)"
                            badge_class = "yellow"
                            giveback_count += 1
                        else:
                            pathology_tag = "🔥 真突破穩健收紅 (守穩均價線)"
                            badge_class = "green"
                    else:
                        lose_count += 1
                        trade_res_str = f"🟢 虧損 ({net_ret_pct:+.2f}%)"
                        val_color = "green"
                        if mfe_pct >= PATHOLOGY_CONFIG["BIG_WIN_NET"]:
                            pathology_tag = f"⚠️ 衝高A轉倒貨 (曾賺 +{mfe_pct:.2f}% 未停利)"
                            badge_class = "yellow"
                            giveback_count += 1
                        elif above_mins <= PATHOLOGY_CONFIG["WHIPSAW_MAX_MINS"]:
                            pathology_tag = f"🔪 瞬間假突破誘多 (僅撐 {above_mins} 分鐘)"
                            badge_class = "red"
                        else:
                            pathology_tag = "💤 盤中動能衰竭緩跌"
                            badge_class = "blue"

                    net_returns.append(net_ret_pct)
                    mfe_list.append(mfe_pct)
                    mae_list.append(mae_pct)

                    if t_zone not in zone_stats:
                        zone_stats[t_zone] = {"total": 0, "win": 0, "ret_sum": 0.0}
                    zone_stats[t_zone]["total"] += 1
                    if is_win:
                        zone_stats[t_zone]["win"] += 1
                    zone_stats[t_zone]["ret_sum"] += net_ret_pct

                    chart_stock_names.append(f"{stock_n}({stock_c})")
                    chart_mfe_data.append(mfe_pct)
                    chart_mae_data.append(mae_pct)
                    chart_net_data.append(net_ret_pct)

                    row["Close_Price"] = close_p
                    row["Trade_Result"] = trade_res_str
                    row["MFE_Pct"] = f"+{mfe_pct:.2f}%"
                    row["MAE_Pct"] = f"{mae_pct:.2f}%"
                    row["Net_Return_Pct"] = f"{net_ret_pct:+.2f}%"
                    row["Above_Entry_Mins"] = f"{above_mins}m"
                    row["Pathology_Tag"] = pathology_tag

                    master_table_rows_html += f"""
                    <tr>
                        <td><span style="color:var(--color-yellow); font-weight:bold;">{t_time}</span> <span class="zone-tag" style="margin-left:4px;">{t_zone}</span></td>
                        <td><strong style="color:#fff; font-size:1rem;">{stock_n}</strong> <span style="color:var(--text-muted);">({stock_c})</span></td>
                        <td style="color:var(--color-yellow); font-weight:bold;">{funds_str} 萬 <span style="color:var(--text-muted); font-size:0.8rem;">(乖離 {dev_str})</span></td>
                        <td>{trig_val} ➔ <strong style="color:var(--color-blue);">{entry_val}</strong> <span style="color:var(--text-muted); font-size:0.8rem;">(滑價 {slip_pct:.2f}%)</span></td>
                        <td style="color:var(--color-red); font-weight:bold;">{stop_val}</td>
                        <td style="color:var(--color-red); font-weight:bold;">+{mfe_pct:.2f}%</td>
                        <td style="color:var(--color-green); font-weight:bold;">{mae_pct:.2f}%</td>
                        <td><strong class="val {val_color}">{close_p} 元 ({net_ret_pct:+.2f}%)</strong></td>
                        <td><span class="status-badge {badge_class}">{pathology_tag}</span></td>
                    </tr>
                    """

                    open_attr = "open" if is_first_card else ""
                    is_first_card = False
                    card_border_color = "var(--color-red)" if is_win else "var(--color-green)"

                    sniper_cards_html += f"""
                    <details class="sniper-card" style="border-left-color: {card_border_color};" {open_attr}>
                        <summary class="card-head" style="cursor: pointer; outline: none; list-style: none;">
                            <div style="display: flex; justify-content: space-between; width: 100%; align-items: center; flex-wrap: wrap; gap: 10px;">
                                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                                    <span class="stock-name">{stock_n} ({stock_c})</span>
                                    <span class="time-tag">⏰ {t_time} [{t_zone}]</span>
                                    <span class="status-badge {badge_class}">{pathology_tag}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 14px;">
                                    <span style="font-size: 0.9rem; color: var(--text-muted);">最高衝刺 <b style="color:var(--color-red);">+{mfe_pct:.2f}%</b> ｜ 最大回撤 <b style="color:var(--color-green);">{mae_pct:.2f}%</b></span>
                                    <span class="val {val_color}" style="font-size: 1.15rem;">{trade_res_str}</span>
                                    <span style="color: var(--text-muted); font-size: 0.8rem;">▼ 展開詳情</span>
                                </div>
                            </div>
                        </summary>

                        <div style="margin-top: 20px; border-top: 1px dashed var(--border-color); padding-top: 20px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
                                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                    <span class="zone-tag">🔥 點火資金：{funds_str} 萬</span>
                                    <span class="zone-tag">📐 觸發乖離：{dev_str}</span>
                                    <span class="zone-tag">⏱️ 進場價之上維持：{above_mins} 分鐘</span>
                                </div>
                                <div style="display: flex; gap: 8px;">
                                    <button type="button" class="tab-btn active" id="tab_5m_{stock_c}" onclick="switchKMode('{stock_c}', '5m')">⚡ 當日 5 分 K (微觀當沖 + 防線)</button>
                                    <button type="button" class="tab-btn" id="tab_1d_{stock_c}" onclick="switchKMode('{stock_c}', '1d')">📅 近 2 月日 K (波段均線)</button>
                                </div>
                            </div>

                            <div class="chart-container" id="container_{stock_c}">
                                <div id="chart_box_{stock_c}" style="width: 100%; height: 280px;"></div>
                            </div>

                            <div class="detail-metrics-grid">
                                <div class="metric-box">
                                    <div class="m-label">⚡ 訊號觸發價 ➔ 建議進場價 (+2檔)</div>
                                    <div class="m-val">{trig_val} 元 ➔ <span style="color:var(--color-blue);">{entry_val} 元</span> <small>(滑價 {slip_pct:.2f}%)</small></div>
                                </div>
                                <div class="metric-box">
                                    <div class="m-label">🛡️ VWAP 嚴格停損防線</div>
                                    <div class="m-val" style="color:var(--color-red);">{stop_val} 元 <small>({'⚠️ 盤中曾觸及' if hit_stop else '✅ 盤中未跌破'})</small></div>
                                </div>
                                <div class="metric-box">
                                    <div class="m-label">📈 最大有利極值 (MFE) / 📉 最大不利極值 (MAE)</div>
                                    <div class="m-val"><span style="color:var(--color-red);">+{mfe_pct:.2f}%</span> ／ <span style="color:var(--color-green);">{mae_pct:.2f}%</span></div>
                                </div>
                                <div class="metric-box">
                                    <div class="m-label">🏁 結算收盤價與最終損益</div>
                                    <div class="m-val {val_color}">{close_p} 元 ｜ {trade_res_str}</div>
                                </div>
                            </div>
                        </div>
                    </details>
                    """
                updated_csv_rows.append(row)

        try:
            with open(csv_filename, mode='w', newline='', encoding='utf-8-sig') as wf:
                writer = csv.DictWriter(wf, fieldnames=csv_fieldnames)
                writer.writeheader()
                writer.writerows(updated_csv_rows)
            if target_date_str == now.strftime('%Y%m%d'):
                backup_csv_to_pcloud_async()
        except Exception as e_csv:
            print(f"⚠️ 結算回寫 CSV 失敗: {e_csv}", flush=True)

    win_rate_num = round((win_count / sent_count) * 100, 1) if sent_count > 0 else 0.0
    win_rate_pct = f"{win_rate_num:.1f}%"
    avg_net_ret = round(sum(net_returns) / len(net_returns), 2) if net_returns else 0.0
    avg_mfe = round(sum(mfe_list) / len(mfe_list), 2) if mfe_list else 0.0
    avg_mae = round(sum(mae_list) / len(mae_list), 2) if mae_list else 0.0

    zone_names = ["早盤", "盤中", "尾盤"]
    zone_win_rates = []
    zone_totals = []
    best_zone_str = "尚無數據"
    best_zone_wr = -1.0
    for zn in zone_names:
        zt = zone_stats.get(zn, {"total": 0, "win": 0})["total"]
        zw = zone_stats.get(zn, {"total": 0, "win": 0})["win"]
        zwr = round((zw / zt) * 100, 1) if zt > 0 else 0.0
        zone_totals.append(zt)
        zone_win_rates.append(zwr)
        if zt > 0 and zwr > best_zone_wr:
            best_zone_wr = zwr
            best_zone_str = f"{zn} ({zw}勝/{zt}檔, {zwr}%)"

    strat_groups_html = ""
    try:
        res_mon = requests.get(f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?t={int(time.time())}", timeout=6).json()
        strat_groups = {
            "🎯 MTS 完美共振區": [],
            "🎖️ S級肥羊特戰區": [],
            "👑 S級核心波段區": [],
            "⚡ 當沖/隔日游擊區": []
        }
        items_to_process = []
        if isinstance(res_mon, dict):
            for k, v in res_mon.items():
                if isinstance(v, dict):
                    v["code"] = k
                    items_to_process.append(v)
        elif isinstance(res_mon, list):
            items_to_process = res_mon

        for info in items_to_process:
            try:
                scode = str(info.get("代碼", info.get("code", ""))).strip()
                sname = info.get("name", info.get("商品", scode))
                stype = str(info.get("type", "general")).lower()
                if not scode: continue

                u_s = f"https://query1.finance.yahoo.com/v8/finance/chart/{scode}.TW?range=5d&interval=1d"
                r_s = requests.get(u_s, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()
                if not r_s.get('chart', {}).get('result'):
                    u_s = f"https://query1.finance.yahoo.com/v8/finance/chart/{scode}.TWO?range=5d&interval=1d"
                    r_s = requests.get(u_s, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()

                r_node = r_s['chart']['result'][0]
                q_s = r_node['indicators']['quote'][0]
                closes_s = [float(x) for x in q_s.get('close', []) if x is not None]
                if len(closes_s) >= 2:
                    cp_s = closes_s[-1]
                    prev_s = closes_s[-2]
                else:
                    m_s = r_node['meta']
                    cp_s = float(m_s.get('regularMarketPrice', 0) or 0)
                    prev_s = float(m_s.get('chartPreviousClose', cp_s) or cp_s)

                if cp_s > 0 and prev_s > 0:
                    chg_s = round(((cp_s - prev_s) / prev_s) * 100, 2)
                    item_d = {"name": sname, "code": scode, "close": round(cp_s, 2), "chg": chg_s}
                    if stype == "mts": strat_groups["🎯 MTS 完美共振區"].append(item_d)
                    elif stype == "b": strat_groups["🎖️ S級肥羊特戰區"].append(item_d)
                    elif stype == "s": strat_groups["👑 S級核心波段區"].append(item_d)
                    else: strat_groups["⚡ 當沖/隔日游擊區"].append(item_d)
            except:
                pass

        for g_title, g_list in strat_groups.items():
            if not g_list:
                strat_groups_html += f"""
                <div class="strat-box">
                    <div class="strat-head"><span>{g_title}</span><span class="badge">0 檔</span></div>
                    <div style="color:var(--text-muted); font-size:0.85rem; padding:10px 0;">分頁無追蹤標的</div>
                </div>
                """
                continue
            g_cnt = len(g_list)
            g_wins = sum(1 for x in g_list if x["chg"] > 0)
            g_wr = round((g_wins / g_cnt) * 100, 1)
            g_avg = round(sum(x["chg"] for x in g_list) / g_cnt, 2)
            avg_cls = "red" if g_avg >= 0 else "green"

            chips_html = ""
            for x in sorted(g_list, key=lambda i: i["chg"], reverse=True):
                c_cls = "chip-red" if x["chg"] > 0 else ("chip-green" if x["chg"] < 0 else "chip-flat")
                chips_html += f'<div class="stock-chip {c_cls}"><span>{x["name"]}({x["code"]})</span><b>{x["close"]} ({x["chg"]:+.2f}%)</b></div>'

            strat_groups_html += f"""
            <div class="strat-box">
                <div class="strat-head">
                    <span>{g_title}</span>
                    <span style="font-size:0.85rem;">勝率 <b style="color:#fff;">{g_wr}%</b> ｜ 均漲跌 <b class="val {avg_cls}">{g_avg:+.2f}%</b></span>
                </div>
                <div class="chip-container">{chips_html}</div>
            </div>
            """
    except Exception as e_mon:
        print(f"⚠️ 選股分頁整合異常: {e_mon}", flush=True)

    funds_codes_str = "、".join(sorted(list(filtered_funds_codes))[:40]) if filtered_funds_codes else "無資金未達標之異常爆量股紀錄"
    overheat_codes_str = "、".join(sorted(list(filtered_overheated_codes))[:40]) if filtered_overheated_codes else "無正乖離過熱攔截股紀錄"

    top_sector_str = global_true_market_top_ind if global_true_market_top_ind else "主流監控中"
    pcloud_public_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/history_reports/{output_html_name}"
    render_live_url = f"https://stock-line-bot-c8em.onrender.com/{output_html_name}"

    kbars_json_str = json.dumps(embedded_kbars, ensure_ascii=False)
    intraday_json_str = json.dumps(embedded_intraday, ensure_ascii=False)
    chart_names_json = json.dumps(chart_stock_names, ensure_ascii=False)
    chart_mfe_json = json.dumps(chart_mfe_data)
    chart_mae_json = json.dumps(chart_mae_data)
    chart_net_json = json.dumps(chart_net_data)
    zone_wr_json = json.dumps(zone_win_rates)
    zone_tot_json = json.dumps(zone_totals)

    review_lines = [
        f"📊 【股海觀浪・{display_date} 機構級戰場鑑識報告】",
        "----------------------",
        f"🎯 動能事件掃描：{total_scans} 次 ｜ 嚴選發報：{sent_count} 檔",
        f"🏆 收盤實戰勝率：{win_rate_pct} ({win_count}勝 {lose_count}敗)",
        f"💰 平均當沖淨損益：{avg_net_ret:+.2f}%",
        f"📈 平均最高衝刺 (MFE)：+{avg_mfe:.2f}% ｜ 平均最大回撤 (MAE)：{avg_mae:.2f}%",
        f"⏰ 最佳作戰時段：{best_zone_str}",
        f"🛡️ 防禦攔截：{real_funds_filtered} 檔資金不足 / {real_overheated_filtered} 檔高檔過熱",
        "----------------------",
        "🌐 完整互動式 5分K/日K 歸因戰情室已就緒！",
        f"👉 雲端秒開連結：\n{render_live_url}",
        f"👉 pCloud 永久封存：\n{pcloud_public_url}"
    ]
    final_report = "\n".join(review_lines)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>13:40 機構級戰場鑑識與盤後歸因總結報告 ({display_date})</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <style>
        :root {{
            --bg-main: #090d16; --bg-card: #111827; --bg-sub: #1e293b; --border-color: #334155;
            --text-main: #e2e8f0; --text-muted: #94a3b8;
            --color-green: #10b981; --color-red: #ef4444; 
            --color-blue: #38bdf8; --color-yellow: #f59e0b; --color-purple: #c084fc;
        }}
        * {{ box-sizing: border-box; }}
        body {{ background-color: var(--bg-main); color: var(--text-main); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif; margin: 0; padding: 25px; line-height: 1.5; }}
        .container {{ max-width: 1360px; margin: 0 auto; }}
        
        .header {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border-color); margin-bottom: 25px; flex-wrap: wrap; gap: 15px; }}
        .header-title {{ font-size: 1.65rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 12px; letter-spacing: 0.5px; }}
        .badge-group {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .badge {{ background: var(--bg-sub); color: var(--text-main); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; border: 1px solid var(--border-color); font-weight: bold; }}
        .badge.hot {{ background: rgba(239,68,68,0.15); color: #fca5a5; border-color: rgba(239,68,68,0.4); }}

        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }}
        .stat-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 18px 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }}
        .stat-title {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 8px; font-weight: 600; }}
        .stat-value {{ font-size: 1.9rem; font-weight: 800; color: var(--color-blue); margin-bottom: 4px; }}
        .stat-value span {{ font-size: 0.95rem; font-weight: normal; color: var(--text-muted); }}
        .stat-value.green {{ color: var(--color-green); }} .stat-value.yellow {{ color: var(--color-yellow); }} .stat-value.red {{ color: var(--color-red); }} .stat-value.purple {{ color: var(--color-purple); }}
        .stat-desc {{ font-size: 0.8rem; color: var(--text-muted); }}

        .analytics-grid {{ display: grid; grid-template-columns: 1.6fr 1fr; gap: 20px; margin-bottom: 35px; }}
        .panel-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 20px; }}
        .panel-title {{ font-size: 1.05rem; font-weight: bold; color: #fff; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; }}

        .section-title {{ font-size: 1.25rem; color: #fff; margin: 35px 0 18px 0; display: flex; align-items: center; gap: 10px; font-weight: 800; border-left: 4px solid var(--color-blue); padding-left: 12px; }}

        .defense-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 20px; overflow-x: auto; margin-bottom: 35px; }}
        table {{ width: 100%; border-collapse: collapse; min-width: 900px; }}
        th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--border-color); font-size: 0.9rem; }}
        th {{ color: var(--text-muted); font-weight: 600; background: rgba(30,41,59,0.5); }}
        tr:hover {{ background: rgba(56,189,248,0.04); }}
        .status-badge {{ background: rgba(245,158,11,0.15); color: var(--color-yellow); padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; border: 1px solid rgba(245,158,11,0.35); display: inline-block; font-weight: bold; }}
        .status-badge.red {{ background: rgba(239,68,68,0.15); color: #fca5a5; border-color: rgba(239,68,68,0.4); }}
        .status-badge.green {{ background: rgba(16,185,129,0.15); color: #6ee7b7; border-color: rgba(16,185,129,0.4); }}
        .status-badge.blue {{ background: rgba(56,189,248,0.15); color: #7dd3fc; border-color: rgba(56,189,248,0.4); }}

        .sniper-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; border-left: 5px solid var(--color-red); padding: 22px; margin-bottom: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.25); }}
        details > summary {{ list-style: none; }}
        details > summary::-webkit-details-marker {{ display: none; }}
        .stock-name {{ font-size: 1.35rem; font-weight: bold; color: #fff; }}
        .time-tag {{ color: var(--color-yellow); font-size: 0.9rem; font-weight: bold; }}
        .zone-tag {{ background: rgba(56,189,248,0.1); color: var(--color-blue); padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; border: 1px solid rgba(56,189,248,0.25); font-weight: 600; }}
        
        .tab-btn {{ background: var(--bg-sub); color: var(--text-muted); border: 1px solid var(--border-color); padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; font-weight: bold; transition: 0.2s; }}
        .tab-btn.active {{ background: var(--color-blue); color: #090d16; border-color: var(--color-blue); }}
        .chart-container {{ position: relative; width: 100%; background: #020617; border: 1px solid #334155; border-radius: 8px; overflow: hidden; margin-top: 8px; }}

        .detail-metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 15px; }}
        .metric-box {{ background: rgba(30,41,59,0.45); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; }}
        .m-label {{ font-size: 0.8rem; color: var(--text-muted); margin-bottom: 5px; }}
        .m-val {{ font-size: 1.05rem; font-weight: bold; color: #fff; }}

        .val {{ font-weight: bold; }}
        .val.green {{ color: var(--color-green); }} .val.red {{ color: var(--color-red); }} .val.yellow {{ color: var(--color-yellow); }} .val.blue {{ color: var(--color-blue); }}

        .strat-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-bottom: 35px; }}
        .strat-box {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 18px; }}
        .strat-head {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 12px; font-weight: bold; color: #fff; font-size: 1rem; }}
        .chip-container {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .stock-chip {{ padding: 6px 10px; border-radius: 6px; font-size: 0.82rem; display: flex; gap: 6px; align-items: center; border: 1px solid transparent; }}
        .chip-red {{ background: rgba(239,68,68,0.12); color: #fca5a5; border-color: rgba(239,68,68,0.3); }}
        .chip-green {{ background: rgba(16,185,129,0.12); color: #6ee7b7; border-color: rgba(16,185,129,0.3); }}
        .chip-flat {{ background: rgba(148,163,184,0.12); color: #cbd5e1; border-color: rgba(148,163,184,0.3); }}

        @media (max-width: 992px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .analytics-grid, .strat-grid {{ grid-template-columns: 1fr; }}
            .detail-metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        @media (max-width: 600px) {{
            body {{ padding: 12px; }}
            .detail-metrics-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-title">⚡ 股海觀浪 ｜ 13:40 機構級戰場鑑識與策略歸因總結報告</div>
        <div class="badge-group">
            <div class="badge hot">🔥 主流監控：{top_sector_str}</div>
            <div class="badge">📅 戰報日期：{display_date}</div>
        </div>
    </div>

    <!-- 歷史 Alpha 衰退趨勢追蹤艙 -->
    <div class="panel-card" style="margin-bottom: 30px;">
        <div class="panel-title">
            <span>📈 近 10 日策略累計勝率與平均報酬率趨勢追蹤 (Alpha 衰退診斷)</span>
            <span style="font-size:0.8rem; color:var(--text-muted);">動態監控策略健康度</span>
        </div>
        <div id="alpha_decay_chart" style="width: 100%; height: 280px;"></div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-title">1. 盤中動能掃描 / 觸發數</div>
            <div class="stat-value blue">{sent_count} <span>檔達標 (掃描 {total_scans} 次)</span></div>
            <div class="stat-desc">通過點火資金、均價線與乖離率把關</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">2. 收盤實戰真實勝率</div>
            <div class="stat-value {'red' if win_rate_num >= 50 else 'green'}">{win_rate_pct} <span>({win_count}勝 {lose_count}敗)</span></div>
            <div class="stat-desc">以建議進場價 (+2檔滑價) 對比收盤價</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">3. 當沖平均淨報酬率</div>
            <div class="stat-value {'red' if avg_net_ret >= 0 else 'green'}">{avg_net_ret:+.2f}% <span>/ 每筆期望值</span></div>
            <div class="stat-desc">全數抱至收盤之實質平均損益</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">4. 平均最高衝刺 (MFE) / 回撤 (MAE)</div>
            <div class="stat-value purple"><span style="color:var(--color-red); font-weight:800; font-size:1.5rem;">+{avg_mfe:.2f}%</span> <span>／</span> <span style="color:var(--color-green); font-weight:800; font-size:1.5rem;">{avg_mae:.2f}%</span></div>
            <div class="stat-desc">診斷抱單潛力與盤中洗盤容忍度</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">5. 盤中最佳作戰時段</div>
            <div class="stat-value yellow" style="font-size:1.35rem;">{best_zone_str}</div>
            <div class="stat-desc">依早盤(09-10) / 盤中(10-11) / 尾盤統計</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">6. 衝高回吐警示 (曾漲>2%未鎖住)</div>
            <div class="stat-value yellow">{giveback_count} <span>檔 ⚠️</span></div>
            <div class="stat-desc">若比例偏高，建議於 MFE +2.5% 分批停利</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">7. 點火資金不足攔截</div>
            <div class="stat-value blue">{real_funds_filtered} <span>檔 🐢</span></div>
            <div class="stat-desc">1分K爆量但未達 5000萬~1億門檻</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">8. 高檔過熱追高攔截</div>
            <div class="stat-value red">{real_overheated_filtered} <span>檔 🚫</span></div>
            <div class="stat-desc">正乖離率 >= 2.5% 強制禁止市價追高</div>
        </div>
    </div>

    <div class="analytics-grid">
        <div class="panel-card">
            <div class="panel-title">
                <span>📊 觸發標的極值歸因對比圖 (MFE 最高衝刺 vs 收盤損益 vs MAE 最大回撤)</span>
                <span style="font-size:0.8rem; color:var(--text-muted);">單位：%</span>
            </div>
            <div id="mfe_mae_chart" style="width: 100%; height: 280px;"></div>
        </div>
        <div class="panel-card">
            <div class="panel-title">
                <span>⏰ 時段效率分析 (早盤 / 盤中 / 尾盤 觸發檔數與勝率)</span>
                <span style="font-size:0.8rem; color:var(--text-muted);">驗證資金黃金期</span>
            </div>
            <div id="zone_eff_chart" style="width: 100%; height: 280px;"></div>
        </div>
    </div>

    <div class="section-title">📋 盤中爆量狙擊・全標的病理診斷總表 ({display_date})</div>
    <div class="defense-card">
        <table>
            <thead>
                <tr>
                    <th>觸發時間 (時段)</th>
                    <th>標的名稱 (代號)</th>
                    <th>主力點火資金 (乖離)</th>
                    <th>觸發價 ➔ 建議進場價</th>
                    <th>VWAP 停損線</th>
                    <th>📈 MFE (最高衝刺)</th>
                    <th>📉 MAE (最大回撤)</th>
                    <th>收盤價 (淨損益)</th>
                    <th>🩺 策略病理診斷</th>
                </tr>
            </thead>
            <tbody>
                {master_table_rows_html if master_table_rows_html else '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:25px;">該交易日尚無符合嚴格把關之觸發標的</td></tr>'}
            </tbody>
        </table>
    </div>

    <div class="section-title">🔥 逐筆微觀覆盤卡片 (點擊可切換「當日 5 分 K + 進場防線」與「近 2 月日 K」)</div>
    {sniper_cards_html if sniper_cards_html else '<div style="color:var(--text-muted); padding:25px; text-align:center; border:1px dashed var(--border-color); border-radius:10px;">該交易日無符合條件標的</div>'}

    <div class="section-title">👑 戰略選股四大分頁・收盤表現獨立驗證</div>
    <div class="strat-grid">
        {strat_groups_html if strat_groups_html else '<div style="color:var(--text-muted);">目前無選股分頁資料</div>'}
    </div>

    <div class="section-title">🛡️ 防禦黑盒子：盤中自動過濾與攔截明細</div>
    <div class="strat-grid">
        <div class="strat-box">
            <div class="strat-head"><span>🐢 資金不足攔截名單 (共 {real_funds_filtered} 檔)</span><span class="badge">成功避開流動性陷阱</span></div>
            <div style="font-size:0.85rem; color:var(--text-muted); word-break:break-all;">{funds_codes_str}</div>
        </div>
        <div class="strat-box">
            <div class="strat-head"><span>🚫 正乖離過熱攔截名單 (共 {real_overheated_filtered} 檔)</span><span class="badge">成功避開高檔A轉割韭菜</span></div>
            <div style="font-size:0.85rem; color:var(--text-muted); word-break:break-all;">{overheat_codes_str}</div>
        </div>
    </div>
</div>

<script>
    const KBARS_DB = {kbars_json_str};
    const INTRADAY_DB = {intraday_json_str};
    const CHART_NAMES = {chart_names_json};
    const CHART_MFE = {chart_mfe_json};
    const CHART_MAE = {chart_mae_json};
    const CHART_NET = {chart_net_json};
    const ZONE_WR = {zone_wr_json};
    const ZONE_TOT = {zone_tot_json};
    const TREND_DATES = {history_trend_dates_json};
    const TREND_WR = {history_trend_wr_json};
    const TREND_RET = {history_trend_ret_json};

    let chartsStore = {{}};

    function initGlobalCharts() {{
        // Alpha 衰退趨勢圖
        const domAlpha = document.getElementById('alpha_decay_chart');
        if (domAlpha && TREND_DATES.length > 0) {{
            const chartAlpha = echarts.init(domAlpha);
            chartAlpha.setOption({{
                tooltip: {{ trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#334155', textStyle: {{ color: '#fff' }} }},
                legend: {{ data: ['歷史勝率(%)', '平均單筆報酬(%)'], textStyle: {{ color: '#cbd5e1', fontSize: 11 }}, top: 0 }},
                grid: {{ left: '6%', right: '6%', top: '16%', bottom: '12%' }},
                xAxis: {{ type: 'category', data: TREND_DATES, axisLabel: {{ color: '#94a3b8', fontSize: 11 }} }},
                yAxis: [
                    {{ type: 'value', name: '勝率%', min: 0, max: 100, axisLabel: {{ color: '#94a3b8', formatter: '{{value}}%' }}, splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }} }},
                    {{ type: 'value', name: '報酬%', axisLabel: {{ color: '#38bdf8', formatter: '{{value}}%' }}, splitLine: {{ show: false }} }}
                ],
                series: [
                    {{ name: '歷史勝率(%)', type: 'line', data: TREND_WR, smooth: true, lineStyle: {{ color: '#f59e0b', width: 3 }}, itemStyle: {{ color: '#f59e0b' }} }},
                    {{ name: '平均單筆報酬(%)', type: 'bar', yAxisIndex: 1, data: TREND_RET, barWidth: '30%', itemStyle: {{ color: '#38bdf8', borderRadius: [4,4,0,0] }} }}
                ]
            }});
            chartsStore['global_alpha'] = chartAlpha;
        }}

        const domMfe = document.getElementById('mfe_mae_chart');
        if (domMfe) {{
            const chartMfe = echarts.init(domMfe);
            chartMfe.setOption({{
                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }}, backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#334155', textStyle: {{ color: '#fff' }} }},
                legend: {{ data: ['MFE 最高衝刺(%)', '收盤實質損益(%)', 'MAE 最大回撤(%)'], textStyle: {{ color: '#cbd5e1', fontSize: 11 }}, top: 0 }},
                grid: {{ left: '6%', right: '3%', top: '16%', bottom: '18%' }},
                xAxis: {{ type: 'category', data: CHART_NAMES.length ? CHART_NAMES : ['無觸發標的'], axisLabel: {{ color: '#94a3b8', fontSize: 11, rotate: CHART_NAMES.length > 6 ? 20 : 0 }} }},
                yAxis: {{ type: 'value', splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }}, axisLabel: {{ color: '#94a3b8', formatter: '{{value}}%' }} }},
                series: [
                    {{ name: 'MFE 最高衝刺(%)', type: 'bar', data: CHART_MFE, itemStyle: {{ color: '#ef4444' }} }},
                    {{ name: '收盤實質損益(%)', type: 'bar', data: CHART_NET, itemStyle: {{ color: '#38bdf8' }} }},
                    {{ name: 'MAE 最大回撤(%)', type: 'bar', data: CHART_MAE, itemStyle: {{ color: '#10b981' }} }}
                ]
            }});
            chartsStore['global_mfe'] = chartMfe;
        }}

        const domZone = document.getElementById('zone_eff_chart');
        if (domZone) {{
            const chartZone = echarts.init(domZone);
            chartZone.setOption({{
                tooltip: {{ trigger: 'axis', backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#334155', textStyle: {{ color: '#fff' }} }},
                legend: {{ data: ['觸發檔數', '時段勝率(%)'], textStyle: {{ color: '#cbd5e1', fontSize: 11 }}, top: 0 }},
                grid: {{ left: '10%', right: '10%', top: '18%', bottom: '12%' }},
                xAxis: {{ type: 'category', data: ['早盤 (09-10)', '盤中 (10-11)', '尾盤 (11-13:24)'], axisLabel: {{ color: '#94a3b8', fontSize: 11 }} }},
                yAxis: [
                    {{ type: 'value', name: '檔數', axisLabel: {{ color: '#94a3b8' }}, splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }} }},
                    {{ type: 'value', name: '勝率%', min: 0, max: 100, axisLabel: {{ color: '#f59e0b', formatter: '{{value}}%' }}, splitLine: {{ show: false }} }}
                ],
                series: [
                    {{ name: '觸發檔數', type: 'bar', barWidth: '35%', data: ZONE_TOT, itemStyle: {{ color: '#3b82f6', borderRadius: [4,4,0,0] }} }},
                    {{ name: '時段勝率(%)', type: 'line', yAxisIndex: 1, data: ZONE_WR, smooth: true, lineStyle: {{ color: '#f59e0b', width: 3 }}, itemStyle: {{ color: '#f59e0b' }} }}
                ]
            }});
            chartsStore['global_zone'] = chartZone;
        }}
    }}

    function renderIntraday5m(code) {{
        const dom = document.getElementById('chart_box_' + code);
        if (!dom) return;
        if (chartsStore['box_' + code]) chartsStore['box_' + code].dispose();

        const info = INTRADAY_DB[code];
        if (!info || !info.bars || info.bars.length === 0) {{
            renderDailyK(code);
            return;
        }}

        let cat = [], vals = [], vols = [];
        info.bars.forEach(b => {{
            cat.push(b.t);
            vals.push([b.o, b.c, b.l, b.h]);
            vols.push({{ value: b.v, itemStyle: {{ color: b.c >= b.o ? '#ef4444' : '#10b981' }} }});
        }});

        const chart = echarts.init(dom);
        chart.setOption({{
            tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }}, backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#334155', textStyle: {{ color: '#fff' }} }},
            axisPointer: {{ link: [{{ xAxisIndex: 'all' }}] }},
            grid: [
                {{ left: '7%', right: '5%', top: '8%', height: '58%' }},
                {{ left: '7%', right: '5%', top: '72%', height: '20%' }}
            ],
            xAxis: [
                {{ type: 'category', data: cat, boundaryGap: true, axisLabel: {{ show: false }}, gridIndex: 0 }},
                {{ type: 'category', data: cat, boundaryGap: true, axisLabel: {{ color: '#94a3b8', fontSize: 10 }}, gridIndex: 1 }}
            ],
            yAxis: [
                {{ type: 'value', scale: true, splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 10 }}, gridIndex: 0 }},
                {{ type: 'value', scale: false, splitLine: {{ show: false }}, axisLabel: {{ show: false }}, gridIndex: 1 }}
            ],
            series: [
                {{
                    name: '當日5分K', type: 'candlestick', data: vals, xAxisIndex: 0, yAxisIndex: 0,
                    itemStyle: {{ color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }},
                    markLine: {{
                        symbol: ['none', 'none'],
                        data: [
                            {{ yAxis: info.entry, name: '建議進場價', lineStyle: {{ color: '#38bdf8', width: 2, type: 'solid' }}, label: {{ formatter: '進場 {{c}}', color: '#38bdf8', position: 'insideEndTop' }} }},
                            {{ yAxis: info.stop, name: 'VWAP停損線', lineStyle: {{ color: '#f59e0b', width: 2, type: 'dashed' }}, label: {{ formatter: 'VWAP防線 {{c}}', color: '#f59e0b', position: 'insideEndBottom' }} }}
                        ]
                    }}
                }},
                {{ name: '5分成交量(張)', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1 }}
            ],
            animation: false
        }});
        chartsStore['box_' + code] = chart;
    }}

    function renderDailyK(code) {{
        const dom = document.getElementById('chart_box_' + code);
        if (!dom) return;
        if (chartsStore['box_' + code]) chartsStore['box_' + code].dispose();

        let kbars = KBARS_DB[code];
        if (!kbars) return;
        let dates = Object.keys(kbars).sort();
        if (dates.length === 0) return;

        let cat = [], vals = [], vols = [];
        dates.forEach(d => {{
            let kb = kbars[d];
            let c = parseFloat(kb.c || 0);
            let o = parseFloat(kb.o || c);
            let l = parseFloat(kb.l || c);
            let h = parseFloat(kb.h || c);
            let v = parseFloat(kb.v || 0);
            if (c <= 0 || isNaN(c)) return;
            cat.push(d.substring(5));
            vals.push([o, c, l, h]);
            vols.push({{ value: v, itemStyle: {{ color: c >= o ? '#ef4444' : '#10b981' }} }});
        }});

        const calcMA = (dayCount, data) => {{
            let res = [];
            for (let i = 0; i < data.length; i++) {{
                if (i < dayCount - 1) {{ res.push('-'); continue; }}
                let sum = 0;
                for (let j = 0; j < dayCount; j++) sum += data[i - j][1];
                res.push(+(sum / dayCount).toFixed(2));
            }}
            return res;
        }};

        const chart = echarts.init(dom);
        chart.setOption({{
            tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }}, backgroundColor: 'rgba(15,23,42,0.95)', borderColor: '#334155', textStyle: {{ color: '#fff' }} }},
            axisPointer: {{ link: [{{ xAxisIndex: 'all' }}] }},
            grid: [
                {{ left: '7%', right: '5%', top: '8%', height: '58%' }},
                {{ left: '7%', right: '5%', top: '72%', height: '20%' }}
            ],
            xAxis: [
                {{ type: 'category', data: cat, boundaryGap: true, axisLabel: {{ show: false }}, gridIndex: 0 }},
                {{ type: 'category', data: cat, boundaryGap: true, axisLabel: {{ color: '#94a3b8', fontSize: 10 }}, gridIndex: 1 }}
            ],
            yAxis: [
                {{ type: 'value', scale: true, min: 'dataMin', splitLine: {{ lineStyle: {{ color: '#1e293b', type: 'dashed' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 10 }}, gridIndex: 0 }},
                {{ type: 'value', scale: false, splitLine: {{ show: false }}, axisLabel: {{ show: false }}, gridIndex: 1 }}
            ],
            series: [
                {{ name: '日K線', type: 'candlestick', data: vals, itemStyle: {{ color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }}, xAxisIndex: 0, yAxisIndex: 0 }},
                {{ name: '5MA', type: 'line', data: calcMA(5, vals), smooth: true, showSymbol: false, lineStyle: {{ color: '#fbbf24', width: 2 }}, xAxisIndex: 0, yAxisIndex: 0 }},
                {{ name: '10MA', type: 'line', data: calcMA(10, vals), smooth: true, showSymbol: false, lineStyle: {{ color: '#3b82f6', width: 2 }}, xAxisIndex: 0, yAxisIndex: 0 }},
                {{ name: '20MA', type: 'line', data: calcMA(20, vals), smooth: true, showSymbol: false, lineStyle: {{ color: '#c084fc', width: 2 }}, xAxisIndex: 0, yAxisIndex: 0 }},
                {{ name: '成交量', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1 }}
            ],
            animation: false
        }});
        chartsStore['box_' + code] = chart;
    }}

    function switchKMode(code, mode) {{
        const btn5m = document.getElementById('tab_5m_' + code);
        const btn1d = document.getElementById('tab_1d_' + code);
        if (mode === '5m') {{
            if (btn5m) btn5m.classList.add('active');
            if (btn1d) btn1d.classList.remove('active');
            renderIntraday5m(code);
        }} else {{
            if (btn1d) btn1d.classList.add('active');
            if (btn5m) btn5m.classList.remove('active');
            renderDailyK(code);
        }}
    }}

    window.addEventListener('load', () => {{
        initGlobalCharts();
        for (let code in INTRADAY_DB) {{
            renderIntraday5m(code);
        }}
        document.querySelectorAll('details.sniper-card').forEach(det => {{
            det.addEventListener('toggle', () => {{
                if (det.open) {{
                    setTimeout(() => {{
                        Object.values(chartsStore).forEach(c => c && c.resize());
                    }}, 60);
                }}
            }});
        }});
    }});

    window.addEventListener('resize', () => {{
        Object.values(chartsStore).forEach(c => c && c.resize());
    }});
</script>
</body>
</html>
"""

    war_room_memory_cache[target_date_str] = html_content
    war_room_summary_cache[target_date_str] = final_report
    with open(output_html_name, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open("daily_review_latest.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        token = os.environ.get('PCLOUD_AUTH_TOKEN', '')
        folder_id_main = os.environ.get('PCLOUD_FOLDER_ID', '31448526072')
        folder_id_history = os.environ.get('PCLOUD_HISTORY_FOLDER_ID', '33133582905')

        if token:
            if os.path.exists(output_html_name):
                with open(output_html_name, 'rb') as f:
                    requests.post(f"https://api.pcloud.com/uploadfile?auth={token}&folderid={folder_id_history}", files={'file': (output_html_name, f, 'text/html')}, timeout=15)
            if os.path.exists('daily_review_latest.html'):
                with open('daily_review_latest.html', 'rb') as f:
                    requests.post(f"https://api.pcloud.com/uploadfile?auth={token}&folderid={folder_id_main}", files={'file': ('daily_review_latest.html', f, 'text/html')}, timeout=15)
    except:
        pass

    if push_to_groups:
        TARGET_GROUP_IDS = [
            "C0481b44935888bb1dc20dfd52a675e8a",
            "C47bfa8e16a7216bd54dceb3b5e90cfa0"
        ]
        for group_id in TARGET_GROUP_IDS:
            try:
                smart_push_with_menu(group_id, final_report)
            except:
                pass

    return html_content, final_report


def afternoon_review_loop():
    import time, datetime
    print("📡 [收盤檢討哨] 雲端 HTML 戰情室自動生成引擎 (支援跨日回溯) 已就位...", flush=True)
    last_sent_date = ""

    # 💥 開機時預先在背景把最近一個交易日的戰情室建立起來，確保隨時點擊秒開！
    try:
        latest_d, _ = resolve_latest_trading_date()
        build_war_room_report(target_date_str=latest_d, push_to_groups=False)
        print(f"✅ [開機預熱完畢] 已自動完成最近交易日 ({latest_d}) 戰情網頁預先編譯！", flush=True)
    except Exception as e_boot:
        print(f"⚠️ 開機預熱戰情網頁略過: {e_boot}", flush=True)

    while True:
        try:
            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            now = datetime.datetime.now(tz_tw)
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute
            current_date_str = now.strftime("%Y-%m-%d")
            today_str = now.strftime("%Y%m%d")

            if not is_weekend and (1355 <= current_time_num <= 1430) and (last_sent_date != current_date_str):
                print("🔍 [戰場鑑識] 時間已達 13:55，開始自動結算今日戰情網頁...", flush=True)
                build_war_room_report(target_date_str=today_str, push_to_groups=True)
                last_sent_date = current_date_str
                print(f"🔒 [防護生效] 今日 ({current_date_str}) 結算已經完成上鎖。", flush=True)

        except Exception as e:
            print(f"⚠️ 雲端收盤鑑識迴圈異常: {e}", flush=True)

        time.sleep(300)


# 啟動盤中巡邏引擎

threading.Thread(target=market_patrol_loop, daemon=True).start()

# 啟動基本面情報掃描引擎

threading.Thread(target=fundamental_patrol_loop, daemon=True).start()

# 💥 啟動當沖雷達連續掃描引擎

threading.Thread(target=continuous_radar_loop, daemon=True).start()

# 💥 啟動收盤後多分頁戰場鑑識引擎

threading.Thread(target=afternoon_review_loop, daemon=True).start()



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

# 💬 戰情大廳：WebSocket 即時通訊樞紐與記憶模組

# ==========================================================

CHAT_FILE = "chat_memory.json"  # 💥 新增：實體對話紀錄檔案

MAX_HISTORY = 1000  # 設定大廳最多保留最新 1000 筆訊息



# 💥 新增：開機時讀取實體硬碟的函數

def load_chat_history():

    if os.path.exists(CHAT_FILE):

        try:

            with open(CHAT_FILE, 'r', encoding='utf-8') as f:

                return json.load(f)

        except: pass

    return []



# 💥 新增：收到訊息時寫入實體硬碟的函數

def save_chat_history(data):

    try:

        with open(CHAT_FILE, 'w', encoding='utf-8') as f:

            json.dump(data, f, ensure_ascii=False)

    except: pass



# 啟動時立刻讀取舊有的對話紀錄

chat_history = load_chat_history()



@socketio.on('connect')

def handle_connect():

    # 戰友連線時，立刻把歷史對話紀錄發給他

    emit('load_history', chat_history)



@socketio.on('send_message')

def handle_client_message(data):

    sender = data.get('sender', '游擊兵')

    msg = data.get('msg', '')

    print(f"💬 [大廳廣播] {sender}: {msg}", flush=True)

    

    # 將訊息打包

    message_data = {'sender': sender, 'msg': msg}

    

    # 寫入母艦記憶體

    chat_history.append(message_data)

    # 如果歷史紀錄超過設定的上限，就剔除最舊的一筆

    if len(chat_history) > MAX_HISTORY:

        chat_history.pop(0)

    

    # 💥 關鍵補給：將更新後的陣列立刻寫入實體檔案存檔！

    save_chat_history(chat_history)

    

    # 瞬間將訊息無延遲空投給所有連線中的戰友

    emit('receive_message', message_data, broadcast=True)



# ==========================================================

# 🔔 Web Push 伺服器端：接收裝置訂閱與發射防空警報

# ==========================================================

from pywebpush import webpush, WebPushException



# 暫存所有訂閱防空警報的戰友裝置清單

push_subscriptions = []



@app.route('/subscribe_push', methods=['POST'])

def subscribe_push():

    data = request.json

    sub = data.get('sub')

    sender = data.get('sender', '未知戰友')

    if sub:

        # 避免重複儲存相同的裝置

        if sub not in push_subscriptions:

            push_subscriptions.append({'sender': sender, 'sub': sub})

        print(f"✅ 成功註冊戰友 [{sender}] 的防空警報接收器！", flush=True)

        return jsonify({"status": "success", "message": "防空警報雷達鎖定成功！"}), 200

    return jsonify({"status": "error", "message": "無效的訂閱資料"}), 400



# 當盤中偵測到爆量訊號時，呼叫此函數向所有已訂閱的戰友發射通知！

def trigger_air_raid_alarm(title, body):

    vapid_private_key = os.environ.get('VAPID_PRIVATE_KEY')

    vapid_claim_email = os.environ.get('VAPID_SUBJECT', 'mailto:pd91233@gmail.com')



    if not vapid_private_key:

        print("⚠️ 警告：未找到 VAPID_PRIVATE_KEY 環境變數，無法發送推播！", flush=True)

        return



    for client in push_subscriptions:

        try:

            webpush(

                subscription_info=client['sub'],

                data=json.dumps({"title": title, "body": body, "url": "https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html"}),

                vapid_private_key=vapid_private_key,

                vapid_claims={"sub": vapid_claim_email}

            )

            print(f"🚀 成功向戰友 [{client['sender']}] 發射防空警報！", flush=True)

        except WebPushException as ex:

            print(f"❌ 推播發送失敗 ({client['sender']}): {ex}", flush=True)





if __name__ == "__main__":

    print("🚀 戰情室與雷達掃描引擎全面啟動 (含 WebSocket 即時通訊與 Web Push 裝甲)...", flush=True)

    port = int(os.environ.get("PORT", 10000))

    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True) 

