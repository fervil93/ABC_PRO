from hyperliquid import Hyperliquid
from secret import WALLET_PRIVATE_KEY, WALLET_ADDRESS

class HyperliquidClient:
    def __init__(self):
        # Si solo quieres leer datos, puedes usar Hyperliquid() sin clave privada.
        # Para operar (testnet/mainnet), inicializa con la clave privada.
        self.hl = Hyperliquid(WALLET_PRIVATE_KEY)

    def get_account(self):
        # Estado de la cuenta (user_state requiere address)
        return self.hl.info.user_state(WALLET_ADDRESS)

    def get_ohlcv(self, symbol, interval, limit):
        # symbol: "BTC", "ETH"...
        # interval: "1m", "5m", "1h", etc.
        # limit: número de velas
        return self.hl.info.candles(symbol, interval, limit)

    def get_order_book(self, symbol):
        # symbol: "BTC", "ETH"...
        return self.hl.info.l2_book(symbol)

    def get_price(self, symbol):
        # symbol: "BTC", "ETH"...
        # Devuelve el mejor precio bid y ask
        ob = self.hl.info.l2_book(symbol)
        return {
            "best_bid": float(ob["bids"][0][0]) if ob["bids"] else None,
            "best_ask": float(ob["asks"][0][0]) if ob["asks"] else None,
            "mid": (float(ob["bids"][0][0]) + float(ob["asks"][0][0])) / 2 if ob["bids"] and ob["asks"] else None
        }

    def create_order(self, symbol, side, size):
        # side: "buy" o "sell"
        is_buy = True if side.lower() == "buy" else False
        return self.hl.order.market(symbol, size, is_buy=is_buy)
