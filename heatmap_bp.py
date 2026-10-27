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

# 32 大全方位產業分類核心戰略池（完整陣容與電機擴充）
RAW_SECTOR_DICT = {
    "半導體": [
        "台積電", "聯電", "世界", "力積電", "旺宏", "華邦電", "南亞科", "群聯", "創見", "威剛", 
        "宇瞻", "晶豪科", "鈺創", "矽統", "聯詠", "瑞昱", "聯發科", "矽力*-KY", "力智", "致新", 
        "天鈺", "矽創", "晶心科", "M31", "世芯-KY", "創意", "智原", "京元電子", "日月光投控", "力成", 
        "南茂", "頎邦", "環球晶", "合晶", "中美晶", "穩懋", "宏捷科", "全新", "漢磊", "嘉晶"
    ],
    "電子組件": [
        "台達電", "國巨", "華通", "欣興", "景碩", "南電", "健鼎", "臻鼎-KY", "楠梓電", "敬鵬", 
        "瀚宇博", "台燿", "金像電", "台光電", "聯茂", "台虹", "嘉澤", "信錦", "川湖", "凡甲", 
        "貿聯-KY", "嘉基", "良維", "建準", "奇鋐", "雙鴻", "健策", "勤誠", "順德", "鉅祥"
    ],
    "金融": [
        "富邦金", "國泰金", "中信金", "兆豐金", "玉山金", "元大金", "第一金", "華南金", "合庫金", "永豐金", 
        "台新新光金", "凱基金", "彰銀", "臺企銀", "上海商銀", "王道銀行", "台中銀", "三商壽", "統一證", "群益證", 
        "康和證", "宏遠證", "國票金"
    ],
    "電腦周邊": [
        "廣達", "緯創", "英業達", "仁寶", "和碩", "鴻海", "神達", "華碩", "宏碁", "技嘉", 
        "微星", "艾訊", "樺漢", "融程電", "研華", "凌華", "友通", "宸曜", "精英", "精元", 
        "倫飛", "勤誠", "晟銘電", "迎廣", "振樺電"
    ],
    "其他電子": [
        "鴻海", "致茂", "光寶科", "群光", "佳世達", "可成", "旭隼", "宏正", "研揚", "振樺電", 
        "盟立", "帆宣", "辛耘", "均豪", "由田", "志聖", "德律", "迅得", "牧德", "東捷", 
        "廣運", "雷科", "亞光", "玉晶光", "大立光", "今國光"
    ],
    "網通": [
        "中磊", "智易", "明泰", "啟碁", "智邦", "正文", "合勤控", "友訊", "神準", "兆赫", 
        "仲琦", "台揚", "建漢", "台通", "全新", "波若威", "聯亞", "上詮", "眾達-KY", "光聖", 
        "華星光", "前鼎", "聯光通"
    ],
    "塑膠": [
        "台塑", "南亞", "台化", "台塑化", "亞聚", "台達化", "台苯", "國喬", "聯成", "華夏", 
        "台聚", "永裕", "三芳", "地球"
    ],
    "光電": [
        "友達", "群創", "彩晶", "元太", "凌巨", "誠美材", "晶彩科", "達運", "瑞儀", "GIS-KY", 
        "光洋科", "揚明光", "佳能", "亞光", "玉晶光", "大立光", "先進光", "聯一光", "富晶通", "達興材料"
    ],
    "航運": [
        "長榮", "陽明", "萬海", "台航", "裕民", "新興", "四維航", "慧洋-KY", "正德", "志信", 
        "台驊投控", "中菲行", "捷迅", "宅配通", "嘉里大榮", "山隆", "榮運"
    ],
    "電機": [
        "中興電", "華城", "士電", "東元", "大同", "亞力", "樂事綠能", "瑞智", "恩德", "鑽全", 
        "氣立", "上銀", "直得", "全球傳動", "鈞興-KY", "東台", "程泰", "瀧澤科", "百德",
        "亞德客-KY", "高力", "新代", "大量", "台灣精銳", "大銀微系統", "豐祥-KY", "廣隆", 
        "時碩工業", "伸興", "中宇", "駐龍", "勤美", "富田-創", "正道", "亞崴"
    ],
    "營建": [
        "華固", "長虹", "興富發", "遠雄", "皇翔", "冠德", "潤弘", "根基", "達麗", "愛山林", 
        "國建", "國揚", "華友聯", "京城", "欣陸", "皇普", "全坤建", "櫻花建", "工信", "鄉林"
    ],
    "鋼鐵": [
        "中鋼", "中鴻", "東和鋼鐵", "豐興", "大成鋼", "威致", "燁興", "燁輝", "第一銅", "官田鋼", 
        "春源", "春雨", "志聯", "彰源", "允強", "千興", "聚亨", "世紀鋼", "海光"
    ],
    "生技": [
        "台灣東洋", "保瑞", "藥華藥", "中裕", "合一", "晶碩", "雃博", "泰博", "訊聯", "基亞", 
        "智擎", "醣聯", "安特羅", "永昕", "順藥", "國光生", "晟德", "葡萄王", "東生華", "健喬", 
        "神隆", "杏輝", "杏國", "台康生技", "浩鼎"
    ],
    "食品": [
        "統一", "味全", "大成", "卜蜂", "泰山", "福壽", "聯華", "聯華食", "佳格", "黑松", 
        "愛之味", "宏亞", "南僑", "台榮", "天仁", "安心", "鮮活果汁-KY", "瓦城", "王品", "六角"
    ],
    "汽車": [
        "裕隆", "中華", "三陽工業", "和泰車", "裕日車", "東陽", "堤維西", "帝寶", "車王電", "江申", 
        "為升", "劍麟", "麗清", "智伸科", "聯嘉投控", "瑞利", "耿鼎", "廣隆", "朋程", "鴻華先進-創", 
        "汎德永業", "宇隆", "巧新", "百達-KY", "艾姆勒", "和大", "怡利電", "虎山", "六方科-KY", "宏旭-KY", 
        "倉佑", "華勝-KY", "永新-KY", "IKKA-KY", "大億", "吉茂"
    ],
    "化學": [
        "台肥", "長興", "中華化", "永光", "勝一", "國精化", "三福化", "永記", "雙鍵", "材料*-KY", 
        "南寶", "上品", "台特化", "台硝", "和桐", "旭富", "康普", "日勝化", "和益", "中碳", 
        "中纖", "興農", "東聯", "東鹼", "國化", "元禎", "國慶科技", "德淵", "花仙子", "展宇", 
        "毛寶"
    ],
    "油電": [
        "台塑化", "台汽電", "森崴能源", "雲豹能源", "泓德能源", "富威電力", "綠電", "台達電", "中興電", "華城", 
        "樂事綠能", "森寶", "天方能源", "全國", "大台北", "欣雄", "新海", "欣天然", "欣高", "山隆"
    ],
    "紡織": [
        "儒鴻", "聚陽", "遠東新", "力麗", "力鵬", "南紡", "東和", "集盛", "宏遠", "佳和", 
        "年興", "得力", "銘旺實", "台南", "福懋", "宜進", "廣越", "利勤", "八貫", "新纖", 
        "新紡", "振大環球", "聯發", "利華", "強盛新", "如興", "宏和", "業旺", "聚隆", "台富", 
        "冠星-KY", "大統新創", "嘉裕", "宏益", "宜新實業", "偉全", "昶和", "南染", "弘裕", "宏洲", 
        "南緯", "大宇", "東華"
    ],
    "貿易": [
        "大聯大", "文曄", "聯強", "至上", "增你強", "威健", "益登", "豐藝", "全科", "擎亞", 
        "崇越", "華立", "長華*", "統一超", "三商", "遠百", "潤泰全", "特力", "寶雅", "富邦媒", 
        "農林", "統領", "高林", "三商家購", "欣欣", "日成-KY", "台南-KY", "金麗-KY", "永邑-KY", "大洋-KY", 
        "阿瘦", "淘帝-KY", "凱羿-KY"
    ],
    "電器": [
        "大同", "東元", "聲寶", "禾聯碩", "瑞智", "三洋實業", "華新", "億光", "光寶科", "台達電", 
        "大亞", "華榮", "大東電", "宏泰", "大山", "三洋電", "合機", "華電", "榮星", "中電", 
        "億泰", "艾美特-KY", "燦星網"
    ],
    "水泥": [
        "台泥", "亞泥", "環泥", "幸福", "信大", "嘉泥", "國產", "根基", "東泥"
    ],
    "電子通路": [
        "大聯大", "文曄", "聯強", "至上", "增你強", "威健", "益登", "豐藝", "全科", "擎亞", 
        "崇越", "華立", "長華*", "茂綸", "光菱", "尚立", "安馳", "富世達", "蔚華科", "弘億股", 
        "精技", "全國電", "展碁國際", "立萬利", "陞泰", "燦坤"
    ],
    "運動休閒": [
        "寶成", "豐泰", "志強-KY", "鈺齊-KY", "來億-KY", "百和", "百和興業-KY", "美利達", "巨大", "桂盟", 
        "拓凱", "岱宇", "明安", "復盛應用", "喬山", "柏文", "東哥遊艇", "中傑-KY", "世界健身-KY", "波力-KY", 
        "大魯閣"
    ],
    "綠能環保": [
        "可寧衛*", "崑鼎", "國統", "山林水", "森崴能源", "泓德能源", "雲豹能源", "元晶", "聯合再生", "茂迪", 
        "上緯投控", "佳龍", "光洋科", "金益鼎", "欣厚-KY", "聯友金屬-創", "兆聯實業", "世紀能源", "東方風能", "中聯資源", 
        "鋼聯", "華懋", "日友", "溢泰實業", "台鎔科技", "中台", "熙特爾-創", "昶昕", "青新-創", "台境*", 
        "寶綠特-KY", "聚恆-創", "成信實業*-創", "富威電力", "平和環保-創", "基士德-KY"
    ],
    "橡膠": [
        "台橡", "南帝", "正新", "建大", "泰豐", "華豐", "六暉-KY", "南港", "申豐", "厚生", 
        "國際中橡", "鑫永銓"
    ],
    "玻璃": [
        "台玻", "冠軍", "和成", "凱撒衛", "宏洲", "中釉"
    ],
    "觀光": [
        "晶華", "雲品", "寒舍", "老爺知", "夏都", "富野", "國賓", "六福", "鳳凰", "山富", 
        "雄獅", "五福", "易飛網", "燦星旅", "易華電", "王品", "美食-KY", "八方雲集", "好樂迪", "第一店", 
        "萬企", "享溫馨", "華園", "遠雄來", "三商餐飲", "新天地"
    ],
    "居家生活": [
        "特力", "寶雅", "櫻花", "和成", "成霖", "橋椿", "億豐", "愛山林", "泰茂", "全域", 
        "居易", "詩肯", "信義", "地心引力", "福興", "商億-KY", "慶豐富", "匯僑設計", "嘉威", "峰源-KY", 
        "三能-KY"
    ],
    "數位雲端": [
        "零壹", "邁達特", "伊雲谷", "是方", "網家", "數字", "91APP*-KY", "創業家", "宏碁資訊", "三商電", 
        "華電網", "精誠", "凌群", "系微", "勤崴國際", "富邦媒", "LINEPAY", "中華資安", "一零四", "GOGOLOOK", 
        "浪凡", "資拓宏宇", "現觀科", "微程式", "奧義賽博-KY創", "愛爾達-創", "永悅健康-創"
    ],
    "資訊服務": [
        "精誠", "敦陽科", "資通", "零壹", "邁達特", "凌群", "華經", "訊連", "網龍", "橘子", 
        "智冠", "宇峻", "鈊象", "傳奇", "昱泉", "辣椒", "關貿", "三商電"
    ],
    "造紙": [
        "永豐餘", "正隆", "榮成", "華紙", "寶隆", "士紙", "永豐實"
    ],
    "其他": [
        "中保科", "新保", "欣天然", "大台北", "欣高", "瓦城", "王品", "六角", "八方雲集", "寶雅", 
        "統一超", "全家", "遠百", "三商", "特力", "信義", "潤泰全", "億豐", "商億-KY", "志強-KY", 
        "桂盟", "中租-KY", "潤泰新", "裕融", "中鼎", "宏全", "和潤企業", "雷虎", "裕慶-KY", "統一實", 
        "和運租車", "百和", "海悅", "科定", "台數科", "茂順", "鼎基", "大華", "大豐電", "勤益控", 
        "鑽石投資", "jpp-KY", "阜爾運通", "八貫", "泰銘", "日盛台駿", "百和興業-KY", "東森", "龍邦", "必應", 
        "威宏-KY", "潤泰材", "立益物流", "康那香", "中福", "政伸", "大武山", "南六", "福貞-KY", "廣豐", 
        "遠見", "新麗", "台火", "中視", "美吉吉-KY", "卓越", "欣泰", "秋雨", "吉源-KY", "川飛"
    ]
}

