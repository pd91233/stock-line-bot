for key, symbol in tickers.items():
        try:
            # 💥 修改點一：加上 includePrePost=true 解鎖盤前與夜盤真實報價
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d&includePrePost=true"
            res = requests.get(url, headers=headers, timeout=5).json()
            
            result_node = res['chart']['result'][0]
            meta = result_node['meta']
            
            # 💥 修改點二：直接抓取盤前/夜盤價 (postMarketPrice)，若無才用常規收盤價
            curr_p = meta.get('postMarketPrice', meta.get('regularMarketPrice', 0))
            prev_p = meta.get('chartPreviousClose', 0)

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

    # 💥 修改點三：強制將 Render 的 UTC 時間加上 8 小時，轉換為精準的台灣時間
    now_tw = datetime.datetime.utcnow() + datetime.timedelta(hours=8)

    # 將市場數據、時間戳記與戰報標籤完整打包
    payload = {
        "timestamp": now_tw.strftime("%Y-%m-%d %H:%M:%S"),
        "quotes": matrix_results,
        "monitor_tags": monitor_tags_map
    }
