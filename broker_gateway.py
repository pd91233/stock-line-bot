# broker_gateway.py
import os
from MasterTradePy.api import MasterTradeAPI
from MasterTradePy.model import Order, OrderPriceChange, OrderQtyChange, OrderCancel
from MasterTradePy.constant import PriceType, OrderType, TradingSession, Side, TradingUnit, RCode

class ConcreteMarketTrader(MarketTrader):
    def __init__(self):
        super().__init__()
        self.last_ord_no = None

    def OnNewOrderReply(self, data) -> None: pass
    def OnChangeReply(self, data) -> None: print("📦 [改單回報]:", data, flush=True)
    def OnCancelReply(self, data) -> None: print("🗑️ [刪單回報]:", data, flush=True)

    def OnReport(self, data) -> None:
        if type(data) is ReportOrder:
            ord_no = getattr(data.order, 'ordNo', '')
            status = getattr(data.order, 'status', '')
            if ord_no and str(ord_no).strip() != "":
                self.last_ord_no = ord_no
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

    def connect(self):
        username = os.environ.get('MASTER_USERNAME', '')
        password = os.environ.get('MASTER_PASSWORD', '')
        is_sim = os.environ.get('MASTER_SIM_MODE', 'True') != 'False'

        if not username or not password:
            print("⚠️ [實盤閘道] 未設定 MASTER_USERNAME / MASTER_PASSWORD，維持關閉或僅供模擬。", flush=True)
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
                print(f"🔥 [實盤閘道] 連線成功！對位帳號: {self.target_account}", flush=True)
                return True
        except Exception as e:
            print(f"❌ [實盤閘道] 初始化例外: {e}", flush=True)
        return False

    def execute_order(self, symbol: str, action: str, price_type_str: str, price_str: str, qty_int: int):
        mode = os.environ.get('EXECUTION_MODE', 'SIMULATOR')
        if mode != 'REAL' or not self.is_connected or not self.api:
            return f"🛡️ [沙盒/未上線模式攔截] 指令收悉：{action} {symbol} 數量 {qty_int}，未發送至真實券商主機。"

        try:
            side_val = Side.Buy if action.upper() == "BUY" else Side.Sell
            ptype = PriceType.MKT if price_type_str.upper() == "MKT" else PriceType.LMT
            
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
            ord_obj = Order(**common_args, priceType=ptype, price=str(price_str), qty=str(qty_int), orderType=OrderType.ROD)
            ret = self.api.NewOrder(ord_obj)
            return f"⚡ [真實實盤送出] RCode={ret}, 捕捉委託單號={self.trader.last_ord_no}"
        except Exception as e:
            return f"❌ [真實實盤發射例外]: {e}"

gateway = BrokerGateway()