NAME_TO_META = {
    "台積電": {"symbol": "2330", "market": "TSE", "mcap": 26500},
    "聯電": {"symbol": "2303", "market": "TSE", "mcap": 6200},
    "世界": {"symbol": "5347", "market": "OTC", "mcap": 1200},
    "力積電": {"symbol": "6770", "market": "TSE", "mcap": 800},
    "旺宏": {"symbol": "2337", "market": "TSE", "mcap": 600},
    "華邦電": {"symbol": "2344", "market": "TSE", "mcap": 900},
    "南亞科": {"symbol": "2408", "market": "TSE", "mcap": 1100},
    "群聯": {"symbol": "8299", "market": "OTC", "mcap": 1300},
    "創見": {"symbol": "2451", "market": "TSE", "mcap": 400},
    "威剛": {"symbol": "3260", "market": "OTC", "mcap": 500},
    "宇瞻": {"symbol": "8271", "market": "TSE", "mcap": 300},
    "晶豪科": {"symbol": "3006", "market": "TSE", "mcap": 350},
    "鈺創": {"symbol": "5351", "market": "OTC", "mcap": 250},
    "矽統": {"symbol": "2363", "market": "TSE", "mcap": 400},
    "聯詠": {"symbol": "3034", "market": "TSE", "mcap": 3100},
    "瑞昱": {"symbol": "2379", "market": "TSE", "mcap": 2400},
    "聯發科": {"symbol": "2454", "market": "TSE", "mcap": 22500},
    "矽力*-KY": {"symbol": "6415", "market": "TSE", "mcap": 1500},
    "力智": {"symbol": "6772", "market": "TSE", "mcap": 400},
    "致新": {"symbol": "8081", "market": "TSE", "mcap": 500},
    "天鈺": {"symbol": "4961", "market": "TSE", "mcap": 600},
    "矽創": {"symbol": "8016", "market": "TSE", "mcap": 500},
    "晶心科": {"symbol": "6533", "market": "TSE", "mcap": 400},
    "M31": {"symbol": "6643", "market": "TSE", "mcap": 500},
    "世芯-KY": {"symbol": "3661", "market": "TSE", "mcap": 2400},
    "創意": {"symbol": "3443", "market": "TSE", "mcap": 1850},
    "智原": {"symbol": "3035", "market": "TSE", "mcap": 1000},
    "京元電子": {"symbol": "2449", "market": "TSE", "mcap": 1600},
    "日月光投控": {"symbol": "3711", "market": "TSE", "mcap": 7300},
    "力成": {"symbol": "6239", "market": "TSE", "mcap": 1100},
    "南茂": {"symbol": "8150", "market": "TSE", "mcap": 400},
    "頎邦": {"symbol": "6147", "market": "TSE", "mcap": 500},
    "環球晶": {"symbol": "6488", "market": "OTC", "mcap": 1950},
    "合晶": {"symbol": "6182", "market": "TSE", "mcap": 400},
    "中美晶": {"symbol": "5483", "market": "OTC", "mcap": 1850},
    "穩懋": {"symbol": "3105", "market": "OTC", "mcap": 650},
    "宏捷科": {"symbol": "8086", "market": "OTC", "mcap": 400},
    "全新": {"symbol": "2455", "market": "OTC", "mcap": 500},
    "漢磊": {"symbol": "3707", "market": "OTC", "mcap": 300},
    "嘉晶": {"symbol": "3016", "market": "OTC", "mcap": 300},
    "台達電": {"symbol": "2308", "market": "TSE", "mcap": 10200},
    "國巨": {"symbol": "2327", "market": "TSE", "mcap": 3250},
    "華通": {"symbol": "2313", "market": "TSE", "mcap": 1100},
    "欣興": {"symbol": "3037", "market": "TSE", "mcap": 2450},
    "景碩": {"symbol": "3189", "market": "TSE", "mcap": 800},
    "南電": {"symbol": "8046", "market": "TSE", "mcap": 1000},
    "健鼎": {"symbol": "3044", "market": "TSE", "mcap": 1100},
    "臻鼎-KY": {"symbol": "4958", "market": "TSE", "mcap": 1200},
    "楠梓電": {"symbol": "2316", "market": "TSE", "mcap": 300},
    "敬鵬": {"symbol": "2355", "market": "TSE", "mcap": 300},
    "瀚宇博": {"symbol": "5469", "market": "TSE", "mcap": 500},
    "台燿": {"symbol": "6274", "market": "OTC", "mcap": 480},
    "金像電": {"symbol": "2368", "market": "TSE", "mcap": 1100},
    "台光電": {"symbol": "2383", "market": "TSE", "mcap": 2100},
    "聯茂": {"symbol": "6213", "market": "TSE", "mcap": 400},
    "台虹": {"symbol": "8039", "market": "TSE", "mcap": 300},
    "嘉澤": {"symbol": "3533", "market": "TSE", "mcap": 1300},
    "信錦": {"symbol": "1582", "market": "TSE", "mcap": 300},
    "川湖": {"symbol": "2059", "market": "TSE", "mcap": 2000},
    "凡甲": {"symbol": "3526", "market": "OTC", "mcap": 400},
    "貿聯-KY": {"symbol": "3665", "market": "TSE", "mcap": 1500},
    "嘉基": {"symbol": "6715", "market": "OTC", "mcap": 300},
    "良維": {"symbol": "6290", "market": "TSE", "mcap": 300},
    "建準": {"symbol": "2421", "market": "TSE", "mcap": 400},
    "奇鋐": {"symbol": "3017", "market": "TSE", "mcap": 2550},
    "雙鴻": {"symbol": "3324", "market": "OTC", "mcap": 620},
    "健策": {"symbol": "3653", "market": "TSE", "mcap": 1950},
    "勤誠": {"symbol": "8210", "market": "TSE", "mcap": 800},
    "順德": {"symbol": "2351", "market": "TSE", "mcap": 400},
    "鉅祥": {"symbol": "2476", "market": "TSE", "mcap": 400},
    "富邦金": {"symbol": "2881", "market": "TSE", "mcap": 12400},
    "國泰金": {"symbol": "2882", "market": "TSE", "mcap": 10100},
    "中信金": {"symbol": "2891", "market": "TSE", "mcap": 7500},
    "兆豐金": {"symbol": "2886", "market": "TSE", "mcap": 5800},
    "玉山金": {"symbol": "2884", "market": "TSE", "mcap": 4500},
    "元大金": {"symbol": "2885", "market": "TSE", "mcap": 4200},
    "第一金": {"symbol": "2892", "market": "TSE", "mcap": 3500},
    "華南金": {"symbol": "2880", "market": "TSE", "mcap": 3000},
    "合庫金": {"symbol": "5880", "market": "TSE", "mcap": 3200},
    "永豐金": {"symbol": "2890", "market": "TSE", "mcap": 3500},
    "台新新光金": {"symbol": "2887", "market": "TSE", "mcap": 4000},
    "凱基金": {"symbol": "2883", "market": "TSE", "mcap": 3000},
    "彰銀": {"symbol": "2801", "market": "TSE", "mcap": 2500},
    "臺企銀": {"symbol": "2834", "market": "TSE", "mcap": 1500},
    "上海商銀": {"symbol": "5876", "market": "TSE", "mcap": 2000},
    "王道銀行": {"symbol": "2897", "market": "TSE", "mcap": 300},
    "台中銀": {"symbol": "2812", "market": "TSE", "mcap": 400},
    "三商壽": {"symbol": "2867", "market": "TSE", "mcap": 300},
    "統一證": {"symbol": "2855", "market": "TSE", "mcap": 400},
    "群益證": {"symbol": "6005", "market": "TSE", "mcap": 400},
    "康和證": {"symbol": "6016", "market": "OTC", "mcap": 150},
    "宏遠證": {"symbol": "6015", "market": "TSE", "mcap": 150},
    "國票金": {"symbol": "2889", "market": "TSE", "mcap": 400},
    "廣達": {"symbol": "2382", "market": "TSE", "mcap": 11800},
    "緯創": {"symbol": "3231", "market": "TSE", "mcap": 3350},
    "英業達": {"symbol": "2356", "market": "TSE", "mcap": 1200},
    "仁寶": {"symbol": "2324", "market": "TSE", "mcap": 1000},
    "和碩": {"symbol": "4938", "market": "TSE", "mcap": 2200},
    "鴻海": {"symbol": "2317", "market": "TSE", "mcap": 29800},
    "神達": {"symbol": "3706", "market": "TSE", "mcap": 1500},
    "華碩": {"symbol": "2357", "market": "TSE", "mcap": 4300},
    "宏碁": {"symbol": "2353", "market": "TSE", "mcap": 1100},
    "技嘉": {"symbol": "2376", "market": "TSE", "mcap": 1900},
    "微星": {"symbol": "2377", "market": "TSE", "mcap": 1100},
    "艾訊": {"symbol": "3088", "market": "TSE", "mcap": 300},
    "樺漢": {"symbol": "6414", "market": "TSE", "mcap": 600},
    "融程電": {"symbol": "3416", "market": "OTC", "mcap": 300},
    "研華": {"symbol": "2395", "market": "TSE", "mcap": 3000},
    "凌華": {"symbol": "6166", "market": "TSE", "mcap": 300},
    "友通": {"symbol": "2397", "market": "TSE", "mcap": 200},
    "宸曜": {"symbol": "6922", "market": "OTC", "mcap": 200},
    "精英": {"symbol": "2331", "market": "TSE", "mcap": 300},
    "精元": {"symbol": "2387", "market": "TSE", "mcap": 300},
    "倫飛": {"symbol": "2364", "market": "TSE", "mcap": 200},
    "晟銘電": {"symbol": "3013", "market": "TSE", "mcap": 500},
    "迎廣": {"symbol": "6117", "market": "TSE", "mcap": 300},
    "振樺電": {"symbol": "8114", "market": "TSE", "mcap": 400},
    "致茂": {"symbol": "2360", "market": "TSE", "mcap": 1680},
    "光寶科": {"symbol": "2301", "market": "TSE", "mcap": 2500},
    "群光": {"symbol": "2385", "market": "TSE", "mcap": 1100},
    "佳世達": {"symbol": "2352", "market": "TSE", "mcap": 900},
    "可成": {"symbol": "2474", "market": "TSE", "mcap": 1300},
    "旭隼": {"symbol": "6409", "market": "TSE", "mcap": 1700},
    "宏正": {"symbol": "6277", "market": "TSE", "mcap": 300},
    "研揚": {"symbol": "6579", "market": "TSE", "mcap": 300},
    "盟立": {"symbol": "2464", "market": "TSE", "mcap": 300},
    "帆宣": {"symbol": "6196", "market": "TSE", "mcap": 500},
    "辛耘": {"symbol": "3583", "market": "OTC", "mcap": 1100},
    "均豪": {"symbol": "5443", "market": "TSE", "mcap": 400},
    "由田": {"symbol": "3455", "market": "OTC", "mcap": 200},
    "志聖": {"symbol": "2467", "market": "TSE", "mcap": 600},
    "德律": {"symbol": "3030", "market": "TSE", "mcap": 500},
    "迅得": {"symbol": "6438", "market": "OTC", "mcap": 400},
    "牧德": {"symbol": "3563", "market": "OTC", "mcap": 400},
    "東捷": {"symbol": "8064", "market": "TSE", "mcap": 200},
    "廣運": {"symbol": "6125", "market": "TSE", "mcap": 400},
    "雷科": {"symbol": "6207", "market": "OTC", "mcap": 200},
    "亞光": {"symbol": "3019", "market": "TSE", "mcap": 800},
    "玉晶光": {"symbol": "3406", "market": "TSE", "mcap": 580},
    "大立光": {"symbol": "3008", "market": "TSE", "mcap": 3450},
    "今國光": {"symbol": "6209", "market": "TSE", "mcap": 200},
    "中磊": {"symbol": "5388", "market": "TSE", "mcap": 1200},
    "智易": {"symbol": "3596", "market": "TSE", "mcap": 800},
    "明泰": {"symbol": "3380", "market": "TSE", "mcap": 400},
    "啟碁": {"symbol": "6285", "market": "TSE", "mcap": 680},
    "智邦": {"symbol": "2345", "market": "TSE", "mcap": 3180},
    "正文": {"symbol": "4906", "market": "TSE", "mcap": 400},
    "合勤控": {"symbol": "3704", "market": "TSE", "mcap": 500},
    "友訊": {"symbol": "2332", "market": "TSE", "mcap": 300},
    "神準": {"symbol": "3558", "market": "OTC", "mcap": 300},
    "兆赫": {"symbol": "2485", "market": "TSE", "mcap": 200},
    "仲琦": {"symbol": "2419", "market": "TSE", "mcap": 200},
    "台揚": {"symbol": "2314", "market": "TSE", "mcap": 200},
    "建漢": {"symbol": "3062", "market": "TSE", "mcap": 200},
    "台通": {"symbol": "8011", "market": "TSE", "mcap": 200},
    "波若威": {"symbol": "3163", "market": "OTC", "mcap": 300},
    "聯亞": {"symbol": "3081", "market": "OTC", "mcap": 500},
    "上詮": {"symbol": "3363", "market": "OTC", "mcap": 400},
    "眾達-KY": {"symbol": "4977", "market": "OTC", "mcap": 300},
    "光聖": {"symbol": "6442", "market": "TSE", "mcap": 350},
    "華星光": {"symbol": "4979", "market": "OTC", "mcap": 500},
    "前鼎": {"symbol": "4908", "market": "OTC", "mcap": 300},
    "聯光通": {"symbol": "4903", "market": "OTC", "mcap": 200},
    "台塑": {"symbol": "1301", "market": "TSE", "mcap": 3100},
    "南亞": {"symbol": "1303", "market": "TSE", "mcap": 3300},
    "台化": {"symbol": "1326", "market": "TSE", "mcap": 2500},
    "台塑化": {"symbol": "6505", "market": "TSE", "mcap": 3800},
    "亞聚": {"symbol": "1308", "market": "TSE", "mcap": 300},
    "台達化": {"symbol": "1309", "market": "TSE", "mcap": 300},
    "台苯": {"symbol": "1310", "market": "TSE", "mcap": 300},
    "國喬": {"symbol": "1312", "market": "TSE", "mcap": 300},
    "聯成": {"symbol": "1313", "market": "TSE", "mcap": 300},
    "華夏": {"symbol": "1305", "market": "TSE", "mcap": 210},
    "台聚": {"symbol": "1304", "market": "TSE", "mcap": 280},
    "永裕": {"symbol": "1323", "market": "TSE", "mcap": 200},
    "三芳": {"symbol": "1307", "market": "TSE", "mcap": 400},
    "地球": {"symbol": "1315", "market": "TSE", "mcap": 200},
    "友達": {"symbol": "2409", "market": "TSE", "mcap": 1350},
    "群創": {"symbol": "3481", "market": "TSE", "mcap": 1450},
    "彩晶": {"symbol": "6116", "market": "TSE", "mcap": 400},
    "元太": {"symbol": "8069", "market": "OTC", "mcap": 3100},
    "凌巨": {"symbol": "8105", "market": "TSE", "mcap": 300},
    "誠美材": {"symbol": "4960", "market": "TSE", "mcap": 250},
    "晶彩科": {"symbol": "3535", "market": "OTC", "mcap": 200},
    "達運": {"symbol": "6120", "market": "TSE", "mcap": 300},
    "瑞儀": {"symbol": "6176", "market": "TSE", "mcap": 800},
    "GIS-KY": {"symbol": "6456", "market": "TSE", "mcap": 400},
    "光洋科": {"symbol": "1785", "market": "OTC", "mcap": 500},
    "揚明光": {"symbol": "3504", "market": "TSE", "mcap": 250},
    "佳能": {"symbol": "2374", "market": "TSE", "mcap": 300},
    "先進光": {"symbol": "3362", "market": "OTC", "mcap": 400},
    "聯一光": {"symbol": "3441", "market": "OTC", "mcap": 200},
    "富晶通": {"symbol": "3623", "market": "OTC", "mcap": 200},
    "達興材料": {"symbol": "5234", "market": "TSE", "mcap": 400},
    "長榮": {"symbol": "2603", "market": "TSE", "mcap": 4600},
    "陽明": {"symbol": "2609", "market": "TSE", "mcap": 2550},
    "萬海": {"symbol": "2615", "market": "TSE", "mcap": 2400},
    "台航": {"symbol": "2617", "market": "TSE", "mcap": 400},
    "裕民": {"symbol": "2606", "market": "TSE", "mcap": 500},
    "新興": {"symbol": "2605", "market": "TSE", "mcap": 400},
    "四維航": {"symbol": "5608", "market": "TSE", "mcap": 300},
    "慧洋-KY": {"symbol": "2637", "market": "TSE", "mcap": 800},
    "正德": {"symbol": "2641", "market": "TSE", "mcap": 300},
    "志信": {"symbol": "2611", "market": "TSE", "mcap": 200},
    "台驊投控": {"symbol": "2636", "market": "TSE", "mcap": 400},
    "中菲行": {"symbol": "5609", "market": "TSE", "mcap": 300},
    "捷迅": {"symbol": "2643", "market": "TSE", "mcap": 200},
    "宅配通": {"symbol": "2642", "market": "TSE", "mcap": 200},
    "嘉里大榮": {"symbol": "2608", "market": "TSE", "mcap": 500},
    "山隆": {"symbol": "2616", "market": "TSE", "mcap": 300},
    "榮運": {"symbol": "2607", "market": "TSE", "mcap": 500},
    "中興電": {"symbol": "1513", "market": "TSE", "mcap": 880},
    "華城": {"symbol": "1519", "market": "TSE", "mcap": 1950},
    "士電": {"symbol": "1503", "market": "TSE", "mcap": 1200},
    "東元": {"symbol": "1504", "market": "TSE", "mcap": 1100},
    "大同": {"symbol": "2371", "market": "TSE", "mcap": 1200},
    "亞力": {"symbol": "1514", "market": "TSE", "mcap": 320},
    "樂事綠能": {"symbol": "1529", "market": "TSE", "mcap": 200},
    "瑞智": {"symbol": "1532", "market": "TSE", "mcap": 300},
    "恩德": {"symbol": "1528", "market": "TSE", "mcap": 200},
    "鑽全": {"symbol": "1527", "market": "TSE", "mcap": 300},
    "氣立": {"symbol": "4555", "market": "TSE", "mcap": 200},
    "上銀": {"symbol": "2049", "market": "TSE", "mcap": 820},
    "直得": {"symbol": "1597", "market": "TSE", "mcap": 300},
    "全球傳動": {"symbol": "4540", "market": "TSE", "mcap": 200},
    "鈞興-KY": {"symbol": "4571", "market": "TSE", "mcap": 300},
    "東台": {"symbol": "4526", "market": "TSE", "mcap": 200},
    "程泰": {"symbol": "1583", "market": "TSE", "mcap": 200},
    "瀧澤科": {"symbol": "6609", "market": "TSE", "mcap": 200},
    "百德": {"symbol": "4563", "market": "OTC", "mcap": 200},
    "亞德客-KY": {"symbol": "1590", "market": "TSE", "mcap": 2100},
    "高力": {"symbol": "8996", "market": "OTC", "mcap": 500},
    "新代": {"symbol": "7751", "market": "OTC", "mcap": 400},
    "大量": {"symbol": "3167", "market": "OTC", "mcap": 300},
    "台灣精銳": {"symbol": "4583", "market": "TSE", "mcap": 600},
    "大銀微系統": {"symbol": "4576", "market": "TSE", "mcap": 400},
    "豐祥-KY": {"symbol": "5288", "market": "TSE", "mcap": 300},
    "時碩工業": {"symbol": "4566", "market": "TSE", "mcap": 300},
    "伸興": {"symbol": "1558", "market": "TSE", "mcap": 300},
    "中宇": {"symbol": "1535", "market": "TSE", "mcap": 300},
    "駐龍": {"symbol": "4572", "market": "OTC", "mcap": 300},
    "勤美": {"symbol": "1532", "market": "TSE", "mcap": 400},
    "富田-創": {"symbol": "4590", "market": "OTC", "mcap": 200},
    "正道": {"symbol": "1506", "market": "TSE", "mcap": 200},
    "亞崴": {"symbol": "1530", "market": "TSE", "mcap": 200},
    "華固": {"symbol": "2548", "market": "TSE", "mcap": 350},
    "長虹": {"symbol": "5534", "market": "TSE", "mcap": 400},
    "興富發": {"symbol": "2542", "market": "TSE", "mcap": 880},
    "遠雄": {"symbol": "5522", "market": "TSE", "mcap": 480},
    "皇翔": {"symbol": "2545", "market": "TSE", "mcap": 300},
    "冠德": {"symbol": "2520", "market": "TSE", "mcap": 310},
    "潤弘": {"symbol": "2597", "market": "TSE", "mcap": 400},
    "根基": {"symbol": "2546", "market": "TSE", "mcap": 300},
    "達麗": {"symbol": "6177", "market": "TSE", "mcap": 300},
    "愛山林": {"symbol": "2540", "market": "TSE", "mcap": 400},
    "國建": {"symbol": "2501", "market": "TSE", "mcap": 500},
    "國揚": {"symbol": "2505", "market": "TSE", "mcap": 300},
    "華友聯": {"symbol": "1436", "market": "TSE", "mcap": 300},
    "京城": {"symbol": "2524", "market": "TSE", "mcap": 400},
    "欣陸": {"symbol": "3703", "market": "TSE", "mcap": 500},
    "皇普": {"symbol": "2528", "market": "TSE", "mcap": 300},
    "全坤建": {"symbol": "2509", "market": "TSE", "mcap": 200},
    "櫻花建": {"symbol": "2539", "market": "TSE", "mcap": 400},
    "工信": {"symbol": "5521", "market": "TSE", "mcap": 200},
    "鄉林": {"symbol": "5531", "market": "TSE", "mcap": 200},
    "中鋼": {"symbol": "2002", "market": "TSE", "mcap": 3450},
    "中鴻": {"symbol": "2014", "market": "TSE", "mcap": 310},
    "東和鋼鐵": {"symbol": "2006", "market": "TSE", "mcap": 600},
    "豐興": {"symbol": "2015", "market": "TSE", "mcap": 500},
    "大成鋼": {"symbol": "2027", "market": "TSE", "mcap": 850},
    "威致": {"symbol": "2028", "market": "TSE", "mcap": 300},
    "燁興": {"symbol": "2007", "market": "TSE", "mcap": 200},
    "燁輝": {"symbol": "2023", "market": "TSE", "mcap": 400},
    "第一銅": {"symbol": "2009", "market": "TSE", "mcap": 200},
    "官田鋼": {"symbol": "2017", "market": "TSE", "mcap": 200},
    "春源": {"symbol": "2010", "market": "TSE", "mcap": 300},
    "春雨": {"symbol": "2012", "market": "TSE", "mcap": 300},
    "志聯": {"symbol": "2024", "market": "TSE", "mcap": 200},
    "彰源": {"symbol": "2030", "market": "TSE", "mcap": 300},
    "允強": {"symbol": "2034", "market": "TSE", "mcap": 400},
    "千興": {"symbol": "2025", "market": "TSE", "mcap": 200},
    "聚亨": {"symbol": "2022", "market": "TSE", "mcap": 200},
    "世紀鋼": {"symbol": "9958", "market": "TSE", "mcap": 700},
    "海光": {"symbol": "2038", "market": "TSE", "mcap": 200},
    "台灣東洋": {"symbol": "4105", "market": "OTC", "mcap": 500},
    "保瑞": {"symbol": "6472", "market": "TSE", "mcap": 820},
    "藥華藥": {"symbol": "6446", "market": "OTC", "mcap": 2150},
    "中裕": {"symbol": "4147", "market": "OTC", "mcap": 300},
    "合一": {"symbol": "4743", "market": "OTC", "mcap": 620},
    "晶碩": {"symbol": "6491", "market": "TSE", "mcap": 310},
    "雃博": {"symbol": "4106", "market": "TSE", "mcap": 250},
    "泰博": {"symbol": "4736", "market": "TSE", "mcap": 400},
    "訊聯": {"symbol": "1784", "market": "OTC", "mcap": 200},
    "基亞": {"symbol": "3176", "market": "OTC", "mcap": 200},
    "智擎": {"symbol": "4162", "market": "OTC", "mcap": 400},
    "醣聯": {"symbol": "4168", "market": "OTC", "mcap": 200},
    "安特羅": {"symbol": "6564", "market": "OTC", "mcap": 200},
    "永昕": {"symbol": "4726", "market": "OTC", "mcap": 300},
    "順藥": {"symbol": "6535", "market": "OTC", "mcap": 400},
    "國光生": {"symbol": "4142", "market": "TSE", "mcap": 400},
    "晟德": {"symbol": "4123", "market": "TSE", "mcap": 500},
    "葡萄王": {"symbol": "1707", "market": "TSE", "mcap": 600},
    "東生華": {"symbol": "8432", "market": "OTC", "mcap": 200},
    "健喬": {"symbol": "4114", "market": "TSE", "mcap": 500},
    "神隆": {"symbol": "1789", "market": "TSE", "mcap": 500},
    "杏輝": {"symbol": "1734", "market": "TSE", "mcap": 300},
    "杏國": {"symbol": "4192", "market": "OTC", "mcap": 200},
    "台康生技": {"symbol": "6589", "market": "OTC", "mcap": 800},
    "浩鼎": {"symbol": "4174", "market": "OTC", "mcap": 400},
    "統一": {"symbol": "1216", "market": "TSE", "mcap": 4900},
    "味全": {"symbol": "1201", "market": "TSE", "mcap": 150},
    "大成": {"symbol": "1210", "market": "TSE", "mcap": 600},
    "卜蜂": {"symbol": "1215", "market": "TSE", "mcap": 500},
    "泰山": {"symbol": "1218", "market": "TSE", "mcap": 350},
    "福壽": {"symbol": "1219", "market": "TSE", "mcap": 200},
    "聯華": {"symbol": "1229", "market": "TSE", "mcap": 600},
    "聯華食": {"symbol": "1231", "market": "TSE", "mcap": 400},
    "佳格": {"symbol": "1227", "market": "TSE", "mcap": 500},
    "黑松": {"symbol": "1234", "market": "TSE", "mcap": 400},
    "愛之味": {"symbol": "1217", "market": "TSE", "mcap": 300},
    "宏亞": {"symbol": "1236", "market": "TSE", "mcap": 200},
    "南僑": {"symbol": "1702", "market": "TSE", "mcap": 400},
    "台榮": {"symbol": "1220", "market": "TSE", "mcap": 200},
    "天仁": {"symbol": "1233", "market": "TSE", "mcap": 200},
    "安心": {"symbol": "1259", "market": "OTC", "mcap": 200},
    "鮮活果汁-KY": {"symbol": "1256", "market": "OTC", "mcap": 200},
    "瓦城": {"symbol": "2729", "market": "OTC", "mcap": 300},
    "王品": {"symbol": "2727", "market": "TSE", "mcap": 400},
    "六角": {"symbol": "2732", "market": "OTC", "mcap": 300},
    "裕隆": {"symbol": "2201", "market": "TSE", "mcap": 800},
    "中華": {"symbol": "2204", "market": "TSE", "mcap": 1200},
    "三陽工業": {"symbol": "2206", "market": "TSE", "mcap": 1500},
    "和泰車": {"symbol": "2207", "market": "TSE", "mcap": 3800},
    "裕日車": {"symbol": "2211", "market": "TSE", "mcap": 1100},
    "東陽": {"symbol": "1319", "market": "TSE", "mcap": 900},
    "堤維西": {"symbol": "1522", "market": "TSE", "mcap": 400},
    "帝寶": {"symbol": "6605", "market": "TSE", "mcap": 500},
    "車王電": {"symbol": "1533", "market": "TSE", "mcap": 200},
    "江申": {"symbol": "1525", "market": "TSE", "mcap": 200},
    "為升": {"symbol": "2231", "market": "TSE", "mcap": 300},
    "劍麟": {"symbol": "2228", "market": "TSE", "mcap": 300},
    "麗清": {"symbol": "3346", "market": "TSE", "mcap": 200},
    "智伸科": {"symbol": "4551", "market": "TSE", "mcap": 400},
    "聯嘉投控": {"symbol": "3717", "market": "TSE", "mcap": 300},
    "瑞利": {"symbol": "1505", "market": "TSE", "mcap": 200},
    "耿鼎": {"symbol": "1524", "market": "TSE", "mcap": 200},
    "廣隆": {"symbol": "1537", "market": "TSE", "mcap": 300},
    "朋程": {"symbol": "8255", "market": "OTC", "mcap": 400},
    "鴻華先進-創": {"symbol": "2258", "market": "TSE", "mcap": 500},
    "汎德永業": {"symbol": "2247", "market": "TSE", "mcap": 600},
    "宇隆": {"symbol": "2233", "market": "TSE", "mcap": 300},
    "巧新": {"symbol": "1563", "market": "TSE", "mcap": 400},
    "百達-KY": {"symbol": "2236", "market": "TSE", "mcap": 200},
    "艾姆勒": {"symbol": "2241", "market": "OTC", "mcap": 200},
    "和大": {"symbol": "1536", "market": "TSE", "mcap": 410},
    "怡利電": {"symbol": "2497", "market": "OTC", "mcap": 300},
    "虎山": {"symbol": "7736", "market": "OTC", "mcap": 200},
    "六方科-KY": {"symbol": "4569", "market": "OTC", "mcap": 200},
    "宏旭-KY": {"symbol": "2243", "market": "TSE", "mcap": 200},
    "倉佑": {"symbol": "1568", "market": "TSE", "mcap": 200},
    "華勝-KY": {"symbol": "2248", "market": "OTC", "mcap": 200},
    "永新-KY": {"symbol": "4557", "market": "TSE", "mcap": 300},
    "IKKA-KY": {"symbol": "5102", "market": "TSE", "mcap": 200},
    "大億": {"symbol": "1521", "market": "TSE", "mcap": 200},
    "吉茂": {"symbol": "1587", "market": "TSE", "mcap": 200},
    "台肥": {"symbol": "1722", "market": "TSE", "mcap": 1200},
    "長興": {"symbol": "1717", "market": "TSE", "mcap": 360},
    "中華化": {"symbol": "1727", "market": "TSE", "mcap": 200},
    "永光": {"symbol": "1711", "market": "TSE", "mcap": 300},
    "勝一": {"symbol": "1773", "market": "TSE", "mcap": 700},
    "國精化": {"symbol": "4722", "market": "TSE", "mcap": 200},
    "三福化": {"symbol": "4755", "market": "TSE", "mcap": 400},
    "永記": {"symbol": "1726", "market": "TSE", "mcap": 400},
    "雙鍵": {"symbol": "4764", "market": "OTC", "mcap": 200},
    "材料*-KY": {"symbol": "4763", "market": "OTC", "mcap": 950},
    "南寶": {"symbol": "4766", "market": "TSE", "mcap": 600},
    "上品": {"symbol": "4770", "market": "OTC", "mcap": 800},
    "台特化": {"symbol": "4772", "market": "OTC", "mcap": 600},
    "台硝": {"symbol": "1724", "market": "TSE", "mcap": 200},
    "和桐": {"symbol": "1714", "market": "TSE", "mcap": 300},
    "旭富": {"symbol": "4119", "market": "TSE", "mcap": 300},
    "康普": {"symbol": "4739", "market": "TSE", "mcap": 400},
    "日勝化": {"symbol": "1735", "market": "TSE", "mcap": 200},
    "和益": {"symbol": "1709", "market": "TSE", "mcap": 300},
    "中碳": {"symbol": "1723", "market": "TSE", "mcap": 600},
    "中纖": {"symbol": "1718", "market": "TSE", "mcap": 300},
    "興農": {"symbol": "1712", "market": "TSE", "mcap": 500},
    "東聯": {"symbol": "1710", "market": "TSE", "mcap": 400},
    "東鹼": {"symbol": "1708", "market": "TSE", "mcap": 300},
    "國化": {"symbol": "1713", "market": "TSE", "mcap": 200},
    "元禎": {"symbol": "1725", "market": "TSE", "mcap": 200},
    "國慶科技": {"symbol": "1721", "market": "TSE", "mcap": 300},
    "德淵": {"symbol": "4720", "market": "TSE", "mcap": 200},
    "花仙子": {"symbol": "1730", "market": "TSE", "mcap": 300},
    "展宇": {"symbol": "1776", "market": "TSE", "mcap": 200},
    "毛寶": {"symbol": "1732", "market": "TSE", "mcap": 200},
    "森崴能源": {"symbol": "6806", "market": "OTC", "mcap": 380},
    "雲豹能源": {"symbol": "6869", "market": "TSE", "mcap": 350},
    "泓德能源": {"symbol": "6873", "market": "TSE", "mcap": 400},
    "富威電力": {"symbol": "6994", "market": "OTC", "mcap": 300},
    "綠電": {"symbol": "8440", "market": "OTC", "mcap": 200},
    "森寶": {"symbol": "3489", "market": "TSE", "mcap": 200},
    "天方能源": {"symbol": "3073", "market": "OTC", "mcap": 200},
    "全國": {"symbol": "9937", "market": "TSE", "mcap": 500},
    "大台北": {"symbol": "9908", "market": "TSE", "mcap": 400},
    "欣雄": {"symbol": "8908", "market": "OTC", "mcap": 300},
    "新海": {"symbol": "9926", "market": "TSE", "mcap": 300},
    "欣天然": {"symbol": "9918", "market": "TSE", "mcap": 400},
    "欣高": {"symbol": "9931", "market": "OTC", "mcap": 300},
    "儒鴻": {"symbol": "1476", "market": "TSE", "mcap": 2800},
    "聚陽": {"symbol": "1477", "market": "TSE", "mcap": 1150},
    "遠東新": {"symbol": "1402", "market": "TSE", "mcap": 1700},
    "力麗": {"symbol": "1444", "market": "TSE", "mcap": 300},
    "力鵬": {"symbol": "1447", "market": "TSE", "mcap": 300},
    "南紡": {"symbol": "1440", "market": "TSE", "mcap": 400},
    "東和": {"symbol": "1414", "market": "TSE", "mcap": 200},
    "集盛": {"symbol": "1455", "market": "TSE", "mcap": 300},
    "宏遠": {"symbol": "1460", "market": "TSE", "mcap": 300},
    "佳和": {"symbol": "1449", "market": "TSE", "mcap": 200},
    "年興": {"symbol": "1451", "market": "TSE", "mcap": 300},
    "得力": {"symbol": "1464", "market": "TSE", "mcap": 300},
    "銘旺實": {"symbol": "4432", "market": "OTC", "mcap": 200},
    "台南": {"symbol": "1473", "market": "TSE", "mcap": 300},
    "福懋": {"symbol": "1434", "market": "TSE", "mcap": 700},
    "宜進": {"symbol": "1457", "market": "TSE", "mcap": 300},
    "廣越": {"symbol": "4438", "market": "TSE", "mcap": 400},
    "利勤": {"symbol": "4426", "market": "OTC", "mcap": 200},
    "八貫": {"symbol": "1342", "market": "TSE", "mcap": 400},
    "新纖": {"symbol": "1409", "market": "TSE", "mcap": 600},
    "新紡": {"symbol": "1419", "market": "TSE", "mcap": 400},
    "振大環球": {"symbol": "4441", "market": "TSE", "mcap": 300},
    "聯發": {"symbol": "1459", "market": "TSE", "mcap": 200},
    "利華": {"symbol": "1423", "market": "TSE", "mcap": 200},
    "強盛新": {"symbol": "1463", "market": "TSE", "mcap": 200},
    "如興": {"symbol": "4414", "market": "TSE", "mcap": 200},
    "宏和": {"symbol": "1446", "market": "TSE", "mcap": 200},
    "業旺": {"symbol": "1475", "market": "TSE", "mcap": 200},
    "聚隆": {"symbol": "1466", "market": "TSE", "mcap": 200},
    "台富": {"symbol": "1454", "market": "TSE", "mcap": 200},
    "冠星-KY": {"symbol": "4439", "market": "TSE", "mcap": 300},
    "大統新創": {"symbol": "1470", "market": "TSE", "mcap": 200},
    "嘉裕": {"symbol": "1417", "market": "TSE", "mcap": 200},
    "宏益": {"symbol": "1452", "market": "TSE", "mcap": 200},
    "宜新實業": {"symbol": "4440", "market": "OTC", "mcap": 200},
    "偉全": {"symbol": "1465", "market": "TSE", "mcap": 200},
    "昶和": {"symbol": "1468", "market": "TSE", "mcap": 200},
    "南染": {"symbol": "1410", "market": "TSE", "mcap": 200},
    "弘裕": {"symbol": "1474", "market": "TSE", "mcap": 200},
    "宏洲": {"symbol": "1413", "market": "TSE", "mcap": 200},
    "南緯": {"symbol": "1467", "market": "TSE", "mcap": 200},
    "大宇": {"symbol": "1445", "market": "TSE", "mcap": 200},
    "東華": {"symbol": "1418", "market": "TSE", "mcap": 200},
    "大聯大": {"symbol": "3702", "market": "TSE", "mcap": 1600},
    "文曄": {"symbol": "3036", "market": "TSE", "mcap": 1200},
    "聯強": {"symbol": "2347", "market": "TSE", "mcap": 1800},
    "至上": {"symbol": "8112", "market": "TSE", "mcap": 1000},
    "增你強": {"symbol": "3028", "market": "TSE", "mcap": 400},
    "威健": {"symbol": "3033", "market": "TSE", "mcap": 300},
    "益登": {"symbol": "3048", "market": "TSE", "mcap": 300},
    "豐藝": {"symbol": "6189", "market": "TSE", "mcap": 400},
    "全科": {"symbol": "3209", "market": "TSE", "mcap": 300},
    "擎亞": {"symbol": "8096", "market": "OTC", "mcap": 200},
    "崇越": {"symbol": "5434", "market": "OTC", "mcap": 1400},
    "華立": {"symbol": "3010", "market": "TSE", "mcap": 600},
    "長華*": {"symbol": "8070", "market": "OTC", "mcap": 450},
    "統一超": {"symbol": "2912", "market": "TSE", "mcap": 3050},
    "三商": {"symbol": "2905", "market": "TSE", "mcap": 400},
    "遠百": {"symbol": "2903", "market": "TSE", "mcap": 600},
    "潤泰全": {"symbol": "2915", "market": "TSE", "mcap": 800},
    "特力": {"symbol": "2908", "market": "TSE", "mcap": 300},
    "寶雅": {"symbol": "5904", "market": "TSE", "mcap": 1800},
    "富邦媒": {"symbol": "8454", "market": "TSE", "mcap": 1100},
    "農林": {"symbol": "2913", "market": "TSE", "mcap": 400},
    "統領": {"symbol": "2910", "market": "TSE", "mcap": 200},
    "高林": {"symbol": "2906", "market": "TSE", "mcap": 200},
    "三商家購": {"symbol": "2945", "market": "OTC", "mcap": 200},
    "欣欣": {"symbol": "2901", "market": "TSE", "mcap": 200},
    "日成-KY": {"symbol": "4807", "market": "OTC", "mcap": 200},
    "台南-KY": {"symbol": "5906", "market": "OTC", "mcap": 200},
    "金麗-KY": {"symbol": "8429", "market": "TSE", "mcap": 200},
    "永邑-KY": {"symbol": "2939", "market": "TSE", "mcap": 200},
    "大洋-KY": {"symbol": "5907", "market": "TSE", "mcap": 200},
    "阿瘦": {"symbol": "8443", "market": "TSE", "mcap": 200},
    "淘帝-KY": {"symbol": "2929", "market": "TSE", "mcap": 200},
    "凱羿-KY": {"symbol": "2936", "market": "TSE", "mcap": 200},
    "大同": {"symbol": "2371", "market": "TSE", "mcap": 1200},
    "聲寶": {"symbol": "1604", "market": "TSE", "mcap": 400},
    "禾聯碩": {"symbol": "5283", "market": "OTC", "mcap": 300},
    "華新": {"symbol": "1605", "market": "TSE", "mcap": 1350},
    "億光": {"symbol": "2393", "market": "TSE", "mcap": 1000},
    "大亞": {"symbol": "1609", "market": "TSE", "mcap": 350},
    "華榮": {"symbol": "1608", "market": "TSE", "mcap": 300},
    "大東電": {"symbol": "1623", "market": "OTC", "mcap": 300},
    "宏泰": {"symbol": "1612", "market": "TSE", "mcap": 300},
    "大山": {"symbol": "1615", "market": "TSE", "mcap": 300},
    "三洋電": {"symbol": "1614", "market": "TSE", "mcap": 300},
    "合機": {"symbol": "1618", "market": "TSE", "mcap": 300},
    "華電": {"symbol": "1603", "market": "TSE", "mcap": 200},
    "榮星": {"symbol": "1617", "market": "TSE", "mcap": 200},
    "中電": {"symbol": "1611", "market": "TSE", "mcap": 200},
    "億泰": {"symbol": "1616", "market": "TSE", "mcap": 200},
    "艾美特-KY": {"symbol": "1626", "market": "KY", "mcap": 200},
    "燦星網": {"symbol": "4930", "market": "OTC", "mcap": 200},
    "台泥": {"symbol": "1101", "market": "TSE", "mcap": 2450},
    "亞泥": {"symbol": "1102", "market": "TSE", "mcap": 1400},
    "環泥": {"symbol": "1104", "market": "TSE", "mcap": 400},
    "幸福": {"symbol": "1108", "market": "TSE", "mcap": 300},
    "信大": {"symbol": "1109", "market": "TSE", "mcap": 300},
    "嘉泥": {"symbol": "1103", "market": "TSE", "mcap": 400},
    "國產": {"symbol": "2504", "market": "TSE", "mcap": 580},
    "東泥": {"symbol": "1110", "market": "TSE", "mcap": 200},
    "茂綸": {"symbol": "6227", "market": "OTC", "mcap": 200},
    "光菱": {"symbol": "8032", "market": "OTC", "mcap": 200},
    "尚立": {"symbol": "3360", "market": "TSE", "mcap": 200},
    "安馳": {"symbol": "3528", "market": "OTC", "mcap": 200},
    "富世達": {"symbol": "6805", "market": "TSE", "mcap": 1200},
    "蔚華科": {"symbol": "3055", "market": "TSE", "mcap": 300},
    "弘億股": {"symbol": "3312", "market": "OTC", "mcap": 200},
    "精技": {"symbol": "2414", "market": "TSE", "mcap": 300},
    "全國電": {"symbol": "6281", "market": "TSE", "mcap": 400},
    "展碁國際": {"symbol": "6776", "market": "OTC", "mcap": 300},
    "立萬利": {"symbol": "3054", "market": "OTC", "mcap": 200},
    "陞泰": {"symbol": "8072", "market": "OTC", "mcap": 200},
    "燦坤": {"symbol": "2430", "market": "TSE", "mcap": 300},
    "寶成": {"symbol": "9904", "market": "TSE", "mcap": 1000},
    "豐泰": {"symbol": "9910", "market": "TSE", "mcap": 1300},
    "志強-KY": {"symbol": "6768", "market": "TSE", "mcap": 500},
    "鈺齊-KY": {"symbol": "9802", "market": "TSE", "mcap": 400},
    "來億-KY": {"symbol": "6890", "market": "TSE", "mcap": 800},
    "百和": {"symbol": "9938", "market": "TSE", "mcap": 210},
    "百和興業-KY": {"symbol": "8404", "market": "TSE", "mcap": 200},
    "美利達": {"symbol": "9914", "market": "TSE", "mcap": 620},
    "巨大": {"symbol": "9921", "market": "TSE", "mcap": 750},
    "桂盟": {"symbol": "5306", "market": "OTC", "mcap": 400},
    "拓凱": {"symbol": "4536", "market": "TSE", "mcap": 400},
    "岱宇": {"symbol": "1598", "market": "TSE", "mcap": 200},
    "明安": {"symbol": "8938", "market": "OTC", "mcap": 300},
    "復盛應用": {"symbol": "6670", "market": "TSE", "mcap": 800},
    "喬山": {"symbol": "1736", "market": "TSE", "mcap": 600},
    "柏文": {"symbol": "8462", "market": "TSE", "mcap": 300},
    "東哥遊艇": {"symbol": "8478", "market": "TSE", "mcap": 800},
    "中傑-KY": {"symbol": "6965", "market": "TSE", "mcap": 400},
    "世界健身-KY": {"symbol": "2762", "market": "TSE", "mcap": 300},
    "波力-KY": {"symbol": "8467", "market": "TSE", "mcap": 300},
    "大魯閣": {"symbol": "1432", "market": "TSE", "mcap": 200},
    "可寧衛*": {"symbol": "8422", "market": "TSE", "mcap": 500},
    "崑鼎": {"symbol": "6803", "market": "TSE", "mcap": 600},
    "國統": {"symbol": "8936", "market": "OTC", "mcap": 400},
    "山林水": {"symbol": "8473", "market": "TSE", "mcap": 300},
    "上緯投控": {"symbol": "3708", "market": "TSE", "mcap": 400},
    "佳龍": {"symbol": "9955", "market": "TSE", "mcap": 200},
    "金益鼎": {"symbol": "8390", "market": "OTC", "mcap": 200},
    "欣厚-KY": {"symbol": "4924", "market": "OTC", "mcap": 200},
    "聯友金屬-創": {"symbol": "6961", "market": "OTC", "mcap": 200},
    "兆聯實業": {"symbol": "6944", "market": "OTC", "mcap": 400},
    "世紀能源": {"symbol": "7703", "market": "OTC", "mcap": 300},
    "東方風能": {"symbol": "7786", "market": "OTC", "mcap": 300},
    "中聯資源": {"symbol": "9930", "market": "TSE", "mcap": 400},
    "鋼聯": {"symbol": "6581", "market": "TSE", "mcap": 300},
    "華懋": {"symbol": "5290", "market": "OTC", "mcap": 200},
    "日友": {"symbol": "8341", "market": "TSE", "mcap": 400},
    "溢泰實業": {"symbol": "6956", "market": "OTC", "mcap": 200},
    "台鎔科技": {"symbol": "6947", "market": "OTC", "mcap": 200},
    "中台": {"symbol": "6923", "market": "OTC", "mcap": 200},
    "熙特爾-創": {"symbol": "7740", "market": "OTC", "mcap": 200},
    "昶昕": {"symbol": "8438", "market": "OTC", "mcap": 200},
    "青新-創": {"symbol": "6951", "market": "OTC", "mcap": 200},
    "台境*": {"symbol": "8476", "market": "OTC", "mcap": 200},
    "寶綠特-KY": {"symbol": "6887", "market": "OTC", "mcap": 200},
    "聚恆-創": {"symbol": "4582", "market": "OTC", "mcap": 200},
    "成信實業*-創": {"symbol": "6969", "market": "OTC", "mcap": 200},
    "平和環保-創": {"symbol": "6771", "market": "OTC", "mcap": 200},
    "基士德-KY": {"symbol": "6641", "market": "OTC", "mcap": 200},
    "台橡": {"symbol": "2103", "market": "TSE", "mcap": 310},
    "南帝": {"symbol": "2108", "market": "TSE", "mcap": 400},
    "正新": {"symbol": "2105", "market": "TSE", "mcap": 1350},
    "建大": {"symbol": "2106", "market": "TSE", "mcap": 600},
    "泰豐": {"symbol": "2102", "market": "TSE", "mcap": 300},
    "華豐": {"symbol": "2109", "market": "TSE", "mcap": 300},
    "六暉-KY": {"symbol": "2115", "market": "OTC", "mcap": 200},
    "南港": {"symbol": "2101", "market": "TSE", "mcap": 500},
    "申豐": {"symbol": "6582", "market": "TSE", "mcap": 300},
    "厚生": {"symbol": "2107", "market": "TSE", "mcap": 400},
    "國際中橡": {"symbol": "2104", "market": "TSE", "mcap": 400},
    "鑫永銓": {"symbol": "2114", "market": "OTC", "mcap": 300},
    "台玻": {"symbol": "1802", "market": "TSE", "mcap": 450},
    "冠軍": {"symbol": "1806", "market": "TSE", "mcap": 200},
    "和成": {"symbol": "1810", "market": "TSE", "mcap": 300},
    "凱撒衛": {"symbol": "1817", "market": "TSE", "mcap": 300},
    "中釉": {"symbol": "1809", "market": "TSE", "mcap": 200},
    "晶華": {"symbol": "2707", "market": "TSE", "mcap": 250},
    "雲品": {"symbol": "2748", "market": "OTC", "mcap": 300},
    "寒舍": {"symbol": "2739", "market": "TSE", "mcap": 300},
    "老爺知": {"symbol": "5704", "market": "OTC", "mcap": 200},
    "夏都": {"symbol": "2722", "market": "TSE", "mcap": 300},
    "富野": {"symbol": "2736", "market": "OTC", "mcap": 200},
    "國賓": {"symbol": "2704", "market": "TSE", "mcap": 500},
    "六福": {"symbol": "2705", "market": "TSE", "mcap": 300},
    "鳳凰": {"symbol": "5706", "market": "TSE", "mcap": 300},
    "山富": {"symbol": "2743", "market": "OTC", "mcap": 300},
    "雄獅": {"symbol": "2731", "market": "TSE", "mcap": 500},
    "五福": {"symbol": "2745", "market": "OTC", "mcap": 300},
    "易飛網": {"symbol": "2734", "market": "OTC", "mcap": 200},
    "燦星旅": {"symbol": "2719", "market": "OTC", "mcap": 200},
    "易華電": {"symbol": "6552", "market": "TSE", "mcap": 300},
    "美食-KY": {"symbol": "2723", "market": "TSE", "mcap": 180},
    "八方雲集": {"symbol": "2753", "market": "TSE", "mcap": 300},
    "好樂迪": {"symbol": "9943", "market": "TSE", "mcap": 400},
    "第一店": {"symbol": "2706", "market": "TSE", "mcap": 300},
    "萬企": {"symbol": "2701", "market": "TSE", "mcap": 300},
    "享溫馨": {"symbol": "7731", "market": "OTC", "mcap": 200},
    "華園": {"symbol": "2702", "market": "TSE", "mcap": 200},
    "遠雄來": {"symbol": "2712", "market": "TSE", "mcap": 200},
    "三商餐飲": {"symbol": "7705", "market": "TSE", "mcap": 300},
    "新天地": {"symbol": "8940", "market": "OTC", "mcap": 200},
    "櫻花": {"symbol": "9939", "market": "TSE", "mcap": 500},
    "成霖": {"symbol": "9934", "market": "TSE", "mcap": 300},
    "橋椿": {"symbol": "2062", "market": "TSE", "mcap": 300},
    "億豐": {"symbol": "8464", "market": "TSE", "mcap": 1500},
    "泰茂": {"symbol": "2230", "market": "OTC", "mcap": 200},
    "全域": {"symbol": "3067", "market": "OTC", "mcap": 200},
    "居易": {"symbol": "6216", "market": "OTC", "mcap": 200},
    "詩肯": {"symbol": "9905", "market": "OTC", "mcap": 200},
    "信義": {"symbol": "9940", "market": "TSE", "mcap": 800},
    "地心引力": {"symbol": "3624", "market": "OTC", "mcap": 200},
    "福興": {"symbol": "9924", "market": "TSE", "mcap": 400},
    "商億-KY": {"symbol": "8482", "market": "TSE", "mcap": 400},
    "慶豐富": {"symbol": "9935", "market": "TSE", "mcap": 300},
    "匯僑設計": {"symbol": "6754", "market": "OTC", "mcap": 200},
    "嘉威": {"symbol": "8394", "market": "OTC", "mcap": 300},
    "峰源-KY": {"symbol": "6807", "market": "TSE", "mcap": 300},
    "三能-KY": {"symbol": "6671", "market": "OTC", "mcap": 200},
    "零壹": {"symbol": "3029", "market": "OTC", "mcap": 500},
    "邁達特": {"symbol": "6112", "market": "TSE", "mcap": 400},
    "伊雲谷": {"symbol": "6689", "market": "TSE", "mcap": 300},
    "是方": {"symbol": "6561", "market": "TSE", "mcap": 800},
    "網家": {"symbol": "8044", "market": "TSE", "mcap": 300},
    "數字": {"symbol": "5287", "market": "OTC", "mcap": 600},
    "91APP*-KY": {"symbol": "6741", "market": "OTC", "mcap": 500},
    "創業家": {"symbol": "8477", "market": "OTC", "mcap": 200},
    "宏碁資訊": {"symbol": "6811", "market": "TSE", "mcap": 800},
    "三商電": {"symbol": "2427", "market": "TSE", "mcap": 300},
    "華電網": {"symbol": "6163", "market": "TSE", "mcap": 300},
    "精誠": {"symbol": "6214", "market": "TSE", "mcap": 1200},
    "凌群": {"symbol": "2453", "market": "TSE", "mcap": 400},
    "系微": {"symbol": "6231", "market": "OTC", "mcap": 500},
    "勤崴國際": {"symbol": "6516", "market": "OTC", "mcap": 300},
    "富邦媒": {"symbol": "8454", "market": "TSE", "mcap": 1100},
    "LINEPAY": {"symbol": "7722", "market": "OTC", "mcap": 1500},
    "中華資安": {"symbol": "7765", "market": "OTC", "mcap": 800},
    "一零四": {"symbol": "3130", "market": "TSE", "mcap": 600},
    "GOGOLOOK": {"symbol": "6902", "market": "OTC", "mcap": 400},
    "浪凡": {"symbol": "6165", "market": "OTC", "mcap": 300},
    "資拓宏宇": {"symbol": "6614", "market": "OTC", "mcap": 300},
    "現觀科": {"symbol": "6906", "market": "OTC", "mcap": 300},
    "微程式": {"symbol": "7721", "market": "OTC", "mcap": 300},
    "奧義賽博-KY創": {"symbol": "7823", "market": "OTC", "mcap": 200},
    "愛爾達-創": {"symbol": "8487", "market": "OTC", "mcap": 300},
    "永悅健康-創": {"symbol": "7835", "market": "OTC", "mcap": 200},
    "敦陽科": {"symbol": "2480", "market": "TSE", "mcap": 800},
    "資通": {"symbol": "2471", "market": "TSE", "mcap": 300},
    "華經": {"symbol": "2468", "market": "TSE", "mcap": 300},
    "訊連": {"symbol": "5203", "market": "OTC", "mcap": 600},
    "網龍": {"symbol": "3083", "market": "OTC", "mcap": 200},
    "橘子": {"symbol": "6180", "market": "TSE", "mcap": 600},
    "智冠": {"symbol": "5478", "market": "OTC", "mcap": 800},
    "宇峻": {"symbol": "3546", "market": "OTC", "mcap": 300},
    "鈊象": {"symbol": "3293", "market": "OTC", "mcap": 3500},
    "傳奇": {"symbol": "4994", "market": "OTC", "mcap": 300},
    "昱泉": {"symbol": "6169", "market": "OTC", "mcap": 200},
    "辣椒": {"symbol": "4946", "market": "OTC", "mcap": 200},
    "關貿": {"symbol": "6183", "market": "TSE", "mcap": 800},
    "永豐餘": {"symbol": "1907", "market": "TSE", "mcap": 900},
    "正隆": {"symbol": "1904", "market": "TSE", "mcap": 600},
    "榮成": {"symbol": "1909", "market": "TSE", "mcap": 500},
    "華紙": {"symbol": "1905", "market": "TSE", "mcap": 400},
    "寶隆": {"symbol": "1906", "market": "TSE", "mcap": 200},
    "士紙": {"symbol": "1903", "market": "TSE", "mcap": 300},
    "永豐實": {"symbol": "6790", "market": "TSE", "mcap": 800},
    "中保科": {"symbol": "9917", "market": "TSE", "mcap": 2000},
    "新保": {"symbol": "9925", "market": "TSE", "mcap": 1000},
    "大台北": {"symbol": "9908", "market": "TSE", "mcap": 400},
    "欣高": {"symbol": "9931", "market": "OTC", "mcap": 300},
    "中租-KY": {"symbol": "5871", "market": "TSE", "mcap": 3500},
    "潤泰新": {"symbol": "9945", "market": "TSE", "mcap": 1800},
    "裕融": {"symbol": "9941", "market": "TSE", "mcap": 1100},
    "中鼎": {"symbol": "9933", "market": "TSE", "mcap": 1200},
    "宏全": {"symbol": "9939", "market": "TSE", "mcap": 800},
    "和潤企業": {"symbol": "6592", "market": "TSE", "mcap": 1000},
    "雷虎": {"symbol": "8033", "market": "OTC", "mcap": 400},
    "裕慶-KY": {"symbol": "6957", "market": "TSE", "mcap": 400},
    "統一實": {"symbol": "9907", "market": "TSE", "mcap": 600},
    "和運租車": {"symbol": "7855", "market": "OTC", "mcap": 300},
    "海悅": {"symbol": "2348", "market": "TSE", "mcap": 500},
    "科定": {"symbol": "6655", "market": "OTC", "mcap": 300},
    "台數科": {"symbol": "6464", "market": "TSE", "mcap": 500},
    "茂順": {"symbol": "9942", "market": "TSE", "mcap": 300},
    "鼎基": {"symbol": "6585", "market": "TSE", "mcap": 500},
    "大華": {"symbol": "9905", "market": "TSE", "mcap": 400},
    "大豐電": {"symbol": "6184", "market": "OTC", "mcap": 300},
    "勤益控": {"symbol": "1437", "market": "TSE", "mcap": 300},
    "鑽石投資": {"symbol": "6901", "market": "TSE", "mcap": 800},
    "jpp-KY": {"symbol": "5284", "market": "OTC", "mcap": 400},
    "阜爾運通": {"symbol": "6914", "market": "TSE", "mcap": 400},
    "泰銘": {"symbol": "9927", "market": "TSE", "mcap": 500},
    "日盛台駿": {"symbol": "6958", "market": "TSE", "mcap": 600},
    "東森": {"symbol": "2614", "market": "TSE", "mcap": 400},
    "龍邦": {"symbol": "2514", "market": "TSE", "mcap": 600},
    "必應": {"symbol": "6625", "market": "OTC", "mcap": 200},
    "威宏-KY": {"symbol": "8442", "market": "TSE", "mcap": 300},
    "潤泰材": {"symbol": "8463", "market": "TSE", "mcap": 300},
    "立益物流": {"symbol": "1443", "market": "TSE", "mcap": 200},
    "康那香": {"symbol": "9919", "market": "TSE", "mcap": 300},
    "中福": {"symbol": "1435", "market": "TSE", "mcap": 200},
    "政伸": {"symbol": "8481", "market": "OTC", "mcap": 200},
    "大武山": {"symbol": "6952", "market": "OTC", "mcap": 200},
    "南六": {"symbol": "6504", "market": "TSE", "mcap": 400},
    "福貞-KY": {"symbol": "8411", "market": "TSE", "mcap": 300},
    "廣豐": {"symbol": "1416", "market": "TSE", "mcap": 300},
    "遠見": {"symbol": "3040", "market": "OTC", "mcap": 200},
    "新麗": {"symbol": "9944", "market": "TSE", "mcap": 200},
    "台火": {"symbol": "9902", "market": "TSE", "mcap": 200},
    "中視": {"symbol": "9928", "market": "TSE", "mcap": 200},
    "美吉吉-KY": {"symbol": "8466", "market": "OTC", "mcap": 200},
    "卓越": {"symbol": "2496", "market": "OTC", "mcap": 200},
    "欣泰": {"symbol": "8917", "market": "OTC", "mcap": 300},
    "秋雨": {"symbol": "9929", "market": "TSE", "mcap": 200},
    "吉源-KY": {"symbol": "8488", "market": "OTC", "mcap": 200},
    "川飛": {"symbol": "1516", "market": "TSE", "mcap": 200}
}

SECTOR_STOCKS = []
for sector_name, names in RAW_SECTOR_DICT.items():
    for name in names:
        meta = NAME_TO_META.get(name, {"symbol": "2330", "market": "TSE", "mcap": 300})
        SECTOR_STOCKS.append({
            "symbol": meta["symbol"],
            "name": name,
            "sector": sector_name,
            "market": meta["market"],
            "mcap": meta["mcap"]
        })

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
