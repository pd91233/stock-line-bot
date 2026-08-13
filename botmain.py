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
handler = WebhookHandler(LINE_CHANNEL_SECRET)
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
            QuickReplyButton(action=MessageAction(label="📊 盤後選股", text="盤後選股"))
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
                )
            ],
            background_color="#0f172a",
            padding_all="15px"
        )
    )
    return FlexSendMessage(alt_text="📊 股海觀浪戰情選單", contents=flex_content)

# 🛡️ 統一回覆中繼站 (任何文字回覆透過此函數送出，都會自動夾帶雙排面板)
def smart_reply_with_menu(event, message_text):
    if isinstance(message_text, str):
        flex_msg = create_flex_menu_message(message_text)
    else:
        flex_msg = message_text 
    try:
        line_bot_api.reply_message(event.reply_token, flex_msg)
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
        try:
            try:
                profile = line_bot_api.get_profile(user_id)
                user_name = profile.display_name
            except Exception:
                user_name = "戰友"

            cache_data = read_cache()
            funds_summary = cache_data.get('fundsText', '目前無大盤數據')
            stocks_summary = cache_data.get('stocksText', '目前無主流數據')

            # 呼叫 Gemini 進行專業盤勢總結編排
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
        except Exception as e:
            reply_msg = f"⚠️ AI 盤勢講評生成異常：{e}"

        smart_reply_with_menu(event, reply_msg[:4000])
        return


    # 💥 新增：讓用戶隨時透過 LINE 調閱完整盤後選股網址
    if user_msg in ["盤後選股", "選股策略", "最新選股"]:
        report_url = "https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/latest_report.html"
        reply_msg = f"📊 【股海觀浪】最新盤後選股策略：\n請點擊以下連結前往觀看：\n{report_url}"
        smart_reply_with_menu(event, reply_msg)
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
                "那斯達克期": "NQ=F",
                "小道瓊期": "YM=F",
                "日經 225": "^N225",
                "南韓綜合": "^KS11",
                "恐慌指數 VIX": "^VIX",
                "美元兌台幣": "TWD=X",
                "微型黃金": "MGC=F", 
                "微型輕原油": "MCL=F",
                "比特幣 (BTC)": "BTC-USD",
                "以太幣 (ETH)": "ETH-USD",
                "台積電 ADR": "TSM",
                "輝達 (NVDA)": "NVDA",
                "甲骨文 (ORCL)": "ORCL",
                "博通 (AVGO)": "AVGO",
                "美光 (MU)": "MU",
                "微軟 (MSFT)": "MSFT",
                "亞馬遜 (AMZN)": "AMZN",
                "谷歌 (GOOGL)": "GOOGL",
                "帕蘭泰爾 (PLTR)": "PLTR",
                "蘋果 (AAPL)": "AAPL",
                "特斯拉 (TSLA)": "TSLA"
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
                )
            ],
            background_color="#0f172a",
            padding_all="15px"
        )
    )
    return FlexSendMessage(alt_text="📊 股海觀浪戰情選單", contents=flex_content)

# 🛡️ 統一回覆中繼站 (任何文字回覆透過此函數送出，都會自動夾帶雙排面板)
def smart_reply_with_menu(event, message_text):
    if isinstance(message_text, str):
        flex_msg = create_flex_menu_message(message_text)
    else:
        flex_msg = message_text # 如果原本就是 FlexSendMessage 就直接發送
    try:
        line_bot_api.reply_message(event.reply_token, flex_msg)
    except Exception as e:
        print(f"⚠️ 回覆發送受阻: {e}", flush=True)

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
# ⚡ 8. 專屬當沖連續掃描引擎 (全市場 2000 檔批次陣列雷達)
# ==========================================================
stock_tick_memory = {}
intraday_alerted_codes = set()

