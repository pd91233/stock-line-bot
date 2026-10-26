import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, jsonify, request, Flask

heatmap_bp = Blueprint("heatmap_bp", __name__)

# 優先讀取環境變數，若無則使用統帥的富果 API Key
FUGLE_API_KEY = os.environ.get(
    "FUGLE_API_KEY",
    "NDkwOGFiN2EtMWRkMC00MmUwLTgzYmUtYTQ0NzdjMDA2MTAzIGY5N2NjMGFlLTk3NjMtNDkyOS04OWI0LTBkZGNlOWI3YTY5Zg=="
)

# 65 秒快取保護（確保永遠不會超過富果基本用戶每分鐘 60 次上限）
CACHE_TTL = 65
CACHE_FILE = "heatmap_cache.json"

_market_cache = {
    "timestamp": 0,
    "stocks_map": {}  # 以 symbol 為 key 儲存，支援局部更新不掉資料
}

# 精選 12 大主流產業 × 30 檔核心領頭羊（單次全掃描僅需 30 次請求，留足 30 次額度供單檔五檔刷新）
SECTOR_STOCKS = [
    # 半導體 (5檔)
    {"symbol": "2330", "name": "台積電", "sector": "半導體", "market": "TSE", "mcap": 215000},
    {"symbol": "2454", "name": "聯發科", "sector": "半導體", "market": "TSE", "mcap": 21800},
    {"symbol": "3711", "name": "日月光投控", "sector": "半導體", "market": "TSE", "mcap": 7200},
    {"symbol": "2303", "name": "聯電", "sector": "半導體", "market": "TSE", "mcap": 6500},
    {"symbol": "3661", "name": "世芯-KY", "sector": "半導體", "market": "TSE", "mcap": 2350},
    # 電腦週邊 (4檔)
    {"symbol": "2382", "name": "廣達", "sector": "電腦週邊", "market": "TSE", "mcap": 11800},
    {"symbol": "3231", "name": "緯創", "sector": "電腦週邊", "market": "TSE", "mcap": 3350},
    {"symbol": "6669", "name": "緯穎", "sector": "電腦週邊", "market": "TSE", "mcap": 3850},
    {"symbol": "3017", "name": "奇鋐", "sector": "電腦週邊", "market": "TSE", "mcap": 2550},
    # 電子組件 (4檔)
    {"symbol": "2308", "name": "台達電", "sector": "電子組件", "market": "TSE", "mcap": 10200},
    {"symbol": "2327", "name": "國巨", "sector": "電子組件", "market": "TSE", "mcap": 3250},
    {"symbol": "3037", "name": "欣興", "sector": "電子組件", "market": "TSE", "mcap": 2450},
    {"symbol": "3324", "name": "雙鴻", "sector": "電子組件", "market": "OTC", "mcap": 620},
    # 其他電子 (3檔)
    {"symbol": "2317", "name": "鴻海", "sector": "其他電子", "market": "TSE", "mcap": 29800},
    {"symbol": "2360", "name": "致茂", "sector": "其他電子", "market": "TSE", "mcap": 1680},
    {"symbol": "2404", "name": "漢唐", "sector": "其他電子", "market": "TSE", "mcap": 790},
    # 重電電機 (3檔)
    {"symbol": "1519", "name": "華城", "sector": "重電電機", "market": "TSE", "mcap": 1950},
    {"symbol": "1503", "name": "士電", "sector": "重電電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1513", "name": "中興電", "sector": "重電電機", "market": "TSE", "mcap": 880},
    # 金融保險 (3檔)
    {"symbol": "2881", "name": "富邦金", "sector": "金融保險", "market": "TSE", "mcap": 12400},
    {"symbol": "2882", "name": "國泰金", "sector": "金融保險", "market": "TSE", "mcap": 10100},
    {"symbol": "2891", "name": "中信金", "sector": "金融保險", "market": "TSE", "mcap": 7500},
    # 航運業 (2檔)
    {"symbol": "2603", "name": "長榮", "sector": "航運業", "market": "TSE", "mcap": 4600},
    {"symbol": "2609", "name": "陽明", "sector": "航運業", "market": "TSE", "mcap": 2550},
    # 光電面板 (2檔)
    {"symbol": "3008", "name": "大立光", "sector": "光電面板", "market": "TSE", "mcap": 3450},
    {"symbol": "3481", "name": "群創", "sector": "光電面板", "market": "TSE", "mcap": 1450},
    # 通訊網路 (1檔)
    {"symbol": "2345", "name": "智邦", "sector": "通訊網路", "market": "TSE", "mcap": 3180},
    # 造船軍工 (1檔)
    {"symbol": "2208", "name": "台船", "sector": "造船軍工", "market": "TSE", "mcap": 195},
    # 生技醫療 (1檔)
    {"symbol": "6446", "name": "藥華藥", "sector": "生技醫療", "market": "OTC", "mcap": 2150},
    # 傳產原物料 (1檔)
    {"symbol": "2002", "name": "中鋼", "sector": "傳產原物料", "market": "TSE", "mcap": 3450},
]


