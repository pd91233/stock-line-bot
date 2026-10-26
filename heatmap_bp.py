import os
import json
import time
import requests
import matplotlib
matplotlib.use('Agg') # 必須在載入 pyplot 之前設定，防範無螢幕畫布錯誤
import matplotlib.pyplot as plt
import squarify
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, jsonify, request, Flask, send_from_directory

heatmap_bp = Blueprint("heatmap_bp", __name__)

FUGLE_API_KEY = os.environ.get(
    "FUGLE_API_KEY",
    "NDkwOGFiN2EtMWRkMC00MmUwLTgzYmUtYTQ0NzdjMDA2MTAzIGY5N2NjMGFlLTk3NjMtNDkyOS04OWI0LTBkZGNlOWI3YTY5Zg=="
)

CACHE_TTL = 65
CACHE_FILE = "heatmap_cache.json"
HEATMAP_IMG_PATH = "static_heatmap.png"  # 動態產生的熱力圖縮圖路徑

_market_cache = {
    "timestamp": 0,
    "stocks_map": {}
}

SECTOR_STOCKS = [
    {"symbol": "2330", "name": "台積電", "sector": "半導體", "market": "TSE", "mcap": 215000},
    {"symbol": "2454", "name": "聯發科", "sector": "半導體", "market": "TSE", "mcap": 21800},
    {"symbol": "3711", "name": "日月光投控", "sector": "半導體", "market": "TSE", "mcap": 7200},
    {"symbol": "2303", "name": "聯電", "sector": "半導體", "market": "TSE", "mcap": 6500},
    {"symbol": "3661", "name": "世芯-KY", "sector": "半導體", "market": "TSE", "mcap": 2350},
    {"symbol": "2382", "name": "廣達", "sector": "電腦週邊", "market": "TSE", "mcap": 11800},
    {"symbol": "3231", "name": "緯創", "sector": "電腦週邊", "market": "TSE", "mcap": 3350},
    {"symbol": "6669", "name": "緯穎", "sector": "電腦週邊", "market": "TSE", "mcap": 3850},
    {"symbol": "3017", "name": "奇鋐", "sector": "電腦週邊", "market": "TSE", "mcap": 2550},
    {"symbol": "2308", "name": "台達電", "sector": "電子組件", "market": "TSE", "mcap": 10200},
    {"symbol": "2327", "name": "國巨", "sector": "電子組件", "market": "TSE", "mcap": 3250},
    {"symbol": "3037", "name": "欣興", "sector": "電子組件", "market": "TSE", "mcap": 2450},
    {"symbol": "3324", "name": "雙鴻", "sector": "電子組件", "market": "OTC", "mcap": 620},
    {"symbol": "2317", "name": "鴻海", "sector": "其他電子", "market": "TSE", "mcap": 29800},
    {"symbol": "2360", "name": "致茂", "sector": "其他電子", "market": "TSE", "mcap": 1680},
    {"symbol": "2404", "name": "漢唐", "sector": "其他電子", "market": "TSE", "mcap": 790},
    {"symbol": "1519", "name": "華城", "sector": "重電電機", "market": "TSE", "mcap": 1950},
    {"symbol": "1503", "name": "士電", "sector": "重電電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1513", "name": "中興電", "sector": "重電電機", "market": "TSE", "mcap": 880},
    {"symbol": "2881", "name": "富邦金", "sector": "金融保險", "market": "TSE", "mcap": 12400},
    {"symbol": "2882", "name": "國泰金", "sector": "金融保險", "market": "TSE", "mcap": 10100},
    {"symbol": "2891", "name": "中信金", "sector": "金融保險", "market": "TSE", "mcap": 7500},
    {"symbol": "2603", "name": "長榮", "sector": "航運業", "market": "TSE", "mcap": 4600},
    {"symbol": "2609", "name": "陽明", "sector": "航運業", "market": "TSE", "mcap": 2550},
    {"symbol": "3008", "name": "大立光", "sector": "光電面板", "market": "TSE", "mcap": 3450},
    {"symbol": "3481", "name": "群創", "sector": "光電面板", "market": "TSE", "mcap": 1450},
    {"symbol": "2345", "name": "智邦", "sector": "通訊網路", "market": "TSE", "mcap": 3180},
    {"symbol": "2208", "name": "台船", "sector": "造船軍工", "market": "TSE", "mcap": 195},
    {"symbol": "6446", "name": "藥華藥", "sector": "生技醫療", "market": "OTC", "mcap": 2150},
    {"symbol": "2002", "name": "中鋼", "sector": "傳產原物料", "market": "TSE", "mcap": 3450},
]

def _load_disk_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                _market_cache["timestamp"] = saved.get("timestamp", 0)
                _market_cache["stocks_map"] = saved.get("stocks_map", {})
        except: pass

def _save_disk_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_market_cache, f, ensure_ascii=False)
    except: pass

_load_disk_cache()

