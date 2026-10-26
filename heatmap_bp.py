import os
import json
import time
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import squarify
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, jsonify, request, send_from_directory

heatmap_bp = Blueprint("heatmap_bp", __name__)

FUGLE_API_KEY = os.environ.get(
    "FUGLE_API_KEY",
    "NDkwOGFiN2EtMWRkMC00MmUwLTgzYmUtYTQ0NzdjMDA2MTAzIGY5N2NjMGFlLTk3NjMtNDkyOS04OWI0LTBkZGNlOWI3YTY5Zg=="
)

CACHE_TTL = 45
CACHE_FILE = "heatmap_cache.json"
HEATMAP_IMG_PATH = "static_heatmap.png"

_market_cache = {
    "timestamp": 0,
    "stocks_map": {}
}

# 27 大標準產業分類核心戰略池
SECTOR_STOCKS = [
    # 1. 半導體
    {"symbol": "2330", "name": "台積電", "sector": "半導體", "market": "TSE", "mcap": 265000},
    {"symbol": "2454", "name": "聯發科", "sector": "半導體", "market": "TSE", "mcap": 22500},
    {"symbol": "3711", "name": "日月光投控", "sector": "半導體", "market": "TSE", "mcap": 7300},
    {"symbol": "2303", "name": "聯電", "sector": "半導體", "market": "TSE", "mcap": 6200},
    {"symbol": "3661", "name": "世芯-KY", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3034", "name": "聯詠", "sector": "半導體", "market": "TSE", "mcap": 3100},
    {"symbol": "2379", "name": "瑞昱", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3443", "name": "創意", "sector": "半導體", "market": "TSE", "mcap": 1850},
    {"symbol": "2449", "name": "京元電子", "sector": "半導體", "market": "TSE", "mcap": 1600},
    {"symbol": "3529", "name": "力旺", "sector": "半導體", "market": "OTC", "mcap": 2100},
    {"symbol": "5274", "name": "信驊", "sector": "半導體", "market": "OTC", "mcap": 2800},
    {"symbol": "6488", "name": "環球晶", "sector": "半導體", "market": "OTC", "mcap": 1950},
    {"symbol": "3105", "name": "穩懋", "sector": "半導體", "market": "OTC", "mcap": 650},

    # 2. 電子組件
    {"symbol": "2308", "name": "台達電", "sector": "電子組件", "market": "TSE", "mcap": 10200},
    {"symbol": "2327", "name": "國巨", "sector": "電子組件", "market": "TSE", "mcap": 3250},
    {"symbol": "3037", "name": "欣興", "sector": "電子組件", "market": "TSE", "mcap": 2450},
    {"symbol": "2383", "name": "台光電", "sector": "電子組件", "market": "TSE", "mcap": 2100},
    {"symbol": "3653", "name": "健策", "sector": "電子組件", "market": "TSE", "mcap": 1950},
    {"symbol": "2368", "name": "金像電", "sector": "電子組件", "market": "TSE", "mcap": 1100},
    {"symbol": "6274", "name": "台燿", "sector": "電子組件", "market": "OTC", "mcap": 480},

    # 3. 金融
    {"symbol": "2881", "name": "富邦金", "sector": "金融", "market": "TSE", "mcap": 12400},
    {"symbol": "2882", "name": "國泰金", "sector": "金融", "market": "TSE", "mcap": 10100},
    {"symbol": "2891", "name": "中信金", "sector": "金融", "market": "TSE", "mcap": 7500},
    {"symbol": "2886", "name": "兆豐金", "sector": "金融", "market": "TSE", "mcap": 5800},
    {"symbol": "2884", "name": "玉山金", "sector": "金融", "market": "TSE", "mcap": 4500},
    {"symbol": "2885", "name": "元大金", "sector": "金融", "market": "TSE", "mcap": 4200},
    {"symbol": "5871", "name": "中租-KY", "sector": "金融", "market": "TSE", "mcap": 2100},

    # 4. 電腦周邊
    {"symbol": "2382", "name": "廣達", "sector": "電腦周邊", "market": "TSE", "mcap": 11800},
    {"symbol": "3231", "name": "緯創", "sector": "電腦周邊", "market": "TSE", "mcap": 3350},
    {"symbol": "6669", "name": "緯穎", "sector": "電腦周邊", "market": "TSE", "mcap": 3850},
    {"symbol": "3017", "name": "奇鋐", "sector": "電腦周邊", "market": "TSE", "mcap": 2550},
    {"symbol": "2357", "name": "華碩", "sector": "電腦周邊", "market": "TSE", "mcap": 4300},
    {"symbol": "2376", "name": "技嘉", "sector": "電腦周邊", "market": "TSE", "mcap": 1900},
    {"symbol": "3324", "name": "雙鴻", "sector": "電腦周邊", "market": "OTC", "mcap": 620},

    # 5. 其他電子
    {"symbol": "2360", "name": "致茂", "sector": "其他電子", "market": "TSE", "mcap": 1680},
    {"symbol": "2404", "name": "漢唐", "sector": "其他電子", "market": "TSE", "mcap": 790},
    {"symbol": "6409", "name": "旭隼", "sector": "其他電子", "market": "TSE", "mcap": 1700},

    # 6. 網通
    {"symbol": "2345", "name": "智邦", "sector": "網通", "market": "TSE", "mcap": 3180},
    {"symbol": "2412", "name": "中華電", "sector": "網通", "market": "TSE", "mcap": 9600},
    {"symbol": "6442", "name": "光聖", "sector": "網通", "market": "TSE", "mcap": 350},
    {"symbol": "6285", "name": "啟碁", "sector": "網通", "market": "TSE", "mcap": 680},
    {"symbol": "3491", "name": "昇達科", "sector": "網通", "market": "OTC", "mcap": 680},

    # 7. 塑膠
    {"symbol": "1301", "name": "台塑", "sector": "塑膠", "market": "TSE", "mcap": 3100},
    {"symbol": "1303", "name": "南亞", "sector": "塑膠", "market": "TSE", "mcap": 3300},
    {"symbol": "1326", "name": "台化", "sector": "塑膠", "market": "TSE", "mcap": 2500},
    {"symbol": "1314", "name": "中石化", "sector": "塑膠", "market": "TSE", "mcap": 310},
    {"symbol": "1304", "name": "台聚", "sector": "塑膠", "market": "TSE", "mcap": 280},
    {"symbol": "1305", "name": "華夏", "sector": "塑膠", "market": "TSE", "mcap": 210},

    # 8. 化學
    {"symbol": "1717", "name": "長興", "sector": "化學", "market": "TSE", "mcap": 360},
    {"symbol": "4763", "name": "材料-KY", "sector": "化學", "market": "OTC", "mcap": 950},

    # 9. 油電
    {"symbol": "6505", "name": "台塑化", "sector": "油電", "market": "TSE", "mcap": 3800},

    # 10. 光電
    {"symbol": "3008", "name": "大立光", "sector": "光電", "market": "TSE", "mcap": 3450},
    {"symbol": "3481", "name": "群創", "sector": "光電", "market": "TSE", "mcap": 1450},
    {"symbol": "2409", "name": "友達", "sector": "光電", "market": "TSE", "mcap": 1350},
    {"symbol": "3406", "name": "玉晶光", "sector": "光電", "market": "TSE", "mcap": 580},
    {"symbol": "8069", "name": "元太", "sector": "光電", "market": "OTC", "mcap": 3100},
    {"symbol": "5483", "name": "中美晶", "sector": "光電", "market": "OTC", "mcap": 1850},

    # 11. 航運
    {"symbol": "2603", "name": "長榮", "sector": "航運", "market": "TSE", "mcap": 4600},
    {"symbol": "2609", "name": "陽明", "sector": "航運", "market": "TSE", "mcap": 2550},
    {"symbol": "2615", "name": "萬海", "sector": "航運", "market": "TSE", "mcap": 2400},
    {"symbol": "2618", "name": "長榮航", "sector": "航運", "market": "TSE", "mcap": 2150},
    {"symbol": "2610", "name": "華航", "sector": "航運", "market": "TSE", "mcap": 1450},
    {"symbol": "2646", "name": "星宇航空", "sector": "航運", "market": "TSE", "mcap": 750},

    # 12. 電機
    {"symbol": "1519", "name": "華城", "sector": "電機", "market": "TSE", "mcap": 1950},
    {"symbol": "1503", "name": "士電", "sector": "電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1513", "name": "中興電", "sector": "電機", "market": "TSE", "mcap": 880},
    {"symbol": "1514", "name": "亞力", "sector": "電機", "market": "TSE", "mcap": 320},
    {"symbol": "1504", "name": "東元", "sector": "電機", "market": "TSE", "mcap": 1100},
    {"symbol": "1590", "name": "亞德客-KY", "sector": "電機", "market": "TSE", "mcap": 2100},
    {"symbol": "2049", "name": "上銀", "sector": "電機", "market": "TSE", "mcap": 820},

    # 13. 營建
    {"symbol": "2542", "name": "興富發", "sector": "營建", "market": "TSE", "mcap": 880},
    {"symbol": "2504", "name": "國產", "sector": "營建", "market": "TSE", "mcap": 580},
    {"symbol": "2548", "name": "華固", "sector": "營建", "market": "TSE", "mcap": 350},
    {"symbol": "2520", "name": "冠德", "sector": "營建", "market": "TSE", "mcap": 310},
    {"symbol": "5522", "name": "遠雄", "sector": "營建", "market": "TSE", "mcap": 480},

    # 14. 鋼鐵
    {"symbol": "2002", "name": "中鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 3450},
    {"symbol": "2027", "name": "大成鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 850},
    {"symbol": "2014", "name": "中鴻", "sector": "鋼鐵", "market": "TSE", "mcap": 310},

    # 15. 生技
    {"symbol": "6472", "name": "保瑞", "sector": "生技", "market": "TSE", "mcap": 820},
    {"symbol": "1795", "name": "美時", "sector": "生技", "market": "TSE", "mcap": 750},
    {"symbol": "6919", "name": "康霈*", "sector": "生技", "market": "TSE", "mcap": 950},
    {"symbol": "6491", "name": "晶碩", "sector": "生技", "market": "TSE", "mcap": 310},
    {"symbol": "6446", "name": "藥華藥", "sector": "生技", "market": "OTC", "mcap": 2150},
    {"symbol": "4743", "name": "合一", "sector": "生技", "market": "OTC", "mcap": 620},

    # 16. 食品
    {"symbol": "1216", "name": "統一", "sector": "食品", "market": "TSE", "mcap": 4900},
    {"symbol": "1201", "name": "味全", "sector": "食品", "market": "TSE", "mcap": 150},

    # 17. 汽車
    {"symbol": "2207", "name": "和泰車", "sector": "汽車", "market": "TSE", "mcap": 3800},
    {"symbol": "1536", "name": "和大", "sector": "汽車", "market": "TSE", "mcap": 410},

    # 18. 紡織
    {"symbol": "1476", "name": "儒鴻", "sector": "紡織", "market": "TSE", "mcap": 2800},
    {"symbol": "1477", "name": "聚陽", "sector": "紡織", "market": "TSE", "mcap": 1150},
    {"symbol": "1402", "name": "遠東新", "sector": "紡織", "market": "TSE", "mcap": 1700},

    # 19. 貿易
    {"symbol": "2912", "name": "統一超", "sector": "貿易", "market": "TSE", "mcap": 3050},
    {"symbol": "8454", "name": "富邦媒", "sector": "貿易", "market": "TSE", "mcap": 1100},

    # 20. 電器
    {"symbol": "1605", "name": "華新", "sector": "電器", "market": "TSE", "mcap": 1350},
    {"symbol": "1609", "name": "大亞", "sector": "電器", "market": "TSE", "mcap": 350},

    # 21. 水泥
    {"symbol": "1101", "name": "台泥", "sector": "水泥", "market": "TSE", "mcap": 2450},
    {"symbol": "1102", "name": "亞泥", "sector": "水泥", "market": "TSE", "mcap": 1400},

    # 22. 電子通路
    {"symbol": "3702", "name": "大聯大", "sector": "電子通路", "market": "TSE", "mcap": 1600},
    {"symbol": "8070", "name": "長華*", "sector": "電子通路", "market": "OTC", "mcap": 450},

    # 23. 運動休閒
    {"symbol": "9910", "name": "豐泰", "sector": "運動休閒", "market": "TSE", "mcap": 1300},
    {"symbol": "9921", "name": "巨大", "sector": "運動休閒", "market": "TSE", "mcap": 750},
    {"symbol": "9914", "name": "美利達", "sector": "運動休閒", "market": "TSE", "mcap": 620},

    # 24. 綠能環保
    {"symbol": "6806", "name": "森崴能源", "sector": "綠能環保", "market": "OTC", "mcap": 380},
    {"symbol": "6873", "name": "雲豹能源", "sector": "綠能環保", "market": "TSE", "mcap": 350},

    # 25. 橡膠
    {"symbol": "2105", "name": "正新", "sector": "橡膠", "market": "TSE", "mcap": 1350},
    {"symbol": "2103", "name": "台橡", "sector": "橡膠", "market": "TSE", "mcap": 310},

    # 26. 玻璃
    {"symbol": "1802", "name": "台玻", "sector": "玻璃", "market": "TSE", "mcap": 450},

    # 27. 其他
    {"symbol": "2317", "name": "鴻海", "sector": "其他", "market": "TSE", "mcap": 29800},
    {"symbol": "2208", "name": "台船", "sector": "其他", "market": "TSE", "mcap": 195},
    {"symbol": "2634", "name": "漢翔", "sector": "其他", "market": "TSE", "mcap": 460},
]

def _load_disk_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                _market_cache["timestamp"] = saved.get("timestamp", 0)
                _market_cache["stocks_map"] = saved.get("stocks_map", {})
        except:
            pass

def _save_disk_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_market_cache, f, ensure_ascii=False)
    except:
        pass

_load_disk_cache()

def _safe_float(val, default=0.0):
    try:
        if val in (None, "-", "", "null"):
            return default
        return float(val)
    except:
        return default

def fetch_twse_batch_quotes(stocks_list):
    results = {}
    chunk_size = 50
    chunks = [stocks_list[i:i + chunk_size] for i in range(0, len(stocks_list), chunk_size)]

    def _fetch_chunk(chunk):
        ex_ch_list = []
        sym_map = {}
        for item in chunk:
            prefix = "tse" if item["market"] == "TSE" else "otc"
            ex_ch_list.append(f"{prefix}_{item['symbol']}.tw")
            sym_map[item["symbol"]] = item

        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={'|'.join(ex_ch_list)}&json=1&delay=0"
        headers = {"User-Agent": "Mozilla/5.0"}
        chunk_res = {}
        try:
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                for msg in data.get("msgArray", []):
                    sym = msg.get("c")
                    if not sym or sym not in sym_map:
                        continue
                    base_info = sym_map[sym]
                    y_close = _safe_float(msg.get("y"), 0.0)
                    z_price = _safe_float(msg.get("z"), 0.0)
                    
                    if z_price <= 0:
                        b_prices = str(msg.get("b", "")).split("_")
                        a_prices = str(msg.get("a", "")).split("_")
                        z_price = _safe_float(b_prices[0], y_close) if b_prices else y_close
                        if z_price <= 0 and a_prices:
                            z_price = _safe_float(a_prices[0], y_close)

                    vol_lots = int(_safe_float(msg.get("v"), 0))
                    chg_pct = round(((z_price - y_close) / y_close) * 100, 2) if y_close > 0 and z_price > 0 else 0.0
                    est_val_yi = round((z_price * vol_lots * 1000) / 1e8, 2)
                    if est_val_yi <= 0:
                        est_val_yi = 0.2

                    chunk_res[sym] = {
                        **base_info,
                        "price": z_price,
                        "change": round(z_price - y_close, 2) if y_close > 0 else 0.0,
                        "changePercent": chg_pct,
                        "tradeValue": est_val_yi,
                        "tradeVolume": vol_lots,
                        "openPrice": _safe_float(msg.get("o"), z_price),
                        "highPrice": _safe_float(msg.get("h"), z_price),
                        "lowPrice": _safe_float(msg.get("l"), z_price),
                        "avgPrice": z_price
                    }
        except Exception as e:
            print(f"⚠️ 批次抓取異常: {e}", flush=True)
        return chunk_res

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(_fetch_chunk, c) for c in chunks]
        for f in as_completed(futures):
            results.update(f.result())

    return results

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
            if trade_val_yi <= 0:
                trade_val_yi = 0.2
            
            bids_raw = d.get("bids", [])
            asks_raw = d.get("asks", [])
            bid_vol = sum(b.get("size", 0) for b in bids_raw)
            ask_vol = sum(a.get("size", 0) for a in asks_raw)

            price = d.get("lastPrice") or d.get("closePrice") or d.get("referencePrice") or 0
            return {
                **stock_info,
                "price": price,
                "change": d.get("change", 0),
                "changePercent": round(d.get("changePercent", 0), 2),
                "openPrice": d.get("openPrice") or price,
                "highPrice": d.get("highPrice") or price,
                "lowPrice": d.get("lowPrice") or price,
                "avgPrice": d.get("avgPrice") or price,
                "tradeValue": trade_val_yi,
                "tradeVolume": total.get("tradeVolume", 0),
                "bidVol": bid_vol,
                "askVol": ask_vol,
                "bids": bids_raw[:5],
                "asks": asks_raw[:5],
            }, 200
    except:
        pass
    return None, 500

def get_realtime_heatmap_data(force_refresh=False):
    now = time.time()
    if not force_refresh and _market_cache["stocks_map"] and len(_market_cache["stocks_map"]) >= 50 and (now - _market_cache["timestamp"] < CACHE_TTL):
        return list(_market_cache["stocks_map"].values()), True

    batch_data = fetch_twse_batch_quotes(SECTOR_STOCKS)
    if batch_data:
        for sym, info in batch_data.items():
            _market_cache["stocks_map"][sym] = info

    missing = [item for item in SECTOR_STOCKS if item["symbol"] not in _market_cache["stocks_map"]]
    if missing:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_single_fugle_quote, item): item for item in missing[:20]}
            for future in as_completed(futures):
                res_data, _ = future.result()
                if res_data:
                    _market_cache["stocks_map"][res_data["symbol"]] = res_data

    _market_cache["timestamp"] = time.time()
    _save_disk_cache()

    return list(_market_cache["stocks_map"].values()), False

