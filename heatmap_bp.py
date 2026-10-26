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

# 12 大產業共 300 檔核心戰略池 (台灣 50 + 中型 100 + 櫃買富櫃 200)
SECTOR_STOCKS = [
    # 1. 半導體 (35檔)
    {"symbol": "2330", "name": "台積電", "sector": "半導體", "market": "TSE", "mcap": 265000},
    {"symbol": "2454", "name": "聯發科", "sector": "半導體", "market": "TSE", "mcap": 22500},
    {"symbol": "3711", "name": "日月光投控", "sector": "半導體", "market": "TSE", "mcap": 7300},
    {"symbol": "2303", "name": "聯電", "sector": "半導體", "market": "TSE", "mcap": 6200},
    {"symbol": "3661", "name": "世芯-KY", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3034", "name": "聯詠", "sector": "半導體", "market": "TSE", "mcap": 3100},
    {"symbol": "2379", "name": "瑞昱", "sector": "半導體", "market": "TSE", "mcap": 2400},
    {"symbol": "3443", "name": "創意", "sector": "半導體", "market": "TSE", "mcap": 1850},
    {"symbol": "2449", "name": "京元電子", "sector": "半導體", "market": "TSE", "mcap": 1600},
    {"symbol": "2344", "name": "華邦電", "sector": "半導體", "market": "TSE", "mcap": 980},
    {"symbol": "2408", "name": "南亞科", "sector": "半導體", "market": "TSE", "mcap": 1150},
    {"symbol": "3035", "name": "智原", "sector": "半導體", "market": "TSE", "mcap": 1100},
    {"symbol": "2388", "name": "威盛", "sector": "半導體", "market": "TSE", "mcap": 650},
    {"symbol": "2458", "name": "義隆", "sector": "半導體", "market": "TSE", "mcap": 820},
    {"symbol": "3006", "name": "晶豪科", "sector": "半導體", "market": "TSE", "mcap": 310},
    {"symbol": "6239", "name": "力成", "sector": "半導體", "market": "TSE", "mcap": 1150},
    {"symbol": "2436", "name": "偉詮電", "sector": "半導體", "market": "TSE", "mcap": 290},
    {"symbol": "3532", "name": "台勝科", "sector": "半導體", "market": "TSE", "mcap": 480},
    {"symbol": "8016", "name": "矽創", "sector": "半導體", "market": "TSE", "mcap": 450},
    {"symbol": "4961", "name": "天鈺", "sector": "半導體", "market": "TSE", "mcap": 550},
    {"symbol": "6770", "name": "力積電", "sector": "半導體", "market": "TSE", "mcap": 720},
    {"symbol": "2337", "name": "旺宏", "sector": "半導體", "market": "TSE", "mcap": 590},
    {"symbol": "8150", "name": "南茂", "sector": "半導體", "market": "TSE", "mcap": 340},
    {"symbol": "3529", "name": "力旺", "sector": "半導體", "market": "OTC", "mcap": 2100},
    {"symbol": "5274", "name": "信驊", "sector": "半導體", "market": "OTC", "mcap": 2800},
    {"symbol": "6488", "name": "環球晶", "sector": "半導體", "market": "OTC", "mcap": 1950},
    {"symbol": "3105", "name": "穩懋", "sector": "半導體", "market": "OTC", "mcap": 650},
    {"symbol": "8299", "name": "群聯", "sector": "半導體", "market": "OTC", "mcap": 1250},
    {"symbol": "5269", "name": "祥碩", "sector": "半導體", "market": "OTC", "mcap": 1400},
    {"symbol": "6531", "name": "愛普*", "sector": "半導體", "market": "OTC", "mcap": 520},
    {"symbol": "4966", "name": "譜瑞-KY", "sector": "半導體", "market": "OTC", "mcap": 1100},
    {"symbol": "8086", "name": "宏捷科", "sector": "半導體", "market": "OTC", "mcap": 310},
    {"symbol": "6182", "name": "合晶", "sector": "半導體", "market": "OTC", "mcap": 250},
    {"symbol": "3264", "name": "欣銓", "sector": "半導體", "market": "OTC", "mcap": 480},
    {"symbol": "6643", "name": "M31", "sector": "半導體", "market": "OTC", "mcap": 580},

    # 2. 電腦週邊 (28檔)
    {"symbol": "2382", "name": "廣達", "sector": "電腦週邊", "market": "TSE", "mcap": 11800},
    {"symbol": "3231", "name": "緯創", "sector": "電腦週邊", "market": "TSE", "mcap": 3350},
    {"symbol": "6669", "name": "緯穎", "sector": "電腦週邊", "market": "TSE", "mcap": 3850},
    {"symbol": "3017", "name": "奇鋐", "sector": "電腦週邊", "market": "TSE", "mcap": 2550},
    {"symbol": "2357", "name": "華碩", "sector": "電腦週邊", "market": "TSE", "mcap": 4300},
    {"symbol": "2376", "name": "技嘉", "sector": "電腦週邊", "market": "TSE", "mcap": 1900},
    {"symbol": "2356", "name": "英業達", "sector": "電腦週邊", "market": "TSE", "mcap": 1800},
    {"symbol": "2324", "name": "仁寶", "sector": "電腦週邊", "market": "TSE", "mcap": 1550},
    {"symbol": "2377", "name": "微星", "sector": "電腦週邊", "market": "TSE", "mcap": 1600},
    {"symbol": "2301", "name": "光寶科", "sector": "電腦週邊", "market": "TSE", "mcap": 3100},
    {"symbol": "2395", "name": "研華", "sector": "電腦週邊", "market": "TSE", "mcap": 2850},
    {"symbol": "8210", "name": "勤誠", "sector": "電腦週邊", "market": "TSE", "mcap": 380},
    {"symbol": "2353", "name": "宏碁", "sector": "電腦週邊", "market": "TSE", "mcap": 1150},
    {"symbol": "3013", "name": "晟銘電", "sector": "電腦週邊", "market": "TSE", "mcap": 310},
    {"symbol": "2421", "name": "建準", "sector": "電腦週邊", "market": "TSE", "mcap": 520},
    {"symbol": "6414", "name": "樺漢", "sector": "電腦週邊", "market": "TSE", "mcap": 620},
    {"symbol": "3706", "name": "神達", "sector": "電腦週邊", "market": "TSE", "mcap": 950},
    {"symbol": "2362", "name": "藍天", "sector": "電腦週邊", "market": "TSE", "mcap": 280},
    {"symbol": "2417", "name": "圓剛", "sector": "電腦週邊", "market": "TSE", "mcap": 190},
    {"symbol": "6579", "name": "研揚", "sector": "電腦週邊", "market": "TSE", "mcap": 240},
    {"symbol": "8114", "name": "振樺電", "sector": "電腦週邊", "market": "TSE", "mcap": 310},
    {"symbol": "3324", "name": "雙鴻", "sector": "電腦週邊", "market": "OTC", "mcap": 620},
    {"symbol": "6121", "name": "新普", "sector": "電腦週邊", "market": "OTC", "mcap": 1050},
    {"symbol": "3211", "name": "順達", "sector": "電腦週邊", "market": "OTC", "mcap": 310},
    {"symbol": "4931", "name": "新盛力", "sector": "電腦週邊", "market": "OTC", "mcap": 150},
    {"symbol": "5351", "name": "鈺創", "sector": "電腦週邊", "market": "OTC", "mcap": 180},
    {"symbol": "3483", "name": "力致", "sector": "電腦週邊", "market": "OTC", "mcap": 290},
    {"symbol": "6230", "name": "尼得科超眾", "sector": "電腦週邊", "market": "OTC", "mcap": 220},

    # 3. 電子組件 (28檔)
    {"symbol": "2308", "name": "台達電", "sector": "電子組件", "market": "TSE", "mcap": 10200},
    {"symbol": "2327", "name": "國巨", "sector": "電子組件", "market": "TSE", "mcap": 3250},
    {"symbol": "3037", "name": "欣興", "sector": "電子組件", "market": "TSE", "mcap": 2450},
    {"symbol": "2383", "name": "台光電", "sector": "電子組件", "market": "TSE", "mcap": 2100},
    {"symbol": "3653", "name": "健策", "sector": "電子組件", "market": "TSE", "mcap": 1950},
    {"symbol": "2368", "name": "金像電", "sector": "電子組件", "market": "TSE", "mcap": 1100},
    {"symbol": "2313", "name": "華通", "sector": "電子組件", "market": "TSE", "mcap": 950},
    {"symbol": "3044", "name": "健鼎", "sector": "電子組件", "market": "TSE", "mcap": 1250},
    {"symbol": "8046", "name": "南電", "sector": "電子組件", "market": "TSE", "mcap": 850},
    {"symbol": "3189", "name": "景碩", "sector": "電子組件", "market": "TSE", "mcap": 780},
    {"symbol": "4958", "name": "臻鼎-KY", "sector": "電子組件", "market": "TSE", "mcap": 2100},
    {"symbol": "6269", "name": "台郡", "sector": "電子組件", "market": "TSE", "mcap": 310},
    {"symbol": "2492", "name": "華新科", "sector": "電子組件", "market": "TSE", "mcap": 850},
    {"symbol": "3533", "name": "嘉澤", "sector": "電子組件", "market": "TSE", "mcap": 3100},
    {"symbol": "3023", "name": "信邦", "sector": "電子組件", "market": "TSE", "mcap": 750},
    {"symbol": "6213", "name": "聯茂", "sector": "電子組件", "market": "TSE", "mcap": 380},
    {"symbol": "2385", "name": "群光", "sector": "電子組件", "market": "TSE", "mcap": 2100},
    {"symbol": "6412", "name": "群電", "sector": "電子組件", "market": "TSE", "mcap": 550},
    {"symbol": "2467", "name": "志聖", "sector": "電子組件", "market": "TSE", "mcap": 410},
    {"symbol": "3090", "name": "日電貿", "sector": "電子組件", "market": "TSE", "mcap": 220},
    {"symbol": "6274", "name": "台燿", "sector": "電子組件", "market": "OTC", "mcap": 480},
    {"symbol": "1815", "name": "富喬", "sector": "電子組件", "market": "OTC", "mcap": 150},
    {"symbol": "8358", "name": "金居", "sector": "電子組件", "market": "OTC", "mcap": 240},
    {"symbol": "5340", "name": "建榮", "sector": "電子組件", "market": "OTC", "mcap": 180},
    {"symbol": "3293", "name": "鈊象", "sector": "電子組件", "market": "OTC", "mcap": 3500},
    {"symbol": "6156", "name": "松上", "sector": "電子組件", "market": "OTC", "mcap": 120},
    {"symbol": "8039", "name": "台虹", "sector": "電子組件", "market": "OTC", "mcap": 280},
    {"symbol": "5469", "name": "瀚宇博", "sector": "電子組件", "market": "OTC", "mcap": 650},

    # 4. 其他電子 (24檔)
    {"symbol": "2317", "name": "鴻海", "sector": "其他電子", "market": "TSE", "mcap": 29800},
    {"symbol": "2360", "name": "致茂", "sector": "其他電子", "market": "TSE", "mcap": 1680},
    {"symbol": "2404", "name": "漢唐", "sector": "其他電子", "market": "TSE", "mcap": 790},
    {"symbol": "2354", "name": "鴻準", "sector": "其他電子", "market": "TSE", "mcap": 1050},
    {"symbol": "6139", "name": "亞翔", "sector": "其他電子", "market": "TSE", "mcap": 550},
    {"symbol": "6196", "name": "帆宣", "sector": "其他電子", "market": "TSE", "mcap": 350},
    {"symbol": "3583", "name": "辛耘", "sector": "其他電子", "market": "TSE", "mcap": 340},
    {"symbol": "2439", "name": "美律", "sector": "其他電子", "market": "TSE", "mcap": 480},
    {"symbol": "6409", "name": "旭隼", "sector": "其他電子", "market": "TSE", "mcap": 1700},
    {"symbol": "2359", "name": "所羅門", "sector": "其他電子", "market": "TSE", "mcap": 310},
    {"symbol": "2312", "name": "金寶", "sector": "其他電子", "market": "TSE", "mcap": 410},
    {"symbol": "2474", "name": "可成", "sector": "其他電子", "market": "TSE", "mcap": 3100},
    {"symbol": "2482", "name": "連宇", "sector": "其他電子", "market": "TSE", "mcap": 150},
    {"symbol": "3030", "name": "德律", "sector": "其他電子", "market": "TSE", "mcap": 380},
    {"symbol": "5536", "name": "聖暉*", "sector": "其他電子", "market": "OTC", "mcap": 420},
    {"symbol": "6187", "name": "萬潤", "sector": "其他電子", "market": "OTC", "mcap": 380},
    {"symbol": "3131", "name": "弘塑", "sector": "其他電子", "market": "OTC", "mcap": 1200},
    {"symbol": "6640", "name": "均華", "sector": "其他電子", "market": "OTC", "mcap": 350},
    {"symbol": "5443", "name": "均豪", "sector": "其他電子", "market": "OTC", "mcap": 280},
    {"symbol": "3563", "name": "牧德", "sector": "其他電子", "market": "OTC", "mcap": 410},
    {"symbol": "6146", "name": "耕興", "sector": "其他電子", "market": "OTC", "mcap": 520},
    {"symbol": "3260", "name": "威剛", "sector": "其他電子", "market": "OTC", "mcap": 620},
    {"symbol": "8044", "name": "網家", "sector": "其他電子", "market": "OTC", "mcap": 110},
    {"symbol": "6510", "name": "精測", "sector": "其他電子", "market": "OTC", "mcap": 450},

    # 5. 光電面板 (22檔)
    {"symbol": "3008", "name": "大立光", "sector": "光電面板", "market": "TSE", "mcap": 3450},
    {"symbol": "3481", "name": "群創", "sector": "光電面板", "market": "TSE", "mcap": 1450},
    {"symbol": "2409", "name": "友達", "sector": "光電面板", "market": "TSE", "mcap": 1350},
    {"symbol": "3406", "name": "玉晶光", "sector": "光電面板", "market": "TSE", "mcap": 580},
    {"symbol": "3019", "name": "亞光", "sector": "光電面板", "market": "TSE", "mcap": 350},
    {"symbol": "6116", "name": "彩晶", "sector": "光電面板", "market": "TSE", "mcap": 280},
    {"symbol": "3714", "name": "富采", "sector": "光電面板", "market": "TSE", "mcap": 320},
    {"symbol": "2393", "name": "億光", "sector": "光電面板", "market": "TSE", "mcap": 240},
    {"symbol": "2349", "name": "錸德", "sector": "光電面板", "market": "TSE", "mcap": 190},
    {"symbol": "2406", "name": "國碩", "sector": "光電面板", "market": "TSE", "mcap": 150},
    {"symbol": "6443", "name": "元晶", "sector": "光電面板", "market": "TSE", "mcap": 210},
    {"symbol": "3576", "name": "聯合再生", "sector": "光電面板", "market": "TSE", "mcap": 180},
    {"symbol": "6209", "name": "今國光", "sector": "光電面板", "market": "TSE", "mcap": 120},
    {"symbol": "4934", "name": "太極", "sector": "光電面板", "market": "TSE", "mcap": 110},
    {"symbol": "3362", "name": "先進光", "sector": "光電面板", "market": "TSE", "mcap": 310},
    {"symbol": "8069", "name": "元太", "sector": "光電面板", "market": "OTC", "mcap": 3100},
    {"symbol": "5371", "name": "中光電", "sector": "光電面板", "market": "OTC", "mcap": 360},
    {"symbol": "3455", "name": "由田", "sector": "光電面板", "market": "OTC", "mcap": 150},
    {"symbol": "3149", "name": "正達", "sector": "光電面板", "market": "OTC", "mcap": 180},
    {"symbol": "6244", "name": "茂迪", "sector": "光電面板", "market": "OTC", "mcap": 190},
    {"symbol": "5483", "name": "中美晶", "sector": "光電面板", "market": "OTC", "mcap": 1850},
    {"symbol": "3297", "name": "杭特", "sector": "光電面板", "market": "OTC", "mcap": 90},

    # 6. 通訊網路 (23檔)
    {"symbol": "2345", "name": "智邦", "sector": "通訊網路", "market": "TSE", "mcap": 3180},
    {"symbol": "2412", "name": "中華電", "sector": "通訊網路", "market": "TSE", "mcap": 9600},
    {"symbol": "3045", "name": "台灣大", "sector": "通訊網路", "market": "TSE", "mcap": 3100},
    {"symbol": "4904", "name": "遠傳", "sector": "通訊網路", "market": "TSE", "mcap": 2850},
    {"symbol": "6442", "name": "光聖", "sector": "通訊網路", "market": "TSE", "mcap": 350},
    {"symbol": "6285", "name": "啟碁", "sector": "通訊網路", "market": "TSE", "mcap": 680},
    {"symbol": "5388", "name": "中磊", "sector": "通訊網路", "market": "TSE", "mcap": 380},
    {"symbol": "2455", "name": "全新", "sector": "通訊網路", "market": "TSE", "mcap": 310},
    {"symbol": "2332", "name": "友訊", "sector": "通訊網路", "market": "TSE", "mcap": 250},
    {"symbol": "3596", "name": "智易", "sector": "通訊網路", "market": "TSE", "mcap": 480},
    {"symbol": "2314", "name": "台揚", "sector": "通訊網路", "market": "TSE", "mcap": 150},
    {"symbol": "2419", "name": "仲琦", "sector": "通訊網路", "market": "TSE", "mcap": 180},
    {"symbol": "2485", "name": "兆赫", "sector": "通訊網路", "market": "TSE", "mcap": 210},
    {"symbol": "3704", "name": "合勤控", "sector": "通訊網路", "market": "TSE", "mcap": 310},
    {"symbol": "4977", "name": "眾達-KY", "sector": "通訊網路", "market": "TSE", "mcap": 160},
    {"symbol": "3081", "name": "聯亞", "sector": "通訊網路", "market": "OTC", "mcap": 320},
    {"symbol": "4979", "name": "華星光", "sector": "通訊網路", "market": "OTC", "mcap": 240},
    {"symbol": "3163", "name": "波若威", "sector": "通訊網路", "market": "OTC", "mcap": 120},
    {"symbol": "3363", "name": "上詮", "sector": "通訊網路", "market": "OTC", "mcap": 410},
    {"symbol": "4908", "name": "前鼎", "sector": "通訊網路", "market": "OTC", "mcap": 190},
    {"symbol": "3234", "name": "光環", "sector": "通訊網路", "market": "OTC", "mcap": 110},
    {"symbol": "6426", "name": "統新", "sector": "通訊網路", "market": "OTC", "mcap": 100},
    {"symbol": "3491", "name": "昇達科", "sector": "通訊網路", "market": "OTC", "mcap": 680},

    # 7. 重電電機 (22檔)
    {"symbol": "1519", "name": "華城", "sector": "重電電機", "market": "TSE", "mcap": 1950},
    {"symbol": "1503", "name": "士電", "sector": "重電電機", "market": "TSE", "mcap": 1200},
    {"symbol": "1513", "name": "中興電", "sector": "重電電機", "market": "TSE", "mcap": 880},
    {"symbol": "1514", "name": "亞力", "sector": "重電電機", "market": "TSE", "mcap": 320},
    {"symbol": "1504", "name": "東元", "sector": "重電電機", "market": "TSE", "mcap": 1100},
    {"symbol": "1609", "name": "大亞", "sector": "重電電機", "market": "TSE", "mcap": 350},
    {"symbol": "1605", "name": "華新", "sector": "重電電機", "market": "TSE", "mcap": 1350},
    {"symbol": "2049", "name": "上銀", "sector": "重電電機", "market": "TSE", "mcap": 820},
    {"symbol": "2371", "name": "大同", "sector": "重電電機", "market": "TSE", "mcap": 1050},
    {"symbol": "1590", "name": "亞德客-KY", "sector": "重電電機", "market": "TSE", "mcap": 2100},
    {"symbol": "1608", "name": "華榮", "sector": "重電電機", "market": "TSE", "mcap": 280},
    {"symbol": "1612", "name": "宏泰", "sector": "重電電機", "market": "TSE", "mcap": 210},
    {"symbol": "1618", "name": "合機", "sector": "重電電機", "market": "TSE", "mcap": 150},
    {"symbol": "1536", "name": "和大", "sector": "重電電機", "market": "TSE", "mcap": 410},
    {"symbol": "4551", "name": "智伸科", "sector": "重電電機", "market": "TSE", "mcap": 310},
    {"symbol": "1560", "name": "中砂", "sector": "重電電機", "market": "TSE", "mcap": 680},
    {"symbol": "4562", "name": "穎漢", "sector": "重電電機", "market": "TSE", "mcap": 120},
    {"symbol": "4583", "name": "台灣精銳", "sector": "重電電機", "market": "TSE", "mcap": 750},
    {"symbol": "6806", "name": "森崴能源", "sector": "重電電機", "market": "OTC", "mcap": 380},
    {"symbol": "8996", "name": "高力", "sector": "重電電機", "market": "OTC", "mcap": 410},
    {"symbol": "1586", "name": "和勤", "sector": "重電電機", "market": "OTC", "mcap": 110},
    {"symbol": "4510", "name": "高鋒", "sector": "重電電機", "market": "OTC", "mcap": 120},

    # 8. 金融保險 (24檔)
    {"symbol": "2881", "name": "富邦金", "sector": "金融保險", "market": "TSE", "mcap": 12400},
    {"symbol": "2882", "name": "國泰金", "sector": "金融保險", "market": "TSE", "mcap": 10100},
    {"symbol": "2891", "name": "中信金", "sector": "金融保險", "market": "TSE", "mcap": 7500},
    {"symbol": "2886", "name": "兆豐金", "sector": "金融保險", "market": "TSE", "mcap": 5800},
    {"symbol": "2884", "name": "玉山金", "sector": "金融保險", "market": "TSE", "mcap": 4500},
    {"symbol": "2885", "name": "元大金", "sector": "金融保險", "market": "TSE", "mcap": 4200},
    {"symbol": "2892", "name": "第一金", "sector": "金融保險", "market": "TSE", "mcap": 3900},
    {"symbol": "2890", "name": "永豐金", "sector": "金融保險", "market": "TSE", "mcap": 3100},
    {"symbol": "2883", "name": "凱基金", "sector": "金融保險", "market": "TSE", "mcap": 2900},
    {"symbol": "2880", "name": "華南金", "sector": "金融保險", "market": "TSE", "mcap": 3100},
    {"symbol": "2887", "name": "台新金", "sector": "金融保險", "market": "TSE", "mcap": 2800},
    {"symbol": "5880", "name": "合庫金", "sector": "金融保險", "market": "TSE", "mcap": 3500},
    {"symbol": "2834", "name": "臺企銀", "sector": "金融保險", "market": "TSE", "mcap": 1100},
    {"symbol": "2801", "name": "彰銀", "sector": "金融保險", "market": "TSE", "mcap": 1800},
    {"symbol": "2812", "name": "台中銀", "sector": "金融保險", "market": "TSE", "mcap": 720},
    {"symbol": "2845", "name": "遠東銀", "sector": "金融保險", "market": "TSE", "mcap": 410},
    {"symbol": "2855", "name": "統一證", "sector": "金融保險", "market": "TSE", "mcap": 550},
    {"symbol": "2867", "name": "三商壽", "sector": "金融保險", "market": "TSE", "mcap": 310},
    {"symbol": "5871", "name": "中租-KY", "sector": "金融保險", "market": "TSE", "mcap": 2100},
    {"symbol": "9941", "name": "裕融", "sector": "金融保險", "market": "TSE", "mcap": 410},
    {"symbol": "6005", "name": "群益證", "sector": "金融保險", "market": "TSE", "mcap": 520},
    {"symbol": "6024", "name": "群益期", "sector": "金融保險", "market": "OTC", "mcap": 210},
    {"symbol": "6016", "name": "康和證", "sector": "金融保險", "market": "OTC", "mcap": 150},
    {"symbol": "5864", "name": "致和證", "sector": "金融保險", "market": "OTC", "mcap": 90},

    # 9. 航運業 (20檔)
    {"symbol": "2603", "name": "長榮", "sector": "航運業", "market": "TSE", "mcap": 4600},
    {"symbol": "2609", "name": "陽明", "sector": "航運業", "market": "TSE", "mcap": 2550},
    {"symbol": "2615", "name": "萬海", "sector": "航運業", "market": "TSE", "mcap": 2400},
    {"symbol": "2618", "name": "長榮航", "sector": "航運業", "market": "TSE", "mcap": 2150},
    {"symbol": "2610", "name": "華航", "sector": "航運業", "market": "TSE", "mcap": 1450},
    {"symbol": "2646", "name": "星宇航空", "sector": "航運業", "market": "TSE", "mcap": 750},
    {"symbol": "2606", "name": "裕民", "sector": "航運業", "market": "TSE", "mcap": 520},
    {"symbol": "2637", "name": "慧洋-KY", "sector": "航運業", "market": "TSE", "mcap": 510},
    {"symbol": "2605", "name": "新興", "sector": "航運業", "market": "TSE", "mcap": 280},
    {"symbol": "2612", "name": "中航", "sector": "航運業", "market": "TSE", "mcap": 210},
    {"symbol": "2617", "name": "台航", "sector": "航運業", "market": "TSE", "mcap": 240},
    {"symbol": "2601", "name": "益航", "sector": "航運業", "market": "TSE", "mcap": 150},
    {"symbol": "2614", "name": "東森", "sector": "航運業", "market": "TSE", "mcap": 190},
    {"symbol": "2634", "name": "榮運", "sector": "航運業", "market": "TSE", "mcap": 310},
    {"symbol": "2608", "name": "嘉里大榮", "sector": "航運業", "market": "TSE", "mcap": 280},
    {"symbol": "5608", "name": "四維航", "sector": "航運業", "market": "TSE", "mcap": 150},
    {"symbol": "2636", "name": "台驊投控", "sector": "航運業", "market": "TSE", "mcap": 220},
    {"symbol": "2641", "name": "正德", "sector": "航運業", "market": "OTC", "mcap": 160},
    {"symbol": "5609", "name": "中菲行", "sector": "航運業", "market": "OTC", "mcap": 210},

    # 10. 造船軍工 (18檔)
    {"symbol": "2208", "name": "台船", "sector": "造船軍工", "market": "TSE", "mcap": 195},
    {"symbol": "2634", "name": "漢翔", "sector": "造船軍工", "market": "TSE", "mcap": 460},
    {"symbol": "8033", "name": "雷虎", "sector": "造船軍工", "market": "TSE", "mcap": 110},
    {"symbol": "6753", "name": "龍德造船", "sector": "造船軍工", "market": "TSE", "mcap": 130},
    {"symbol": "2645", "name": "長榮航太", "sector": "造船軍工", "market": "TSE", "mcap": 410},
    {"symbol": "5222", "name": "全訊", "sector": "造船軍工", "market": "TSE", "mcap": 120},
    {"symbol": "4572", "name": "駐龍", "sector": "造船軍工", "market": "TSE", "mcap": 65},
    {"symbol": "8222", "name": "寶一", "sector": "造船軍工", "market": "TSE", "mcap": 50},
    {"symbol": "3004", "name": "豐達科", "sector": "造船軍工", "market": "TSE", "mcap": 150},
    {"symbol": "4540", "name": "全球傳動", "sector": "造船軍工", "market": "TSE", "mcap": 120},
    {"symbol": "2429", "name": "銘旺科", "sector": "造船軍工", "market": "TSE", "mcap": 80},
    {"symbol": "5386", "name": "青雲", "sector": "造船軍工", "market": "TSE", "mcap": 110},
    {"symbol": "2643", "name": "捷迅", "sector": "造船軍工", "market": "OTC", "mcap": 140},
    {"symbol": "4541", "name": "晟田", "sector": "造船軍工", "market": "OTC", "mcap": 110},
    {"symbol": "6829", "name": "千附精密", "sector": "造船軍工", "market": "OTC", "mcap": 210},
    {"symbol": "4916", "name": "事欣科", "sector": "造船軍工", "market": "OTC", "mcap": 150},
    {"symbol": "3441", "name": "聯一光", "sector": "造船軍工", "market": "OTC", "mcap": 90},
    {"symbol": "5314", "name": "世紀*", "sector": "造船軍工", "market": "OTC", "mcap": 80},

    # 11. 生技醫療 (24檔)
    {"symbol": "6472", "name": "保瑞", "sector": "生技醫療", "market": "TSE", "mcap": 820},
    {"symbol": "1795", "name": "美時", "sector": "生技醫療", "market": "TSE", "mcap": 750},
    {"symbol": "6919", "name": "康霈*", "sector": "生技醫療", "market": "TSE", "mcap": 950},
    {"symbol": "6491", "name": "晶碩", "sector": "生技醫療", "market": "TSE", "mcap": 310},
    {"symbol": "6782", "name": "視陽", "sector": "生技醫療", "market": "TSE", "mcap": 160},
    {"symbol": "1760", "name": "寶齡富錦", "sector": "生技醫療", "market": "TSE", "mcap": 210},
    {"symbol": "4137", "name": "麗豐-KY", "sector": "生技醫療", "market": "TSE", "mcap": 180},
    {"symbol": "1789", "name": "神隆", "sector": "生技醫療", "market": "TSE", "mcap": 220},
    {"symbol": "4142", "name": "國光生", "sector": "生技醫療", "market": "TSE", "mcap": 250},
    {"symbol": "1734", "name": "杏輝", "sector": "生技醫療", "market": "TSE", "mcap": 190},
    {"symbol": "4119", "name": "旭富", "sector": "生技醫療", "market": "TSE", "mcap": 150},
    {"symbol": "6446", "name": "藥華藥", "sector": "生技醫療", "market": "OTC", "mcap": 2150},
    {"symbol": "4743", "name": "合一", "sector": "生技醫療", "market": "OTC", "mcap": 620},
    {"symbol": "6469", "name": "大樹", "sector": "生技醫療", "market": "OTC", "mcap": 280},
    {"symbol": "4128", "name": "中天", "sector": "生技醫療", "market": "OTC", "mcap": 380},
    {"symbol": "4147", "name": "中裕", "sector": "生技醫療", "market": "OTC", "mcap": 310},
    {"symbol": "4105", "name": "東洋", "sector": "生技醫療", "market": "OTC", "mcap": 1250},
    {"symbol": "4162", "name": "智擎", "sector": "生技醫療", "market": "OTC", "mcap": 950},
    {"symbol": "6547", "name": "高端疫苗", "sector": "生技醫療", "market": "OTC", "mcap": 450},
    {"symbol": "4123", "name": "晟德", "sector": "生技醫療", "market": "OTC", "mcap": 410},
    {"symbol": "8436", "name": "大江", "sector": "生技醫療", "market": "OTC", "mcap": 350},
    {"symbol": "4107", "name": "邦特", "sector": "生技醫療", "market": "OTC", "mcap": 320},
    {"symbol": "6589", "name": "台康生技", "sector": "生技醫療", "market": "OTC", "mcap": 580},
    {"symbol": "4736", "name": "泰博", "sector": "生技醫療", "market": "OTC", "mcap": 480},

    # 12. 傳產原物料 (32檔)
    {"symbol": "2002", "name": "中鋼", "sector": "傳產原物料", "market": "TSE", "mcap": 3450},
    {"symbol": "1301", "name": "台塑", "sector": "傳產原物料", "market": "TSE", "mcap": 3100},
    {"symbol": "1303", "name": "南亞", "sector": "傳產原物料", "market": "TSE", "mcap": 3300},
    {"symbol": "1326", "name": "台化", "sector": "傳產原物料", "market": "TSE", "mcap": 2500},
    {"symbol": "6505", "name": "台塑化", "sector": "傳產原物料", "market": "TSE", "mcap": 3800},
    {"symbol": "1101", "name": "台泥", "sector": "傳產原物料", "market": "TSE", "mcap": 2450},
    {"symbol": "1102", "name": "亞泥", "sector": "傳產原物料", "market": "TSE", "mcap": 1400},
    {"symbol": "1216", "name": "統一", "sector": "傳產原物料", "market": "TSE", "mcap": 4900},
    {"symbol": "2912", "name": "統一超", "sector": "傳產原物料", "market": "TSE", "mcap": 3050},
    {"symbol": "2207", "name": "和泰車", "sector": "傳產原物料", "market": "TSE", "mcap": 3800},
    {"symbol": "2542", "name": "興富發", "sector": "傳產原物料", "market": "TSE", "mcap": 880},
    {"symbol": "2504", "name": "國產", "sector": "傳產原物料", "market": "TSE", "mcap": 580},
    {"symbol": "2027", "name": "大成鋼", "sector": "傳產原物料", "market": "TSE", "mcap": 850},
    {"symbol": "2014", "name": "中鴻", "sector": "傳產原物料", "market": "TSE", "mcap": 310},
    {"symbol": "2105", "name": "正新", "sector": "傳產原物料", "market": "TSE", "mcap": 1350},
    {"symbol": "1402", "name": "遠東新", "sector": "傳產原物料", "market": "TSE", "mcap": 1700},
    {"symbol": "1907", "name": "永豐餘", "sector": "傳產原物料", "market": "TSE", "mcap": 550},
    {"symbol": "9910", "name": "豐泰", "sector": "傳產原物料", "market": "TSE", "mcap": 1300},
    {"symbol": "1476", "name": "儒鴻", "sector": "傳產原物料", "market": "TSE", "mcap": 2800},
    {"symbol": "1477", "name": "聚陽", "sector": "傳產原物料", "market": "TSE", "mcap": 1150},
    {"symbol": "9921", "name": "巨大", "sector": "傳產原物料", "market": "TSE", "mcap": 750},
    {"symbol": "9914", "name": "美利達", "sector": "傳產原物料", "market": "TSE", "mcap": 620},
    {"symbol": "2548", "name": "華固", "sector": "傳產原物料", "market": "TSE", "mcap": 350},
    {"symbol": "2520", "name": "冠德", "sector": "傳產原物料", "market": "TSE", "mcap": 310},
    {"symbol": "5522", "name": "遠雄", "sector": "傳產原物料", "market": "TSE", "mcap": 480},
    {"symbol": "1802", "name": "台玻", "sector": "傳產原物料", "market": "TSE", "mcap": 450},
    {"symbol": "1717", "name": "長興", "sector": "傳產原物料", "market": "TSE", "mcap": 360},
    {"symbol": "8454", "name": "富邦媒", "sector": "傳產原物料", "market": "TSE", "mcap": 1100},
    {"symbol": "5512", "name": "力麒", "sector": "傳產原物料", "market": "OTC", "mcap": 210},
    {"symbol": "5508", "name": "永信建", "sector": "傳產原物料", "market": "OTC", "mcap": 350},
    {"symbol": "8083", "name": "瑞穎", "sector": "傳產原物料", "market": "OTC", "mcap": 150},
    {"symbol": "8924", "name": "大田", "sector": "傳產原物料", "market": "OTC", "mcap": 140},
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
    if not force_refresh and _market_cache["stocks_map"] and len(_market_cache["stocks_map"]) >= 250 and (now - _market_cache["timestamp"] < CACHE_TTL):
        return list(_market_cache["stocks_map"].values()), True

    batch_data = fetch_twse_batch_quotes(SECTOR_STOCKS)
    if batch_data:
        for sym, info in batch_data.items():
            _market_cache["stocks_map"][sym] = info

    missing = [item for item in SECTOR_STOCKS if item["symbol"] not in _market_cache["stocks_map"]]
    if missing:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_single_fugle_quote, item): item for item in missing[:30]}
            for future in as_completed(futures):
                res_data, _ = future.result()
                if res_data:
                    _market_cache["stocks_map"][res_data["symbol"]] = res_data

    _market_cache["timestamp"] = time.time()
    _save_disk_cache()

    try:
        generate_heatmap_image(list(_market_cache["stocks_map"].values()))
    except Exception as e:
        print(f"⚠️ 繪製縮圖失敗: {e}", flush=True)

    return list(_market_cache["stocks_map"].values()), False