def _load_disk_cache():
    """啟動時載入本地硬碟快取，避免重開程式時重複消耗 API 額度"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                _market_cache["timestamp"] = saved.get("timestamp", 0)
                _market_cache["stocks_map"] = saved.get("stocks_map", {})
        except Exception as e:
            print(f"⚠️ 讀取本地快取略過: {e}", flush=True)


def _save_disk_cache():
    """將最新抓取結果寫入硬碟快取"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_market_cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ 寫入本地快取略過: {e}", flush=True)


# 模組載入時先預讀硬碟快取
_load_disk_cache()


def fetch_single_fugle_quote(stock_info):
    """向富果 API 抓取單一個股即時報價與五檔"""
    sym = stock_info["symbol"]
    url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{sym}"
    headers = {"X-API-KEY": FUGLE_API_KEY, "User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            d = res.json()
            total = d.get("total", {})
            trade_val_yi = round(total.get("tradeValue", 0) / 1e8, 2)
            if trade_val_yi <= 0:
                trade_val_yi = 0.5
            return {
                **stock_info,
                "price": d.get("lastPrice") or d.get("closePrice") or d.get("referencePrice") or 0,
                "refPrice": d.get("referencePrice") or d.get("previousClose") or 0,
                "openPrice": d.get("openPrice") or 0,
                "highPrice": d.get("highPrice") or 0,
                "lowPrice": d.get("lowPrice") or 0,
                "avgPrice": d.get("avgPrice") or 0,
                "change": d.get("change", 0),
                "changePercent": round(d.get("changePercent", 0), 2),
                "tradeValue": trade_val_yi,
                "tradeVolume": total.get("tradeVolume", 0),
                "bidVol": total.get("tradeVolumeAtBid", 0),
                "askVol": total.get("tradeVolumeAtAsk", 0),
                "bids": d.get("bids", []),
                "asks": d.get("asks", []),
            }, 200
        else:
            return None, res.status_code
    except Exception as e:
        print(f"⚠️ 抓取 {sym} 連線異常: {e}", flush=True)
        return None, 500


def get_realtime_heatmap_data(force_refresh=False):
    """取得全市場熱力圖資料（含 65 秒保護快取與硬碟快取容錯）"""
    now = time.time()
    elapsed = now - _market_cache["timestamp"]

    # 若在 65 秒保護期內且已有完整資料，直接回傳快取
    if not force_refresh and _market_cache["stocks_map"] and elapsed < CACHE_TTL:
        remain = int(CACHE_TTL - elapsed)
        print(f"⚡ [智慧快取命中] 距離下次富果 API 刷新還有 {remain} 秒 (共 {len(_market_cache['stocks_map'])} 檔)", flush=True)
        return list(_market_cache["stocks_map"].values()), True

    print("📡 正在向富果 API 併發同步 12 大產業最新數據...", flush=True)
    success_count = 0
    rate_limited_count = 0

    # 限制 max_workers=5 溫和併發，避免瞬間塞爆連線
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_fugle_quote, item): item for item in SECTOR_STOCKS}
        for future in as_completed(futures):
            item = futures[future]
            res_data, status_code = future.result()
            if res_data:
                _market_cache["stocks_map"][item["symbol"]] = res_data
                success_count += 1
            elif status_code == 429:
                rate_limited_count += 1

    if rate_limited_count > 0:
        print(f"⚠️ 提醒：有 {rate_limited_count} 檔觸發富果每分鐘 60 次限速 (HTTP 429)，已自動以快取資料補齊！", flush=True)

    if success_count > 0:
        _market_cache["timestamp"] = time.time()
        _save_disk_cache()
        print(f"✅ 成功更新 {success_count} 檔即時報價！(目前快取池共 {len(_market_cache['stocks_map'])} 檔)", flush=True)

    return list(_market_cache["stocks_map"].values()), False