def process_tick_data(data, meta_info, top_ind):
    import time, datetime
    code = data.get('c')
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
        
        chg_pct = round(((z - y) / y) * 100, 2)
        gap_pct = round(((o - y) / y) * 100, 2)
        
        try:
            vwap_est = round((o + h + l + (z * v / (v if v > 0 else 1))) / 4, 2) if v > 0 else round((o + h + l + z * 2) / 5, 2)
            if abs(vwap_est - z) / z > 0.07: vwap_est = round((o + h + l + z * 2) / 5, 2)
        except:
            vwap_est = round((o + h + l + z * 2) / 5, 2)

        now_ts = time.time()
        tz = datetime.timezone(datetime.timedelta(hours=8))
        now_dt = datetime.datetime.now(tz)
        time_str = now_dt.strftime("%H:%M:%S")
        current_time_num = now_dt.hour * 100 + now_dt.minute

        if 900 <= current_time_num < 1000: time_status = "golden"
        elif 1000 <= current_time_num < 1100: time_status = "cooling"
        else: time_status = "dead_water"

        if code not in stock_tick_memory: stock_tick_memory[code] = []
        stock_tick_memory[code].append((now_ts, z, v, h, l))
        if len(stock_tick_memory[code]) > 10: stock_tick_memory[code].pop(0)

        ticks = stock_tick_memory[code]
        if len(ticks) >= 6:
            current_z, current_v = ticks[-1][1], ticks[-1][2]
            z_1m_ago, v_1m_ago = ticks[-2][1], ticks[-2][2]
            z_5m_ago, v_5m_ago = ticks[-6][1], ticks[-6][2]

            vol_1m = current_v - v_1m_ago
            vol_5m = current_v - v_5m_ago
            avg_1m_vol_in_5m = vol_5m / 5 if vol_5m > 0 else 1.0
            ignite_value = vol_1m * current_z * 1000

            is_real_attack = current_z >= z_1m_ago
            is_volume_surge = False
            
            # 💥【極度敏感測試參數】：只要有一點點量就觸發，證明雷達會叫！
            if time_status == "golden":
                if vol_1m >= 10 and ignite_value >= 500000: # 只要 10 張，50萬台幣
                    is_volume_surge = True
            elif time_status == "cooling":
                if vol_1m >= 20 and ignite_value >= 1000000: # 只要 20 張，100萬台幣
                    is_volume_surge = True
            elif time_status == "dead_water":
                if vol_1m >= 30 and ignite_value >= 2000000: # 只要 30 張，200萬台幣
                    is_volume_surge = True

            is_above_vwap = current_z >= vwap_est
            is_trend_up = current_z >= z_5m_ago

            if is_above_vwap and is_trend_up and is_volume_surge and is_real_attack:
                dist_to_high_pct = ((h - current_z) / current_z) * 100 if h > 0 else 0
                is_near_ceiling = (0 < dist_to_high_pct <= 0.8) and (current_time_num > 930)
                is_below_20ma = (ma20 > 0 and current_z < ma20)
                is_strong_gap = (gap_pct >= 2.0 and current_z >= o)

                alert_type = None
                action_guide = ""
                
                if is_near_ceiling or is_below_20ma:
                    alert_type = "⚠️ 【兵臨城下】高檔測壓或反彈逃命波"
                    action_guide = f"🎯 【小白實戰指令：⛔ 空手觀望】\n👉 戰況：{'距離今日高點極近，上方壓力沉重' if is_near_ceiling else '長線偏空'}！\n⚠️ 怎麼買：極可能是法人對倒或假點火，嚴禁此時低接或追高！\n🛡️ 策略：今日動能預期已耗盡，建議直接放棄此檔！"
                elif 1.0 <= chg_pct <= 4.5:
                    alert_type = "🌅 【破曉初升】安全起漲點火"
                    stop_loss_price = ticks[-1][4] if ticks[-1][4] > 0 else vwap_est
                    action_guide = f"🎯 【小白實戰指令：✅ 多方起漲】\n👉 戰況：{'跳空強勢開局，' if is_strong_gap else ''}底部出量點火，實體紅K攻擊！\n💰 委託：拉回 {vwap_est} ~ {current_z} 區間可分批低接。\n🛡️ 防守：以起漲K棒低點 {stop_loss_price} 為最後防守線！"
                elif 4.5 < chg_pct <= 9.0: # 放寬漲幅上限
                    alert_type = "🔥 【極限動能】高檔強勢換手區"
                    action_guide = f"🎯 【小白實戰指令：⚠️ 縮小部位短打】\n👉 戰況：短線衝太快，正乖離過大！\n⚠️ 怎麼買：切勿被爆量沖昏頭去重倉追高！\n🛡️ 策略：強勢股若拉回不破 {vwap_est}，才可小注試單。"
                    
                if alert_type:
                    intraday_alerted_codes.add(code)
                    hot_tag = f"🌟 [主流共振：{ind}]" if (top_ind != "" and top_ind in ind) else f"🏷️ [{ind}]"
                    return (
                        f"[{time_str}] ⚡ {name}({code}) {alert_type}\n"
                        f"{hot_tag} | 現價：{current_z} (均價線:{vwap_est})\n"
                        f"漲幅：{chg_pct}% | 開盤缺口：{gap_pct}%\n"
                        f"🔥 1分絕對爆量：{int(vol_1m)} 張 (點火資金 {int(ignite_value/10000)}萬)\n"
                        f"----------------------\n"
                        f"{action_guide}"
                    )
    except Exception:
        pass
    return None

