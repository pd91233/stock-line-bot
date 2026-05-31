# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
)
from google import genai
import requests
import os
import re
import itertools

app = Flask(__name__)

# ==========================================================
# 💓 0. 督戰隊心跳接收點 
# ==========================================================
@app.route("/", methods=['GET'])
def home():
    return "前線偵察兵：戰備狀態正常，未休眠！"

# ==========================================================
# 🔑 1. 金鑰設定與輪轉彈匣
# ==========================================================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

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
else:
    print("⚠️ 警告：雲端保險箱內未偵測到任何 GEMINI_API_KEY！")

# ==========================================================
# 📚 2. 台股標的庫 (動態雙雷達系統)
# ==========================================================
global_stock_dict = {}

def get_stock_dict():
    global global_stock_dict
    if len(global_stock_dict) > 0:
        return global_stock_dict
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        l_res = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=10, verify=False)
        if l_res.status_code == 200:
            for item in l_res.json():
                global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
                
        o_res = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", headers=headers, timeout=10, verify=False)
        if o_res.status_code == 200:
            for item in o_res.json():
                global_stock_dict[item.get('公司簡稱', '').strip()] = item.get('公司代號', '').strip()
    except:
        pass

    if len(global_stock_dict) == 0:
        try:
            url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
            res = requests.get(url, timeout=10, verify=False).json()
            if res.get("msg") == "success":
                for item in res.get("data", []):
                    if item.get("stock_name") and item.get("stock_id"):
                        global_stock_dict[item.get("stock_name").strip()] = item.get("stock_id").strip()
        except:
            pass
            
    return global_stock_dict

# ==========================================================
# 📊 3. 戰場即時數據探測儀 (直連底層 API，免套件防封鎖)
# ==========================================================
def fetch_realtime_data(stock_code):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0"}
    try:
        # 🌟 專屬大盤通道：加權指數不加後綴
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
        
        if len(valid_closes) < 20:
            return "⚠️ 歷史數據不足，無法計算均線。"
            
        latest_close = round(valid_closes[-1], 2)
        latest_vol = int(valid_vols[-1] / 1000)
        ma5 = round(sum(valid_closes[-5:]) / 5, 2)
        ma10 = round(sum(valid_closes[-10:]) / 10, 2)
        ma20 = round(sum(valid_closes[-20:]) / 20, 2)
        
        return f"最新報價 {latest_close}，成交量 {latest_vol}。5MA={ma5}，10MA={ma10}，20MA={ma20}。"
    except Exception as e:
        return "⚠️ 雷達連線受阻，無法取得數字。"

# ==========================================================
# 📡 4. Webhook 接收通道
# ==========================================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ==========================================================
# 🧠 5. 智慧過濾與戰略卡片發射 (全方位戰術武裝版)
# ==========================================================
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_msg = event.message.text.strip()
        
        # 🌟 攔截戰術連擊指令 (支援 5 大深挖模組)
        analysis_type = "綜合"
        
        # 🌟 攔截大盤專屬指令
        if user_msg == "大盤":
            analysis_type = "大盤"
        elif "技術面" in user_msg:
            analysis_type = "技術面"
            user_msg = user_msg.replace("技術面", "").strip()
        elif "籌碼面" in user_msg:
            analysis_type = "籌碼面"
            user_msg = user_msg.replace("籌碼面", "").strip()
        elif "基本面" in user_msg:
            analysis_type = "基本面"
            user_msg = user_msg.replace("基本面", "").strip()
        elif "題材面" in user_msg:
            analysis_type = "題材面"
            user_msg = user_msg.replace("題材面", "").strip()
        elif "同族群" in user_msg:
            analysis_type = "同族群"
            user_msg = user_msg.replace("同族群", "").strip()

        if len(user_msg) > 15:
            return

        is_stock_query = False
        stock_query = ""
        stock_code = ""

        # 🌟 大盤強制分流，不比對字典
        if analysis_type == "大盤" or user_msg == "大盤":
            is_stock_query = True
            stock_query = "加權指數 (大盤)"
            stock_code = "^TWII"
            analysis_type = "大盤"
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
                sorted_matches = sorted(matches.items(), key=lambda x: len(x[0]))[:10]
                choices = "\n".join([f"• {n} ({c})" for n, c in sorted_matches])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📍 找到多筆資料，請確認：\n{choices}"))
                return
            else:
                if "查詢" in user_msg or len(user_msg) >= 2:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"⚠️ 找不到符合「{user_msg}」的標的。"))
                return

        if is_stock_query:
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
                        prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【加權指數(大盤)】的整體盤勢。請直接給出客觀結論(150字內)：
1. 大盤均線多空趨勢研判。
2. 支撐與壓力防線。
3. 統帥近期總體戰略建議(積極/防禦)。
絕對不要有免責聲明與內心戲。"""
                        card_title = "📉 大盤多空雷達"
                        
                    elif analysis_type == "技術面":
                        prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】的純技術面。請直接給出客觀結論(150字內)：
1. 均線排列與乖離狀況。
2. 支撐壓力推演。
3. 短線觀察重點與風險提示。
絕對不要有免責聲明與內心戲。"""
                        card_title = "📈 技術面深度解析"
                        
                    elif analysis_type == "籌碼面":
                        prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】的籌碼與主力心理。請直接給出客觀結論(150字內)：
1. 根據目前價量，推測大戶意圖(洗盤/出貨/吃貨)。
2. 散戶目前可能的心理狀態。
3. 籌碼變化觀察重點。
絕對不要有免責聲明與內心戲。"""
                        card_title = "🕵️ 籌碼面深度解析"
                        
                    elif analysis_type == "基本面":
                        prompt = f"""你是一位台股分析師。請分析【{stock_query}】的基本面與護城河。請直接給出客觀結論(150字內)：