def get_top_sectors_summary():
    stocks, _ = get_realtime_heatmap_data()
    if not stocks:
        return "⚠️ 行情數據同步中，請稍後再試。"

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

    ranked.sort(key=lambda x: x["tradeValue"], reverse=True)
    lines = [f"🔥 【盤中即時資金熱力速報】(共 27 大產業 / {len(stocks)} 檔核心指標股)"]
    for idx, r in enumerate(ranked[:6], 1):
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
    updated_str = time.strftime("%H:%M:%S", time.localtime(_market_cache["timestamp"])) if _market_cache["timestamp"] else "--:--:--"
    return jsonify({
        "status": "ok",
        "cached": cached,
        "updatedAt": updated_str,
        "stocks": stocks
    })

@heatmap_bp.route("/api/heatmap/quote/<symbol>")
def api_single_quote(symbol):
    target = next((s for s in SECTOR_STOCKS if s["symbol"] == symbol), {"symbol": symbol, "name": symbol, "sector": "其他", "market": "TSE", "mcap": 500})
    fresh, _ = fetch_single_fugle_quote(target)
    if fresh:
        return jsonify({"status": "ok", "stock": fresh})
    cached_st = _market_cache["stocks_map"].get(symbol)
    if cached_st:
        return jsonify({"status": "ok", "stock": {**cached_st, "bidVol": 50, "askVol": 50, "bids": [], "asks": []}})
    return jsonify({"status": "error"}, 500)

@heatmap_bp.route("/heatmap-image.png")
def serve_heatmap_image():
    if os.path.exists(HEATMAP_IMG_PATH):
        return send_from_directory(".", HEATMAP_IMG_PATH)
    return "Image not ready", 404

@heatmap_bp.route("/heatmap")
def render_heatmap_page():
    if os.path.exists("stock_heatmap_mobile.html"):
        with open("stock_heatmap_mobile.html", "r", encoding="utf-8") as f:
            return f.read()
    return "HTML template not found", 404
