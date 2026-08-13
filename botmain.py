def continuous_radar_loop():
    print("📡 [當沖雷達] 啟動終極 V8 穿甲通道 (純種股票過濾版)，全面突破封鎖...", flush=True)
    import time, datetime, requests
    
    error_count = 0 
    
    while True:
        try:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
            is_weekend = now.weekday() >= 5
            current_time_num = now.hour * 100 + now.minute
            
            # 🔒 09:00 到 13:30 之間雷達才運作
            if not is_weekend and (900 <= current_time_num <= 1330):
                # 換上最高級的瀏覽器偽裝
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
                
                current_cache = read_cache()
                full_stocks = current_cache.get("fundamental_full", [])
                
                if not full_stocks:
                    time.sleep(10)
                    continue

                # 💥 戰術微調：縮小批次為 20 檔，避免 URL 過長遭 Yahoo 攔截
                batch_size = 20
                for i in range(0, len(full_stocks), batch_size):
                    batch = full_stocks[i:i+batch_size]
                    
                    ex_ch_list = []
                    stock_meta = {}
                    for s in batch:
                        code = str(s.get('code', '')).strip()
                        market = s.get('market', '上市')
                        suffix = ".TW" if market == "上市" else ".TWO"
                        
                        # 💥 終極防護：嚴格限定只有「4位數」的正規股票與 ETF 才能進入雷達！
                        # 徹底封殺會導致 Yahoo 報 400 錯誤的 6 位數權證與怪異代碼！
                        if code and len(code) == 4:
                            ex_ch_list.append(f"{code}{suffix}")
                            stock_meta[code] = s
                            
                    if not ex_ch_list: continue
                    
                    symbols = ",".join(ex_ch_list)
                    
                    # 💥 拔除會造成 400 錯誤的 range 與 interval 參數，讓 Yahoo 自由輸出盤中即時報價！
                    api_url = f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={symbols}"
                    
                    try:
                        res = requests.get(api_url, headers=headers, timeout=5)
                        if res.status_code == 200:
                            res_json = res.json()
                            if 'spark' in res_json and 'result' in res_json['spark'] and res_json['spark']['result']:
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
                                        'o': meta.get('regularMarketPrice', '-'), 
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
                                print(f"⚠️ [V8通道異常] 狀態碼: {res.status_code} | URL長度: {len(api_url)}", flush=True)
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
