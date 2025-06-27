from hyperliquid import Client
from secret import WALLET_ADDRESS, WALLET_PRIVATE_KEY
from config import API_URL

class HyperliquidClient:
    def __init__(self):
        self.client = Client(
            base_url=API_URL,
            wallet_address=WALLET_ADDRESS,
            wallet_private_key=WALLET_PRIVATE_KEY
        )

    def get_account(self):
        return self.client.account_state()

    def get_ohlcv(self, symbol, interval, limit):
        return self.client.candles(
            symbol=symbol + "USDT",
            interval=interval,
            limit=limit
        )

    def get_order_book(self, symbol):
        return self.client.orderbook(symbol + "USDT")

    def get_price(self, symbol):
        ticker = self.client.ticker(symbol + "USDT")
        return {'price': ticker['last']}

    def create_order(self, symbol, side, size):
        return self.client.market_order(
            symbol=symbol + "USDT",
            side=side,
            size=size
        )