def generate_heatmap_image(stocks):
    if not stocks:
        return
    top_stocks = sorted(stocks, key=lambda x: x.get("tradeValue", 0), reverse=True)[:35]
    plt.figure(figsize=(10, 6), facecolor='#0b0f19')
    ax = plt.subplot(111)
    ax.set_facecolor('#0b0f19')

    labels = [f"{s['name']}\n{s['changePercent']:+.2f}%" for s in top_stocks]
    sizes = [max(s['tradeValue'], 1.0) for s in top_stocks]

    colors = []
    for s in top_stocks:
        p = s['changePercent']
        if p >= 3: colors.append('#991b1b')
        elif p > 0: colors.append('#dc2626')
        elif p == 0: colors.append('#374151')
        elif p > -3: colors.append('#059669')
        else: colors.append('#065f46')

    squarify.plot(sizes=sizes, label=labels, color=colors, alpha=0.9, text_kwargs={'color':'white', 'fontsize':8, 'weight':'bold'}, pad=True)
    plt.title("StockCommander Realtime Heatmap (Top 35 Active)", color='white', fontsize=12, fontweight='bold', pad=10)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(HEATMAP_IMG_PATH, dpi=150, facecolor='#0b0f19', edgecolor='none')
    plt.close()

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
    lines = [f"🔥 【盤中即時資金熱力速報】(共 12 大產業 / {len(stocks)} 檔核心指標股)"]
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
    target = next((s for s in SECTOR_STOCKS if s["symbol"] == symbol), {"symbol": symbol, "name": symbol, "sector": "自選", "market": "TSE", "mcap": 500})
    fresh, _ = fetch_single_fugle_quote(target)
    if fresh:
        return jsonify({"status": "ok", "stock": fresh})
    cached_st = _market_cache["stocks_map"].get(symbol)
    if cached_st:
        return jsonify({"status": "ok", "stock": {**cached_st, "bidVol": 50, "askVol": 50, "bids": [], "asks": []}})
    return jsonify({"status": "error"}}, 500

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
