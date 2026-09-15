# broker_gateway.py
import os
import time

try:
    from MasterTradePy.api import MarketTrader, MasterTradeAPI
    from MasterTradePy.model import Order, OrderPriceChange, OrderQtyChange, OrderCancel, OrderDelete, ReportOrder, SystemEvent
    from MasterTradePy.constant import PriceType, OrderType, TradingSession, Side, TradingUnit, RCode
    HAS_MASTER_SDK = True
except ImportError:
    HAS_MASTER_SDK = False
    print("⚠️ [BrokerGateway] 找不到 MasterTradePy 模組，自動降級為雲端安全模擬/沙盒模式。", flush=True)
    # 宣告 mock 基底類別避免繼承崩潰
    class MarketTrader: pass
    class ReportOrder: pass
    class SystemEvent: pass
    class RCode:
        OK = 0
        USER_NOT_VERIFIED = 1
        PART_USER_VERIFIED = 2

class ConcreteMarketTrader(MarketTrader):
    def __init__(self):
        if HAS_MASTER_SDK and hasattr(super(), '__init__'):
            super().__init__()
        self.last_ord_no = None
        self.active_orders = {}

    def OnNewOrderReply(self, data) -> None: pass
    def OnChangeReply(self, data) -> None: pass
    def OnCancelReply(self, data) -> None: pass
    def OnReport(self, data) -> None:
        if HAS_MASTER_SDK and type(data) is ReportOrder:
            ord_no = getattr(data.order, 'ordNo', '')
            status = getattr(data.order, 'status', '')
            if ord_no and str(ord_no).strip() != "":
                self.last_ord_no = ord_no
                self.active_orders[ord_no] = status

    def OnReqResult(self, workID: str, data) -> None: pass
    def OnSystemEvent(self, data) -> None: pass
    def OnAnnouncementEvent(self, data) -> None: pass
    def OnError(self, data): pass

class BrokerGateway:
    def __init__(self):
        self.api = None
        self.trader = None
        self.is_connected = False
        self.target_account = os.environ.get('MASTER_TRADING_ACCOUNT', '0478783')

    def connect_and_sync(self):
        if not HAS_MASTER_SDK:
            print("🛡️ [實盤閘道] 雲端無 SDK，略過實盤連線。", flush=True)
            return False
            
        username = os.environ.get('MASTER_USERNAME', '')
        password = os.environ.get('MASTER_PASSWORD', '')
        is_sim = os.environ.get('MASTER_SIM_MODE', 'True') != 'False'

        if not username or not password:
            print("🛡️ [實盤閘道] 未設定帳密，維持沙盒模式。", flush=True)
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
                print(f"🔥 [實盤閘道] 雲端連線成功！帳號: {self.target_account}", flush=True)
                return True
        except Exception as e:
            print(f"❌ [實盤閘道] 連線異常: {e}", flush=True)
        self.is_connected = False
        return False

    def execute_order(self, symbol: str, action: str, volume: int = 1):
        mode = os.environ.get('EXECUTION_MODE', 'SIMULATOR')
        if mode != 'REAL' or not self.is_connected or not self.api or not HAS_MASTER_SDK:
            return f"🛡️ [雲端沙盒攔截] 指令收悉：{action} {symbol} 數量 {volume} (已記錄但未送出真實主機)"

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
            return f"⚡ [真實實盤已送出] RCode={ret}, 單號={self.trader.last_ord_no}"
        except Exception as e:
            return f"❌ [實盤發射異常]: {e}"

gateway = BrokerGateway()