def continuous_radar_loop():
    print("📡 [當沖雷達] 啟動終極穿甲通道 (Yahoo V8 Spark API)，全面突破封鎖...", flush=True)
    import time, datetime, requests
    
    error_count = 0 
    
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute
            
            # 🔒 09:00 到 13:30 之間雷達才運作
            if not is_weekend and (900 <= current_time_num <= 1330):
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                
                current_cache = read_cache()
                full_stocks = current_cache.get("fundamental_full", [])
                
                if not full_stocks:
                    time.sleep(10)
                    continue

                batch_size = 40
                for i in range(0, len(full_stocks), batch_size):
                    batch = full_stocks[i:i+batch_size]
                    
                    ex_ch_list = []
                    stock_meta = {}
                    for s in batch:
                        code = str(s.get('code', '')).strip()
                        market = s.get('market', '上市')
                        suffix = ".TW" if market == "上市" else ".TWO"
                        if code:
                            ex_ch_list.append(f"{code}{suffix}")
                            stock_meta[code] = s
                            
                    if not ex_ch_list: continue
                    
                    symbols = ",".join(ex_ch_list)
                    
                    # 💥 終極穿甲彈：使用不會報 401 且支援批次的 Yahoo V8 Spark API
                    api_url = f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}&range=1d&interval=1d"
                    
                    try:
                        res = requests.get(api_url, headers=headers, timeout=5)
                        if res.status_code == 200:
                            res_json = res.json()
                            if 'spark' in res_json and 'result' in res_json['spark']:
                                results = res_json['spark']['result']
                                
                                for data in results:
                                    if not data or not data.get('response'): continue
                                    
                                    meta = data['response'][0].get('meta', {})
                                    code = data.get('symbol', '').split('.')[0]
                                    
                                    if 'regularMarketPrice' not in meta: continue

                                    # 將 Yahoo 資料翻譯成雷達能看懂的格式
                                    formatted_data = {
                                        'c': code,
                                        'z': meta.get('regularMarketPrice', '-'),
                                        'y': meta.get('chartPreviousClose', meta.get('previousClose', '-')),
                                        'o': meta.get('regularMarketPrice', '-'), # Spark 預設以現價為基準
                                        'h': meta.get('regularMarketDayHigh', meta.get('regularMarketPrice', '-')),
                                        'l': meta.get('regularMarketDayLow', meta.get('regularMarketPrice', '-')),
                                        'v': meta.get('regularMarketVolume', 0) / 1000  # Yahoo 單位為股，轉成張
                                    }
                                    
                                    alert_msg = process_tick_data(formatted_data, stock_meta.get(code, {}), global_true_market_top_ind)
                                    
                                    if alert_msg and alert_msg not in intraday_breakout_cache:
                                        intraday_breakout_cache.insert(0, alert_msg)
                                        
                                        new_cache = read_cache()
                                        new_cache["intraday_alerts"] = intraday_breakout_cache[:10]
                                        update_cache(new_cache)
                                        
                                        try:
                                            trigger_air_raid_alarm(f"🔥 {stock_meta.get(code, {}).get('name', code)} 爆量點火！", alert_msg)
                                        except: pass
                                        
                                        TARGET_GROUP_IDS = [
                                            "C0481b44935888bb1dc20dfd52a675e8a", 
                                            "C47bfa8e16a7216bd54dceb3b5e90cfa0"  
                                        ]
                                        for group_id in TARGET_GROUP_IDS:
                                            smart_push_with_menu(group_id, f"🚨 【全市場同步跟單急報】\n{alert_msg}")
                                        
                                        print(f"🚀 [全市場雷達] 成功捕獲 {code} 爆量並空投戰報！", flush=True)
                        else:
                            error_count += 1
                            if error_count % 10 == 0:
                                print(f"⚠️ [V8通道異常] 狀態碼: {res.status_code}", flush=True)
                    except Exception as e:
                        error_count += 1
                        if error_count % 10 == 0:
                            print(f"⚠️ [雷達連線超時]: {e}", flush=True)
                    
                    if i == 0:
                        now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M:%S")
                        print(f"👁️ [{now_str}] 終極 V8 穿甲掃描中... 記憶體已追蹤 {len(stock_tick_memory)} 檔標的。", flush=True)
                        
                    time.sleep(1.2)
                    
            else:
                time.sleep(60) 
        except Exception as e:
            time.sleep(60)


# ==========================================================
# 📊 💥 終極完全體：下午 1:40 多分頁選股戰報績效驗證與當沖鑑識哨
# ==========================================================
def afternoon_review_loop():
    import time
    import datetime
    import requests
    import re
    
    print("📡 [收盤檢討哨] 多分頁選股戰報與當沖鑑識雙效驗證引擎已就位，等待下午 13:40 後執行...", flush=True)
    
    last_sent_date = ""

    while True:
        try:
            now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute
            current_date_str = now.strftime("%Y-%m-%d")
            
            if not is_weekend and current_time_num >= 1340 and last_sent_date != current_date_str:
                print("🔍 [戰場鑑識] 時間已過 13:40，開始執行收盤結算與分頁覆盤...", flush=True)
                
                review_lines = ["📊 【股海觀浪・全方位戰場鑑識與分頁驗證】\n" + "----------------------"]
                
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
                
                final_report = "\n".join(review_lines)
                
                TARGET_GROUP_IDS = [
                    "C0481b44935888bb1dc20dfd52a675e8a", 
                    "C47bfa8e16a7216bd54dceb3b5e90cfa0"
                ]
                
                # 💥 阻斷無限迴圈的打卡點
                last_sent_date = current_date_str
                
                for group_id in TARGET_GROUP_IDS:
                    smart_push_with_menu(
                        group_id,
                        final_report
                    )
                
                print("🚀 全方位爆量雷達與分頁驗證戰報已嘗試空投！", flush=True)
            
        except Exception as e:
            print(f"⚠️ 戰場鑑識異常: {e}", flush=True)
            
        time.sleep(30)


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
