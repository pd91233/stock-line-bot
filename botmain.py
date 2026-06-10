def execute_force_refresh():
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

        # 2. 資金流向排行
        try:
            class_res = requests.get("https://tw.stock.yahoo.com/class", headers=headers, timeout=8)
            if class_res.status_code == 200:
                soup = BeautifulSoup(class_res.text, 'html.parser')
                target_industries = ["半導體", "電腦週邊", "電子零組件", "通信網路", "光電業", "生技醫療", "金融保險", "鋼鐵工業", "航運業", "建材營造"]
                leaderboard = {}
                for ind in target_industries:
                    ind_element = soup.find(text=re.compile(ind))
                    if ind_element:
                        pct_match = re.search(r'([+-]?\d+\.\d+)%', ind_element.find_parent().get_text())
                        if pct_match: leaderboard[ind] = float(pct_match.group(1))
                if leaderboard:
                    top = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[0]
                    true_market_top_ind, true_market_top_chg = top[0], top[1]
        except: pass

        # 3. 戰報對齊與快取寫入
        json_url = f"https://filedn.com/lMJ0lWu9PSUV5Vv6Ks3W6bJ/money/monitor_list.json?v={time.time()}"
        res_json = requests.get(json_url, headers=headers, timeout=10)
        
        if res_json.status_code == 200:
            raw_data = res_json.json()
            if isinstance(raw_data, list):
                # 這裡重新組裝 ai_payload 確保資料完整
                ai_payload = [{"name": item.get("商品", item.get("代碼")), "code": item.get("代碼"), "z": 0.0, "chg": 0.0} for item in raw_data if "代碼" in item]
            
            # 準備顯示文字
            flow_text = f"🔥 資金主攻：【{true_market_top_ind}】({true_market_top_chg}%)"
            news_headline = fetch_cnyes_news()
            
            # 安全寫入快取，確保 ai_payload 有值
            display_stocks = " ｜ ".join([f"{s['name']}({s['code']})" for s in ai_payload]) if ai_payload else "📡 監控中..."
            
            update_cache({
                "fundsText": f"📊 加權指數 {round(twii_chg, 2)}% ｜ {flow_text} ｜ {news_headline}",
                "stocksText": display_stocks
            })
            print("✅ [戰術回報] 變數防護版寫入成功！")
            
    except Exception as e:
        print(f"❌ 致命錯誤: {e}")
