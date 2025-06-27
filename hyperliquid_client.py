from hyperliquid import Hyperliquid
from secret import WALLET_PRIVATE_KEY, WALLET_ADDRESS

class HyperliquidClient:
    def __init__(self):
        # Instancia para operar y consultar (requiere private key para trading real/testnet)
        self.hl = Hyperliquid(WALLET_PRIVATE_KEY)

    def get_account(self):
        # Devuelve el estado de la cuenta
        return self.hl.info.user_state(WALLET_ADDRESS)

    def get_ohlcv(self, symbol, interval, limit):
        # symbol: "BTC", "ETH", ...
        # interval: "1m", "5m", etc.
        # limit: número de velas
        return self.hl.info.candles(symbol, interval, limit)

    def get_order_book(self, symbol):
        return self.hl.info.l2_book(symbol)

    def get_price(self, symbol):
        ob = self.hl.info.l2_book(symbol)
        best_ask = float(ob["asks"][0][0]) if ob["asks"] else None
        best_bid = float(ob["bids"][0][0]) if ob["bids"] else None
        mid = (best_ask + best_bid) / 2 if best_ask and best_bid else None
        return {"best_bid": best_bid, "best_ask": best_ask, "mid": mid}

    def create_order(self, symbol, side, size):
        # side: "buy" o "sell"
        is_buy = True if side.lower() == "buy" else False
        return self.hl.order.market(symbol, size, is_buy=is_buy)
