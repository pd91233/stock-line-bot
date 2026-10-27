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

CACHE_TTL = 1
CACHE_FILE = "heatmap_cache.json"
HEATMAP_IMG_PATH = "static_heatmap.png"

if os.path.exists(CACHE_FILE):
    try:
        os.remove(CACHE_FILE)
    except:
        pass

_market_cache = {
    "timestamp": 0,
    "stocks_map": {}
}

SECTOR_STOCKS = [
    # 護國神山與半導體核心
    {"symbol": "2330", "name": "台積電", "sector": "半導體", "market": "TSE", "mcap": 250000},
    {"symbol": "2454", "name": "聯發科", "sector": "半導體", "market": "TSE", "mcap": 22500},
    {"symbol": "3711", "name": "日月光投控", "sector": "半導體", "market": "TSE", "mcap": 7300},
    {"symbol": "2303", "name": "聯電", "sector": "半導體", "market": "TSE", "mcap": 6200},
    {"symbol": "3661", "name": "世芯-KY", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3034", "name": "聯詠", "sector": "半導體", "market": "TSE", "mcap": 3100},
    {"symbol": "2379", "name": "瑞昱", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3443", "name": "創意", "sector": "半導體", "market": "TSE", "mcap": 1850},
    {"symbol": "2449", "name": "京元電子", "sector": "半導體", "market": "TSE", "mcap": 1600},
    {"symbol": "5347", "name": "世界", "sector": "半導體", "market": "OTC", "mcap": 1200},
    {"symbol": "6488", "name": "環球晶", "sector": "半導體", "market": "OTC", "mcap": 1950},
    {"symbol": "3105", "name": "穩懋", "sector": "半導體", "market": "OTC", "mcap": 650},
    {"symbol": "6770", "name": "力積電", "sector": "半導體", "market": "TSE", "mcap": 800},
    {"symbol": "2337", "name": "旺宏", "sector": "半導體", "market": "TSE", "mcap": 600},
    {"symbol": "2344", "name": "華邦電", "sector": "半導體", "market": "TSE", "mcap": 900},
    {"symbol": "2408", "name": "南亞科", "sector": "半導體", "market": "TSE", "mcap": 1100},
    {"symbol": "8299", "name": "群聯", "sector": "半導體", "market": "OTC", "mcap": 1300},
    {"symbol": "2451", "name": "創見", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "3260", "name": "威剛", "sector": "半導體", "market": "OTC", "mcap": 500},
    {"symbol": "8271", "name": "宇瞻", "sector": "半導體", "market": "TSE", "mcap": 300},
    {"symbol": "3006", "name": "晶豪科", "sector": "半導體", "market": "TSE", "mcap": 350},
    {"symbol": "5351", "name": "鈺創", "sector": "半導體", "market": "OTC", "mcap": 250},
    {"symbol": "2363", "name": "矽統", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "6415", "name": "矽力*-KY", "sector": "半導體", "market": "TSE", "mcap": 1500},
    {"symbol": "6772", "name": "力智", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "8081", "name": "致新", "sector": "半導體", "market": "TSE", "mcap": 500},
    {"symbol": "4961", "name": "天鈺", "sector": "半導體", "market": "TSE", "mcap": 600},
    {"symbol": "8016", "name": "矽創", "sector": "半導體", "market": "TSE", "mcap": 500},
    {"symbol": "6533", "name": "晶心科", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "6643", "name": "M31", "sector": "半導體", "market": "TSE", "mcap": 500},
    {"symbol": "3035", "name": "智原", "sector": "半導體", "market": "TSE", "mcap": 1000},
    {"symbol": "6239", "name": "力成", "sector": "半導體", "market": "TSE", "mcap": 1100},
    {"symbol": "8150", "name": "南茂", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "6147", "name": "頎邦", "sector": "半導體", "market": "TSE", "mcap": 500},
    {"symbol": "6182", "name": "合晶", "sector": "半導體", "market": "TSE", "mcap": 400},
    {"symbol": "5483", "name": "中美晶", "sector": "半導體", "market": "OTC", "mcap": 1850},
    {"symbol": "8086", "name": "宏捷科", "sector": "半導體", "market": "OTC", "mcap": 400},
    {"symbol": "2455", "name": "全新", "sector": "半導體", "market": "OTC", "mcap": 500},
    {"symbol": "3707", "name": "漢磊", "sector": "半導體", "market": "OTC", "mcap": 300},
    {"symbol": "3016", "name": "嘉晶", "sector": "半導體", "market": "OTC", "mcap": 300},

    # 電子組件
    {"symbol": "2308", "name": "台達電", "sector": "電子組件", "market": "TSE", "mcap": 10200},
    {"symbol": "2327", "name": "國巨", "sector": "電子組件", "market": "TSE", "mcap": 3250},
    {"symbol": "2313", "name": "華通", "sector": "電子組件", "market": "TSE", "mcap": 1100},
    {"symbol": "3037", "name": "欣興", "sector": "電子組件", "market": "TSE", "mcap": 2450},
    {"symbol": "3189", "name": "景碩", "sector": "電子組件", "market": "TSE", "mcap": 800},
    {"symbol": "8046", "name": "南電", "sector": "電子組件", "market": "TSE", "mcap": 1000},
    {"symbol": "3044", "name": "健鼎", "sector": "電子組件", "market": "TSE", "mcap": 1100},
    {"symbol": "4958", "name": "臻鼎-KY", "sector": "電子組件", "market": "TSE", "mcap": 1200},
    {"symbol": "2316", "name": "楠梓電", "sector": "電子組件", "market": "TSE", "mcap": 300},
    {"symbol": "2355", "name": "敬鵬", "sector": "電子組件", "market": "TSE", "mcap": 300},
    {"symbol": "5469", "name": "瀚宇博", "sector": "電子組件", "market": "TSE", "mcap": 500},
    {"symbol": "6274", "name": "台燿", "sector": "電子組件", "market": "OTC", "mcap": 480},
    {"symbol": "2368", "name": "金像電", "sector": "電子組件", "market": "TSE", "mcap": 1100},
    {"symbol": "2383", "name": "台光電", "sector": "電子組件", "market": "TSE", "mcap": 2100},
    {"symbol": "6213", "name": "聯茂", "sector": "電子組件", "market": "TSE", "mcap": 400},
    {"symbol": "8039", "name": "台虹", "sector": "電子組件", "market": "TSE", "mcap": 300},
    {"symbol": "3533", "name": "嘉澤", "sector": "電子組件", "market": "TSE", "mcap": 1300},
    {"symbol": "1582", "name": "信錦", "sector": "電子組件", "market": "TSE", "mcap": 300},
    {"symbol": "2059", "name": "川湖", "sector": "電子組件", "market": "TSE", "mcap": 2000},
    {"symbol": "3526", "name": "凡甲", "sector": "電子組件", "market": "OTC", "mcap": 400},
    {"symbol": "3665", "name": "貿聯-KY", "sector": "電子組件", "market": "TSE", "mcap": 1500},
    {"symbol": "6715", "name": "嘉基", "sector": "電子組件", "market": "OTC", "mcap": 300},
    {"symbol": "6290", "name": "良維", "sector": "電子組件", "market": "TSE", "mcap": 300},
    {"symbol": "2421", "name": "建準", "sector": "電子組件", "market": "TSE", "mcap": 400},
    {"symbol": "3017", "name": "奇鋐", "sector": "電子組件", "market": "TSE", "mcap": 2550},
    {"symbol": "3324", "name": "雙鴻", "sector": "電子組件", "market": "OTC", "mcap": 620},
    {"symbol": "3653", "name": "健策", "sector": "電子組件", "market": "TSE", "mcap": 1950},
    {"symbol": "8210", "name": "勤誠", "sector": "電子組件", "market": "TSE", "mcap": 800},
    {"symbol": "2351", "name": "順德", "sector": "電子組件", "market": "TSE", "mcap": 400},
    {"symbol": "2476", "name": "鉅祥", "sector": "電子組件", "market": "TSE", "mcap": 400},

    # 金融
    {"symbol": "2881", "name": "富邦金", "sector": "金融", "market": "TSE", "mcap": 12400},
    {"symbol": "2882", "name": "國泰金", "sector": "金融", "market": "TSE", "mcap": 10100},
    {"symbol": "2891", "name": "中信金", "sector": "金融", "market": "TSE", "mcap": 7500},
    {"symbol": "2886", "name": "兆豐金", "sector": "金融", "market": "TSE", "mcap": 5800},
    {"symbol": "2884", "name": "玉山金", "sector": "金融", "market": "TSE", "mcap": 4500},
    {"symbol": "2885", "name": "元大金", "sector": "金融", "market": "TSE", "mcap": 4200},
    {"symbol": "2892", "name": "第一金", "sector": "金融", "market": "TSE", "mcap": 3500},
    {"symbol": "2880", "name": "華南金", "sector": "金融", "market": "TSE", "mcap": 3000},
    {"symbol": "5880", "name": "合庫金", "sector": "金融", "market": "TSE", "mcap": 3200},
    {"symbol": "2890", "name": "永豐金", "sector": "金融", "market": "TSE", "mcap": 3500},
    {"symbol": "2887", "name": "台新新光金", "sector": "金融", "market": "TSE", "mcap": 4000},
    {"symbol": "2883", "name": "凱基金", "sector": "金融", "market": "TSE", "mcap": 3000},
    {"symbol": "2801", "name": "彰銀", "sector": "金融", "market": "TSE", "mcap": 2500},
    {"symbol": "2834", "name": "臺企銀", "sector": "金融", "market": "TSE", "mcap": 1500},
    {"symbol": "5876", "name": "上海商銀", "sector": "金融", "market": "TSE", "mcap": 2000},
    {"symbol": "2897", "name": "王道銀行", "sector": "金融", "market": "TSE", "mcap": 300},
    {"symbol": "2812", "name": "台中銀", "sector": "金融", "market": "TSE", "mcap": 400},
    {"symbol": "2867", "name": "三商壽", "sector": "金融", "market": "TSE", "mcap": 300},
    {"symbol": "2855", "name": "統一證", "sector": "金融", "market": "TSE", "mcap": 400},
    {"symbol": "6005", "name": "群益證", "sector": "金融", "market": "TSE", "mcap": 400},
    {"symbol": "6016", "name": "康和證", "sector": "金融", "market": "OTC", "mcap": 150},
    {"symbol": "6015", "name": "宏遠證", "sector": "金融", "market": "TSE", "mcap": 150},
    {"symbol": "2889", "name": "國票金", "sector": "金融", "market": "TSE", "mcap": 400},

    # 電腦周邊
    {"symbol": "2382", "name": "廣達", "sector": "電腦周邊", "market": "TSE", "mcap": 11800},
    {"symbol": "3231", "name": "緯創", "sector": "電腦周邊", "market": "TSE", "mcap": 3350},
    {"symbol": "2356", "name": "英業達", "sector": "電腦周邊", "market": "TSE", "mcap": 1200},
    {"symbol": "2324", "name": "仁寶", "sector": "電腦周邊", "market": "TSE", "mcap": 1000},
    {"symbol": "4938", "name": "和碩", "sector": "電腦周邊", "market": "TSE", "mcap": 2200},
    {"symbol": "2317", "name": "鴻海", "sector": "電腦周邊", "market": "TSE", "mcap": 29800},
    {"symbol": "3706", "name": "神達", "sector": "電腦周邊", "market": "TSE", "mcap": 1500},
    {"symbol": "2357", "name": "華碩", "sector": "電腦周邊", "market": "TSE", "mcap": 4300},
    {"symbol": "2353", "name": "宏碁", "sector": "電腦周邊", "market": "TSE", "mcap": 1100},
    {"symbol": "2376", "name": "技嘉", "sector": "電腦周邊", "market": "TSE", "mcap": 1900},
    {"symbol": "2377", "name": "微星", "sector": "電腦周邊", "market": "TSE", "mcap": 1100},
    {"symbol": "3088", "name": "艾訊", "sector": "電腦周邊", "market": "TSE", "mcap": 300},
    {"symbol": "6414", "name": "樺漢", "sector": "電腦周邊", "market": "TSE", "mcap": 600},
    {"symbol": "3416", "name": "融程電", "sector": "電腦周邊", "market": "OTC", "mcap": 300},
    {"symbol": "2395", "name": "研華", "sector": "電腦周邊", "market": "TSE", "mcap": 3000},
    {"symbol": "6166", "name": "凌華", "sector": "電腦周邊", "market": "TSE", "mcap": 300},
    {"symbol": "2397", "name": "友通", "sector": "電腦周邊", "market": "TSE", "mcap": 200},
    {"symbol": "6922", "name": "宸曜", "sector": "電腦周邊", "market": "OTC", "mcap": 200},
    {"symbol": "2331", "name": "精英", "sector": "電腦周邊", "market": "TSE", "mcap": 300},
    {"symbol": "2387", "name": "精元", "sector": "電腦周邊", "market": "TSE", "mcap": 300},
    {"symbol": "2364", "name": "倫飛", "sector": "電腦周邊", "market": "TSE", "mcap": 200},
    {"symbol": "3013", "name": "晟銘電", "sector": "電腦周邊", "market": "TSE", "mcap": 500},
    {"symbol": "6117", "name": "迎廣", "sector": "電腦周邊", "market": "TSE", "mcap": 300},
    {"symbol": "8114", "name": "振樺電", "sector": "電腦周邊", "market": "TSE", "mcap": 400},

    # 其他電子
    {"symbol": "2360", "name": "致茂", "sector": "其他電子", "market": "TSE", "mcap": 1680},
    {"symbol": "2301", "name": "光寶科", "sector": "其他電子", "market": "TSE", "mcap": 2500},
    {"symbol": "2385", "name": "群光", "sector": "其他電子", "market": "TSE", "mcap": 1100},
    {"symbol": "2352", "name": "佳世達", "sector": "其他電子", "market": "TSE", "mcap": 900},
    {"symbol": "2474", "name": "可成", "sector": "其他電子", "market": "TSE", "mcap": 1300},
    {"symbol": "6409", "name": "旭隼", "sector": "其他電子", "market": "TSE", "mcap": 1700},
    {"symbol": "6277", "name": "宏正", "sector": "其他電子", "market": "TSE", "mcap": 300},
    {"symbol": "6579", "name": "研揚", "sector": "其他電子", "market": "TSE", "mcap": 300},
    {"symbol": "2464", "name": "盟立", "sector": "其他電子", "market": "TSE", "mcap": 300},
    {"symbol": "6196", "name": "帆宣", "sector": "其他電子", "market": "TSE", "mcap": 500},
    {"symbol": "3583", "name": "辛耘", "sector": "其他電子", "market": "OTC", "mcap": 1100},
    {"symbol": "5443", "name": "均豪", "sector": "其他電子", "market": "TSE", "mcap": 400},
    {"symbol": "3455", "name": "由田", "sector": "其他電子", "market": "OTC", "mcap": 200},
    {"symbol": "2467", "name": "志聖", "sector": "其他電子", "market": "TSE", "mcap": 600},
    {"symbol": "3030", "name": "德律", "sector": "其他電子", "market": "TSE", "mcap": 500},
    {"symbol": "6438", "name": "迅得", "sector": "其他電子", "market": "OTC", "mcap": 400},
    {"symbol": "3563", "name": "牧德", "sector": "其他電子", "market": "OTC", "mcap": 400},
    {"symbol": "8064", "name": "東捷", "sector": "其他電子", "market": "TSE", "mcap": 200},
    {"symbol": "6125", "name": "廣運", "sector": "其他電子", "market": "TSE", "mcap": 400},
    {"symbol": "6207", "name": "雷科", "sector": "其他電子", "market": "OTC", "mcap": 200},
    {"symbol": "3019", "name": "亞光", "sector": "其他電子", "market": "TSE", "mcap": 800},
    {"symbol": "3406", "name": "玉晶光", "sector": "其他電子", "market": "TSE", "mcap": 580},
    {"symbol": "3008", "name": "大立光", "sector": "其他電子", "market": "TSE", "mcap": 3450},
    {"symbol": "6209", "name": "今國光", "sector": "其他電子", "market": "TSE", "mcap": 200},

    # 網通
    {"symbol": "5388", "name": "中磊", "sector": "網通", "market": "TSE", "mcap": 1200},
    {"symbol": "3596", "name": "智易", "sector": "網通", "market": "TSE", "mcap": 800},
    {"symbol": "3380", "name": "明泰", "sector": "網通", "market": "TSE", "mcap": 400},
    {"symbol": "6285", "name": "啟碁", "sector": "網通", "market": "TSE", "mcap": 680},
    {"symbol": "2345", "name": "智邦", "sector": "網通", "market": "TSE", "mcap": 3180},
    {"symbol": "4906", "name": "正文", "sector": "網通", "market": "TSE", "mcap": 400},
    {"symbol": "3704", "name": "合勤控", "sector": "網通", "market": "TSE", "mcap": 500},
    {"symbol": "2332", "name": "友訊", "sector": "網通", "market": "TSE", "mcap": 300},
    {"symbol": "3558", "name": "神準", "sector": "網通", "market": "OTC", "mcap": 300},
    {"symbol": "2485", "name": "兆赫", "sector": "網通", "market": "TSE", "mcap": 200},
    {"symbol": "2419", "name": "仲琦", "sector": "網通", "market": "TSE", "mcap": 200},
    {"symbol": "2314", "name": "台揚", "sector": "網通", "market": "TSE", "mcap": 200},
    {"symbol": "3062", "name": "建漢", "sector": "網通", "market": "TSE", "mcap": 200},
    {"symbol": "8011", "name": "台通", "sector": "網通", "market": "TSE", "mcap": 200},
    {"symbol": "3163", "name": "波若威", "sector": "網通", "market": "OTC", "mcap": 300},
    {"symbol": "3081", "name": "聯亞", "sector": "網通", "market": "OTC", "mcap": 500},
    {"symbol": "3363", "name": "上詮", "sector": "網通", "market": "OTC", "mcap": 400},
    {"symbol": "4977", "name": "眾達-KY", "sector": "網通", "market": "OTC", "mcap": 300},
    {"symbol": "6442", "name": "光聖", "sector": "網通", "market": "TSE", "mcap": 350},
    {"symbol": "4979", "name": "華星光", "sector": "網通", "market": "OTC", "mcap": 500},
    {"symbol": "4908", "name": "前鼎", "sector": "網通", "market": "OTC", "mcap": 300},
    {"symbol": "4903", "name": "聯光通", "sector": "網通", "market": "OTC", "mcap": 200},

    # 塑膠
    {"symbol": "1301", "name": "台塑", "sector": "塑膠", "market": "TSE", "mcap": 3100},
    {"symbol": "1303", "name": "南亞", "sector": "塑膠", "market": "TSE", "mcap": 3300},
    {"symbol": "1326", "name": "台化", "sector": "塑膠", "market": "TSE", "mcap": 2500},
    {"symbol": "6505", "name": "台塑化", "sector": "塑膠", "market": "TSE", "mcap": 3800},
    {"symbol": "1308", "name": "亞聚", "sector": "塑膠", "market": "TSE", "mcap": 300},
    {"symbol": "1309", "name": "台達化", "sector": "塑膠", "market": "TSE", "mcap": 300},
    {"symbol": "1310", "name": "台苯", "sector": "塑膠", "market": "TSE", "mcap": 300},
    {"symbol": "1312", "name": "國喬", "sector": "塑膠", "market": "TSE", "mcap": 300},
    {"symbol": "1313", "name": "聯成", "sector": "塑膠", "market": "TSE", "mcap": 300},
    {"symbol": "1305", "name": "華夏", "sector": "塑膠", "market": "TSE", "mcap": 210},
    {"symbol": "1304", "name": "台聚", "sector": "塑膠", "market": "TSE", "mcap": 280},
    {"symbol": "1323", "name": "永裕", "sector": "塑膠", "market": "TSE", "mcap": 200},
    {"symbol": "1307", "name": "三芳", "sector": "塑膠", "market": "TSE", "mcap": 400},
    {"symbol": "1315", "name": "地球", "sector": "塑膠", "market": "TSE", "mcap": 200},

    # 光電
    {"symbol": "2409", "name": "友達", "sector": "光電", "market": "TSE", "mcap": 1350},
    {"symbol": "3481", "name": "群創", "sector": "光電", "market": "TSE", "mcap": 1450},
    {"symbol": "6116", "name": "彩晶", "sector": "光電", "market": "TSE", "mcap": 400},
    {"symbol": "8069", "name": "元太", "sector": "光電", "market": "OTC", "mcap": 3100},
    {"symbol": "8105", "name": "凌巨", "sector": "光電", "market": "TSE", "mcap": 300},
    {"symbol": "4960", "name": "誠美材", "sector": "光電", "market": "TSE", "mcap": 250},
    {"symbol": "3535", "name": "晶彩科", "sector": "光電", "market": "OTC", "mcap": 200},
    {"symbol": "6120", "name": "達運", "sector": "光電", "market": "TSE", "mcap": 300},
    {"symbol": "6176", "name": "瑞儀", "sector": "光電", "market": "TSE", "mcap": 800},
    {"symbol": "6456", "name": "GIS-KY", "sector": "光電", "market": "TSE", "mcap": 400},
    {"symbol": "1785", "name": "光洋科", "sector": "光電", "market": "OTC", "mcap": 500},
    {"symbol": "3504", "name": "揚明光", "sector": "光電", "market": "TSE", "mcap": 250},
    {"symbol": "2374", "name": "佳能", "sector": "光電", "market": "TSE", "mcap": 300},
    {"symbol": "3362", "name": "先進光", "sector": "光電", "market": "OTC", "mcap": 400},
    {"symbol": "3441", "name": "聯一光", "sector": "光電", "market": "OTC", "mcap": 200},
    {"symbol": "3623", "name": "富晶通", "sector": "光電", "market": "OTC", "mcap": 200},
    {"symbol": "5234", "name": "達興材料", "sector": "光電", "market": "TSE", "mcap": 400},

    # 航運
    {"symbol": "2603", "name": "長榮", "sector": "航運", "market": "TSE", "mcap": 4600},
    {"symbol": "2609", "name": "陽明", "sector": "航運", "market": "TSE", "mcap": 2550},
    {"symbol": "2615", "name": "萬海", "sector": "航運", "market": "TSE", "mcap": 2400},
    {"symbol": "2617", "name": "台航", "sector": "航運", "market": "TSE", "mcap": 400},
    {"symbol": "2606", "name": "裕民", "sector": "航運", "market": "TSE", "mcap": 500},
    {"symbol": "2605", "name": "新興", "sector": "航運", "market": "TSE", "mcap": 400},
    {"symbol": "5608", "name": "四維航", "sector": "航運", "market": "TSE", "mcap": 300},
    {"symbol": "2637", "name": "慧洋-KY", "sector": "航運", "market": "TSE", "mcap": 800},
    {"symbol": "2641", "name": "正德", "sector": "航運", "market": "TSE", "mcap": 300},
    {"symbol": "2611", "name": "志信", "sector": "航運", "market": "TSE", "mcap": 200},
    {"symbol": "2636", "name": "台驊投控", "sector": "航運", "market": "TSE", "mcap": 400},
    {"symbol": "5609", "name": "中菲行", "sector": "航運", "market": "TSE", "mcap": 300},
    {"symbol": "2643", "name": "捷迅", "sector": "航運", "market": "TSE", "mcap": 200},
    {"symbol": "2642", "name": "宅配通", "sector": "航運", "market": "TSE", "mcap": 200},
    {"symbol": "2608", "name": "嘉里大榮", "sector": "航運", "market": "TSE", "mcap": 500},
    {"symbol": "2616", "name": "山隆", "sector": "航運", "market": "TSE", "mcap": 300},
    {"symbol": "2607", "name": "榮運", "sector": "航運", "market": "TSE", "mcap": 500},

    # 電機
    {"symbol": "1513", "name": "中興電", "sector": "電機", "market": "TSE", "mcap": 880},
    {"symbol": "1519", "name": "華城", "sector": "電機", "market": "TSE", "mcap": 1950},
    {"symbol": "1503", "name": "士電", "sector": "電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1504", "name": "東元", "sector": "電機", "market": "TSE", "mcap": 1100},
    {"symbol": "2371", "name": "大同", "sector": "電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1514", "name": "亞力", "sector": "電機", "market": "TSE", "mcap": 320},
    {"symbol": "1529", "name": "樂事綠能", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "1532", "name": "瑞智", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "1528", "name": "恩德", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "1527", "name": "鑽全", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "4555", "name": "氣立", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "2049", "name": "上銀", "sector": "電機", "market": "TSE", "mcap": 820},
    {"symbol": "1597", "name": "直得", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "4540", "name": "全球傳動", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "4571", "name": "鈞興-KY", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "4526", "name": "東台", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "1583", "name": "程泰", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "6609", "name": "瀧澤科", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "4563", "name": "百德", "sector": "電機", "market": "OTC", "mcap": 200},
    {"symbol": "1590", "name": "亞德客-KY", "sector": "電機", "market": "TSE", "mcap": 2100},
    {"symbol": "8996", "name": "高力", "sector": "電機", "market": "OTC", "mcap": 500},
    {"symbol": "7751", "name": "新代", "sector": "電機", "market": "OTC", "mcap": 400},
    {"symbol": "3167", "name": "大量", "sector": "電機", "market": "OTC", "mcap": 300},
    {"symbol": "4583", "name": "台灣精銳", "sector": "電機", "market": "TSE", "mcap": 600},
    {"symbol": "4576", "name": "大銀微系統", "sector": "電機", "market": "TSE", "mcap": 400},
    {"symbol": "5288", "name": "豐祥-KY", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "1537", "name": "廣隆", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "4566", "name": "時碩工業", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "1558", "name": "伸興", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "1535", "name": "中宇", "sector": "電機", "market": "TSE", "mcap": 300},
    {"symbol": "4572", "name": "駐龍", "sector": "電機", "market": "OTC", "mcap": 300},
    {"symbol": "4590", "name": "富田-創", "sector": "電機", "market": "OTC", "mcap": 200},
    {"symbol": "1506", "name": "正道", "sector": "電機", "market": "TSE", "mcap": 200},
    {"symbol": "1530", "name": "亞崴", "sector": "電機", "market": "TSE", "mcap": 200},

    # 營建
    {"symbol": "2548", "name": "華固", "sector": "營建", "market": "TSE", "mcap": 350},
    {"symbol": "5534", "name": "長虹", "sector": "營建", "market": "TSE", "mcap": 400},
    {"symbol": "2542", "name": "興富發", "sector": "營建", "market": "TSE", "mcap": 880},
    {"symbol": "5522", "name": "遠雄", "sector": "營建", "market": "TSE", "mcap": 480},
    {"symbol": "2545", "name": "皇翔", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "2520", "name": "冠德", "sector": "營建", "market": "TSE", "mcap": 310},
    {"symbol": "2597", "name": "潤弘", "sector": "營建", "market": "TSE", "mcap": 400},
    {"symbol": "2546", "name": "根基", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "6177", "name": "達麗", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "2540", "name": "愛山林", "sector": "營建", "market": "TSE", "mcap": 400},
    {"symbol": "2501", "name": "國建", "sector": "營建", "market": "TSE", "mcap": 500},
    {"symbol": "2505", "name": "國揚", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "1436", "name": "華友聯", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "2524", "name": "京城", "sector": "營建", "market": "TSE", "mcap": 400},
    {"symbol": "3703", "name": "欣陸", "sector": "營建", "market": "TSE", "mcap": 500},
    {"symbol": "2528", "name": "皇普", "sector": "營建", "market": "TSE", "mcap": 300},
    {"symbol": "2509", "name": "全坤建", "sector": "營建", "market": "TSE", "mcap": 200},
    {"symbol": "2539", "name": "櫻花建", "sector": "營建", "market": "TSE", "mcap": 400},
    {"symbol": "5521", "name": "工信", "sector": "營建", "market": "TSE", "mcap": 200},
    {"symbol": "5531", "name": "鄉林", "sector": "營建", "market": "TSE", "mcap": 200},

    # 鋼鐵
    {"symbol": "2002", "name": "中鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 3450},
    {"symbol": "2014", "name": "中鴻", "sector": "鋼鐵", "market": "TSE", "mcap": 310},
    {"symbol": "2006", "name": "東和鋼鐵", "sector": "鋼鐵", "market": "TSE", "mcap": 600},
    {"symbol": "2015", "name": "豐興", "sector": "鋼鐵", "market": "TSE", "mcap": 500},
    {"symbol": "2027", "name": "大成鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 850},
    {"symbol": "2028", "name": "威致", "sector": "鋼鐵", "market": "TSE", "mcap": 300},
    {"symbol": "2007", "name": "燁興", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "2023", "name": "燁輝", "sector": "鋼鐵", "market": "TSE", "mcap": 400},
    {"symbol": "2009", "name": "第一銅", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "2017", "name": "官田鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "2010", "name": "春源", "sector": "鋼鐵", "market": "TSE", "mcap": 300},
    {"symbol": "2012", "name": "春雨", "sector": "鋼鐵", "market": "TSE", "mcap": 300},
    {"symbol": "2024", "name": "志聯", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "2030", "name": "彰源", "sector": "鋼鐵", "market": "TSE", "mcap": 300},
    {"symbol": "2034", "name": "允強", "sector": "鋼鐵", "market": "TSE", "mcap": 400},
    {"symbol": "2025", "name": "千興", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "2022", "name": "聚亨", "sector": "鋼鐵", "market": "TSE", "mcap": 200},
    {"symbol": "9958", "name": "世紀鋼", "sector": "鋼鐵", "market": "TSE", "mcap": 700},
    {"symbol": "2038", "name": "海光", "sector": "鋼鐵", "market": "TSE", "mcap": 200},

    # 生技
    {"symbol": "4105", "name": "台灣東洋", "sector": "生技", "market": "OTC", "mcap": 500},
    {"symbol": "6472", "name": "保瑞", "sector": "生技", "market": "TSE", "mcap": 820},
    {"symbol": "6446", "name": "藥華藥", "sector": "生技", "market": "OTC", "mcap": 2150},
    {"symbol": "4147", "name": "中裕", "sector": "生技", "market": "OTC", "mcap": 300},
    {"symbol": "4743", "name": "合一", "sector": "生技", "market": "OTC", "mcap": 620},
    {"symbol": "6491", "name": "晶碩", "sector": "生技", "market": "TSE", "mcap": 310},
    {"symbol": "4106", "name": "雃博", "sector": "生技", "market": "TSE", "mcap": 250},
    {"symbol": "4736", "name": "泰博", "sector": "生技", "market": "TSE", "mcap": 400},
    {"symbol": "1784", "name": "訊聯", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "3176", "name": "基亞", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "4162", "name": "智擎", "sector": "生技", "market": "OTC", "mcap": 400},
    {"symbol": "4168", "name": "醣聯", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "6564", "name": "安特羅", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "4726", "name": "永昕", "sector": "生技", "market": "OTC", "mcap": 300},
    {"symbol": "6535", "name": "順藥", "sector": "生技", "market": "OTC", "mcap": 400},
    {"symbol": "4142", "name": "國光生", "sector": "生技", "market": "TSE", "mcap": 400},
    {"symbol": "4123", "name": "晟德", "sector": "生技", "market": "TSE", "mcap": 500},
    {"symbol": "1707", "name": "葡萄王", "sector": "生技", "market": "TSE", "mcap": 600},
    {"symbol": "8432", "name": "東生華", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "4114", "name": "健喬", "sector": "生技", "market": "TSE", "mcap": 500},
    {"symbol": "1789", "name": "神隆", "sector": "生技", "market": "TSE", "mcap": 500},
    {"symbol": "1734", "name": "杏輝", "sector": "生技", "market": "TSE", "mcap": 300},
    {"symbol": "4192", "name": "杏國", "sector": "生技", "market": "OTC", "mcap": 200},
    {"symbol": "6589", "name": "台康生技", "sector": "生技", "market": "OTC", "mcap": 800},
    {"symbol": "4174", "name": "浩鼎", "sector": "生技", "market": "OTC", "mcap": 400},

    # 食品
    {"symbol": "1216", "name": "統一", "sector": "食品", "market": "TSE", "mcap": 4900},
    {"symbol": "1201", "name": "味全", "sector": "食品", "market": "TSE", "mcap": 150},
    {"symbol": "1210", "name": "大成", "sector": "食品", "market": "TSE", "mcap": 600},
    {"symbol": "1215", "name": "卜蜂", "sector": "食品", "market": "TSE", "mcap": 500},
    {"symbol": "1218", "name": "泰山", "sector": "食品", "market": "TSE", "mcap": 350},
    {"symbol": "1219", "name": "福壽", "sector": "食品", "market": "TSE", "mcap": 200},
    {"symbol": "1229", "name": "聯華", "sector": "食品", "market": "TSE", "mcap": 600},
    {"symbol": "1231", "name": "聯華食", "sector": "食品", "market": "TSE", "mcap": 400},
    {"symbol": "1227", "name": "佳格", "sector": "食品", "market": "TSE", "mcap": 500},
    {"symbol": "1234", "name": "黑松", "sector": "食品", "market": "TSE", "mcap": 400},
    {"symbol": "1217", "name": "愛之味", "sector": "食品", "market": "TSE", "mcap": 300},
    {"symbol": "1236", "name": "宏亞", "sector": "食品", "market": "TSE", "mcap": 200},
    {"symbol": "1702", "name": "南僑", "sector": "食品", "market": "TSE", "mcap": 400},
    {"symbol": "1220", "name": "台榮", "sector": "食品", "market": "TSE", "mcap": 200},
    {"symbol": "1233", "name": "天仁", "sector": "食品", "market": "TSE", "mcap": 200},
    {"symbol": "1259", "name": "安心", "sector": "食品", "market": "OTC", "mcap": 200},
    {"symbol": "1256", "name": "鮮活果汁-KY", "sector": "食品", "market": "OTC", "mcap": 200},
    {"symbol": "2729", "name": "瓦城", "sector": "食品", "market": "OTC", "mcap": 300},
    {"symbol": "2727", "name": "王品", "sector": "食品", "market": "TSE", "mcap": 400},
    {"symbol": "2732", "name": "六角", "sector": "食品", "market": "OTC", "mcap": 300},

    # 汽車
    {"symbol": "2201", "name": "裕隆", "sector": "汽車", "market": "TSE", "mcap": 800},
    {"symbol": "2204", "name": "中華", "sector": "汽車", "market": "TSE", "mcap": 1200},
    {"symbol": "2206", "name": "三陽工業", "sector": "汽車", "market": "TSE", "mcap": 1500},
    {"symbol": "2207", "name": "和泰車", "sector": "汽車", "market": "TSE", "mcap": 3800},
    {"symbol": "2211", "name": "裕日車", "sector": "汽車", "market": "TSE", "mcap": 1100},
    {"symbol": "1319", "name": "東陽", "sector": "汽車", "market": "TSE", "mcap": 900},
    {"symbol": "1522", "name": "堤維西", "sector": "汽車", "market": "TSE", "mcap": 400},
    {"symbol": "6605", "name": "帝寶", "sector": "汽車", "market": "TSE", "mcap": 500},
    {"symbol": "1533", "name": "車王電", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1525", "name": "江申", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "2231", "name": "為升", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "2228", "name": "劍麟", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "3346", "name": "麗清", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "4551", "name": "智伸科", "sector": "汽車", "market": "TSE", "mcap": 400},
    {"symbol": "3717", "name": "聯嘉投控", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "1505", "name": "瑞利", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1524", "name": "耿鼎", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1537", "name": "廣隆", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "8255", "name": "朋程", "sector": "汽車", "market": "OTC", "mcap": 400},
    {"symbol": "2258", "name": "鴻華先進-創", "sector": "汽車", "market": "TSE", "mcap": 500},
    {"symbol": "2247", "name": "汎德永業", "sector": "汽車", "market": "TSE", "mcap": 600},
    {"symbol": "2233", "name": "宇隆", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "1563", "name": "巧新", "sector": "汽車", "market": "TSE", "mcap": 400},
    {"symbol": "2236", "name": "百達-KY", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "2241", "name": "艾姆勒", "sector": "汽車", "market": "OTC", "mcap": 200},
    {"symbol": "1536", "name": "和大", "sector": "汽車", "market": "TSE", "mcap": 410},
    {"symbol": "2497", "name": "怡利電", "sector": "汽車", "market": "OTC", "mcap": 300},
    {"symbol": "7736", "name": "虎山", "sector": "汽車", "market": "OTC", "mcap": 200},
    {"symbol": "4569", "name": "六方科-KY", "sector": "汽車", "market": "OTC", "mcap": 200},
    {"symbol": "2243", "name": "宏旭-KY", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1568", "name": "倉佑", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "2248", "name": "華勝-KY", "sector": "汽車", "market": "OTC", "mcap": 200},
    {"symbol": "4557", "name": "永新-KY", "sector": "汽車", "market": "TSE", "mcap": 300},
    {"symbol": "5102", "name": "IKKA-KY", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1521", "name": "大億", "sector": "汽車", "market": "TSE", "mcap": 200},
    {"symbol": "1587", "name": "吉茂", "sector": "汽車", "market": "TSE", "mcap": 200},

    # 化學
    {"symbol": "1722", "name": "台肥", "sector": "化學", "market": "TSE", "mcap": 1200},
    {"symbol": "1717", "name": "長興", "sector": "化學", "market": "TSE", "mcap": 360},
    {"symbol": "1727", "name": "中華化", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1711", "name": "永光", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "1773", "name": "勝一", "sector": "化學", "market": "TSE", "mcap": 700},
    {"symbol": "4722", "name": "國精化", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "4755", "name": "三福化", "sector": "化學", "market": "TSE", "mcap": 400},
    {"symbol": "1726", "name": "永記", "sector": "化學", "market": "TSE", "mcap": 400},
    {"symbol": "4764", "name": "雙鍵", "sector": "化學", "market": "OTC", "mcap": 200},
    {"symbol": "4763", "name": "材料*-KY", "sector": "化學", "market": "OTC", "mcap": 950},
    {"symbol": "4766", "name": "南寶", "sector": "化學", "market": "TSE", "mcap": 600},
    {"symbol": "4770", "name": "上品", "sector": "化學", "market": "OTC", "mcap": 800},
    {"symbol": "4772", "name": "台特化", "sector": "化學", "market": "OTC", "mcap": 600},
    {"symbol": "1724", "name": "台硝", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1714", "name": "和桐", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "4119", "name": "旭富", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "4739", "name": "康普", "sector": "化學", "market": "TSE", "mcap": 400},
    {"symbol": "1735", "name": "日勝化", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1709", "name": "和益", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "1723", "name": "中碳", "sector": "化學", "market": "TSE", "mcap": 600},
    {"symbol": "1718", "name": "中纖", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "1712", "name": "興農", "sector": "化學", "market": "TSE", "mcap": 500},
    {"symbol": "1710", "name": "東聯", "sector": "化學", "market": "TSE", "mcap": 400},
    {"symbol": "1708", "name": "東鹼", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "1713", "name": "國化", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1725", "name": "元禎", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1721", "name": "國慶科技", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "4720", "name": "德淵", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1730", "name": "花仙子", "sector": "化學", "market": "TSE", "mcap": 300},
    {"symbol": "1776", "name": "展宇", "sector": "化學", "market": "TSE", "mcap": 200},
    {"symbol": "1732", "name": "毛寶", "sector": "化學", "market": "TSE", "mcap": 200},

    # 油電
    {"symbol": "6806", "name": "森崴能源", "sector": "油電", "market": "OTC", "mcap": 380},
    {"symbol": "6869", "name": "雲豹能源", "sector": "油電", "market": "TSE", "mcap": 350},
    {"symbol": "6873", "name": "泓德能源", "sector": "油電", "market": "TSE", "mcap": 400},
    {"symbol": "6994", "name": "富威電力", "sector": "油電", "market": "OTC", "mcap": 300},
    {"symbol": "8440", "name": "綠電", "sector": "油電", "market": "OTC", "mcap": 200},
    {"symbol": "3489", "name": "森寶", "sector": "油電", "market": "TSE", "mcap": 200},
    {"symbol": "3073", "name": "天方能源", "sector": "油電", "market": "OTC", "mcap": 200},
    {"symbol": "9937", "name": "全國", "sector": "油電", "market": "TSE", "mcap": 500},
    {"symbol": "9908", "name": "大台北", "sector": "油電", "market": "TSE", "mcap": 400},
    {"symbol": "8908", "name": "欣雄", "sector": "油電", "market": "OTC", "mcap": 300},
    {"symbol": "9926", "name": "新海", "sector": "油電", "market": "TSE", "mcap": 300},
    {"symbol": "9918", "name": "欣天然", "sector": "油電", "market": "TSE", "mcap": 400},
    {"symbol": "9931", "name": "欣高", "sector": "油電", "market": "OTC", "mcap": 300},

    # 紡織
    {"symbol": "1476", "name": "儒鴻", "sector": "紡織", "market": "TSE", "mcap": 2800},
    {"symbol": "1477", "name": "聚陽", "sector": "紡織", "market": "TSE", "mcap": 1150},
    {"symbol": "1402", "name": "遠東新", "sector": "紡織", "market": "TSE", "mcap": 1700},
    {"symbol": "1444", "name": "力麗", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1447", "name": "力鵬", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1440", "name": "南紡", "sector": "紡織", "market": "TSE", "mcap": 400},
    {"symbol": "1414", "name": "東和", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1455", "name": "集盛", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1460", "name": "宏遠", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1449", "name": "佳和", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1451", "name": "年興", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1464", "name": "得力", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "4432", "name": "銘旺實", "sector": "紡織", "market": "OTC", "mcap": 200},
    {"symbol": "1473", "name": "台南", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1434", "name": "福懋", "sector": "紡織", "market": "TSE", "mcap": 700},
    {"symbol": "1457", "name": "宜進", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "4438", "name": "廣越", "sector": "紡織", "market": "TSE", "mcap": 400},
    {"symbol": "4426", "name": "利勤", "sector": "紡織", "market": "OTC", "mcap": 200},
    {"symbol": "1342", "name": "八貫", "sector": "紡織", "market": "TSE", "mcap": 400},
    {"symbol": "1409", "name": "新纖", "sector": "紡織", "market": "TSE", "mcap": 600},
    {"symbol": "1419", "name": "新紡", "sector": "紡織", "market": "TSE", "mcap": 400},
    {"symbol": "4441", "name": "振大環球", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1459", "name": "聯發", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1423", "name": "利華", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1463", "name": "強盛新", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "4414", "name": "如興", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1446", "name": "宏和", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1475", "name": "業旺", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1466", "name": "聚隆", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1454", "name": "台富", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "4439", "name": "冠星-KY", "sector": "紡織", "market": "TSE", "mcap": 300},
    {"symbol": "1470", "name": "大統新創", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1417", "name": "嘉裕", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1452", "name": "宏益", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "4440", "name": "宜新實業", "sector": "紡織", "market": "OTC", "mcap": 200},
    {"symbol": "1465", "name": "偉全", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1468", "name": "昶和", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1410", "name": "南染", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1474", "name": "弘裕", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1413", "name": "宏洲", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1467", "name": "南緯", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1445", "name": "大宇", "sector": "紡織", "market": "TSE", "mcap": 200},
    {"symbol": "1418", "name": "東華", "sector": "紡織", "market": "TSE", "mcap": 200},

    # 貿易
    {"symbol": "3702", "name": "大聯大", "sector": "貿易", "market": "TSE", "mcap": 1600},
    {"symbol": "3036", "name": "文曄", "sector": "貿易", "market": "TSE", "mcap": 1200},
    {"symbol": "2347", "name": "聯強", "sector": "貿易", "market": "TSE", "mcap": 1800},
    {"symbol": "8112", "name": "至上", "sector": "貿易", "market": "TSE", "mcap": 1000},
    {"symbol": "3028", "name": "增你強", "sector": "貿易", "market": "TSE", "mcap": 400},
    {"symbol": "3033", "name": "威健", "sector": "貿易", "market": "TSE", "mcap": 300},
    {"symbol": "3048", "name": "益登", "sector": "貿易", "market": "TSE", "mcap": 300},
    {"symbol": "6189", "name": "豐藝", "sector": "貿易", "market": "TSE", "mcap": 400},
    {"symbol": "3209", "name": "全科", "sector": "貿易", "market": "TSE", "mcap": 300},
    {"symbol": "8096", "name": "擎亞", "sector": "貿易", "market": "OTC", "mcap": 200},
    {"symbol": "5434", "name": "崇越", "sector": "貿易", "market": "OTC", "mcap": 1400},
    {"symbol": "3010", "name": "華立", "sector": "貿易", "market": "TSE", "mcap": 600},
    {"symbol": "8070", "name": "長華*", "sector": "貿易", "market": "OTC", "mcap": 450},
    {"symbol": "2912", "name": "統一超", "sector": "貿易", "market": "TSE", "mcap": 3050},
    {"symbol": "2905", "name": "三商", "sector": "貿易", "market": "TSE", "mcap": 400},
    {"symbol": "2903", "name": "遠百", "sector": "貿易", "market": "TSE", "mcap": 600},
    {"symbol": "2915", "name": "潤泰全", "sector": "貿易", "market": "TSE", "mcap": 800},
    {"symbol": "2908", "name": "特力", "sector": "貿易", "market": "TSE", "mcap": 300},
    {"symbol": "5904", "name": "寶雅", "sector": "貿易", "market": "TSE", "mcap": 1800},
    {"symbol": "8454", "name": "富邦媒", "sector": "貿易", "market": "TSE", "mcap": 1100},
    {"symbol": "2913", "name": "農林", "sector": "貿易", "market": "TSE", "mcap": 400},
    {"symbol": "2910", "name": "統領", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "2906", "name": "高林", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "2945", "name": "三商家購", "sector": "貿易", "market": "OTC", "mcap": 200},
    {"symbol": "2901", "name": "欣欣", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "4807", "name": "日成-KY", "sector": "貿易", "market": "OTC", "mcap": 200},
    {"symbol": "5906", "name": "台南-KY", "sector": "貿易", "market": "OTC", "mcap": 200},
    {"symbol": "8429", "name": "金麗-KY", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "2939", "name": "永邑-KY", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "5907", "name": "大洋-KY", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "8443", "name": "阿瘦", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "2929", "name": "淘帝-KY", "sector": "貿易", "market": "TSE", "mcap": 200},
    {"symbol": "2936", "name": "凱羿-KY", "sector": "貿易", "market": "TSE", "mcap": 200},

    # 電器
    {"symbol": "1604", "name": "聲寶", "sector": "電器", "market": "TSE", "mcap": 400},
    {"symbol": "5283", "name": "禾聯碩", "sector": "電器", "market": "OTC", "mcap": 300},
    {"symbol": "1605", "name": "華新", "sector": "電器", "market": "TSE", "mcap": 1350},
    {"symbol": "2393", "name": "億光", "sector": "電器", "market": "TSE", "mcap": 1000},
    {"symbol": "1609", "name": "大亞", "sector": "電器", "market": "TSE", "mcap": 350},
    {"symbol": "1608", "name": "華榮", "sector": "電器", "market": "TSE", "mcap": 300},
    {"symbol": "1623", "name": "大東電", "sector": "電器", "market": "OTC", "mcap": 300},
    {"symbol": "1612", "name": "宏泰", "sector": "電器", "market": "TSE", "mcap": 300},
    {"symbol": "1615", "name": "大山", "sector": "電器", "market": "TSE", "mcap": 300},
    {"symbol": "1614", "name": "三洋電", "sector": "電器", "market": "TSE", "mcap": 300},
    {"symbol": "1618", "name": "合機", "sector": "電器", "market": "TSE", "mcap": 300},
    {"symbol": "1603", "name": "華電", "sector": "電器", "market": "TSE", "mcap": 200},
    {"symbol": "1617", "name": "榮星", "sector": "電器", "market": "TSE", "mcap": 200},
    {"symbol": "1611", "name": "中電", "sector": "電器", "market": "TSE", "mcap": 200},
    {"symbol": "1616", "name": "億泰", "sector": "電器", "market": "TSE", "mcap": 200},
    {"symbol": "1626", "name": "艾美特-KY", "sector": "電器", "market": "KY", "mcap": 200},
    {"symbol": "4930", "name": "燦星網", "sector": "電器", "market": "OTC", "mcap": 200},

    # 水泥
    {"symbol": "1101", "name": "台泥", "sector": "水泥", "market": "TSE", "mcap": 2450},
    {"symbol": "1102", "name": "亞泥", "sector": "水泥", "market": "TSE", "mcap": 1400},
    {"symbol": "1104", "name": "環泥", "sector": "水泥", "market": "TSE", "mcap": 400},
    {"symbol": "1108", "name": "幸福", "sector": "水泥", "market": "TSE", "mcap": 300},
    {"symbol": "1109", "name": "信大", "sector": "水泥", "market": "TSE", "mcap": 300},
    {"symbol": "1103", "name": "嘉泥", "sector": "水泥", "market": "TSE", "mcap": 400},
    {"symbol": "2504", "name": "國產", "sector": "水泥", "market": "TSE", "mcap": 580},
    {"symbol": "1110", "name": "東泥", "sector": "水泥", "market": "TSE", "mcap": 200},

    # 電子通路
    {"symbol": "6227", "name": "茂綸", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "8032", "name": "光菱", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "3360", "name": "尚立", "sector": "電子通路", "market": "TSE", "mcap": 200},
    {"symbol": "3528", "name": "安馳", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "6805", "name": "富世達", "sector": "電子通路", "market": "TSE", "mcap": 1200},
    {"symbol": "3055", "name": "蔚華科", "sector": "電子通路", "market": "TSE", "mcap": 300},
    {"symbol": "3312", "name": "弘億股", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "2414", "name": "精技", "sector": "電子通路", "market": "TSE", "mcap": 300},
    {"symbol": "6281", "name": "全國電", "sector": "電子通路", "market": "TSE", "mcap": 400},
    {"symbol": "6776", "name": "展碁國際", "sector": "電子通路", "market": "OTC", "mcap": 300},
    {"symbol": "3054", "name": "立萬利", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "8072", "name": "陞泰", "sector": "電子通路", "market": "OTC", "mcap": 200},
    {"symbol": "2430", "name": "燦坤", "sector": "電子通路", "market": "TSE", "mcap": 300},

    # 運動休閒
    {"symbol": "9904", "name": "寶成", "sector": "運動休閒", "market": "TSE", "mcap": 1000},
    {"symbol": "9910", "name": "豐泰", "sector": "運動休閒", "market": "TSE", "mcap": 1300},
    {"symbol": "6768", "name": "志強-KY", "sector": "運動休閒", "market": "TSE", "mcap": 500},
    {"symbol": "9802", "name": "鈺齊-KY", "sector": "運動休閒", "market": "TSE", "mcap": 400},
    {"symbol": "6890", "name": "來億-KY", "sector": "運動休閒", "market": "TSE", "mcap": 800},
    {"symbol": "9938", "name": "百和", "sector": "運動休閒", "market": "TSE", "mcap": 210},
    {"symbol": "8404", "name": "百和興業-KY", "sector": "運動休閒", "market": "TSE", "mcap": 200},
    {"symbol": "9914", "name": "美利達", "sector": "運動休閒", "market": "TSE", "mcap": 620},
    {"symbol": "9921", "name": "巨大", "sector": "運動休閒", "market": "TSE", "mcap": 750},
    {"symbol": "5306", "name": "桂盟", "sector": "運動休閒", "market": "OTC", "mcap": 400},
    {"symbol": "4536", "name": "拓凱", "sector": "運動休閒", "market": "TSE", "mcap": 400},
    {"symbol": "1598", "name": "岱宇", "sector": "運動休閒", "market": "TSE", "mcap": 200},
    {"symbol": "8938", "name": "明安", "sector": "運動休閒", "market": "OTC", "mcap": 300},
    {"symbol": "6670", "name": "復盛應用", "sector": "運動休閒", "market": "TSE", "mcap": 800},
    {"symbol": "1736", "name": "喬山", "sector": "運動休閒", "market": "TSE", "mcap": 600},
    {"symbol": "8462", "name": "柏文", "sector": "運動休閒", "market": "TSE", "mcap": 300},
    {"symbol": "8478", "name": "東哥遊艇", "sector": "運動休閒", "market": "TSE", "mcap": 800},
    {"symbol": "6965", "name": "中傑-KY", "sector": "運動休閒", "market": "TSE", "mcap": 400},
    {"symbol": "2762", "name": "世界健身-KY", "sector": "運動休閒", "market": "TSE", "mcap": 300},
    {"symbol": "8467", "name": "波力-KY", "sector": "運動休閒", "market": "TSE", "mcap": 300},
    {"symbol": "1432", "name": "大魯閣", "sector": "運動休閒", "market": "TSE", "mcap": 200},

    # 綠能環保
    {"symbol": "8422", "name": "可寧衛*", "sector": "綠能環保", "market": "TSE", "mcap": 500},
    {"symbol": "6803", "name": "崑鼎", "sector": "綠能環保", "market": "TSE", "mcap": 600},
    {"symbol": "8936", "name": "國統", "sector": "綠能環保", "market": "OTC", "mcap": 400},
    {"symbol": "8473", "name": "山林水", "sector": "綠能環保", "market": "TSE", "mcap": 300},
    {"symbol": "3708", "name": "上緯投控", "sector": "綠能環保", "market": "TSE", "mcap": 400},
    {"symbol": "9955", "name": "佳龍", "sector": "綠能環保", "market": "TSE", "mcap": 200},
    {"symbol": "8390", "name": "金益鼎", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "4924", "name": "欣厚-KY", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6961", "name": "聯友金屬-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6944", "name": "兆聯實業", "sector": "綠能環保", "market": "OTC", "mcap": 400},
    {"symbol": "7703", "name": "世紀能源", "sector": "綠能環保", "market": "OTC", "mcap": 300},
    {"symbol": "7786", "name": "東方風能", "sector": "綠能環保", "market": "OTC", "mcap": 300},
    {"symbol": "9930", "name": "中聯資源", "sector": "綠能環保", "market": "TSE", "mcap": 400},
    {"symbol": "6581", "name": "鋼聯", "sector": "綠能環保", "market": "TSE", "mcap": 300},
    {"symbol": "5290", "name": "華懋", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "8341", "name": "日友", "sector": "綠能環保", "market": "TSE", "mcap": 400},
    {"symbol": "6956", "name": "溢泰實業", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6947", "name": "台鎔科技", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6923", "name": "中台", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "7740", "name": "熙特爾-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "8438", "name": "昶昕", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6951", "name": "青新-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "8476", "name": "台境*", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6887", "name": "寶綠特-KY", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "4582", "name": "聚恆-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6969", "name": "成信實業*-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6771", "name": "平和環保-創", "sector": "綠能環保", "market": "OTC", "mcap": 200},
    {"symbol": "6641", "name": "基士德-KY", "sector": "綠能環保", "market": "OTC", "mcap": 200},

    # 橡膠
    {"symbol": "2103", "name": "台橡", "sector": "橡膠", "market": "TSE", "mcap": 310},
    {"symbol": "2108", "name": "南帝", "sector": "橡膠", "market": "TSE", "mcap": 400},
    {"symbol": "2105", "name": "正新", "sector": "橡膠", "market": "TSE", "mcap": 1350},
    {"symbol": "2106", "name": "建大", "sector": "橡膠", "market": "TSE", "mcap": 600},
    {"symbol": "2102", "name": "泰豐", "sector": "橡膠", "market": "TSE", "mcap": 300},
    {"symbol": "2109", "name": "華豐", "sector": "橡膠", "market": "TSE", "mcap": 300},
    {"symbol": "2115", "name": "六暉-KY", "sector": "橡膠", "market": "OTC", "mcap": 200},
    {"symbol": "2101", "name": "南港", "sector": "橡膠", "market": "TSE", "mcap": 500},
    {"symbol": "6582", "name": "申豐", "sector": "橡膠", "market": "TSE", "mcap": 300},
    {"symbol": "2107", "name": "厚生", "sector": "橡膠", "market": "TSE", "mcap": 400},
    {"symbol": "2104", "name": "國際中橡", "sector": "橡膠", "market": "TSE", "mcap": 400},
    {"symbol": "2114", "name": "鑫永銓", "sector": "橡膠", "market": "OTC", "mcap": 300},

    # 玻璃
    {"symbol": "1802", "name": "台玻", "sector": "玻璃", "market": "TSE", "mcap": 450},
    {"symbol": "1806", "name": "冠軍", "sector": "玻璃", "market": "TSE", "mcap": 200},
    {"symbol": "1810", "name": "和成", "sector": "玻璃", "market": "TSE", "mcap": 300},
    {"symbol": "1817", "name": "凱撒衛", "sector": "玻璃", "market": "TSE", "mcap": 300},
    {"symbol": "1809", "name": "中釉", "sector": "玻璃", "market": "TSE", "mcap": 200},

    # 觀光
    {"symbol": "2707", "name": "晶華", "sector": "觀光", "market": "TSE", "mcap": 250},
    {"symbol": "2748", "name": "雲品", "sector": "觀光", "market": "OTC", "mcap": 300},
    {"symbol": "2739", "name": "寒舍", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "5704", "name": "老爺知", "sector": "觀光", "market": "OTC", "mcap": 200},
    {"symbol": "2722", "name": "夏都", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "2736", "name": "富野", "sector": "觀光", "market": "OTC", "mcap": 200},
    {"symbol": "2704", "name": "國賓", "sector": "觀光", "market": "TSE", "mcap": 500},
    {"symbol": "2705", "name": "六福", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "5706", "name": "鳳凰", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "2743", "name": "山富", "sector": "觀光", "market": "OTC", "mcap": 300},
    {"symbol": "2731", "name": "雄獅", "sector": "觀光", "market": "TSE", "mcap": 500},
    {"symbol": "2745", "name": "五福", "sector": "觀光", "market": "OTC", "mcap": 300},
    {"symbol": "2734", "name": "易飛網", "sector": "觀光", "market": "OTC", "mcap": 200},
    {"symbol": "2719", "name": "燦星旅", "sector": "觀光", "market": "OTC", "mcap": 200},
    {"symbol": "6552", "name": "易華電", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "2723", "name": "美食-KY", "sector": "觀光", "market": "TSE", "mcap": 180},
    {"symbol": "2753", "name": "八方雲集", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "9943", "name": "好樂迪", "sector": "觀光", "market": "TSE", "mcap": 400},
    {"symbol": "2706", "name": "第一店", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "2701", "name": "萬企", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "7731", "name": "享溫馨", "sector": "觀光", "market": "OTC", "mcap": 200},
    {"symbol": "2702", "name": "華園", "sector": "觀光", "market": "TSE", "mcap": 200},
    {"symbol": "2712", "name": "遠雄來", "sector": "觀光", "market": "TSE", "mcap": 200},
    {"symbol": "7705", "name": "三商餐飲", "sector": "觀光", "market": "TSE", "mcap": 300},
    {"symbol": "8940", "name": "新天地", "sector": "觀光", "market": "OTC", "mcap": 200},

    # 居家生活
    {"symbol": "9939", "name": "櫻花", "sector": "居家生活", "market": "TSE", "mcap": 500},
    {"symbol": "9934", "name": "成霖", "sector": "居家生活", "market": "TSE", "mcap": 300},
    {"symbol": "2062", "name": "橋椿", "sector": "居家生活", "market": "TSE", "mcap": 300},
    {"symbol": "8464", "name": "億豐", "sector": "居家生活", "market": "TSE", "mcap": 1500},
    {"symbol": "2230", "name": "泰茂", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "3067", "name": "全域", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "6216", "name": "居易", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "9905", "name": "詩肯", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "9940", "name": "信義", "sector": "居家生活", "market": "TSE", "mcap": 800},
    {"symbol": "3624", "name": "地心引力", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "9924", "name": "福興", "sector": "居家生活", "market": "TSE", "mcap": 400},
    {"symbol": "8482", "name": "商億-KY", "sector": "居家生活", "market": "TSE", "mcap": 400},
    {"symbol": "9935", "name": "慶豐富", "sector": "居家生活", "market": "TSE", "mcap": 300},
    {"symbol": "6754", "name": "匯僑設計", "sector": "居家生活", "market": "OTC", "mcap": 200},
    {"symbol": "8394", "name": "嘉威", "sector": "居家生活", "market": "OTC", "mcap": 300},
    {"symbol": "6807", "name": "峰源-KY", "sector": "居家生活", "market": "TSE", "mcap": 300},
    {"symbol": "6671", "name": "三能-KY", "sector": "居家生活", "market": "OTC", "mcap": 200},

    # 數位雲端
    {"symbol": "3029", "name": "零壹", "sector": "數位雲端", "market": "OTC", "mcap": 500},
    {"symbol": "6112", "name": "邁達特", "sector": "數位雲端", "market": "TSE", "mcap": 400},
    {"symbol": "6689", "name": "伊雲谷", "sector": "數位雲端", "market": "TSE", "mcap": 300},
    {"symbol": "6561", "name": "是方", "sector": "數位雲端", "market": "TSE", "mcap": 800},
    {"symbol": "8044", "name": "網家", "sector": "數位雲端", "market": "TSE", "mcap": 300},
    {"symbol": "5287", "name": "數字", "sector": "數位雲端", "market": "OTC", "mcap": 600},
    {"symbol": "6741", "name": "91APP*-KY", "sector": "數位雲端", "market": "OTC", "mcap": 500},
    {"symbol": "8477", "name": "創業家", "sector": "數位雲端", "market": "OTC", "mcap": 200},
    {"symbol": "6811", "name": "宏碁資訊", "sector": "數位雲端", "market": "TSE", "mcap": 800},
    {"symbol": "2427", "name": "三商電", "sector": "數位雲端", "market": "TSE", "mcap": 300},
    {"symbol": "6163", "name": "華電網", "sector": "數位雲端", "market": "TSE", "mcap": 300},
    {"symbol": "6214", "name": "精誠", "sector": "數位雲端", "market": "TSE", "mcap": 1200},
    {"symbol": "2453", "name": "凌群", "sector": "數位雲端", "market": "TSE", "mcap": 400},
    {"symbol": "6231", "name": "系微", "sector": "數位雲端", "market": "OTC", "mcap": 500},
    {"symbol": "6516", "name": "勤崴國際", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "8454", "name": "富邦媒", "sector": "數位雲端", "market": "TSE", "mcap": 1100},
    {"symbol": "7722", "name": "LINEPAY", "sector": "數位雲端", "market": "OTC", "mcap": 1500},
    {"symbol": "7765", "name": "中華資安", "sector": "數位雲端", "market": "OTC", "mcap": 800},
    {"symbol": "3130", "name": "一零四", "sector": "數位雲端", "market": "TSE", "mcap": 600},
    {"symbol": "6902", "name": "GOGOLOOK", "sector": "數位雲端", "market": "OTC", "mcap": 400},
    {"symbol": "6165", "name": "浪凡", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "6614", "name": "資拓宏宇", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "6906", "name": "現觀科", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "7721", "name": "微程式", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "7823", "name": "奧義賽博-KY創", "sector": "數位雲端", "market": "OTC", "mcap": 200},
    {"symbol": "8487", "name": "愛爾達-創", "sector": "數位雲端", "market": "OTC", "mcap": 300},
    {"symbol": "7835", "name": "永悅健康-創", "sector": "數位雲端", "market": "OTC", "mcap": 200},

    # 資訊服務
    {"symbol": "2480", "name": "敦陽科", "sector": "資訊服務", "market": "TSE", "mcap": 800},
    {"symbol": "2471", "name": "資通", "sector": "資訊服務", "market": "TSE", "mcap": 300},
    {"symbol": "2468", "name": "華經", "sector": "資訊服務", "market": "TSE", "mcap": 300},
    {"symbol": "5203", "name": "訊連", "sector": "資訊服務", "market": "OTC", "mcap": 600},
    {"symbol": "3083", "name": "網龍", "sector": "資訊服務", "market": "OTC", "mcap": 200},
    {"symbol": "6180", "name": "橘子", "sector": "資訊服務", "market": "TSE", "mcap": 600},
    {"symbol": "5478", "name": "智冠", "sector": "資訊服務", "market": "OTC", "mcap": 800},
    {"symbol": "3546", "name": "宇峻", "sector": "資訊服務", "market": "OTC", "mcap": 300},
    {"symbol": "3293", "name": "鈊象", "sector": "資訊服務", "market": "OTC", "mcap": 3500},
    {"symbol": "4994", "name": "傳奇", "sector": "資訊服務", "market": "OTC", "mcap": 300},
    {"symbol": "6169", "name": "昱泉", "sector": "資訊服務", "market": "OTC", "mcap": 200},
    {"symbol": "4946", "name": "辣椒", "sector": "資訊服務", "market": "OTC", "mcap": 200},
    {"symbol": "6183", "name": "關貿", "sector": "資訊服務", "market": "TSE", "mcap": 800},

    # 造紙
    {"symbol": "1907", "name": "永豐餘", "sector": "造紙", "market": "TSE", "mcap": 900},
    {"symbol": "1904", "name": "正隆", "sector": "造紙", "market": "TSE", "mcap": 600},
    {"symbol": "1909", "name": "榮成", "sector": "造紙", "market": "TSE", "mcap": 500},
    {"symbol": "1905", "name": "華紙", "sector": "造紙", "market": "TSE", "mcap": 400},
    {"symbol": "1906", "name": "寶隆", "sector": "造紙", "market": "TSE", "mcap": 200},
    {"symbol": "1903", "name": "士紙", "sector": "造紙", "market": "TSE", "mcap": 300},
    {"symbol": "6790", "name": "永豐實", "sector": "造紙", "market": "TSE", "mcap": 800},

    # 其他
    {"symbol": "9917", "name": "中保科", "sector": "其他", "market": "TSE", "mcap": 2000},
    {"symbol": "9925", "name": "新保", "sector": "其他", "market": "TSE", "mcap": 1000},
    {"symbol": "9918", "name": "欣天然", "sector": "其他", "market": "TSE", "mcap": 400},
    {"symbol": "5871", "name": "中租-KY", "sector": "其他", "market": "TSE", "mcap": 3500},
    {"symbol": "9945", "name": "潤泰新", "sector": "其他", "market": "TSE", "mcap": 1800},
    {"symbol": "9941", "name": "裕融", "sector": "其他", "market": "TSE", "mcap": 1100},
    {"symbol": "9933", "name": "中鼎", "sector": "其他", "market": "TSE", "mcap": 1200},
    {"symbol": "9939", "name": "宏全", "sector": "其他", "market": "TSE", "mcap": 800},
    {"symbol": "6592", "name": "和潤企業", "sector": "其他", "market": "TSE", "mcap": 1000},
    {"symbol": "8033", "name": "雷虎", "sector": "其他", "market": "OTC", "mcap": 400},
    {"symbol": "6957", "name": "裕慶-KY", "sector": "其他", "market": "TSE", "mcap": 400},
    {"symbol": "9907", "name": "統一實", "sector": "其他", "market": "TSE", "mcap": 600},
    {"symbol": "7855", "name": "和運租車", "sector": "其他", "market": "OTC", "mcap": 300},
    {"symbol": "2348", "name": "海悅", "sector": "其他", "market": "TSE", "mcap": 500},
    {"symbol": "6655", "name": "科定", "sector": "其他", "market": "OTC", "mcap": 300},
    {"symbol": "6464", "name": "台數科", "sector": "其他", "market": "TSE", "mcap": 500},
    {"symbol": "9942", "name": "茂順", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "6585", "name": "鼎基", "sector": "其他", "market": "TSE", "mcap": 500},
    {"symbol": "6184", "name": "大豐電", "sector": "其他", "market": "OTC", "mcap": 300},
    {"symbol": "1437", "name": "勤益控", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "6901", "name": "鑽石投資", "sector": "其他", "market": "TSE", "mcap": 800},
    {"symbol": "5284", "name": "jpp-KY", "sector": "其他", "market": "OTC", "mcap": 400},
    {"symbol": "6914", "name": "阜爾運通", "sector": "其他", "market": "TSE", "mcap": 400},
    {"symbol": "9927", "name": "泰銘", "sector": "其他", "market": "TSE", "mcap": 500},
    {"symbol": "6958", "name": "日盛台駿", "sector": "其他", "market": "TSE", "mcap": 600},
    {"symbol": "2614", "name": "東森", "sector": "其他", "market": "TSE", "mcap": 400},
    {"symbol": "2514", "name": "龍邦", "sector": "其他", "market": "TSE", "mcap": 600},
    {"symbol": "6625", "name": "必應", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "8442", "name": "威宏-KY", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "8463", "name": "潤泰材", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "1443", "name": "立益物流", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "9919", "name": "康那香", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "1435", "name": "中福", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "8481", "name": "政伸", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "6952", "name": "大武山", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "6504", "name": "南六", "sector": "其他", "market": "TSE", "mcap": 400},
    {"symbol": "8411", "name": "福貞-KY", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "1416", "name": "廣豐", "sector": "其他", "market": "TSE", "mcap": 300},
    {"symbol": "3040", "name": "遠見", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "9944", "name": "新麗", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "9902", "name": "台火", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "9928", "name": "中視", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "8466", "name": "美吉吉-KY", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "2496", "name": "卓越", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "8917", "name": "欣泰", "sector": "Other", "market": "OTC", "mcap": 300},
    {"symbol": "9929", "name": "秋雨", "sector": "其他", "market": "TSE", "mcap": 200},
    {"symbol": "8488", "name": "吉源-KY", "sector": "其他", "market": "OTC", "mcap": 200},
    {"symbol": "1516", "name": "川飛", "sector": "其他", "market": "TSE", "mcap": 200}
]

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

    guard_stocks = {
        "2330": {"name": "台積電", "sector": "半導體", "price": 1050.0, "changePercent": 0.96, "tradeValue": 350.5},
        "2317": {"name": "鴻海", "sector": "電腦周邊", "price": 210.0, "changePercent": 1.20, "tradeValue": 180.0},
        "2454": {"name": "聯發科", "sector": "半導體", "price": 1300.0, "changePercent": -0.76, "tradeValue": 120.0},
        "2382": {"name": "廣達", "sector": "電腦周邊", "price": 290.0, "changePercent": 2.10, "tradeValue": 150.0},
        "2881": {"name": "富邦金", "sector": "金融", "price": 90.0, "changePercent": 0.50, "tradeValue": 80.0}
    }

    for sym, info in guard_stocks.items():
        if sym not in results:
            results[sym] = {
                "symbol": sym,
                "name": info["name"],
                "sector": info["sector"],
                "market": "TSE",
                "mcap": 10000,
                "price": info["price"],
                "change": 5.0,
                "changePercent": info["changePercent"],
                "tradeValue": info["tradeValue"],
                "tradeVolume": 10000,
                "openPrice": info["price"],
                "highPrice": info["price"],
                "lowPrice": info["price"],
                "avgPrice": info["price"]
            }

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
    batch_data = fetch_twse_batch_quotes(SECTOR_STOCKS)
    stocks_map = {}
    if batch_data:
        for sym, info in batch_data.items():
            stocks_map[sym] = info

    missing = [item for item in SECTOR_STOCKS if item["symbol"] not in stocks_map]
    if missing:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_single_fugle_quote, item): item for item in missing[:20]}
            for future in as_completed(futures):
                res_data, _ = future.result()
                if res_data:
                    stocks_map[res_data["symbol"]] = res_data

    _market_cache["timestamp"] = time.time()
    _market_cache["stocks_map"] = stocks_map

    return list(stocks_map.values()), False

def fetch_taiex_index():
    try:
        url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
        if r.status_code == 200:
            msg = r.json().get("msgArray", [])[0]
            z = float(msg.get("z", 0) or msg.get("y", 0))
            y = float(msg.get("y", 0))
            chg = round(z - y, 2)
            return {"index": z, "change": chg}
    except:
        pass
    return {"index": 23000.0, "change": 0.0}

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
    lines = [f"🔥 【盤中即時資金熱力速報】(共 32 大產業 / {len(stocks)} 檔核心指標股)"]
    for idx, r in enumerate(ranked[:6], 1):
        sign = "+" if r["avgChange"] > 0 else ""
        icon = "🔴" if r["avgChange"] > 0 else ("🟢" if r["avgChange"] < 0 else "⚪")
        ts = r["topStock"]
        ts_sign = "+" if ts["changePercent"] > 0 else ""
        lines.append(f"#{idx} {icon} {r['sector']} ({sign}{r['avgChange']}% | {r['tradeValue']}億)\n    └ 領頭羊：{ts['name']} {ts['price']} ({ts_sign}{ts['changePercent']}%)")
    return "\n".join(lines)

@heatmap_bp.route("/api/heatmap/snapshot")
def api_heatmap_snapshot():
    stocks, cached = get_realtime_heatmap_data()
    taiex = fetch_taiex_index()
    updated_str = time.strftime("%H:%M:%S", time.localtime(_market_cache["timestamp"])) if _market_cache["timestamp"] else "--:--:--"
    return jsonify({
        "status": "ok",
        "cached": cached,
        "updatedAt": updated_str,
        "stocks": stocks,
        "taiex": taiex
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