def fetch_single_fugle_quote(stock_info):
    sym = stock_info["symbol"]
    url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{sym}"
    headers = {"X-API-KEY": FUGLE_API_KEY, "User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            d = res.json()
            total = d.get("total", {})
            trade_val_yi = round(total.get("tradeValue", 0) / 1e8, 2)
            if trade_val_yi <= 0: trade_val_yi = 0.5
            return {
                **stock_info,
                "price": d.get("lastPrice") or d.get("closePrice") or d.get("referencePrice") or 0,
                "changePercent": round(d.get("changePercent", 0), 2),
                "tradeValue": trade_val_yi,
                "tradeVolume": total.get("tradeVolume", 0),
                "bids": d.get("bids", []),
                "asks": d.get("asks", []),
            }, 200
    except: pass
    return None, 500

def get_realtime_heatmap_data(force_refresh=False):
    now = time.time()
    if not force_refresh and _market_cache["stocks_map"] and (now - _market_cache["timestamp"] < CACHE_TTL):
        return list(_market_cache["stocks_map"].values()), True

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_fugle_quote, item): item for item in SECTOR_STOCKS}
        for future in as_completed(futures):
            item = futures[future]
            res_data, status_code = future.result()
            if res_data:
                _market_cache["stocks_map"][item["symbol"]] = res_data

    _market_cache["timestamp"] = time.time()
    _save_disk_cache()
    
    # 每次更新數據後，自動在背景繪製最新熱力圖圖片
    try:
        generate_heatmap_image(list(_market_cache["stocks_map"].values()))
    except Exception as e:
        print(f"⚠️ 動態繪製熱力圖圖片失敗: {e}", flush=True)

    return list(_market_cache["stocks_map"].values()), False

def generate_heatmap_image(stocks):
    """使用 matplotlib 與 squarify 即時動態繪製方塊熱力圖圖片"""
    plt.figure(figsize=(10, 6), facecolor='#0b0f19')
    ax = plt.subplot(111)
    ax.set_facecolor('#0b0f19')

    labels = [f"{s['name']}\n{s['changePercent']:+.2f}%" for s in stocks]
    sizes = [max(s['tradeValue'], 1.0) for s in stocks]
    
    # 依漲跌幅決定 Finviz 經典色系
    colors = []
    for s in stocks:
        p = s['changePercent']
        if p >= 3: colors.append('#991b1b')
        elif p > 0: colors.append('#dc2626')
        elif p == 0: colors.append('#374151')
        elif p > -3: colors.append('#059669')
        else: colors.append('#065f46')

    squarify.plot(sizes=sizes, label=labels, color=colors, alpha=0.9, text_kwargs={'color':'white', 'fontsize':9, 'weight':'bold'}, pad=True)
    plt.title("StockCommander Realtime Heatmap", color='white', fontsize=12, fontweight='bold', pad=10)
    plt.axis('off')
    
    plt.tight_layout()
    plt.savefig(HEATMAP_IMG_PATH, dpi=150, facecolor='#0b0f19', edgecolor='none')
    plt.close()

def get_top_sectors_summary():
    stocks, _ = get_realtime_heatmap_data()
    if not stocks: return "⚠️ 富果 API 額度冷卻中，請稍後再試。"

    sectors = {}
    for s in stocks:
        sec = s["sector"]
        if sec not in sectors: sectors[sec] = {"tradeValue": 0.0, "weightedChange": 0.0, "topStock": s}
        sectors[sec]["tradeValue"] += s["tradeValue"]
        sectors[sec]["weightedChange"] += s["changePercent"] * s["tradeValue"]
        if s["tradeValue"] > sectors[sec]["topStock"]["tradeValue"]: sectors[sec]["topStock"] = s

    ranked = []
    for sec_name, info in sectors.items():
        avg_chg = info["weightedChange"] / info["tradeValue"] if info["tradeValue"] > 0 else 0
        ranked.append({"sector": sec_name, "tradeValue": round(info["tradeValue"], 1), "avgChange": round(avg_chg, 2), "topStock": info["topStock"]})

    ranked.sort(key=lambda x: x["tradeValue"], reverse=True)
    lines = [f"🔥 【盤中即時資金熱力速報】(共 12 大產業)"]
    for idx, r in enumerate(ranked[:5], 1):
        sign = "+" if r["avgChange"] > 0 else ""
        icon = "🔴" if r["avgChange"] > 0 else ("🟢" if r["avgChange"] < 0 else "⚪")
        ts = r["topStock"]
        ts_sign = "+" if ts["changePercent"] > 0 else ""
        lines.append(f"#{idx} {icon} {r['sector']} ({sign}{r['avgChange']}% | {r['tradeValue']}億)\n   └ 領頭羊：{ts['name']} {ts['price']} ({ts_sign}{ts['changePercent']}%)")
    return "\n".join(lines)

@heatmap_bp.route("/api/heatmap/snapshot")
def api_heatmap_snapshot():
    force = request.args.get("force") == "1"
    stocks, cached = get_realtime_heatmap_data(force_refresh=force)
    return jsonify({"status": "ok", "cached": cached, "stocks": stocks})

@heatmap_bp.route("/api/heatmap/quote/<symbol>")
def api_single_quote(symbol):
    target = next((s for s in SECTOR_STOCKS if s["symbol"] == symbol), {"symbol": symbol, "name": symbol, "sector": "自選", "market": "TSE", "mcap": 500})
    fresh, _ = fetch_single_fugle_quote(target)
    if fresh: return jsonify({"status": "ok", "stock": fresh})
    return jsonify({"status": "error"}), 500

@heatmap_bp.route("/heatmap-image.png")
def serve_heatmap_image():
    """提供 LINE 機器人引用的即時動態熱力圖縮圖"""
    if os.path.exists(HEATMAP_IMG_PATH):
        return send_from_directory(".", HEATMAP_IMG_PATH)
    return "Image not ready", 404

@heatmap_bp.route("/heatmap")
def render_heatmap_page():
    if os.path.exists("stock_heatmap_mobile.html"):
        with open("stock_heatmap_mobile.html", "r", encoding="utf-8") as f: return f.read()
    return "HTML template not found", 404