def get_top_sectors_summary():
    """供 LINE Bot 指令直接呼叫：回傳當下前 5 大吸金產業文字速報"""
    stocks, _ = get_realtime_heatmap_data()
    if not stocks:
        return "⚠️ 富果 API 額度冷卻中（每分鐘上限 60 次），請等待 60 秒後再試。"

    sectors = {}
    for s in stocks:
        sec = s["sector"]
        if sec not in sectors:
            sectors[sec] = {"tradeValue": 0.0, "weightedChange": 0.0, "topStock": s}
        sectors[sec]["tradeValue"] += s["tradeValue"]
        sectors[sec]["weightedChange"] += s["changePercent"] * s["tradeValue"]
        if s["tradeValue"] > sectors[sec]["topStock"]["tradeValue"]:
            sectors[sec]["topStock"] = s

    ranked = []
    for sec_name, info in sectors.items():
        avg_chg = info["weightedChange"] / info["tradeValue"] if info["tradeValue"] > 0 else 0
        ranked.append({
            "sector": sec_name,
            "tradeValue": round(info["tradeValue"], 1),
            "avgChange": round(avg_chg, 2),
            "topStock": info["topStock"]
        })

    # 依成交額由大到小動態排序
    ranked.sort(key=lambda x: x["tradeValue"], reverse=True)

    lines = [f"🔥 【盤中即時資金熱力速報】(共 {len(ranked)} 大產業)"]
    for idx, r in enumerate(ranked[:6], 1):
        sign = "+" if r["avgChange"] > 0 else ""
        icon = "🔴" if r["avgChange"] > 0 else ("🟢" if r["avgChange"] < 0 else "⚪")
        ts = r["topStock"]
        ts_sign = "+" if ts["changePercent"] > 0 else ""
        lines.append(
            f"#{idx} {icon} {r['sector']} ({sign}{r['avgChange']}% | {r['tradeValue']}億)\n"
            f"   └ 領頭羊：{ts['name']} {ts['price']} ({ts_sign}{ts['changePercent']}%)"
        )
    return "\n".join(lines)


# ==================== API 路由 ====================

@heatmap_bp.route("/api/heatmap/snapshot")
def api_heatmap_snapshot():
    """前端取得全市場即時快照 API"""
    force = request.args.get("force") == "1"
    stocks, cached = get_realtime_heatmap_data(force_refresh=force)
    return jsonify({
        "status": "ok",
        "cached": cached,
        "updatedAt": time.strftime("%H:%M:%S", time.localtime(_market_cache["timestamp"] or time.time())),
        "count": len(stocks),
        "stocks": stocks
    })


@heatmap_bp.route("/api/heatmap/quote/<symbol>")
def api_single_quote(symbol):
    """點擊單一個股抽屜時，1對1即時刷新最新五檔（僅消耗 1 次請求額度）"""
    target = next(
        (s for s in SECTOR_STOCKS if s["symbol"] == symbol),
        {"symbol": symbol, "name": symbol, "sector": "自選", "market": "TSE", "mcap": 500}
    )
    fresh, status_code = fetch_single_fugle_quote(target)
    if fresh:
        _market_cache["stocks_map"][symbol] = fresh
        _save_disk_cache()
        return jsonify({"status": "ok", "stock": fresh})
    # 若單檔剛好遇到 429，回傳快取中的資料
    if symbol in _market_cache["stocks_map"]:
        return jsonify({"status": "ok", "cached": True, "stock": _market_cache["stocks_map"][symbol]})
    return jsonify({"status": "error", "code": status_code}), status_code


@heatmap_bp.route("/heatmap")
def render_heatmap_page():
    """直接渲染手機版互動資金熱力圖"""
    if os.path.exists("stock_heatmap_mobile.html"):
        with open("stock_heatmap_mobile.html", "r", encoding="utf-8") as f:
            return f.read()
    return "請確認 stock_heatmap_mobile.html 已放置於 D:\\StockCommander_V68 目錄下。", 200


if __name__ == "__main__":
    app = Flask(__name__)
    app.register_blueprint(heatmap_bp)
    print("🚀 盤中即時熱力圖測試伺服器啟動！")
    print("👉 請用電腦或手機瀏覽器打開： http://127.0.0.1:5000/heatmap")
    print("📊 正在執行富果 API 實盤併發測試...")
    print(get_top_sectors_summary())
    # 💥 關鍵修正：加上 use_reloader=False，防止 Watchdog 重複啟動吃光富果 API 額度！
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)