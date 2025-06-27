import hyperliquid
from config import API_URL

class HyperliquidClient:
    def __init__(self):
        self.client = hyperliquid.Exchange(api_url=API_URL)

    def get_account(self, address):
        # Devuelve el estado de la cuenta pública
        return self.client.get_user_state(address)

    def get_ohlcv(self, symbol, interval, limit):
        # Retorna velas OHLCV, por defecto 1m, 5m, etc.
        return self.client.candles(symbol + "USDT", interval, limit)

    def get_order_book(self, symbol):
        return self.client.orderbook(symbol + "USDT")

    def get_price(self, symbol):
        # Devuelve el precio mark, puede ajustarse a best_bid/best_ask si lo prefieres
        ticker = self.client.ticker(symbol + "USDT")
        return {'price': ticker['mark']}