1. 公司核心獲利業務。
2. 產業地位與未來成長動能。
3. 長線投資價值評估。
絕對不要有免責聲明與內心戲。"""
                        card_title = "🏢 基本面價值分析"
                        
                    elif analysis_type == "題材面":
                        prompt = f"""你是一位台股操盤手。請分析【{stock_query}】目前的市場題材。請直接給出客觀結論(150字內)：
1. 所屬強勢概念股分類。
2. 近期市場炒作的利多/題材動能。
3. 資金關注度研判。
絕對不要有免責聲明與內心戲。"""
                        card_title = "🔥 題材面動能解析"
                        
                    elif analysis_type == "同族群":
                        prompt = f"""你是一位台股操盤手。請尋找【{stock_query}】的同族群戰友。請直接給出客觀結論(150字內)：
1. 列出 3~5 檔同業競爭對手或上下游供應鏈(需含股票代號)。
2. 簡述該族群目前的整體產業趨勢是向上或向下。
絕對不要有免責聲明與內心戲。"""
                        card_title = "🤝 同族群戰友雷達"
                        
                    else:
                        prompt = f"""你是一位台股操盤手。請根據真實數據：【{real_data}】
分析【{stock_query}】。請直接給出客觀結論(150字內)：
1. 📈 均線與趨勢。
2. 🕵️ 籌碼與心理推測。
3. ⚔️ 關鍵防守與觀察點。
絕對不要有免責聲明與內心戲。"""
                        card_title = "🎯 綜合戰術推演"

                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    
                    if not response.text:
                        raise ValueError("AI 回傳空白 (可能觸發安全機制)")
                        
                    ai_reply = response.text.strip()
                    success = True
                    break 
                except Exception as e:
                    print(f"⚠️ 請求失敗: {e}")
                    attempts += 1

            if success:
                # 🌟 [全新戰略儀表板]：徹底廢棄 QuickReply，改用 Flex Footer 排列 3x2 對稱網格
                footer_contents = []
                
                if analysis_type == "大盤":
                    footer_contents = [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "style": "primary", "color": "#2B6CB0", "height": "sm", "action": {"type": "message", "label": "🔥 查台積電", "text": "2330"}},
                                {"type": "button", "style": "primary", "color": "#2B6CB0", "height": "sm", "action": {"type": "message", "label": "🚢 查長榮", "text": "2603"}}
                            ]
                        }
                    ]
                else:
                    # 判斷目前在哪個分頁，點亮的給藍色(primary)，沒點的給淺灰(secondary)
                    def get_style(target):
                        return "primary" if analysis_type == target else "secondary"
                    def get_color(target):
                        return "#2B6CB0" if analysis_type == target else None

                    def create_btn(label, target, cmd):
                        btn = {
                            "type": "button",
                            "style": get_style(target),
                            "height": "sm",
                            "action": {"type": "message", "label": label, "text": cmd}
                        }
                        c = get_color(target)
                        if c: btn["color"] = c
                        return btn

                    # 第一排：技術 / 籌碼 / 基本
                    row1 = {
                        "type": "box",
                        "layout": "horizontal",
                        "spacing": "sm",
                        "contents": [
                            create_btn("📈 技術", "技術面", f"技術面 {stock_code}"),
                            create_btn("🕵️ 籌碼", "籌碼面", f"籌碼面 {stock_code}"),
                            create_btn("🏢 基本", "基本面", f"基本面 {stock_code}")
                        ]
                    }
                    
                    # 第二排：題材 / 族群 / 大盤 (大盤永遠深灰)
                    row2 = {
                        "type": "box",
                        "layout": "horizontal",
                        "spacing": "sm",
                        "margin": "sm",
                        "contents": [
                            create_btn("🔥 題材", "題材面", f"題材面 {stock_code}"),
                            create_btn("🤝 族群", "同族群", f"同族群 {stock_code}"),
                            {
                                "type": "button",
                                "style": "primary",
                                "color": "#4A5568",
                                "height": "sm",
                                "action": {"type": "message", "label": "📉 大盤", "text": "大盤"}
                            }
                        ]
                    }
                    footer_contents = [row1, row2]

                flex_content = {
                    "type": "bubble",
                    "styles": {
                        "header": {"backgroundColor": "#1A365D"}, 
                        "body": {"backgroundColor": "#F7FAFC"},
                        "footer": {"backgroundColor": "#E2E8F0"} # 加上頁尾專屬背景色，將內文與按鈕區隔
                    },
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": card_title, "color": "#D69E2E", "weight": "bold", "size": "sm"},
                            {"type": "text", "text": stock_query, "color": "#FFFFFF", "weight": "bold", "size": "xl", "margin": "md"}
                        ]
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": f"📊 雷達數據：\n{real_data}", "color": "#1A365D", "size": "xs", "weight": "bold", "wrap": True},
                            {"type": "separator", "margin": "md"},
                            {"type": "text", "text": ai_reply, "color": "#2D3748", "wrap": True, "size": "sm", "margin": "md"}
                        ]
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": footer_contents
                    }
                }
                
                # 🌟 [發射端更新]：將原本的 quick_reply 參數徹底刪除，按鈕已全數整合進卡片本體！
                line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text=f"戰報：{stock_query}", contents=flex_content))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 報告統帥：AI 金鑰連線異常，或觸發金融防護限制！"))
    
    except Exception as e:
        print(f"致命錯誤: {e}")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 系統發生不明錯誤，請稍後再試！"))
        except:
            pass

if __name__ == "__main__":
    app.run(port=5000)
