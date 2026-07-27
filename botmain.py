<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta id="viewport-meta" name="viewport" content="width=1400">
    <title>股海觀浪 - 戰情大廳模擬測試</title>
    <link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@400;700&family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
    <style>
        /* 沿用統帥原有的基礎配色與字體 */
        :root {
            --bg-color: #05070a; --panel-bg: #0f172a; --border-color: #1e293b;
            --text-main: #f8fafc; --text-dim: #94a3b8; --gold: #fbbf24;
            --red: #f43f5e; --green: #10b981; --blue: #3b82f6; 
        }
        body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Urbanist', 'Noto Sans TC', sans-serif; margin: 0; padding: 20px; }
        
        /* 模擬原有的戰情室背景板 */
        .mock-dashboard {
            background: linear-gradient(135deg, #1e1b4b 0%, #020617 100%);
            border: 1px solid #312e81; border-radius: 16px; padding: 40px;
            text-align: center; height: 80vh; display: flex; flex-direction: column; justify-content: center;
        }
        .mock-dashboard h1 { color: var(--gold); font-size: 40px; letter-spacing: 4px; text-shadow: 0 0 15px rgba(251,191,36,0.3); }
        .mock-dashboard p { color: var(--text-dim); font-size: 18px; }

        /* ==========================================
           💬 戰情大廳 (即時聊天室) 專屬 CSS
           ========================================== */
        /* 懸浮喚醒按鈕 (帶有呼吸燈效) */
        #chat-toggle-btn {
            position: fixed; bottom: 85px; right: 25px; /* 放置於您原本的切換手機版按鈕上方 */
            background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%);
            color: #fff; border: 2px solid var(--blue); border-radius: 30px; 
            padding: 12px 24px; font-size: 16px; font-weight: 900; cursor: pointer; 
            z-index: 99999; box-shadow: 0 5px 15px rgba(0,0,0,0.6); transition: 0.3s;
            display: flex; align-items: center; gap: 8px;
            animation: breatheChat 2s infinite ease-in-out;
        }
        #chat-toggle-btn:hover { transform: scale(1.05); box-shadow: 0 5px 25px rgba(59, 130, 246, 0.6); animation: none; border-color: var(--gold); color: var(--gold); }
        
        @keyframes breatheChat { 
            0%, 100% { box-shadow: 0 0 10px rgba(59, 130, 246, 0.4); } 
            50% { box-shadow: 0 0 25px rgba(59, 130, 246, 0.8); } 
        }

        /* 右側滑出抽屜主體 */
        #chat-sidebar {
            position: fixed; top: 0; right: -420px; /* 預設隱藏在畫面外 */
            width: 400px; height: 100vh;
            background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
            border-left: 2px solid var(--gold);
            box-shadow: -10px 0 30px rgba(0,0,0,0.8);
            z-index: 100000; transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex; flex-direction: column;
        }
        #chat-sidebar.open { right: 0; } /* 展開狀態 */

        /* 聊天室頭部 */
        .chat-header {
            background: #020617; padding: 18px 20px; border-bottom: 1px solid #334155;
            display: flex; justify-content: space-between; align-items: center;
        }
        .chat-title { color: var(--gold); font-size: 18px; font-weight: 900; letter-spacing: 1px; display: flex; align-items: center; gap: 8px;}
        .chat-close-btn { background: none; border: none; color: var(--text-dim); font-size: 26px; cursor: pointer; line-height: 1; transition: 0.2s;}
        .chat-close-btn:hover { color: var(--red); transform: scale(1.2); }

        /* 聊天室訊息區 */
        .chat-body {
            flex: 1; padding: 20px; overflow-y: auto; 
            display: flex; flex-direction: column; gap: 15px;
        }
        
        /* 一般戰友訊息氣泡 */
        .chat-msg { 
            background: #1e293b; padding: 12px 16px; border-radius: 0 12px 12px 12px; 
            font-size: 14px; line-height: 1.6; color: #cbd5e1; border-left: 4px solid var(--blue);
            align-self: flex-start; max-width: 85%;
        }
        .chat-sender { font-weight: 900; margin-bottom: 6px; color: #93c5fd; font-size: 12px; }
        
        /* 統帥/系統專屬訊息氣泡 */
        .chat-msg.admin { 
            background: rgba(251, 191, 36, 0.1); border-left: 4px solid var(--gold); 
            border-radius: 12px 12px 12px 0; align-self: flex-start;
        }
        .chat-sender.admin { color: var(--gold); font-size: 13px; }

        /* 自己發送的訊息氣泡 */
        .chat-msg.self {
            background: rgba(16, 185, 129, 0.1); border-left: none; border-right: 4px solid var(--green);
            border-radius: 12px 0 12px 12px; align-self: flex-end;
        }
        .chat-sender.self { color: #6ee7b7; text-align: right; }

        /* 聊天室底部輸入區 */
        .chat-footer {
            padding: 15px; background: #020617; border-top: 1px solid #334155; 
            display: flex; gap: 10px; align-items: center;
        }
        .chat-input {
            flex: 1; background: #0f172a; border: 1px solid #334155; color: #fff; 
            padding: 12px 15px; border-radius: 8px; outline: none; font-size: 14px;
            transition: 0.3s;
        }
        .chat-input:focus { border-color: var(--gold); box-shadow: 0 0 10px rgba(251,191,36,0.2); }
        .chat-send-btn {
            background: linear-gradient(135deg, #b45309 0%, #78350f 100%); color: #fff; 
            border: 1px solid var(--gold); padding: 0 20px; height: 42px; border-radius: 8px; 
            font-weight: 900; cursor: pointer; transition: 0.3s; white-space: nowrap;
        }
        .chat-send-btn:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(251,191,36,0.4); }

        /* 手機版自適應：全螢幕覆蓋 */
        @media (max-width: 768px) {
            #chat-sidebar { width: 100%; right: -100%; border-left: none; }
            #chat-toggle-btn { bottom: 85px; right: 15px; } /* 配合手機版按鈕位置 */
        }
    </style>
</head>
<body>

    <!-- ==========================================
         🛡️ 新增：身分驗證彈窗 (首次進入大廳時觸發)
         ========================================== -->
    <div id="callsign-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:999999; justify-content:center; align-items:center; backdrop-filter: blur(5px);">
        <div style="background:#0f172a; border:2px solid var(--gold); border-radius:12px; padding:30px; text-align:center; width:320px; box-shadow: 0 10px 40px rgba(0,0,0,0.8);">
            <h3 style="color:var(--gold); margin-top:0; font-size:22px; letter-spacing:2px;">🛡️ 指揮所門禁</h3>
            <p style="color:#94a3b8; font-size:14px; margin-bottom:20px;">進入地下戰情大廳前<br>請設定您的專屬匿名通訊代號</p>
            <input type="text" id="callsign-input" placeholder="例如：游擊兵007" style="width:100%; padding:12px; margin-bottom:20px; border-radius:6px; border:1px solid #334155; background:#020617; color:#fff; box-sizing:border-box; font-size:16px; text-align:center; outline:none;">
            <button onclick="saveCallsign()" style="background:linear-gradient(135deg, #b45309 0%, #78350f 100%); color:#fff; font-weight:900; border:1px solid var(--gold); padding:12px 20px; border-radius:6px; cursor:pointer; width:100%; font-size:16px; transition:0.3s;">確認授權，進入大廳</button>
        </div>
    </div>

    <!-- 模擬原有的主畫面 -->
    <div class="mock-dashboard">
        <h1>股海觀浪 戰情室 V84.0</h1>
        <p>（此處為您原有的 K線圖表與數據儀表板，完全不受聊天室展開影響）</p>
        <p style="margin-top:20px; color:#4ade80;">👇 請點擊右下角的「戰情大廳」按鈕測試滑出效果</p>
    </div>

    <!-- 您原本就有的切換手機按鈕 (示意用) -->
    <button style="position: fixed; bottom: 25px; right: 25px; background: #334155; color: #fff; border: 1px solid #475569; border-radius: 30px; padding: 12px 24px; font-weight: 900;">📱 切換手機版</button>

    <!-- ==========================================
         💬 新增：戰情大廳懸浮按鈕與抽屜結構
         ========================================== -->
    <button id="chat-toggle-btn" onclick="toggleChat()">💬 戰情大廳 <span style="background:#ef4444; color:#fff; border-radius:50%; padding:2px 6px; font-size:11px;">3</span></button>

    <div id="chat-sidebar">
        <div class="chat-header">
            <div class="chat-title">🟢 戰情交誼廳 <span style="font-size:12px; color:#64748b; font-weight:normal;">(線上 128 人)</span></div>
            <button class="chat-close-btn" onclick="toggleChat()">&times;</button>
        </div>
        
        <div class="chat-body" id="chat-messages">
            <!-- 系統/統帥 訊息 -->
            <div class="chat-msg admin">
                <div class="chat-sender admin">👑 統帥 (管理員)</div>
                <div>歡迎各位弟兄進入地下指揮所！本區絕對匿名，請盡情討論盤勢。遵守紀律，嚴禁洗版。</div>
            </div>
            
            <!-- 系統快訊模擬 -->
            <div class="chat-msg admin" style="border-left-color: #ef4444;">
                <div class="chat-sender admin" style="color:#fca5a5;">🚨 系統防空警報</div>
                <div>偵測到 2330 台積電 1分K 爆出 3000 張天量！請注意追高風險！</div>
            </div>

            <!-- 一般成員 訊息 -->
            <div class="chat-msg">
                <div class="chat-sender">游擊兵_007</div>
                <div>收到！剛好在高點獲利了結，感謝統帥的雷達！今天這波洗盤真狠。</div>
            </div>
            
            <div class="chat-msg">
                <div class="chat-sender">套牢的阿伯</div>
                <div>請問統帥，2605 新興現在還可以進場低接嗎？</div>
            </div>
        </div>

        <div class="chat-footer">
            <input type="text" id="chat-input-field" class="chat-input" placeholder="設定您的代號並輸入訊息..." onkeypress="handleEnter(event)">
            <button class="chat-send-btn" onclick="sendMessage()">發送</button>
        </div>
    </div>

    <!-- ==========================================
         💬 裝備升級：Socket.IO 官方通訊天線 + 記憶晶片
         ========================================== -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        let myCallsign = localStorage.getItem('chat_callsign');
        const socket = io('https://stock-line-bot-c8em.onrender.com');

        socket.on('connect', function() {
            console.log('✅ 通訊管線已接通！');
            document.querySelector('.chat-title').innerHTML = '🟢 戰情交誼廳 <span style="font-size:12px; color:#6ee7b7; font-weight:normal;">(母艦連線成功)</span>';
        });

        // 💥 新增：接收母艦空投的歷史對話紀錄
        socket.on('load_history', function(historyArray) {
            const chatBody = document.getElementById('chat-messages');
            chatBody.innerHTML = ''; // 清空大廳內預設的測試假訊息
            
            // 將歷史訊息一筆一筆畫回大廳
            historyArray.forEach(data => {
                const isMe = data.sender === myCallsign;
                const msgClass = isMe ? 'self' : '';
                const displayName = isMe ? `我 (${data.sender})` : data.sender;
                
                const newMsgHtml = `
                    <div class="chat-msg ${msgClass}">
                        <div class="chat-sender ${msgClass}">${displayName}</div>
                        <div>${data.msg}</div>
                    </div>
                `;
                chatBody.insertAdjacentHTML('beforeend', newMsgHtml);
            });
            scrollToBottom();
        });

        // 接收新廣播訊息
        socket.on('receive_message', function(data) {
            const chatBody = document.getElementById('chat-messages');
            const isMe = data.sender === myCallsign;
            const msgClass = isMe ? 'self' : '';
            const displayName = isMe ? `我 (${data.sender})` : data.sender;
            
            const newMsgHtml = `
                <div class="chat-msg ${msgClass}">
                    <div class="chat-sender ${msgClass}">${displayName}</div>
                    <div>${data.msg}</div>
                </div>
            `;
            
            chatBody.insertAdjacentHTML('beforeend', newMsgHtml);
            scrollToBottom();
        });

        function toggleChat() {
            if (!myCallsign) {
                document.getElementById('callsign-modal').style.display = 'flex';
                setTimeout(() => document.getElementById('callsign-input').focus(), 100);
                return;
            }
            const sidebar = document.getElementById('chat-sidebar');
            sidebar.classList.toggle('open');
            if(sidebar.classList.contains('open')) scrollToBottom();
        }

        function saveCallsign() {
            const input = document.getElementById('callsign-input').value.trim();
            if (input) {
                myCallsign = input;
                localStorage.setItem('chat_callsign', myCallsign);
                document.getElementById('callsign-modal').style.display = 'none';
                toggleChat();
            } else {
                alert("統帥有令：請輸入有效的通訊代號！");
            }
        }

        document.getElementById('callsign-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') saveCallsign();
        });

        function handleEnter(e) {
            if(e.key === 'Enter') sendMessage();
        }

        function sendMessage() {
            const inputField = document.getElementById('chat-input-field');
            const msgText = inputField.value.trim();
            if(!msgText || !myCallsign) return;

            socket.emit('send_message', { sender: myCallsign, msg: msgText });
            inputField.value = '';
        }

        function scrollToBottom() {
            const chatBody = document.getElementById('chat-messages');
            chatBody.scrollTop = chatBody.scrollHeight;
        }
    </script>

</body>
</html>
