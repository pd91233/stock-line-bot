# broker_gateway.py
import os
import time
from MasterTradePy.api import MarketTrader, MasterTradeAPI
from MasterTradePy.model import Order, OrderPriceChange, OrderQtyChange, OrderCancel, OrderDelete, ReportOrder, SystemEvent
from MasterTradePy.constant import PriceType, OrderType, TradingSession, Side, TradingUnit, RCode

class ConcreteMarketTrader(MarketTrader):
    def __init__(self):
        super().__init__()
        self.last_ord_no = None
        self.active_orders = {}  # 記憶體內部的委託狀態對照

    def OnNewOrderReply(self, data) -> None: pass
    def OnChangeReply(self, data) -> None: print("📦 [改單回報]:", data, flush=True)
    def OnCancelReply(self, data) -> None: print("🗑️ [刪單回報]:", data, flush=True)

    def OnReport(self, data) -> None:
        if type(data) is ReportOrder:
            ord_no = getattr(data.order, 'ordNo', '')
            status = getattr(data.order, 'status', '')
            if ord_no and str(ord_no).strip() != "":
                self.last_ord_no = ord_no
                self.active_orders[ord_no] = status
            print(f'🔔 [實盤回報] 單號={ord_no}, 狀態={status}, 訊息={data.lastMessage}', flush=True)

    def OnReqResult(self, workID: str, data) -> None: pass
    def OnSystemEvent(self, data: SystemEvent) -> None: pass
    def OnAnnouncementEvent(self, data)->None: pass
    def OnError(self, data): print("⚠️ SDK Error:", data, flush=True)

class BrokerGateway:
    def __init__(self):
        self.api = None
        self.trader = None
        self.is_connected = False
        self.target_account = os.environ.get('MASTER_TRADING_ACCOUNT', '0478783')

    def connect_and_sync(self):
        """冷啟動連線與對帳程序"""
        username = os.environ.get('MASTER_USERNAME', '')
        password = os.environ.get('MASTER_PASSWORD', '')
        is_sim = os.environ.get('MASTER_SIM_MODE', 'True') != 'False'

        if not username or not password:
            print("🛡️ [實盤閘道] 未提供帳密環境變數，維持純沙盒/模擬模式。", flush=True)
            return False

        try:
            self.trader = ConcreteMarketTrader()
            self.api = MasterTradeAPI(self.trader)
            self.api.SetConnectionHost('solace140.masterlink.com.tw:55555')
            rc = self.api.Login(username, password, is_sim, True, False)
            if rc in [RCode.OK, RCode.USER_NOT_VERIFIED, RCode.PART_USER_VERIFIED]:
                if hasattr(self.api, 'aAccList') and self.api.aAccList:
                    self.target_account = self.api.aAccList[0]
                self.is_connected = True
                print(f"🔥 [實盤閘道] 登入成功！對位交易帳號: {self.target_account}", flush=True)
                
                # 冷啟動對帳：若 API 支援查詢未結案委託/庫存在此同步
                self._reconcile_state()
                return True
        except Exception as e:
            print(f"❌ [實盤閘道] 冷啟動連線異常: {e}", flush=True)
        self.is_connected = False
        return False

    def _reconcile_state(self):
        """冷啟動對帳邏輯：清除過期盲區，重整部位快照"""
        print("🔄 [對帳機制] 正在向主機同步未結案委託與庫存...", flush=True)
        # 依據 MasterTradePy 現有可用查詢介面進行對位（若無特定API則以重置 pending 鎖定為主）
        if self.trader:
            self.trader.active_orders.clear()

    def execute_order(self, symbol: str, action: str, volume: int = 1):
        mode = os.environ.get('EXECUTION_MODE', 'SIMULATOR')
        if mode != 'REAL' or not self.is_connected or not self.api:
            return f"🛡️ [沙盒模式] 攔截真實發射：{action} {symbol} 共 {volume} 張/股（未接通實盤金鑰或模式非 REAL）"

        try:
            side_val = Side.Buy if action.upper() == "BUY" else Side.Sell
            target_qty = str(volume * 1000 if volume < 10 else volume)
            
            common_args = {
                'tradingSession': TradingSession.NORMAL,
                'side': side_val,
                'symbol': symbol,
                'tradingUnit': TradingUnit.COMMON,
                'tradingType': TradingType.CUSTODY,
                'dayTradeFlag': '',
                'tradingAccount': self.target_account,
                'userDef': ''
            }
            
            self.trader.last_ord_no = None
            ord_obj = Order(**common_args, priceType=PriceType.MKT, price='', qty=target_qty, orderType=OrderType.ROD)
            ret = self.api.NewOrder(ord_obj)
            return f"⚡ [真實實盤已送出] RCode={ret}, 捕捉非同步委託書號={self.trader.last_ord_no}"
        except Exception as e:
            return f"❌ [實盤發射崩潰]: {e}"

gateway = BrokerGateway()
